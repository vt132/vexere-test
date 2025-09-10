from pydantic import BaseModel
from typing import Optional, Dict, Any


class UserRequest(BaseModel):
    """
    User text request schema:
    - user_id: Optional[int] = None # support for unauthenticated users
    """
    user_id: Optional[int] = None # support for unauthenticated users
    text: str
    image: Optional[str] = None # image URL (not used currently)
    voice: Optional[str] = None # voice URL (not used currently)
    intent: Optional[str] = None


class GatewayResponse(BaseModel):
    answer: str
    model: str
    meta: Dict[str, Any] = {}
 