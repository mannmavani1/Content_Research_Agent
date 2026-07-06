import os
from PIL import Image
from transformers import pipeline
import warnings

warnings.filterwarnings('ignore')

# Global cache for the pipelines to avoid re-loading on every file
_captioner = None
_vqa = None

def get_pipelines():
    global _captioner, _vqa
    if _captioner is None:
        print("Initializing Salesforce/blip-image-captioning-base pipeline...")
        _captioner = pipeline("image-text-to-text", model="Salesforce/blip-image-captioning-base")
    if _vqa is None:
        print("Initializing dandelin/vilt-b32-finetuned-vqa pipeline...")
        _vqa = pipeline("visual-question-answering", model="dandelin/vilt-b32-finetuned-vqa")
    return _captioner, _vqa

def get_captioner():
    captioner, _ = get_pipelines()
    return captioner


def process_image_file(file_path: str) -> list:
    """
    Ingests an image, extracts metadata, generates a visual caption locally,
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
    
    # 2. Run local image-to-text captioning and VQA
    caption = "No description available"
    vqa_details = []
    
    try:
        captioner, vqa = get_pipelines()
        with Image.open(file_path) as img:
            # Ensure RGB
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            # Base Caption
            res = captioner(img, text="")
            caption = res[0].get("generated_text", "No description available")
            
            # Detect if people are present
            has_person = vqa(image=img, question="Is there a person in this image?")[0]['answer'].lower()
            
            if 'yes' in has_person:
                gender = vqa(image=img, question="What is the gender of the person?")[0]['answer']
                age = vqa(image=img, question="What is the approximate age of the person?")[0]['answer']
                clothing = vqa(image=img, question="What is the person wearing?")[0]['answer']
                
                vqa_details.append(f"Person Details: Gender appears to be {gender}.")
                vqa_details.append(f"Age estimate: {age}.")
                vqa_details.append(f"Clothing/Appearance: {clothing}.")
            
            # Additional contextual questions
            setting = vqa(image=img, question="Where is this image taken?")[0]['answer']
            vqa_details.append(f"Setting/Environment: {setting}.")

    except Exception as e:
        print(f"Error generating caption/VQA for {filename}: {e}")
        caption = "Visual content could not be processed automatically."
        
    # 3. Format detailed content text for search indexing
    vqa_text = " ".join(vqa_details) if vqa_details else ""
    content_text = (
        f"Image Analysis File: {filename}\n"
        f"Visual Description: {caption}. {vqa_text}\n"
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
            "format": img_format,
            "caption": caption,
            "vqa_analysis": vqa_text
        }
    }
    
    return [doc_chunk]
