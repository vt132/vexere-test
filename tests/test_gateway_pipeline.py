import pytest
from fastapi.testclient import TestClient

from services.user_gateway.app.main import app as gateway_app


class Dummy:
    pass


@pytest.fixture(autouse=True)
def _patch_urls(monkeypatch):
    # Point to fake endpoints (we will monkeypatch httpx.AsyncClient instead)
    monkeypatch.setenv("LLM_SERVICE_URL", "http://fake-llm")
    monkeypatch.setenv("DATA_SERVICE_URL", "http://fake-data")


@pytest.fixture
def client():
    return TestClient(gateway_app)


class MockResp:
    def __init__(self, status_code=200, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text or ""
        self._headers = headers or {"content-type": "application/json"}

    def json(self):
        return self._json

    @property
    def headers(self):
        return self._headers


_PLAN_MODE = {"mode": "missing_change_time"}


@pytest.fixture
def plan_mode():
    def set_mode(m: str):
        _PLAN_MODE["mode"] = m

    return set_mode


@pytest.fixture(autouse=True)
def mock_async_client(monkeypatch):
    class MockAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None):
            if url.endswith("/intents/plan"):
                mode = _PLAN_MODE["mode"]
                if mode == "missing_change_time":
                    return MockResp(
                        json_data={
                            "intent": "change_time",
                            "slots": {"order_id": 12},
                            "action": {"name": "update_ticket_time", "args": {"order_id": 12}},
                        }
                    )
                if mode == "full_change_time":
                    return MockResp(
                        json_data={
                            "intent": "change_time",
                            "slots": {"order_id": 12, "new_time": "2025-09-15T10:00:00"},
                            "action": {
                                "name": "update_ticket_time",
                                "args": {"order_id": 12, "new_time_iso": "2025-09-15T10:00:00"},
                            },
                        }
                    )
                if mode == "trips":
                    return MockResp(
                        json_data={
                            "intent": "get_trips",
                            "slots": {"route_id": "HCM-HN"},
                            "action": {"name": "get_trips", "args": {"route_id": "HCM-HN"}},
                        }
                    )
                if mode == "faq":
                    return MockResp(
                        json_data={
                            "intent": "faq",
                            "slots": {"question": json.get("text") if json else "FAQ?"},
                            "action": {
                                "name": "faq",
                                "args": {"question": json.get("text") if json else "FAQ?"},
                            },
                        }
                    )
            if url.endswith("/agent/change_time"):
                return MockResp(
                    json_data={"answer": "Updated", "tool_calls": [], "tool_results": []}
                )
            if url.endswith("/orders/update_time"):
                return MockResp(
                    json_data={
                        "updated": True,
                        "order": {"order_id": 12, "departure_time": "2025-09-15T10:00:00"},
                    }
                )
            if url.endswith("/faq/ask"):
                return MockResp(json_data={"answer": "FAQ", "context": ""})
            return MockResp(text="Unhandled POST", status_code=500)

        async def get(self, url):
            if "/trips/" in url:
                return MockResp(json_data=[{"trip_id": 1}])
            if "/orders/" in url and url.endswith("/pending"):
                return MockResp(json_data=[{"order_id": 55, "status": "pending"}])
            return MockResp(text="Unhandled GET", status_code=404)

    monkeypatch.setattr("httpx.AsyncClient", MockAsyncClient)


def test_change_time_missing_time_triggers_clarification(client, plan_mode):
    plan_mode("missing_change_time")
    resp = client.post("/intents/plan", json={"text": "Đổi giờ vé order 12", "user_id": 7})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["needs_clarification"] is True
    assert "new_time_iso" in data["missing"]


def test_change_time_full_exec(client, plan_mode):
    plan_mode("full_change_time")
    resp = client.post(
        "/intents/plan", json={"text": "Đổi giờ vé order 12 sang 2025-09-15T10:00:00", "user_id": 7}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["needs_clarification"] is False
    assert data["result"]["updated"] is True


def test_get_trips_flow(client, plan_mode):
    plan_mode("trips")
    resp = client.post("/intents/plan", json={"text": "Lấy chuyến HCM-HN", "user_id": 7})
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"]["intent"] == "get_trips"
    assert isinstance(data["result"], list)


def test_faq_fallback(client, plan_mode):
    plan_mode("faq")
    resp = client.post("/intents/plan", json={"text": "FAQ: thời gian đổi vé?", "user_id": 7})
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"]["intent"] == "faq"
    assert "answer" in data["result"] or "context" in data["result"]
