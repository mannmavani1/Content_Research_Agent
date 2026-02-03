import os
from langchain_community.document_loaders import (
    PyPDFLoader, Docx2txtLoader, TextLoader, UnstructuredExcelLoader, UnstructuredPowerPointLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores.utils import filter_complex_metadata
from backend.database.vector_store import get_vectorstore
from backend.config.settings import settings

def get_loader_for_file(file_path: str):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf": return PyPDFLoader(file_path)
    elif ext == ".docx": return Docx2txtLoader(file_path)
    elif ext == ".txt": return TextLoader(file_path, encoding="utf-8")
    elif ext in [".xlsx", ".xls"]: return UnstructuredExcelLoader(file_path, mode="elements")
    elif ext == ".pptx": return UnstructuredPowerPointLoader(file_path, mode="elements")
    else: raise ValueError(f"Unsupported file type: {ext}")

def process_document(file_path: str) -> int:
    # 1. Load
    loader = get_loader_for_file(file_path)
    docs = loader.load()
    print(f"Loaded {len(docs)} documents of type {type(docs)}")
    # 2. Split
    documents = filter_complex_metadata(docs)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(documents)
    print(f"Split into {len(splits)} chunks")
    # 3. Store
    vectorstore = get_vectorstore()
    vectorstore.add_documents(splits) 
    print(f"Added {len(splits)} chunks to vectorstore")
    return len(splits)