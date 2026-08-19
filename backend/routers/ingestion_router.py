import os
import shutil
import time
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Path, Depends, BackgroundTasks
from typing import Optional
from backend.config.settings import settings
from backend.schemas.api_models import PasteRequest, StandardResponse
from backend.utils.responses import success_response
from backend.services.ingestion import process_document, process_document_background, reset_database
from backend.utils.dependencies import get_current_user
from backend.database.database import (
    verify_conversation_owner,
    delete_document_chunks,
    get_files_for_workspace,
    create_document_task,
    get_document_task
)

router = APIRouter(
    prefix="/ingestion", 
    tags=["Ingestion"],
    dependencies=[Depends(get_current_user)]
)

def get_workspace_id(current_user: dict) -> int:
    """Helper to extract workspace identifier from JWT payload."""
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Workspace identity could not be established.")
    return int(workspace_id)

@router.post("/upload", response_model=StandardResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    conversation_id: Optional[int] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Handles file uploads and enqueues indexing as a background task.
    """
    workspace_id = get_workspace_id(current_user)
    if conversation_id and not await verify_conversation_owner(conversation_id, workspace_id):
        raise HTTPException(status_code=403, detail="Access denied to this conversation.")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        task_id = await create_document_task(workspace_id, file.filename, conversation_id=conversation_id)
        background_tasks.add_task(
            process_document_background,
            task_id,
            file_path,
            workspace_id,
            conversation_id
        )
        return success_response(
            message="File upload accepted and processing in background",
            data={
                "task_id": task_id,
                "filename": file.filename,
                "status": "PENDING"
            }
        )
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/paste", response_model=StandardResponse)
async def paste_content(
    request: PasteRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Accepts raw text input and enqueues indexing as a background task.
    """
    workspace_id = get_workspace_id(current_user)
    if request.conversation_id and not await verify_conversation_owner(request.conversation_id, workspace_id):
        raise HTTPException(status_code=403, detail="Access denied to this conversation.")

    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")

    timestamp = int(time.time())
    base_name = request.filename if request.filename else "pasted_content"
    clean_filename = f"{base_name}_{timestamp}.txt"
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, clean_filename)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(request.text)
            
        task_id = await create_document_task(workspace_id, clean_filename, conversation_id=request.conversation_id)
        background_tasks.add_task(
            process_document_background,
            task_id,
            file_path,
            workspace_id,
            request.conversation_id
        )
        return success_response(
            message="Pasted content accepted and processing in background",
            data={
                "task_id": task_id,
                "filename": clean_filename,
                "status": "PENDING"
            }
        )
    except Exception as e:
        if os.path.exists(file_path): 
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{task_id}", response_model=StandardResponse)
async def get_task_status(task_id: int, current_user: dict = Depends(get_current_user)):
    """
    Polls the processing status of a background ingestion task.
    """
    workspace_id = get_workspace_id(current_user)
    task = await get_document_task(task_id, workspace_id=workspace_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return success_response(
        message=f"Task is {task['status']}",
        data=task
    )


@router.post("/reset")
async def reset_database_router(conversation_id: Optional[int] = None, current_user: dict = Depends(get_current_user)):
    """
    Clears the workspace documents and vectors.
    """
    workspace_id = get_workspace_id(current_user)
    if conversation_id and not await verify_conversation_owner(conversation_id, workspace_id):
        raise HTTPException(status_code=403, detail="Access denied to this conversation.")

    try:
        await reset_database(workspace_id)
        return success_response(message="Database reset complete")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/file", response_model=StandardResponse)
async def delete_file(filename: str, conversation_id: Optional[int] = None, current_user: dict = Depends(get_current_user)):
    """
    Deletes a specific file physically and removes its chunks from the database.
    """
    workspace_id = get_workspace_id(current_user)
    if conversation_id and not await verify_conversation_owner(conversation_id, workspace_id):
        raise HTTPException(status_code=403, detail="Access denied to this conversation.")

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
        chunks_deleted = await delete_document_chunks(filename, workspace_id=workspace_id, conversation_id=conversation_id)
        # Also clean vector store
        from backend.database.vector_db import delete_vector_store_documents
        delete_vector_store_documents(filename, workspace_id=workspace_id, conversation_id=conversation_id)
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
async def get_files(conversation_id: int = Path(...), current_user: dict = Depends(get_current_user)):
    """
    Fetches the list of filenames active in the specified conversation.
    """
    workspace_id = get_workspace_id(current_user)
    if not await verify_conversation_owner(conversation_id, workspace_id):
        raise HTTPException(status_code=403, detail="Access denied to this conversation.")

    try:
        files = await get_files_for_workspace(workspace_id, conversation_id=conversation_id)
        return success_response(
            message="Files fetched successfully",
            data={"files": files}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))