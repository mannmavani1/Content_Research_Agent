from fastapi import APIRouter, HTTPException
from backend.schemas.api_models import ChatRequest
from backend.agent.workflow import research_agent

router = APIRouter(prefix="/tools", tags=["Research Tools"])

async def run_agent(message: str, force_mode: str = None):
    try:
        initial_state = {"question": message, "messages": []}
        
        if force_mode:
            if force_mode == "summarize": message = "Summarize this document: " + message
            elif force_mode == "compare": message = "Compare these documents: " + message
            elif force_mode == "extract": message = "Extract data from: " + message
            elif force_mode == "insight": message = "Generate insights for: " + message
            
            initial_state["question"] = message

        result = research_agent.invoke(initial_state)
        return {
            "answer": result["generation"]
        }
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

# --- 1. Main Auto-Routing Endpoint ---
@router.post("/chat")
async def auto_chat(request: ChatRequest):
    """Automatically routes to the best tool"""
    return await run_agent(request.message)

# --- 2. Specific Function Endpoints ---
@router.post("/summarize")
async def force_summarize(request: ChatRequest):
    return await run_agent(request.message, force_mode="summarize")

@router.post("/compare")
async def force_compare(request: ChatRequest):
    return await run_agent(request.message, force_mode="compare")

@router.post("/extract")
async def force_extract(request: ChatRequest):
    return await run_agent(request.message, force_mode="extract")

@router.post("/insight")
async def force_insight(request: ChatRequest):
    return await run_agent(request.message, force_mode="insight")