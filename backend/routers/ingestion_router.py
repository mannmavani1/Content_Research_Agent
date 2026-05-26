import os
import shutil
import time
from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.config.settings import settings
from backend.schemas.api_models import PasteRequest, StandardResponse
from backend.utils.responses import success_response
from backend.services.ingestion import process_document, reset_database

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])

@router.post("/upload", response_model=StandardResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    Handles file uploads and triggers the indexing process.

    This endpoint:
    1. Saves the uploaded file physically to the configured `UPLOAD_DIR`.
    2. Invokes the `process_document` service to chunk and embed the content.
    3. Returns the status and number of chunks created.

    Args:
        file (UploadFile): The binary file object sent via multipart/form-data.

    Returns:
        IngestionResponse: structured response containing status, filename, and chunk count.

    Raises:
        HTTPException: 500 status if file saving or processing fails.
    """
    file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        num_chunks = process_document(file_path)
        return success_response(
            message="File successfully indexed",
            data={
                "filename": file.filename,
                "chunks_processed": num_chunks
            }
        )
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/paste", response_model=StandardResponse)
async def paste_content(request: PasteRequest):
    """
    Accepts raw text input and treats it as a file for indexing.

    Useful for "Paste Text" features in the UI. It creates a temporary .txt file 
    timestamped to prevent collisions, then processes it exactly like an uploaded file.

    Args:
        request (PasteRequest): JSON body containing 'text' and an optional 'filename'.

    Returns:
        IngestionResponse: structured response containing status and chunk count.

    Raises:
        HTTPException: 400 if text is empty, 500 if file writing or processing fails.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")

    timestamp = int(time.time())
    # Ensure a default name if none provided
    base_name = request.filename if request.filename else "pasted_content"
    clean_filename = f"{base_name}_{timestamp}.txt"
    file_path = os.path.join(settings.UPLOAD_DIR, clean_filename)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(request.text)
            
        num_chunks = process_document(file_path)
        return success_response(
            message="Pasted content successfully indexed",
            data={
                "filename": clean_filename,
                "chunks_processed": num_chunks
            }
        )
    except Exception as e:
        if os.path.exists(file_path): 
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset")
def reset_database_router():
    """
    Clears the entire local database.

    WARNING: This is a destructive action. It deletes the persistent SQLite 
    database and re-initializes it. All indexed documents will be lost.
    """
    try:
        reset_database()
        return success_response(message="Database reset complete")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))