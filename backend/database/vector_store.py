from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from backend.config.settings import settings

def get_embedding_function():
    return HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)

def get_vectorstore():
    """Returns the ChromaDB instance connected to disk."""
    return Chroma(
        persist_directory=settings.VECTOR_DB_DIR,
        embedding_function=get_embedding_function()
    )

def get_retriever():
    """Returns the search interface for the LangGraph agents."""
    vectorstore = get_vectorstore()
    return vectorstore.as_retriever(search_kwargs={"k": 5})