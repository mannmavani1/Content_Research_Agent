from pydantic import BaseModel
from typing import Optional

class PasteRequest(BaseModel):
    text: str
    filename: str = "pasted_content"

class IngestionResponse(BaseModel):
    status: str
    filename: str
    chunks_processed: int
    message: str

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"