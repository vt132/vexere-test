from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class GenerationRequest(BaseModel):
    model: str = Field(default="gpt-4o")
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.7
    json_mode: bool = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[str] = Field(default="auto")

class GenerationResponse(BaseModel):
    model: str
    output: str
    raw: Optional[Dict[str, Any]] = None


class FAQAskRequest(BaseModel):
    question: str

class FAQAskResponse(BaseModel):
    answer: str
    context: str

class ChangeTimeRequest(BaseModel):
    question: str
    
class ChangeTimeResponse(BaseModel):
    answer: str
    tool_calls: list
    tool_results: list


# Intent detection / action declaration
class IntentPlanRequest(BaseModel):
    text: str
    user_id: Optional[int] = None

class IntentAction(BaseModel):
    name: str
    args: Dict[str, Any] = {}

class IntentPlanResponse(BaseModel):
    intent: str  # e.g., change_time | get_pending_orders | get_trips | faq | unknown
    slots: Dict[str, Any] = {}
    action: Optional[IntentAction] = None
    notes: Optional[str] = None
    