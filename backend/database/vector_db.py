import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from backend.config.settings import settings

_embeddings = None

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        # Load local sentence transformers model
        _embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings

# Place Chroma DB in storage directory alongside sqlite db
PERSIST_DIRECTORY = os.path.join(os.path.dirname(settings.LOCAL_DB_PATH), "chroma_db")

def get_vector_store(conversation_id: int = None) -> Chroma:
    """
    Returns an instance of ChromaDB vector store.
    Uses collection namespaces per conversation.
    """
    os.makedirs(PERSIST_DIRECTORY, exist_ok=True)
    embeddings = get_embeddings()
    collection_name = f"conv_{conversation_id}" if conversation_id is not None else "global_docs"
    return Chroma(
        persist_directory=PERSIST_DIRECTORY,
        embedding_function=embeddings,
        collection_name=collection_name
    )

def add_documents_to_vector_store(documents, conversation_id: int = None):
    """
    Indexes document chunks into the Chroma vector store.
    """
    db = get_vector_store(conversation_id)
    db.add_documents(documents)

def search_vector_store(query: str, conversation_id: int = None, k: int = 5):
    """
    Performs semantic search queries against ChromaDB.
    """
    db = get_vector_store(conversation_id)
    return db.similarity_search(query, k=k)

def delete_vector_store_documents(filename: str, conversation_id: int = None):
    """
    Deletes all vector store records associated with a specific filename.
    """
    db = get_vector_store(conversation_id)
    collection = db._collection
    # Fetch all records to filter by metadata source
    results = collection.get()
    ids_to_delete = []
    
    for i, meta in enumerate(results.get("metadatas", [])):
        if meta and (os.path.basename(meta.get("source", "")) == filename or meta.get("source", "") == filename):
            ids_to_delete.append(results["ids"][i])
            
    if ids_to_delete:
        collection.delete(ids=ids_to_delete)

def delete_all_vector_store_documents(conversation_id: int = None):
    """
    Clears all documents from the vector store collection.
    """
    db = get_vector_store(conversation_id)
    collection = db._collection
    results = collection.get()
    ids = results.get("ids", [])
    if ids:
        collection.delete(ids=ids)
