from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from backend.config.settings import settings

def get_embedding_function():
    """
    Initializes the embedding model used to convert text into vector representations.

    This function loads the HuggingFace model specified in the settings (default: all-MiniLM-L6-v2).
    It is consistent across both ingestion (saving documents) and retrieval (querying).

    Returns:
        HuggingFaceEmbeddings: An instance of the embedding model wrapper.
    """
    return HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)

def get_vectorstore():
    """
    Connects to the persistent ChromaDB instance on disk.

    This function initializes the vector store client pointing to the directory defined 
    in `settings.VECTOR_DB_DIR`. If the database does not exist, it will be initialized.

    Returns:
        Chroma: The LangChain wrapper for the Chroma vector database.
    """
    return Chroma(
        persist_directory=settings.VECTOR_DB_DIR,
        embedding_function=get_embedding_function()
    )

def get_retriever():
    """
    Creates a retrieval interface for the LangGraph agents to query the database.

    This function wraps the vector store in a Retriever abstraction, configured to 
    return the top 5 most relevant document chunks based on semantic similarity.

    Returns:
        VectorStoreRetriever: A runnable retriever component compatible with LangChain chains.
    """
    vectorstore = get_vectorstore()
    return vectorstore.as_retriever(search_kwargs={"k": 5})