import uvicorn
import os
import sys
from fastapi import FastAPI
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
app.include_router(ingestion_router.router)
app.include_router(chat_router.router)

# --- Exception Handlers ---
add_exception_handlers(app)

# --- Frontend Serving ---
# Mount the "frontend" directory to serve static assets (JS, CSS, Images).
app.mount("/static", StaticFiles(directory="frontend"), name="static")

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