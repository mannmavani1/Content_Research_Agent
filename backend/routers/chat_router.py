from fastapi import APIRouter, HTTPException, Path, Depends, WebSocket, WebSocketDisconnect
from backend.schemas.api_models import ChatRequest, CreateConversationRequest, RenameConversationRequest
from backend.utils.responses import success_response
from backend.agent.workflow import research_agent
from backend.database.database import (
    create_conversation, get_conversations, add_message, get_messages, 
    verify_conversation_owner, delete_conversation, rename_conversation
)
from langchain_core.messages import HumanMessage, AIMessage
from backend.utils.dependencies import get_current_user, get_current_user_ws

router = APIRouter(
    prefix="/tools", 
    tags=["Research Tools"]
)

def get_workspace_id(current_user: dict) -> int:
    """Helper to extract workspace identifier from JWT payload."""
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Workspace identity could not be established.")
    return int(workspace_id)

async def run_agent(message: str, force_mode: str = None, conversation_id: int = None, workspace_id: int = None):
    try:
        # Load history if conversation_id is provided
        history_msgs = []
        if conversation_id:
            if workspace_id and not await verify_conversation_owner(conversation_id, workspace_id):
                raise HTTPException(status_code=403, detail="Access denied to this conversation.")
            db_msgs = await get_messages(conversation_id, workspace_id=workspace_id)
            for msg in db_msgs:
                if msg["role"] == "user":
                    history_msgs.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "bot":
                    history_msgs.append(AIMessage(content=msg["content"]))

        initial_state = {
            "question": message, 
            "messages": history_msgs, 
            "conversation_id": conversation_id or 0,
            "workspace_id": workspace_id or 0
        }
        
        # If a specific mode is forced, we engineer the prompt to ensure 
        # the Router Node classifies it correctly.
        if force_mode:
            if force_mode == "summarize": message = "Summarize this document: " + message
            elif force_mode == "compare": message = "Compare these documents: " + message
            elif force_mode == "extract": message = "Extract data from: " + message
            elif force_mode == "insight": message = "Generate insights for: " + message
            
            initial_state["question"] = message

        # Make sure to run agent asynchronously
        result = await research_agent.ainvoke(initial_state)
        
        # Save to DB if conversation is valid
        if conversation_id:
            await add_message(conversation_id, "user", message)
            await add_message(conversation_id, "bot", result["generation"])

        return success_response(
            message="Answer Fetched Successful",
            data={"answer": result["generation"]}
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error executing agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 1. Conversations API Endpoints ---
@router.post("/conversations")
async def create_new_conversation(req: CreateConversationRequest, current_user: dict = Depends(get_current_user)):
    """Creates a new conversation session for the current user."""
    workspace_id = get_workspace_id(current_user)
    conv = await create_conversation(workspace_id, title=req.title)
    return success_response(message="Created conversation", data=conv)

@router.get("/conversations")
async def list_conversations(current_user: dict = Depends(get_current_user)):
    """Lists all conversations owned by the current workspace."""
    workspace_id = get_workspace_id(current_user)
    convs = await get_conversations(workspace_id=workspace_id)
    return success_response(message="Conversations fetched", data=convs)

@router.delete("/conversations/{conv_id}")
async def delete_conversation_endpoint(conv_id: int = Path(...), current_user: dict = Depends(get_current_user)):
    """Deletes a conversation owned by the current workspace."""
    workspace_id = get_workspace_id(current_user)
    if not await verify_conversation_owner(conv_id, workspace_id):
        raise HTTPException(status_code=403, detail="Access denied to this conversation.")
    await delete_conversation(conv_id, workspace_id=workspace_id)
    return success_response(message="Conversation deleted")

@router.put("/conversations/{conv_id}")
async def rename_conversation_endpoint(req: RenameConversationRequest, conv_id: int = Path(...), current_user: dict = Depends(get_current_user)):
    """Renames a conversation owned by the current workspace."""
    workspace_id = get_workspace_id(current_user)
    if not await verify_conversation_owner(conv_id, workspace_id):
        raise HTTPException(status_code=403, detail="Access denied to this conversation.")
    await rename_conversation(conv_id, req.title, workspace_id=workspace_id)
    return success_response(message="Conversation renamed")

@router.get("/conversations/{conv_id}")
async def get_conversation_history(conv_id: int = Path(...), current_user: dict = Depends(get_current_user)):
    """Gets the message history for a specific conversation owned by the current workspace."""
    workspace_id = get_workspace_id(current_user)
    if not await verify_conversation_owner(conv_id, workspace_id):
        raise HTTPException(status_code=403, detail="Access denied to this conversation.")
    msgs = await get_messages(conv_id, workspace_id=workspace_id)
    return success_response(message="Messages fetched", data=msgs)

# --- WebSocket Chat Streaming Endpoint ---
@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, user_payload: dict = Depends(get_current_user_ws)):
    await websocket.accept()
    workspace_id = user_payload.get("workspace_id")
    if not workspace_id:
        await websocket.close(code=4001, reason="Workspace identity missing")
        return
    workspace_id = int(workspace_id)
    
    try:
        while True:
            # Expecting message JSON format: {"message": "...", "conversation_id": ...}
            try:
                data = await websocket.receive_json()
            except Exception:
                # Break if client sent invalid JSON or closed connection without proper disconnect event
                break

            message = data.get("message")
            conversation_id = data.get("conversation_id")
            mode = data.get("mode")

            if not message:
                await websocket.send_json({"type": "error", "message": "Missing message content."})
                continue

            if conversation_id:
                if not await verify_conversation_owner(conversation_id, workspace_id):
                    await websocket.send_json({"type": "error", "message": "Access denied to this conversation."})
                    continue

            # Load history if conversation_id is provided
            history_msgs = []
            if conversation_id:
                db_msgs = await get_messages(conversation_id, workspace_id=workspace_id)
                for msg in db_msgs:
                    if msg["role"] == "user":
                        history_msgs.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "bot":
                        history_msgs.append(AIMessage(content=msg["content"]))

            initial_state = {
                "question": message,
                "messages": history_msgs,
                "conversation_id": conversation_id or 0,
                "workspace_id": workspace_id
            }

            # Handle force mode matching the REST endpoints logic
            if mode and mode != "chat":
                if mode == "summarize": message = "Summarize this document: " + message
                elif mode == "compare": message = "Compare these documents: " + message
                elif mode == "extract": message = "Extract data from: " + message
                elif mode == "insight": message = "Generate insights for: " + message
                initial_state["question"] = message

            # Inform frontend we have started generating
            await websocket.send_json({"type": "start"})

            full_response = ""
            try:
                # Stream events using LangGraph
                async for event in research_agent.astream_events(initial_state, version="v2"):
                    event_type = event.get("event")
                    if event_type == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
                        text = chunk.content
                        if text:
                            full_response += text
                            await websocket.send_json({"type": "chunk", "text": text})
            except Exception as e:
                print(f"Error executing agent stream: {e}")
                await websocket.send_json({"type": "error", "message": f"Execution error: {str(e)}"})
                continue

            # Save to DB if conversation is valid
            if conversation_id and full_response:
                await add_message(conversation_id, "user", message)
                await add_message(conversation_id, "bot", full_response)

            # Inform frontend generation is finished and send the complete response text
            await websocket.send_json({"type": "end", "text": full_response})

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for workspace: {workspace_id}")
    except Exception as e:
        print(f"WebSocket processing error: {e}")

