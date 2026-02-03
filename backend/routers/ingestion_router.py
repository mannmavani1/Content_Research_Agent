import os
import shutil
import time
from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.config.settings import settings
from backend.schemas.api_models import PasteRequest, IngestionResponse
from backend.services.ingestion import process_document

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])

@router.post("/upload", response_model=IngestionResponse)
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        num_chunks = process_document(file_path)
        return IngestionResponse(
            status="success",
            filename=file.filename,
            chunks_processed=num_chunks,
            message="File successfully indexed"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/paste", response_model=IngestionResponse)
async def paste_content(request: PasteRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")

    timestamp = int(time.time())
    clean_filename = f"{request.filename}_{timestamp}.txt"
    file_path = os.path.join(settings.UPLOAD_DIR, clean_filename)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(request.text)
            
        num_chunks = process_document(file_path)
        return IngestionResponse(
            status="success",
            filename=clean_filename,
            chunks_processed=num_chunks,
            message="Pasted content successfully indexed"
        )
    except Exception as e:
        if os.path.exists(file_path): os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))