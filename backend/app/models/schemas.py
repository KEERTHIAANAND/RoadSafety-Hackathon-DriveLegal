from pydantic import BaseModel
from typing import List, Optional

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    query: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    chat_history: Optional[List[ChatMessage]] = []

class ChatResponse(BaseModel):
    response: str
    
class ChallanRequest(BaseModel):
    violation: str
    vehicle_type: Optional[str] = "all"
    state: Optional[str] = "national"

class ChallanResponse(BaseModel):
    fine_details: str
