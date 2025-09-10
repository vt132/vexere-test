from typing import Optional, Tuple, Any
import httpx
from ..config import DATA_SERVICE_URL, HTTP_TIMEOUT_SECONDS


def detect_intent(text: str, user_id: Optional[int]) -> Tuple[Optional[str], Optional[str]]:
    lower = text.lower()
    if "pending" in lower and "order" in lower and user_id is not None:
        return "get_pending_orders", None
    if lower.startswith("trips "):
        route = lower.split(" ", 1)[1].strip()
        return "get_trips", route
    return None, None


async def fetch_data(intent: Optional[str], user_id: Optional[int], extra: Optional[str]) -> Optional[Any]:
    if not intent:
        return None
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        if intent == "get_pending_orders" and user_id is not None:
            r = await client.get(f"{DATA_SERVICE_URL}/orders/{user_id}/pending")
            r.raise_for_status()
            return r.json()
        if intent == "get_trips" and extra:
            r = await client.get(f"{DATA_SERVICE_URL}/trips/{extra}")
            r.raise_for_status()
            return r.json()
    return None
