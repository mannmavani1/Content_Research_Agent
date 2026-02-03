from langchain_groq import ChatGroq
from backend.config.settings import settings
import os
from dotenv import load_dotenv

load_dotenv()

def get_llm():
    """
    Get the LLM model from Groq API
    """
    return ChatGroq(
        model=settings.LLM_MODEL,
        temperature=0,
        max_retries=2,
        api_key=os.getenv("GROQ_API_KEY")
    )