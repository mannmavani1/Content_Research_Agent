import os
import base64
import warnings
from PIL import Image
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

warnings.filterwarnings('ignore')
load_dotenv()

# Global cache for the ChatGroq model instance
_vision_llm = None

def get_vision_llm():
    global _vision_llm
    if _vision_llm is None:
        api_key = os.getenv("GROQ_API_KEY")
        _vision_llm = ChatGroq(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            temperature=0.1,
            max_retries=2,
            api_key=api_key
        )
    return _vision_llm

def get_captioner():
    """
    Dummy/fallback function for legacy compatibility.
    Returns a callable that mimics the transformers pipeline using Groq Vision API.
    """
    class GroqCaptioner:
        def __call__(self, img, text=""):
            # Temporary save PIL image to caption it
            import tempfile
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, "temp_video_frame.jpg")
            img.save(temp_path, format="JPEG")
            try:
                caption = caption_image_with_vision(temp_path)
                return [{"generated_text": caption}]
            except Exception as e:
                print(f"Error in GroqCaptioner: {e}")
                return [{"generated_text": "Visual scene description unavailable"}]
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
    return GroqCaptioner()

def caption_image_with_vision(image_path: str) -> str:
    """
    Utility function to send a local image to Groq's Vision API and get a description.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
        
    # Get image format/extension for MIME type mapping
    try:
        with Image.open(image_path) as img:
            img_format = img.format or "JPEG"
    except Exception:
        img_format = "JPEG"
        
    mime_type = "image/jpeg"
    fmt = img_format.lower()
    if fmt == "png":
        mime_type = "image/png"
    elif fmt == "webp":
        mime_type = "image/webp"
    elif fmt == "gif":
        mime_type = "image/gif"
        
    # Read and encode
    with open(image_path, "rb") as f:
        img_bytes = f.read()
    base64_image = base64.b64encode(img_bytes).decode("utf-8")
    
    llm = get_vision_llm()
    prompt = (
        "You are an expert document and image analyst. "
        "Analyze this image and provide a highly detailed description of its contents. "
        "If it is a chart, graph, table, or diagram, transcribe or summarize the data, trends, titles, "
        "and all key numbers. If it contains text, transcribe the text. "
        "Provide the output as a clean description ready for a search database index."
    )
    
    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_image}"
                }
            }
        ]
    )
    
    response = llm.invoke([message])
    return getattr(response, "content", str(response)).strip()

def process_image_file(file_path: str) -> list:
    """
    Ingests an image, extracts metadata, generates a visual caption using Groq Vision API,
    and returns a list of chunk dicts ready to be indexed.
    
    Returns:
        List of dicts, each having 'content' (str) and 'metadata' (dict).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Image file not found: {file_path}")
        
    filename = os.path.basename(file_path)
    
    # 1. Extract metadata
    try:
        with Image.open(file_path) as img:
            width, height = img.size
            img_format = img.format
            mode = img.mode
    except Exception as e:
        print(f"Error reading image metadata for {filename}: {e}")
        width, height, img_format, mode = 0, 0, "Unknown", "RGB"
        
    file_size_kb = round(os.path.getsize(file_path) / 1024, 2)
    
    # 2. Run Groq Vision Captioning
    try:
        print(f"Sending {filename} to Groq Vision API...")
        description = caption_image_with_vision(file_path)
    except Exception as e:
        print(f"Error generating caption for {filename}: {e}")
        description = "Visual content could not be processed automatically due to API error."
        
    # 3. Format detailed content text for search indexing
    content_text = (
        f"Image Analysis File: {filename}\n"
        f"Visual Description: {description}\n"
        f"Format: {img_format} ({mode}), Dimensions: {width}x{height} pixels, Size: {file_size_kb} KB.\n"
    )
    
    # 4. Construct chunk
    doc_chunk = {
        "content": content_text,
        "metadata": {
            "source": file_path,
            "filename": filename,
            "media_type": "image",
            "dimensions": f"{width}x{height}",
            "file_size_kb": file_size_kb,
            "format": img_format or "Unknown",
            "caption": description[:100] + "..." if len(description) > 100 else description,
            "vqa_analysis": description
        }
    }
    
    return [doc_chunk]
