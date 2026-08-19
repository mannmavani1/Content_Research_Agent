import os
import shutil
import asyncio
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores.utils import filter_complex_metadata
from backend.database.database import add_documents, add_triplets
from backend.config.settings import settings

def get_loader_for_file(file_path: str):
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

async def async_extract_triplets_from_text(text: str) -> list:
    from backend.services.llm import get_llm
    from langchain_core.prompts import PromptTemplate
    import re
    import json

    llm = get_llm(streaming=False)
    prompt = PromptTemplate.from_template(
        """Extract relationships from text in the form of triplets: (Subject, Predicate, Object).
Output ONLY a JSON list:
[
  {{"subject": "Entity A", "predicate": "relationship", "object": "Entity B"}}
]

Text: {text}
"""
    )
    chain = prompt | llm
    try:
        # Limit token count to prevent rate limits
        response = await chain.ainvoke({"text": text[:500]})
        response_text = getattr(response, "content", str(response))
        
        # 1. Strip reasoning / thinking tags if present
        response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL).strip()
        
        # 2. Extract JSON code block if wrapped in markdown
        json_match = re.search(r'```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            raw_json = json_match.group(1).strip()
        else:
            array_match = re.search(r'(\[\s*\{.*?\}\s*\])', response_text, re.DOTALL)
            if array_match:
                raw_json = array_match.group(1).strip()
            else:
                obj_match = re.search(r'(\{.*?\})', response_text, re.DOTALL)
                raw_json = obj_match.group(1).strip() if obj_match else response_text

        try:
            data = json.loads(raw_json)
        except Exception:
            individual_objs = re.findall(r'\{\s*"subject"\s*:\s*".*?"\s*,\s*"predicate"\s*:\s*".*?"\s*,\s*"object"\s*:\s*".*?"\s*\}', response_text, re.DOTALL)
            if individual_objs:
                data = [json.loads(o) for o in individual_objs]
            else:
                data = []

        results = data if isinstance(data, list) else [data]
        
        triplets = []
        for item in results:
            if isinstance(item, dict):
                s = item.get("subject")
                p = item.get("predicate")
                o = item.get("object")
                if s and p and o:
                    triplets.append((str(s).strip(), str(p).strip(), str(o).strip()))
        return triplets
    except Exception as e:
        if "429" not in str(e):
            print(f"Failed to extract triplets: {e}")
        return []


def extract_triplets_from_text(text: str) -> list:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(lambda: asyncio.run(async_extract_triplets_from_text(text))).result()
    else:
        return loop.run_until_complete(async_extract_triplets_from_text(text))



def extract_and_caption_pdf_images(file_path: str) -> list:
    import fitz
    from langchain_core.documents import Document
    from backend.services.multimodal.image_processor import caption_image_with_vision
    import tempfile
    import concurrent.futures
    
    doc_chunks = []
    try:
        doc = fitz.open(file_path)
        filename = os.path.basename(file_path)
        temp_dir = tempfile.gettempdir()
        
        extracted_image_tasks = []
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
                
                extracted_image_tasks.append((page_num + 1, xref, temp_image_path))
                image_count += 1
                if image_count >= 8:  # Process up to 8 primary images for fast ingestion
                    break
            
            if image_count >= 8:
                break

        def process_pdf_image(item):
            page_no, xref, img_path = item
            try:
                print(f"Captioning PDF page {page_no} image {xref} in parallel...")
                caption = caption_image_with_vision(img_path)
                content_text = (
                    f"PDF Document Visual Component (from {filename}, Page {page_no}):\n"
                    f"Visual Scene Description: \"{caption}\""
                )
                return Document(
                    page_content=content_text,
                    metadata={
                        "source": file_path,
                        "filename": filename,
                        "media_type": "image",
                        "page": page_no,
                        "caption": caption
                    }
                )
            except Exception as e:
                print(f"Error captioning extracted PDF image {xref}: {e}")
                return None
            finally:
                if os.path.exists(img_path):
                    os.remove(img_path)

        if extracted_image_tasks:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(extracted_image_tasks))) as executor:
                results = list(executor.map(process_pdf_image, extracted_image_tasks))
                doc_chunks = [doc for doc in results if doc is not None]
                
    except Exception as e:
        print(f"Failed to extract images from PDF {file_path}: {e}")
        
    return doc_chunks

