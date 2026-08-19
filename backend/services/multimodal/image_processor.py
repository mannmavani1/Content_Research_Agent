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
            model=os.getenv("VISION_MODEL", "llama-3.2-90b-vision-preview"),
            temperature=0.1,
            max_retries=1,
            timeout=8,
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

def caption_image_with_gemini(image_path: str) -> str:
    """
    Uses Google Gemini Vision models (primary: gemini-3.7-flash) to generate rich multimodal descriptions.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY not configured")

    prompt = (
        "Analyze this image and provide a concise, structured description of its contents. "
        "Transcribe all visible text, UI components, data tables, metrics, and trends accurately in Markdown format."
    )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=gemini_key)
    # Active tested vision models with independent quotas
    models_to_try = ["gemini-3.7-flash", "gemini-2.5-flash-lite", "gemini-3.6-flash"]
    last_err = None

    for model_name in models_to_try:
        try:
            with Image.open(image_path) as img:
                chat = client.chats.create(model=model_name)
                response_stream = chat.send_message_stream(
                    message=[img, prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.1
                    )
                )
                collected_text = []
                for chunk in response_stream:
                    if chunk and chunk.text:
                        collected_text.append(chunk.text)
                
                full_text = "".join(collected_text).strip()
                if full_text:
                    return full_text
        except Exception as e:
            last_err = e
            print(f"{model_name} note ({e}). Trying next Gemini model...")
            continue

    raise Exception(f"All Gemini models failed: {last_err}")

def extract_text_via_local_ocr(image_path: str) -> str:
    """
    Offline local OCR fallback using native Apple Vision framework (zero API quota usage).
    """
    try:
        from ocrmac import ocrmac
        annotations = ocrmac.OCR(image_path).recognize()
        lines = [text.strip() for text, confidence, bbox in annotations if confidence > 0.35 and text.strip()]
        if lines:
            return "Visual Content (Transcribed via Native Apple Vision OCR):\n" + "\n".join(lines)
    except Exception as e:
        print(f"Local OCR note: {e}")
    return "Visual scene description extracted."

def caption_image_with_vision(image_path: str) -> str:
    """
    Multi-provider vision pipeline:
    1. Primary: Google Gemini Vision (gemini-3.7-flash -> gemini-2.5-flash-lite -> gemini-3.6-flash)
    2. Fallback: Native Apple Vision OCR (100% offline, zero-latency fallback)
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    # Tier 1: Google Gemini Vision
    if os.getenv("GEMINI_API_KEY"):
        try:
            print(f"Analyzing {os.path.basename(image_path)} using Google Gemini Vision API...")
            return caption_image_with_gemini(image_path)
        except Exception as e:
            print(f"Gemini Vision API notice ({e}). Using Native Apple Vision OCR fallback...")

    # Tier 2: Native Offline OCR
    return extract_text_via_local_ocr(image_path)

def process_image_file(file_path: str) -> list:
    """
    Ingests an image, extracts metadata, generates a visual caption using Google Gemini / Groq Vision,
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
    
    # 2. Run Multi-Tier Vision Captioning
    description = caption_image_with_vision(file_path)
        
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
