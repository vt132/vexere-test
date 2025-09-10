from fastapi import APIRouter, HTTPException
import httpx
from typing import Any, Dict, Optional, List
from ..schemas.gateway import UserRequest, GatewayResponse
from ..config import LLM_SERVICE_URL, DATA_SERVICE_URL, HTTP_TIMEOUT_SECONDS
from ..logic.pipeline import detect_intent, fetch_data
from PIL import Image

router = APIRouter()

# whisper = ... load whisper model here if needed ...

@router.post("/query", response_model=GatewayResponse)
async def query(req: UserRequest):
    intent, route = detect_intent(req.text, req.user_id)
    fetched = await fetch_data(intent, req.user_id, route)
    if req.voice:
        # Use whisper to process voice input (not implemented)
        # extracted_text = whisper.transcribe(req.voice)
        # prompt = f"User said: {extracted_text}\n\n{req.text}"
        
        raise HTTPException(status_code=400, detail="Voice input not supported yet")
    if req.image:
        # Download and process image input then put it into prompt for MLLM (not supported) 
        # image = Image.open(httpx.get(req.image).content)
        raise HTTPException(status_code=400, detail="Image input not supported yet")
    
    prompt = req.text
    if fetched:
        prompt += f"\nRelevant data: {fetched}"

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        gen = await client.post(f"{LLM_SERVICE_URL}/generate", json={"model": req.model, "prompt": prompt})
        if gen.status_code != 200:
            raise HTTPException(status_code=gen.status_code, detail=gen.text)
        payload = gen.json()

    return GatewayResponse(answer=payload.get("output", ""), model=payload.get("model", req.model), meta={"intent": intent, "fetched": fetched})


@router.post("/intents/plan")
async def plan(req: UserRequest):
    if req.voice:
        # Use whisper to process voice input (not implemented)
        # extracted_text = whisper.transcribe(req.voice)
        # prompt = f"User said: {extracted_text}\n\n{req.text}"
        
        raise HTTPException(status_code=400, detail="Voice input not supported yet")
    if req.image:
        # Download and process image input then put it into prompt for MLLM (not supported) 
        # image = Image.open(httpx.get(req.image).content)
        raise HTTPException(status_code=400, detail="Image input not supported yet")
    
    body = {"text": req.text, "user_id": req.user_id}

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            r = await client.post(f"{LLM_SERVICE_URL}/intents/plan", json=body)
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code, detail=r.text)
            plan = r.json()
    except httpx.ReadTimeout:
        raise HTTPException(status_code=504, detail="Timeout contacting LLM service for intent planning. Try again.")

    # Define available action functions
    async def do_update_ticket_time(args: Dict[str, Any]) -> Dict[str, Any]:
        order_id = args.get("order_id")
        new_time_iso = args.get("new_time_iso") or args.get("new_time")
        if order_id is None or not new_time_iso:
            # Fallback: let LLM agent handle extraction from natural text
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
                rr = await client.post(f"{LLM_SERVICE_URL}/agent/change_time", json={"question": req.text})
                return rr.json() if rr.headers.get("content-type", "").startswith("application/json") else {"raw": rr.text}
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            rr = await client.post(f"{DATA_SERVICE_URL}/orders/update_time", json={"order_id": order_id, "new_time": new_time_iso})
            if rr.status_code != 200:
                raise HTTPException(status_code=rr.status_code, detail=rr.text)
            return rr.json()

    async def do_get_trips(args: Dict[str, Any]) -> Dict[str, Any]:
        route_id = args.get("route_id")
        if not route_id:
            raise HTTPException(status_code=400, detail="Missing route_id for get_trips")
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            rr = await client.get(f"{DATA_SERVICE_URL}/trips/{route_id}")
            if rr.status_code != 200:
                raise HTTPException(status_code=rr.status_code, detail=rr.text)
            return rr.json()

    async def do_get_pending_orders(args: Dict[str, Any]) -> Dict[str, Any]:
        uid = args.get("user_id") or req.user_id
        if uid is None:
            raise HTTPException(status_code=400, detail="Missing user_id for get_pending_orders")
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            rr = await client.get(f"{DATA_SERVICE_URL}/orders/{uid}/pending")
            if rr.status_code != 200:
                raise HTTPException(status_code=rr.status_code, detail=rr.text)
            return rr.json()

    async def do_faq(args: Dict[str, Any]) -> Dict[str, Any]:
        question = args.get("question") or req.text
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            rr = await client.post(f"{LLM_SERVICE_URL}/faq/ask", json={"question": question})
            if rr.status_code != 200:
                raise HTTPException(status_code=rr.status_code, detail=rr.text)
            return rr.json()

    ACTIONS = {
        "update_ticket_time": do_update_ticket_time,
        "get_trips": do_get_trips,
        "get_pending_orders": do_get_pending_orders,
        "faq": do_faq,
    }

    # Decide which action to run
    intent = plan.get("intent", "unknown")
    action = plan.get("action") or {}
    action_name = action.get("name") if isinstance(action, dict) else None
    args = action.get("args", {}) if isinstance(action, dict) else {}

    # Provide sensible defaults if planner omitted action
    if not action_name:
        if intent == "get_trips":
            action_name = "get_trips"
            args = {"route_id": (plan.get("slots", {}) or {}).get("route_id")}
        elif intent == "get_pending_orders":
            action_name = "get_pending_orders"
            args = {"user_id": req.user_id}
        elif intent == "change_time":
            action_name = "update_ticket_time"
            slots = plan.get("slots", {}) or {}
            args = {"order_id": slots.get("order_id"), "new_time_iso": slots.get("new_time")}
        elif intent == "faq":
            action_name = "faq"
            args = {"question": (plan.get("slots", {}) or {}).get("question") or req.text}

    # Normalize aliases for args
    if action_name == "update_ticket_time" and "new_time_iso" not in args and args.get("new_time"):
        args["new_time_iso"] = args.get("new_time")

    # Check required args for the selected action
    required: Dict[str, List[str]] = {
        "update_ticket_time": ["order_id", "new_time_iso"],
        "get_trips": ["route_id"],
        "get_pending_orders": ["user_id"],
        # faq has no required args
    }
    if action_name in required:
        missing = [k for k in required[action_name] if not args.get(k)]
        if missing:
            # Build a concise clarification message (VN)
            if action_name == "update_ticket_time":
                msg = (
                    "Vui lòng cung cấp đầy đủ thông tin để đổi giờ vé: "
                    + ", ".join(missing)
                    + ". Ví dụ: 'Đổi vé order 123 sang 2025-09-15T10:00:00'."
                )
            elif action_name == "get_trips":
                msg = "Vui lòng cung cấp route_id (ví dụ: HCM-HN)."
            elif action_name == "get_pending_orders":
                msg = "Vui lòng cung cấp user_id hoặc đăng nhập."
            else:
                msg = "Thiếu thông tin cần thiết."

            return {
                "plan": plan,
                "needs_clarification": True,
                "missing": missing,
                "message": msg,
                "suggested_action": action_name,
            }

    # Execute when all required args are present or not needed
    if action_name not in ACTIONS:
        return {"plan": plan, "error": f"No handler for action '{action_name}'", "intent": intent}

    result = await ACTIONS[action_name](args)
    return {"plan": plan, "result": result, "needs_clarification": False}