async def process_document(file_path: str, workspace_id: int, conversation_id: int = None) -> int:
    ext = os.path.splitext(file_path)[1].lower()
    from langchain_core.documents import Document
    
    # 1. Multimodal File Ingestion Routing
    if ext in [".jpg", ".jpeg", ".png", ".webp"]:
        from backend.services.multimodal.image_processor import process_image_file
        chunks = await asyncio.to_thread(process_image_file, file_path)
        splits = [Document(page_content=c["content"], metadata=c["metadata"]) for c in chunks]
        print(f"Processed image {file_path} into {len(splits)} chunks")
        
    elif ext in [".mp3", ".wav", ".m4a"]:
        from backend.services.multimodal.audio_processor import process_audio_file
        chunks = await asyncio.to_thread(process_audio_file, file_path)
        splits = [Document(page_content=c["content"], metadata=c["metadata"]) for c in chunks]
        print(f"Processed audio {file_path} into {len(splits)} chunks")
        
    elif ext in [".mp4", ".mov", ".mkv"]:
        from backend.services.multimodal.video_processor import process_video_file
        chunks = await asyncio.to_thread(process_video_file, file_path)
        splits = [Document(page_content=c["content"], metadata=c["metadata"]) for c in chunks]
        print(f"Processed video {file_path} into {len(splits)} chunks")
        
    else:
        # 2. Standard Text Ingestion Pipeline
        loader = get_loader_for_file(file_path)
        docs = await asyncio.to_thread(loader.load)
        print(f"Loaded {len(docs)} documents of type {type(docs)}")
        
        documents = filter_complex_metadata(docs)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(documents)
        print(f"Split text into {len(splits)} chunks")

        # If it's a PDF, also run the visual image extraction pass
        if ext == ".pdf":
            try:
                print("Running PDF image extraction pass...")
                visual_splits = await asyncio.to_thread(extract_and_caption_pdf_images, file_path)
                if visual_splits:
                    print(f"Adding {len(visual_splits)} visual chunks to PDF document splits")
                    splits.extend(visual_splits)
            except Exception as e:
                print(f"Error extracting visual chunks from PDF: {e}")
    
    # Inject conversation_id into all splits
    if conversation_id is not None:
        for split in splits:
            split.metadata["conversation_id"] = conversation_id

    # 3. Store in Postgres
    inserted_ids = await add_documents(splits, workspace_id)
    print(f"Added {len(splits)} chunks to local Postgres documents table")
    
    # 4. Store in Chroma Vector Store
    try:
        from backend.database.vector_db import add_documents_to_vector_store
        await asyncio.to_thread(add_documents_to_vector_store, splits, workspace_id)
        print("Indexed chunks into vector store")
    except Exception as e:
        print(f"Failed to save to vector store: {e}")
        
    # 5. Extract and Store Knowledge Graph triplets (GraphRAG)
    if conversation_id is not None:
        print("Extracting knowledge graph triplets in parallel...")
        # Process key chunks to stay well within model rate limits
        target_splits = splits[:4]
        sem = asyncio.Semaphore(2)

        async def process_triplets_for_chunk(idx, split):
            chunk_id = inserted_ids[idx] if idx < len(inserted_ids) else None
            async with sem:
                triplets = await async_extract_triplets_from_text(split.page_content)
                if triplets:
                    await add_triplets(triplets, conversation_id, chunk_id)

        await asyncio.gather(*(process_triplets_for_chunk(i, s) for i, s in enumerate(target_splits)))
        print(f"Graph extraction completed.")

    
    return len(splits)

async def reset_database(workspace_id: int):
    print("Resetting database...")
    try:
        # Physical cleanup
        if os.path.exists(settings.UPLOAD_DIR):
            shutil.rmtree(settings.UPLOAD_DIR)
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

        # Database cleanup
        from backend.database.database import delete_all_documents
        await delete_all_documents(workspace_id)
        print("Cleared documents table.")
        
        # Vector store cleanup
        try:
            from backend.database.vector_db import delete_all_vector_store_documents
            delete_all_vector_store_documents(workspace_id)
            print("Cleared vector store.")
        except Exception as e:
            print(f"Failed to clear vector store: {e}")
        
    except Exception as e:
        print(f"Warning during DB reset: {e}")

    print("Database reset complete")


async def process_document_background(task_id: int, file_path: str, workspace_id: int, conversation_id: int = None):
    """
    Background worker function that updates task status while executing document ingestion.
    """
    from backend.database.database import update_document_task_status
    try:
        await update_document_task_status(task_id, status="PROCESSING")
        num_chunks = await process_document(file_path, workspace_id, conversation_id=conversation_id)
        await update_document_task_status(task_id, status="COMPLETED", chunks_processed=num_chunks)
        print(f"Background task {task_id} completed successfully with {num_chunks} chunks.")
    except Exception as e:
        print(f"Background task {task_id} failed: {e}")
        await update_document_task_status(task_id, status="FAILED", error_message=str(e))