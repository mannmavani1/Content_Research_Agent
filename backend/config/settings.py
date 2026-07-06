import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """
    Central configuration management for the Content Research Agent.

    This class defines global constants, file system paths, and model identifiers
    used throughout the application. It ensures that necessary storage directories
    are established upon initialization.

    Attributes:
        PROJECT_NAME (str): The display name of the application.
        VERSION (str): The current semantic version of the agent.
        BASE_DIR (str): The root directory of the project, calculated dynamically.
        STORAGE_DIR (str): The main directory for persistent data.
        UPLOAD_DIR (str): The subdirectory where raw uploaded files are stored.
        LOCAL_DB_DIR (str): The subdirectory where the SQLite database persists.
        LLM_MODEL (str): The specific LLM version identifier (e.g., for Groq or Ollama).
        RETRIEVAL_STRATEGY (str): The retrieval strategy, e.g., 'vectorless', 'vector', 'hybrid'.
        WORKOS_CLIENT_ID (str): WorkOS Client ID
        WORKOS_API_KEY (str): WorkOS API Key
        WORKOS_REDIRECT_URI (str): OAuth Callback URI
        JWT_SECRET_KEY (str): Secret for signing session JWTs
    """
    PROJECT_NAME: str = "Content Research Agent"
    VERSION: str = "1.0.0"
    
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    STORAGE_DIR = os.path.join(BASE_DIR, "storage")
    UPLOAD_DIR = os.path.join(STORAGE_DIR, "uploads")
    LOCAL_DB_DIR = os.path.join(STORAGE_DIR, "local_db")
    
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    RETRIEVAL_STRATEGY: str = "vectorless"
    LOCAL_DB_PATH: str = os.path.join(LOCAL_DB_DIR, "documents.db")

    WORKOS_CLIENT_ID: str = os.getenv("WORKOS_CLIENT_ID", "")
    WORKOS_API_KEY: str = os.getenv("WORKOS_API_KEY", "")
    WORKOS_REDIRECT_URI: str = os.getenv("WORKOS_REDIRECT_URI", "http://localhost:8000/auth/callback")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change_me_to_a_secure_random_string_in_production")

    def init_dirs(self):
        """
        Ensures that the required storage directory structure exists.

        This method checks for the existence of 'uploads' and 'local_db' directories
        within the 'storage' folder. If they do not exist, it creates them recursively.
        This prevents FileNotFoundError issues during runtime file operations.
        """
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)
        os.makedirs(self.LOCAL_DB_DIR, exist_ok=True)

settings = Settings()
settings.init_dirs()