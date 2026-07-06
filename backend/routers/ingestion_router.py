import os
import shutil
import time
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Path
from typing import Optional
from backend.config.settings import settings
from backend.schemas.api_models import PasteRequest, StandardResponse
from backend.utils.responses import success_response
from backend.services.ingestion import process_document, reset_database

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])

@router.post("/upload", response_model=StandardResponse)
async def upload_file(file: UploadFile = File(...), conversation_id: Optional[int] = Form(None)):
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
        num_chunks = process_document(file_path, conversation_id=conversation_id)
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
            
        num_chunks = process_document(file_path, conversation_id=request.conversation_id)
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
def reset_database_router(conversation_id: Optional[int] = None):
    """
    Clears the entire local database or only for a specific conversation.
    """
    try:
        reset_database(conversation_id)
        return success_response(message="Database reset complete")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/file", response_model=StandardResponse)
async def delete_file(filename: str, conversation_id: Optional[int] = None):
    """
    Deletes a specific file physically and removes its chunks from the SQLite database.
    """
    if not filename.strip():
        raise HTTPException(status_code=400, detail="Filename cannot be empty")
    
    # 1. Physical file delete
    file_path = os.path.join(settings.UPLOAD_DIR, filename)
    physical_deleted = False
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            physical_deleted = True
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete file physically: {str(e)}")
            
    # 2. Database chunks delete
    try:
        from backend.database.database import delete_document_chunks
        chunks_deleted = delete_document_chunks(filename, conversation_id=conversation_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove database records: {str(e)}")
        
    if not physical_deleted and chunks_deleted == 0:
        raise HTTPException(status_code=404, detail="File not found in active workspace")
        
    return success_response(
        message=f"Successfully removed {filename} from workspace",
        data={
            "filename": filename,
            "chunks_removed": chunks_deleted
        }
    )

@router.get("/files/{conversation_id}", response_model=StandardResponse)
async def get_files(conversation_id: int = Path(...)):
    """
    Fetches the list of filenames active in the specified conversation.
    """
    try:
        from backend.database.database import get_files_for_conversation
        files = get_files_for_conversation(conversation_id)
        return success_response(
            message="Files fetched successfully",
            data={"files": files}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))