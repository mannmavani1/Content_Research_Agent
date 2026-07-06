from fastapi import APIRouter, HTTPException, Path
from backend.schemas.api_models import ChatRequest, CreateConversationRequest, RenameConversationRequest
from backend.utils.responses import success_response
from backend.agent.workflow import research_agent
from backend.database.database import create_conversation, get_conversations, add_message, get_messages
from langchain_core.messages import HumanMessage, AIMessage

router = APIRouter(prefix="/tools", tags=["Research Tools"])

async def run_agent(message: str, force_mode: str = None, conversation_id: int = None):
    try:
        # Load history if conversation_id is provided
        history_msgs = []
        if conversation_id:
            db_msgs = get_messages(conversation_id)
            for msg in db_msgs:
                if msg["role"] == "user":
                    history_msgs.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "bot":
                    history_msgs.append(AIMessage(content=msg["content"]))

        initial_state = {"question": message, "messages": history_msgs, "conversation_id": conversation_id or 0}
        
        # If a specific mode is forced, we engineer the prompt to ensure 
        # the Router Node classifies it correctly.
        if force_mode:
            if force_mode == "summarize": message = "Summarize this document: " + message
            elif force_mode == "compare": message = "Compare these documents: " + message
            elif force_mode == "extract": message = "Extract data from: " + message
            elif force_mode == "insight": message = "Generate insights for: " + message
            
            initial_state["question"] = message

        result = research_agent.invoke(initial_state)
        
        # Save to DB if conversation is valid
        if conversation_id:
            add_message(conversation_id, "user", message)
            add_message(conversation_id, "bot", result["generation"])

        return success_response(
            message="Answer Fetched Successful",
            data={"answer": result["generation"]}
        )
    except Exception as e:
        print(f"Error executing agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 1. Conversations API Endpoints ---
@router.post("/conversations")
async def create_new_conversation(req: CreateConversationRequest):
    """Creates a new conversation session."""
    conv = create_conversation(req.title)
    return success_response(message="Created conversation", data=conv)

@router.get("/conversations")
async def list_conversations():
    """Lists all conversations ordered by recent activity."""
    convs = get_conversations()
    return success_response(message="Conversations fetched", data=convs)

@router.delete("/conversations/{conv_id}")
async def delete_conversation_endpoint(conv_id: int = Path(...)):
    """Deletes a conversation."""
    from backend.database.database import delete_conversation
    delete_conversation(conv_id)
    return success_response(message="Conversation deleted")

@router.put("/conversations/{conv_id}")
async def rename_conversation_endpoint(req: RenameConversationRequest, conv_id: int = Path(...)):
    """Renames a conversation."""
    from backend.database.database import rename_conversation
    rename_conversation(conv_id, req.title)
    return success_response(message="Conversation renamed")

@router.get("/conversations/{conv_id}")
async def get_conversation_history(conv_id: int = Path(...)):
    """Gets the message history for a specific conversation."""
    msgs = get_messages(conv_id)
    return success_response(message="Messages fetched", data=msgs)

# --- 2. Main Auto-Routing Endpoint ---
@router.post("/chat")
async def auto_chat(request: ChatRequest):
    return await run_agent(request.message, conversation_id=request.conversation_id)

# --- 3. Specific Function Endpoints ---
@router.post("/summarize")
async def force_summarize(request: ChatRequest):
    return await run_agent(request.message, force_mode="summarize", conversation_id=request.conversation_id)

@router.post("/compare")
async def force_compare(request: ChatRequest):
    return await run_agent(request.message, force_mode="compare", conversation_id=request.conversation_id)

@router.post("/extract")
async def force_extract(request: ChatRequest):
    return await run_agent(request.message, force_mode="extract", conversation_id=request.conversation_id)

@router.post("/insight")
async def force_insight(request: ChatRequest):
    return await run_agent(request.message, force_mode="insight", conversation_id=request.conversation_id)