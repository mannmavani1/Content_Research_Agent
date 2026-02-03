from langchain_groq import ChatGroq
from backend.config.settings import settings
import os
from dotenv import load_dotenv

# Load environment variables from .env file (specifically GROQ_API_KEY)
load_dotenv()

def get_llm():
    """
    Initializes the ChatGroq language model client.

    This function acts as a factory for the LLM instance used across the application.
    It configures the model with:
    - **Temperature = 0**: To ensure deterministic and factual outputs (crucial for RAG).
    - **Max Retries = 2**: To handle transient API errors gracefully.
    - **Model Name**: Pulled from the global settings configuration.

    The function assumes `GROQ_API_KEY` is present in the environment variables.

    Returns:
        ChatGroq: An instance of the LangChain-compatible Groq LLM wrapper.
    """
    return ChatGroq(
        model=settings.LLM_MODEL,
        temperature=0,
        max_retries=2,
        api_key=os.getenv("GROQ_API_KEY")
    )