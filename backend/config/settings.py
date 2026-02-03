import os

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
        VECTOR_DB_DIR (str): The subdirectory where the vector database persists.
        EMBEDDING_MODEL (str): The HuggingFace model ID used for generating embeddings.
        LLM_MODEL (str): The specific LLM version identifier (e.g., for Groq or Ollama).
    """
    PROJECT_NAME: str = "Content Research Agent"
    VERSION: str = "1.0.0"
    
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    STORAGE_DIR = os.path.join(BASE_DIR, "storage")
    UPLOAD_DIR = os.path.join(STORAGE_DIR, "uploads")
    VECTOR_DB_DIR = os.path.join(STORAGE_DIR, "vector_db")
    
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    LLM_MODEL: str = "llama-3.3-70b-versatile" 

    def init_dirs(self):
        """
        Ensures that the required storage directory structure exists.

        This method checks for the existence of 'uploads' and 'vector_db' directories
        within the 'storage' folder. If they do not exist, it creates them recursively.
        This prevents FileNotFoundError issues during runtime file operations.
        """
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)
        os.makedirs(self.VECTOR_DB_DIR, exist_ok=True)

settings = Settings()
settings.init_dirs()