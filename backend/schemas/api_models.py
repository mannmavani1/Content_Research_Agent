from typing import Any, Optional
from pydantic import BaseModel

class PasteRequest(BaseModel):
    """
    Schema for the raw text ingestion endpoint (/ingestion/paste).

    Used when a user pastes text directly into the UI rather than uploading a file.

    Attributes:
        text (str): The raw content string to be processed and embedded.
        filename (str): An optional identifier for the content. 
                        Defaults to "pasted_content" if not provided.
    """
    text: str
    filename: str = "pasted_content"
    conversation_id: Optional[int] = None

class StandardResponse(BaseModel):
    """
    Standardized API response model for both success and error payloads.
    
    Attributes:
        status (int): HTTP status code.
        message (str): A human-readable status message for the UI.
        data (dict, optional): The payload for successful operations.
        error (dict, optional): Error details if any.
    """
    status: int
    message: str
    data: Optional[Any] = None
    error: Optional[Any] = None

class ChatRequest(BaseModel):
    """
    Input schema for the chat and research tool endpoints.

    Attributes:
        message (str): The user's natural language query or command.
        conversation_id (int, optional): The ID of the conversation to append to.
    """
    message: str
    conversation_id: Optional[int] = None

class CreateConversationRequest(BaseModel):
    title: str = "New Chat"

class RenameConversationRequest(BaseModel):
    title: str