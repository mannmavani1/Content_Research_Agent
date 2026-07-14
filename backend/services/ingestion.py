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
        PyPDFLoader, Docx2txtLoader, TextLoader, UnstructuredExcelLoader, UnstructuredPowerPointLoader, UnstructuredMarkdownLoader, CSVLoader
    )
    
    if ext == ".pdf": return PyPDFLoader(file_path)
    elif ext == ".docx": return Docx2txtLoader(file_path)
    elif ext == ".txt": return TextLoader(file_path, encoding="utf-8")
    elif ext == ".csv": return CSVLoader(file_path)
    elif ext == ".md": return UnstructuredMarkdownLoader(file_path)
    elif ext in [".xlsx", ".xls"]: return UnstructuredExcelLoader(file_path, mode="elements")
    elif ext == ".pptx": return UnstructuredPowerPointLoader(file_path, mode="elements")
    else: raise ValueError(f"Unsupported file type: {ext}")

def extract_triplets_from_text(text: str) -> list:
    """
    Invokes Groq LLM to extract entity-relationship-entity triplets from the text.
    Returns a list of tuples: (subject, predicate, object)
    """
    from backend.services.llm import get_llm
    from langchain_core.prompts import PromptTemplate
    import re
    import json

    llm = get_llm()
    prompt = PromptTemplate.from_template(
        """You are an advanced Knowledge Graph extraction agent. Your job is to read the provided text chunk and extract key semantic relationships between entities.
        
        Extract relationships in the form of triplets: (Subject, Predicate, Object).
        - Subject and Object should be specific entities (names of companies, people, places, dates, products, concepts, etc.).
        - Predicate should be a short verb or relation representing the connection (e.g., "acquired", "subsidiary of", "founded by", "partnered with", "is a").
        
        If no clear relationships are found, return an empty list.
        
        Output format must be a strict JSON list of objects (do not include any introduction or explanation, output ONLY the raw JSON):
        [
          {{"subject": "Entity A", "predicate": "relationship", "object": "Entity B"}},
          ...
        ]
        
        Text: {text}
        """
    )
    chain = prompt | llm
    try:
        response = chain.invoke({"text": text})
        # Extract content text from message or get string
        response_text = getattr(response, "content", str(response))
        
        # Regex to locate the JSON array block
        match = re.search(r'\[\s*\{.*\}\s*\]', response_text, re.DOTALL)
        if not match:
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
        if not match:
            print(f"No JSON block found in response: {response_text[:100]}")
            return []
            
        data = json.loads(match.group(0))
        results = data if isinstance(data, list) else [data]
        
        triplets = []
        for item in results:
            s = item.get("subject")
            p = item.get("predicate")
            o = item.get("object")
            if s and p and o:
                triplets.append((s, p, o))
        return triplets
    except Exception as e:
        print(f"Failed to extract triplets: {e}")
        return []


def extract_and_caption_pdf_images(file_path: str) -> list:
    """
    Extracts embedded images from a PDF, captions them using the Groq Vision API,
    and returns a list of Document objects representing those visual components.
    """
    import fitz
    from langchain_core.documents import Document
    from backend.services.multimodal.image_processor import caption_image_with_vision
    import tempfile
    
    doc_chunks = []
    try:
        doc = fitz.open(file_path)
        filename = os.path.basename(file_path)
        temp_dir = tempfile.gettempdir()
        
        image_count = 0
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)
            
            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                temp_image_path = os.path.join(temp_dir, f"extracted_pdf_img_{xref}.{image_ext}")
                with open(temp_image_path, "wb") as f:
                    f.write(image_bytes)
                
                try:
                    print(f"Extracted image {xref} from PDF page {page_num + 1}. Captioning...")
                    caption = caption_image_with_vision(temp_image_path)
                    
                    content_text = (
                        f"PDF Document Visual Component (from {filename}, Page {page_num + 1}):\n"
                        f"Visual Scene Description: \"{caption}\""
                    )
                    
                    doc_chunks.append(Document(
                        page_content=content_text,
                        metadata={
                            "source": file_path,
                            "filename": filename,
                            "media_type": "image",
                            "page": page_num + 1,
                            "caption": caption
                        }
                    ))
                    image_count += 1
                    if image_count >= 15: # Safety cap
                        print("Reached maximum image extraction limit (15 images). Skipping remaining images.")
                        break
                except Exception as e:
                    print(f"Error captioning extracted PDF image {xref}: {e}")
                finally:
                    if os.path.exists(temp_image_path):
                        os.remove(temp_image_path)
            
            if image_count >= 15:
                break
                
    except Exception as e:
        print(f"Failed to extract images from PDF {file_path}: {e}")
        
    return doc_chunks


def process_document(file_path: str, conversation_id: int = None) -> int:
    """
    Orchestrates the complete ingestion pipeline for a single document or media file.

    Steps:
    1. **Load/Route**: Decides pipeline based on file type.
    2. **Process/Extract**: Runs OCR/Captioning, Speech-to-text, or Frame extraction.
    3. **Store**: Indexes parsed content chunks, vector embeddings, and relational metadata.

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

        # If it's a PDF, also run the visual image extraction pass
        if ext == ".pdf":
            try:
                print("Running PDF image extraction pass...")
                visual_splits = extract_and_caption_pdf_images(file_path)
                if visual_splits:
                    print(f"Adding {len(visual_splits)} visual chunks to PDF document splits")
                    splits.extend(visual_splits)
            except Exception as e:
                print(f"Error extracting visual chunks from PDF: {e}")
    
    # Inject conversation_id into all splits
    if conversation_id is not None:
        for split in splits:
            split.metadata["conversation_id"] = conversation_id

    # 3. Store in SQLite
    inserted_ids = add_documents(splits)
    print(f"Added {len(splits)} chunks to local SQLite documents table")
    
    # 4. Store in Chroma Vector Store
    try:
        from backend.database.vector_db import add_documents_to_vector_store
        add_documents_to_vector_store(splits, conversation_id)
        print("Indexed chunks into vector store")
    except Exception as e:
        print(f"Failed to save to vector store: {e}")
        
    # 5. Extract and Store Knowledge Graph triplets (GraphRAG)
    if conversation_id is not None:
        print("Extracting knowledge graph triplets...")
        from backend.database.database import add_triplets
        # Extract triplets for up to 30 chunks to prevent rate limits
        for i, split in enumerate(splits[:30]):
            chunk_id = inserted_ids[i] if i < len(inserted_ids) else None
            triplets = extract_triplets_from_text(split.page_content)
            if triplets:
                add_triplets(triplets, conversation_id, chunk_id)
        print(f"Graph extraction completed.")
    
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
        
        # Vector store cleanup
        try:
            from backend.database.vector_db import delete_all_vector_store_documents
            delete_all_vector_store_documents(conversation_id)
            print("Cleared vector store.")
        except Exception as e:
            print(f"Failed to clear vector store: {e}")
        
    except Exception as e:
        print(f"Warning during DB reset: {e}")

    print("Database reset complete")