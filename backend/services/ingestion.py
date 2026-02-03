import os
import shutil
from langchain_community.document_loaders import (
    PyPDFLoader, Docx2txtLoader, TextLoader, UnstructuredExcelLoader, UnstructuredPowerPointLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores.utils import filter_complex_metadata
from backend.database.vector_store import get_vectorstore
from backend.config.settings import settings

def get_loader_for_file(file_path: str):
    """
    Factory function to select the appropriate LangChain document loader based on file extension.

    Args:
        file_path (str): The absolute path to the file on disk.

    Returns:
        BaseLoader: An instantiated loader object ready to call `.load()`.

    Raises:
        ValueError: If the file extension is not supported (currently supports: pdf, docx, txt, xlsx, xls, pptx).
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf": return PyPDFLoader(file_path)
    elif ext == ".docx": return Docx2txtLoader(file_path)
    elif ext == ".txt": return TextLoader(file_path, encoding="utf-8")
    elif ext in [".xlsx", ".xls"]: return UnstructuredExcelLoader(file_path, mode="elements")
    elif ext == ".pptx": return UnstructuredPowerPointLoader(file_path, mode="elements")
    else: raise ValueError(f"Unsupported file type: {ext}")

def process_document(file_path: str) -> int:
    """
    Orchestrates the complete ingestion pipeline for a single document.

    Steps:
    1. **Load**: Reads the file content using the appropriate loader.
    2. **Clean**: Filters out complex metadata that might break the vector store.
    3. **Split**: Chunks the text using `RecursiveCharacterTextSplitter` to ensure 
       semantic context is preserved within a reasonable token limit (1000 chars).
    4. **Store**: Embeds the chunks and saves them to the persistent ChromaDB.

    Args:
        file_path (str): Path to the uploaded file.

    Returns:
        int: The total number of text chunks created and indexed.
    """
    # 1. Load
    loader = get_loader_for_file(file_path)
    docs = loader.load()
    print(f"Loaded {len(docs)} documents of type {type(docs)}")
    
    # 2. Split
    # sanitize metadata before splitting to prevent vector store errors
    documents = filter_complex_metadata(docs)
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(documents)
    print(f"Split into {len(splits)} chunks")
    
    # 3. Store
    vectorstore = get_vectorstore()
    vectorstore.add_documents(splits) 
    print(f"Added {len(splits)} chunks to vectorstore")
    
    return len(splits)

def reset_vectorstore():
    """
    Performs a hard reset of the system's memory.

    This function is destructive:
    1. Deletes the physical `uploads` directory to remove raw files.
    2. Re-creates the `uploads` directory.
    3. Connects to the Vector DB and deletes all indexed records by ID.
    
    Used primarily for testing or when the user wants to start a fresh session.
    """
    print("Resetting vectorstore...")
    try:
        # Physical cleanup
        if os.path.exists(settings.UPLOAD_DIR):
            shutil.rmtree(settings.UPLOAD_DIR)
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

        # Database cleanup
        vectorstore = get_vectorstore()
        result = vectorstore.get()
        all_ids = result['ids']
        
        if all_ids:
            vectorstore.delete(ids=all_ids)
            print(f"Deleted {len(all_ids)} records from Vector DB")
        else:
            print("Vector DB is already empty.")
        
    except Exception as e:
        print(f"Warning during DB reset: {e}")

    print("Vectorstore reset complete")