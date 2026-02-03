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

class IngestionResponse(BaseModel):
    """
    Standardized response model for all data ingestion operations.

    Returned by both /upload and /paste endpoints to confirm successful indexing.

    Attributes:
        status (str): The outcome of the operation (e.g., "success", "error").
        filename (str): The name of the file (or virtual file) that was processed.
        chunks_processed (int): The number of text chunks created and stored in the vector DB.
        message (str): A human-readable status message for the UI.
    """
    status: str
    filename: str
    chunks_processed: int
    message: str

class ChatRequest(BaseModel):
    """
    Input schema for the chat and research tool endpoints.

    Attributes:
        message (str): The user's natural language query or command.
        session_id (str): A unique identifier for the conversation session. 
                          Currently defaults to "default", but useful for future 
                          multi-user or persistent history implementations.
    """
    message: str
    session_id: str = "default"