# --- 2. Main Auto-Routing Endpoint ---
@router.post("/chat")
async def auto_chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    workspace_id = get_workspace_id(current_user)
    if request.conversation_id and not await verify_conversation_owner(request.conversation_id, workspace_id):
        raise HTTPException(status_code=403, detail="Access denied to this conversation.")
    return await run_agent(request.message, conversation_id=request.conversation_id, workspace_id=workspace_id)

# --- 3. Specific Function Endpoints ---
@router.post("/summarize")
async def force_summarize(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    workspace_id = get_workspace_id(current_user)
    if request.conversation_id and not await verify_conversation_owner(request.conversation_id, workspace_id):
        raise HTTPException(status_code=403, detail="Access denied to this conversation.")
    return await run_agent(request.message, force_mode="summarize", conversation_id=request.conversation_id, workspace_id=workspace_id)

@router.post("/compare")
async def force_compare(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    workspace_id = get_workspace_id(current_user)
    if request.conversation_id and not await verify_conversation_owner(request.conversation_id, workspace_id):
        raise HTTPException(status_code=403, detail="Access denied to this conversation.")
    return await run_agent(request.message, force_mode="compare", conversation_id=request.conversation_id, workspace_id=workspace_id)

@router.post("/extract")
async def force_extract(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    workspace_id = get_workspace_id(current_user)
    if request.conversation_id and not await verify_conversation_owner(request.conversation_id, workspace_id):
        raise HTTPException(status_code=403, detail="Access denied to this conversation.")
    return await run_agent(request.message, force_mode="extract", conversation_id=request.conversation_id, workspace_id=workspace_id)

@router.post("/insight")
async def force_insight(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    workspace_id = get_workspace_id(current_user)
    if request.conversation_id and not await verify_conversation_owner(request.conversation_id, workspace_id):
        raise HTTPException(status_code=403, detail="Access denied to this conversation.")
    return await run_agent(request.message, force_mode="insight", conversation_id=request.conversation_id, workspace_id=workspace_id)