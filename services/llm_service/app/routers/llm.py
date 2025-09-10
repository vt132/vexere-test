import re
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

from ..logic.utils import load_faq_data
from ..config import BASE_URL, LLM_MODEL, EMBEDDING_MODEL, DATA_SERVICE_URL, HTTP_TIMEOUT_SECONDS
from ..schemas.llm import (
    FAQAskRequest,
    FAQAskResponse,
    ChangeTimeRequest,
    ChangeTimeResponse,
    IntentPlanRequest,
    IntentPlanResponse,
    IntentAction,
)
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
import httpx

router = APIRouter()

llm = ChatOpenAI(
    base_url=BASE_URL,
    model=LLM_MODEL,
    api_key="none",
)

# Build FAQ documents
faq_data = load_faq_data()
faq_docs = [
    # Index only the question text for retrieval similarity
    Document(
        page_content=str(faq.get("question", "")),
        metadata=faq,
    )
    for faq in faq_data
]

# Embeddings + VectorStore
faq_embeddings = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL,
)

vectorstore = FAISS.from_documents(faq_docs, faq_embeddings) if faq_docs else None
retriever = vectorstore.as_retriever(search_kwargs={"k": 3}) if vectorstore else None

faq_prompt = ChatPromptTemplate.from_template(
    (
        "Bạn là một trợ lý FAQ hữu ích cho Vexere, nền tảng đặt vé toàn diện — "
        "từ xe khách, tàu hoả đến máy bay và dịch vụ thuê xe trên khắp Việt Nam; đồng "
        "thời cung cấp giải pháp SaaS giúp nhà xe quản lý bán vé và vận chuyển hàng hoá. "
        "Hãy sử dụng ngữ cảnh sau để trả lời câu hỏi của người dùng.\n"
        "Nếu ngữ cảnh trả về không đủ đáp ứng để trả lời một phần câu hỏi nào đó, "
        "hãy nói rằng bạn không biết.\n"
        "Ngữ cảnh:\n{context}\n"
        "Câu hỏi của người dùng: {question}\n"
    )
)


def get_faq_context(question: str) -> str:
    if not retriever:
        return ""
    docs = retriever.get_relevant_documents(question)
    # Provide Q/A pairs in context while retrieval used only the question text
    lines = []
    for d in docs:
        q = d.page_content
        a = ""
        md = getattr(d, "metadata", {}) or {}
        try:
            a = md.get("answer", "")
        except Exception:
            a = ""
        lines.append(f"Q: {q}\nA: {a}")
    return "\n\n".join(lines)


@router.post("/faq/ask")
async def faq_ask(req: FAQAskRequest, stream: bool = False):
    if not retriever:
        if stream:
            async def err_gen():
                yield "FAQ data not loaded."
            return StreamingResponse(err_gen(), media_type="text/plain")
        return FAQAskResponse(answer="FAQ data not loaded.", context="")

    context = get_faq_context(req.question)
    prompt = faq_prompt.format(context=context, question=req.question)

    if not stream:
        try:
            answer_msg = await llm.ainvoke(prompt)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return FAQAskResponse(answer=answer_msg.content, context=context)

    async def token_generator():
        yield f"[CONTEXT_START]\n{context}\n[CONTEXT_END]\n[ANSWER_START]\n"
        try:
            async for chunk in llm.astream(prompt):
                if getattr(chunk, "content", None):
                    yield chunk.content
        except Exception as exc:
            yield f"\n[ERROR] {exc}"
        yield "\n[ANSWER_END]"

    return StreamingResponse(token_generator(), media_type="text/plain")


# --- Tool Calling: change ticket time ---

