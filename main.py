import uvicorn
import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.utils.exceptions import add_exception_handlers

# Ensure the backend module can be found in the system path.
# This fixes import errors when running the script directly from the root directory.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.config.settings import settings
from backend.routers import ingestion_router
from backend.routers import chat_router
from backend.routers import auth_router

"""
Content Research Agent - Main Entry Point

This script bootstraps the FastAPI application, configuring:
1.  **Middleware**: Sets up CORS to allow communication with the frontend.
2.  **Routing**: Aggregates endpoints from the Ingestion and Chat modules.
3.  **Static Files**: Serves the frontend assets directly for a monolithic deployment.
"""

# Initialize the ASGI application
app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

# --- CORS Configuration ---
"""
Cross-Origin Resource Sharing (CORS) Middleware.

Currently configured to allow ALL origins ("*").
In a production environment, you should restrict `allow_origins` to the specific 
domains where your frontend is hosted (e.g., ["https://myapp.com"]).
"""
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Router Registration ---
# Mount the specialized routers to keep the API logic modular and clean.
app.include_router(auth_router.router)
app.include_router(ingestion_router.router)
app.include_router(chat_router.router)

# --- Exception Handlers ---
add_exception_handlers(app)

# --- Frontend serving and Storage ---
# Mount the "frontend" directory to serve static assets (JS, CSS, Images).
app.mount("/static", StaticFiles(directory="frontend"), name="static")
# Mount the "storage" directory to serve uploaded audio/video and extracted keyframes.
# Serve storage files with fuzzy matching to handle client/LLM emoji or metadata mismatches
@app.get("/storage/{path:path}")
async def serve_storage_file(path: str):
    """
    Serves files from the storage directory.
    If the exact filename is not found (e.g., due to emoji mismatches or 
    character set translations), attempts a fuzzy match based on normalized alphanumeric parts.
    """
    import urllib.parse
    unquoted_path = urllib.parse.unquote(path)

    # 1. Resolve to absolute path to prevent directory traversal attacks (Path Traversal Vulnerability check)
    safe_storage_dir = os.path.abspath(settings.STORAGE_DIR)
    resolved_path = os.path.abspath(os.path.join(safe_storage_dir, unquoted_path))
    
    # Enforce directory boundary check to prevent partial matching bypasses
    if not resolved_path.startswith(safe_storage_dir + os.sep) and resolved_path != safe_storage_dir:
        raise HTTPException(status_code=403, detail="Access denied")
        
    # If the file exists, serve it directly
    if os.path.exists(resolved_path) and os.path.isfile(resolved_path):
        return FileResponse(resolved_path)
        
    # If the exact path is not found, do a recursive fuzzy search inside the entire storage directory
    import re
    
    def normalize(s):
        return re.sub(r'[^a-zA-Z0-9_]', '', s).lower()
        
    base_name = os.path.basename(resolved_path)
    norm_base = normalize(base_name)
    
    try:
        # Walk through the entire storage directory
        for root, dirs, files in os.walk(safe_storage_dir):
            for f in files:
                if normalize(f) == norm_base:
                    matched_path = os.path.join(root, f)
                    if os.path.isfile(matched_path):
                        # Ensure safety check on matched file path
                        if os.path.abspath(matched_path).startswith(safe_storage_dir + os.sep):
                            return FileResponse(matched_path)
    except Exception as e:
        pass
        
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/")
async def home():
    """
    Serves the main entry point (index.html) for the frontend application.
    
    This allows the backend to serve the UI directly, making it easy to run
    the full stack locally without a separate Node.js server.
    """
    return FileResponse("frontend/index.html")
    

if __name__ == "__main__":
    """
    Entry point for local development.
    
    Uses Uvicorn as the ASGI server.
    - host="0.0.0.0": Makes the server accessible on the local network.
    - port=8000: Standard FastAPI port.
    - reload=True: Enables hot-reloading when code changes are detected.
    """
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)