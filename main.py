import uvicorn
import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure the backend module can be found
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.config.settings import settings
from backend.routers import ingestion_router

# Initialize App
app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(ingestion_router.router)

@app.get("/")
def home():
    return {"message": "System is running", "docs_url": "/docs"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)