import os

class Settings:
    PROJECT_NAME: str = "Content Research Agent"
    VERSION: str = "1.0.0"
    

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    STORAGE_DIR = os.path.join(BASE_DIR, "storage")
    UPLOAD_DIR = os.path.join(STORAGE_DIR, "uploads")
    VECTOR_DB_DIR = os.path.join(STORAGE_DIR, "vector_db")
    
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    LLM_MODEL: str = "llama3" 

    def init_dirs(self):
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)
        os.makedirs(self.VECTOR_DB_DIR, exist_ok=True)

settings = Settings()
settings.init_dirs()