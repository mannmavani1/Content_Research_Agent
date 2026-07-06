import os
import shutil
# pyrefly: ignore [missing-import]
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores.utils import filter_complex_metadata
from backend.database.database import add_documents, init_db
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
    
    from langchain_community.document_loaders import (
        PyPDFLoader, Docx2txtLoader, TextLoader, UnstructuredExcelLoader, UnstructuredPowerPointLoader, UnstructuredMarkdownLoader
    )
    
    if ext == ".pdf": return PyPDFLoader(file_path)
    elif ext == ".docx": return Docx2txtLoader(file_path)
    elif ext == ".txt": return TextLoader(file_path, encoding="utf-8")
    elif ext == ".md": return UnstructuredMarkdownLoader(file_path)
    elif ext in [".xlsx", ".xls"]: return UnstructuredExcelLoader(file_path, mode="elements")
    elif ext == ".pptx": return UnstructuredPowerPointLoader(file_path, mode="elements")
    else: raise ValueError(f"Unsupported file type: {ext}")

def process_document(file_path: str, conversation_id: int = None) -> int:
    """
    Orchestrates the complete ingestion pipeline for a single document or media file.

    Steps:
    1. **Load/Route**: Decides pipeline based on file type.
    2. **Process/Extract**: Runs OCR/Captioning, Speech-to-text, or Frame extraction.
    3. **Store**: Indexes parsed content chunks and relational metadata.

    Args:
        file_path (str): Path to the uploaded file.

    Returns:
        int: The total number of chunks created and indexed.
    """
    ext = os.path.splitext(file_path)[1].lower()
    from langchain_core.documents import Document
    
    # 1. Multimodal File Ingestion Routing
    if ext in [".jpg", ".jpeg", ".png", ".webp"]:
        from backend.services.multimodal.image_processor import process_image_file
        chunks = process_image_file(file_path)
        splits = [Document(page_content=c["content"], metadata=c["metadata"]) for c in chunks]
        print(f"Processed image {file_path} into {len(splits)} chunks")
        
    elif ext in [".mp3", ".wav", ".m4a"]:
        from backend.services.multimodal.audio_processor import process_audio_file
        chunks = process_audio_file(file_path)
        splits = [Document(page_content=c["content"], metadata=c["metadata"]) for c in chunks]
        print(f"Processed audio {file_path} into {len(splits)} chunks")
        
    elif ext in [".mp4", ".mov", ".mkv"]:
        from backend.services.multimodal.video_processor import process_video_file
        chunks = process_video_file(file_path)
        splits = [Document(page_content=c["content"], metadata=c["metadata"]) for c in chunks]
        print(f"Processed video {file_path} into {len(splits)} chunks")
        
    else:
        # 2. Standard Text Ingestion Pipeline
        loader = get_loader_for_file(file_path)
        docs = loader.load()
        print(f"Loaded {len(docs)} documents of type {type(docs)}")
        
        documents = filter_complex_metadata(docs)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(documents)
        print(f"Split text into {len(splits)} chunks")
    
    # Inject conversation_id into all splits
    if conversation_id is not None:
        for split in splits:
            split.metadata["conversation_id"] = conversation_id

    # 3. Store
    add_documents(splits)
    print(f"Added {len(splits)} chunks to local database")
    
    return len(splits)

def reset_database(conversation_id: int = None):
    """
    Performs a hard reset of the system's memory for a specific conversation.

    This function is destructive:
    1. Deletes the physical `uploads` directory to remove raw files.
    2. Re-creates the `uploads` directory.
    3. Deletes the local SQLite database file to clear all indexed records.
    
    Used primarily for testing or when the user wants to start a fresh session.
    """
    print("Resetting database...")
    try:
        # Physical cleanup
        if os.path.exists(settings.UPLOAD_DIR):
            shutil.rmtree(settings.UPLOAD_DIR)
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

        # Database cleanup
        from backend.database.database import delete_all_documents
        delete_all_documents(conversation_id)
        print("Cleared documents table.")
        
    except Exception as e:
        print(f"Warning during DB reset: {e}")

    print("Database reset complete")