@tool("update_ticket_time")
def update_ticket_time(order_id: int, new_time_iso: str) -> str:
    """Update a ticket's departure time to a new ISO-8601 datetime.

    Args:
        order_id: The order ID to update.
        new_time_iso: ISO 8601 datetime string, e.g. '2025-09-12T10:30:00'.

    Returns: The raw JSON response from Data Service, or an error message.
    """
    try:
        r = httpx.post(
            f"{DATA_SERVICE_URL}/orders/update_time",
            json={"order_id": int(order_id), "new_time": str(new_time_iso)},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        r.raise_for_status()
        return r.text
    except Exception as exc:
        return f"ERROR: {exc}"


@tool("query_ticket_time")
def query_ticket_time(order_id: int) -> str:
    """Query a ticket's departure time.

    Args:
        order_id: The order ID to query.

    Returns: The raw JSON response from Data Service, or an error message.
    """
    try:
        r = httpx.post(
            f"{DATA_SERVICE_URL}/orders/query_time",
            json={"order_id": int(order_id)},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        r.raise_for_status()
        return r.text
    except Exception as exc:
        return f"ERROR: {exc}"

TOOLS = {
    "update_ticket_time": update_ticket_time,
    "query_ticket_time": update_ticket_time
}


@router.post("/agent/change_time", response_model=ChangeTimeResponse)
async def agent_change_time(req: ChangeTimeRequest):
    """Use an LLM + tool to update a ticket departure time from a natural question.

    If the question lacks order_id or new_time, the assistant will respond asking
    for the missing details without performing the update.
    """
    llm_with_tools = llm.bind_tools(list(TOOLS.values()))
    messages = [
        SystemMessage(
            content=(
                "You can update a ticket departure time using the tool 'update_ticket_time'. "
                "Extract order_id (integer) and new_time_iso (ISO-8601). "
                "If either is missing or unclear, ask a concise clarification (in Vietnamese) and DO NOT call the tool."
            )
        ),
        HumanMessage(content=req.question),
    ]

    # First LLM pass (may include tool calls)
    ai = await llm_with_tools.ainvoke(messages)
    tool_calls = getattr(ai, "tool_calls", []) or []

    tool_results = []
    if tool_calls:
        # Execute tool calls
        for call in tool_calls:
            name = call["name"] if isinstance(call, dict) else getattr(call, "name", None)
            args = call.get("args", {}) if isinstance(call, dict) else getattr(call, "args", {})
            tool_fn = TOOLS.get(name)
            if tool_fn is None:
                result = f"ERROR: Unknown tool {name}"
            else:
                try:
                    result = tool_fn.invoke(args)  # langchain tool wrapper supports .invoke
                except Exception as exc:
                    result = f"ERROR: {exc}"
            tool_results.append({"tool": name, "args": args, "result": result})

        # Send tool results back to the LLM for a final answer
        tool_messages = []
        for call, tr in zip(tool_calls, tool_results):
            call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", None)
            tool_messages.append(ToolMessage(content=str(tr["result"]), tool_call_id=call_id))
        final = await llm.ainvoke(messages + [ai] + tool_messages)
        return ChangeTimeResponse(
            answer=getattr(final, "content", str(final)),
            tool_calls=tool_calls,
            tool_results=tool_results,
        )

    # No tool call; just return the assistant message content
    return ChangeTimeResponse(
        answer=getattr(ai, "content", str(ai)),
        tool_calls=[],
        tool_results=[],
    )


# --- Intent planning endpoint ---

intent_prompt = ChatPromptTemplate.from_template(
    (
        "You are an intent classifier and action planner for a travel ticketing assistant. "
        "Classify the user's Vietnamese text into one of: change_time, get_pending_orders, get_trips, faq, unknown. "
        "Extract slots and propose a single action if applicable. Output strict JSON with keys: "
        "intent (string, within listed intents), slots (object), action (object|null), notes (string|null). "
        "Slots may include: order_id (int), new_time (ISO-8601 string), route_id (string), question (string). "
        "If requesting trips and a route is specified, set action to {{\"name\": \"get_trips\", \"args\": {{\"route_id\": \"<route_id>\"}}}}. "
        "If changing time with order_id & new_time present, set action to {{\"name\": \"update_ticket_time\", \"args\": {{\"order_id\": <int>, \"new_time_iso\": \"<ISO-8601>\"}}}}. "
        "If asking a general question, intent faq with question in slots."
        "\nUser text: {text}\nUser id: {user_id}"
    )
)


@router.post("/intents/plan", response_model=IntentPlanResponse)
async def plan_intent(req: IntentPlanRequest):
        prompt = intent_prompt.format(
            text=req.text,
            user_id=getattr(req, "user_id", None) # user_id is optional
        )
        msg = await llm.ainvoke(prompt)
        print(msg)

        content = msg.content if hasattr(msg, "content") else str(msg)
        match = re.search(r"\{[\s\S]*\}", content)
        data = json.loads(match.group(0) if match else content)
        # Coerce types and defaults
        intent = str(data.get("intent", "unknown"))
        slots = data.get("slots", {}) or {}
        action = data.get("action") or None
        if action and isinstance(action, dict):
            action = IntentAction(name=str(action.get("name", "")), args=action.get("args", {}) or {})
        notes = data.get("notes")
        return IntentPlanResponse(intent=intent, slots=slots, action=action, notes=notes)
