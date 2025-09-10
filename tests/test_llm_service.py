import sys
import types
import json
import pytest
from fastapi.testclient import TestClient


class _DummyEmbeddings:
    def __init__(self, *a, **k):
        pass


class _DummyDoc:
    def __init__(self, page_content: str, metadata: dict | None = None):
        self.page_content = page_content
        self.metadata = metadata or {}


class _DummyRetriever:
    def __init__(self, docs=None):
        self._docs = docs or [
            _DummyDoc("Chính sách đổi vé?", {"answer": "Bạn có thể đổi vé trước giờ khởi hành 24h."}),
            _DummyDoc("Phí huỷ vé?", {"answer": "Phụ thuộc vào nhà xe, thường 10-30%."}),
        ]

    def get_relevant_documents(self, question: str):
        return self._docs


class _DummyFAISS:
    def __init__(self, docs=None):
        self._retriever = _DummyRetriever(docs)

    @classmethod
    def from_documents(cls, docs, embeddings):
        return cls(docs)

    def as_retriever(self, search_kwargs=None):
        return self._retriever


@pytest.fixture(scope="module")
def llm_client(monkeypatch):
    # Patch vector store and embeddings before importing the app
    monkeypatch.setitem(sys.modules, "langchain_community.embeddings", types.SimpleNamespace(HuggingFaceEmbeddings=_DummyEmbeddings))
    monkeypatch.setitem(sys.modules, "langchain_community.vectorstores", types.SimpleNamespace(FAISS=_DummyFAISS))

    # Import after patching
    from services.llm_service.app.main import app as llm_app
    from services.llm_service.app.routers import llm as llm_router

    # Provide a controllable LLM stub
    class LLMStub:
        def __init__(self):
            self.responses = {
                "faq": types.SimpleNamespace(content="Trả lời FAQ mô phỏng"),
                "plan": types.SimpleNamespace(content=json.dumps({
                    "intent": "faq",
                    "slots": {"question": "Giờ đổi vé?"},
                    "action": {"name": "faq", "args": {"question": "Giờ đổi vé?"}},
                    "notes": None,
                })),
            }

        def bind_tools(self, tools):
            # Return an object whose ainvoke yields a tool call
            class WithTools:
                async def ainvoke(self_inner, messages):
                    return types.SimpleNamespace(
                        content="",
                        tool_calls=[{
                            "id": "call-1",
                            "name": "update_ticket_time",
                            "args": {"order_id": 12, "new_time_iso": "2025-09-15T10:00:00"},
                        }],
                    )
            return WithTools()

        async def ainvoke(self, prompt_or_messages):
            # Heuristic: planner contains "intent" keys in template; FAQ prompt contains "Ngữ cảnh" marker
            if isinstance(prompt_or_messages, str):
                # Not expected in our code path, but default to plan
                return self.responses["plan"]
            text = str(prompt_or_messages)
            if "Ngữ cảnh" in text:
                return self.responses["faq"]
            return self.responses["plan"]

    # Swap in the stubbed llm
    llm_router.llm = LLMStub()

    # Replace TOOLS with a dummy tool that doesn't call network
    class DummyTool:
        def __init__(self, name):
            self.name = name
        def invoke(self, args):
            return json.dumps({"updated": True, "order_id": args.get("order_id"), "new_time": args.get("new_time_iso")})

    llm_router.TOOLS = {
        "update_ticket_time": DummyTool("update_ticket_time"),
    }

    return TestClient(llm_app)


def test_faq_ask_returns_answer_and_context(llm_client):
    r = llm_client.post("/faq/ask", json={"question": "Chính sách đổi vé?"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["answer"].startswith("Trả lời")
    assert "Q:" in data["context"]


def test_intents_plan_parses_json(llm_client):
    r = llm_client.post("/intents/plan", json={"text": "FAQ về đổi vé", "user_id": 1})
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] in {"faq", "change_time", "get_trips", "get_pending_orders", "unknown"}
    assert isinstance(data["slots"], dict)


def test_agent_change_time_executes_tool_and_returns_final_answer(llm_client):
    r = llm_client.post("/agent/change_time", json={"question": "Đổi giờ order 12 sang 2025-09-15T10:00:00"})
    assert r.status_code == 200, r.text
    data = r.json()
    # Should contain recorded tool call and some answer string
    assert data["tool_calls"], "Expected tool calls recorded"
    assert any(tc.get("name") == "update_ticket_time" for tc in data["tool_calls"]) 
    assert isinstance(data["answer"], str) and len(data["answer"]) >= 0
