import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

def format_timestamp(seconds: float) -> str:
    """Formats seconds float into MM:SS format."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"

def process_audio_file(file_path: str) -> list:
    """
    Ingests an audio file, transcribes it using Groq's Whisper API,
    chunks the resulting transcription with timestamp mappings,
    and returns a list of chunk dicts ready for SQLite indexing.
    
    Returns:
        List of dicts, each with 'content' (str) and 'metadata' (dict).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")
        
    filename = os.path.basename(file_path)
    file_size_kb = round(os.path.getsize(file_path) / 1024, 2)
    
    # 1. Choose appropriate MIME type based on file extension
    ext = os.path.splitext(file_path)[1].lower()
    mime_type = "audio/mpeg"
    if ext == ".wav":
        mime_type = "audio/wav"
    elif ext == ".m4a":
        mime_type = "audio/mp4"

    # 2. Query Groq Whisper API
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    chunks = []
    
    try:
        with open(file_path, "rb") as f:
            files = {
                "file": (filename, f, mime_type)
            }
            data = {
                "model": "whisper-large-v3-turbo",
                "response_format": "verbose_json"
            }
            
            print(f"Sending {filename} to Groq Whisper for transcription...")
            res = requests.post(url, headers=headers, files=files, data=data)
            
            if res.status_code != 200:
                raise Exception(f"Groq Whisper transcription failed: {res.text}")
                
            result_json = res.json()
            segments = result_json.get("segments", [])
            
            # If no segments, fallback to full text
            if not segments:
                full_text = result_json.get("text", "")
                if full_text.strip():
                    chunks.append({
                        "content": f"Audio Transcription ({filename}):\n{full_text}",
                        "metadata": {
                            "source": file_path,
                            "filename": filename,
                            "media_type": "audio",
                            "timestamp": "00:00",
                            "start_seconds": 0.0,
                            "file_size_kb": file_size_kb
                        }
                    })
                return chunks
                
            # Group segments into semantic chunks of ~3-5 sentences / segments to preserve context
            current_chunk_text = []
            current_start_seconds = None
            
            for seg in segments:
                text = seg.get("text", "").strip()
                if not text:
                    continue
                    
                start = seg.get("start", 0.0)
                
                if current_start_seconds is None:
                    current_start_seconds = start
                    
                current_chunk_text.append(text)
                
                # Create a chunk if we have ~3 segments or ~300 characters
                joined_text = " ".join(current_chunk_text)
                if len(current_chunk_text) >= 3 or len(joined_text) >= 400:
                    timestamp_str = format_timestamp(current_start_seconds)
                    content_text = f"Audio Transcription ({filename}) at [{timestamp_str}]:\n\"{joined_text}\""
                    
                    chunks.append({
                        "content": content_text,
                        "metadata": {
                            "source": file_path,
                            "filename": filename,
                            "media_type": "audio",
                            "timestamp": timestamp_str,
                            "start_seconds": current_start_seconds,
                            "file_size_kb": file_size_kb
                        }
                    })
                    
                    # Reset for next chunk
                    current_chunk_text = []
                    current_start_seconds = None
                    
            # Handle any remaining segments
            if current_chunk_text:
                joined_text = " ".join(current_chunk_text)
                timestamp_str = format_timestamp(current_start_seconds or 0.0)
                content_text = f"Audio Transcription ({filename}) at [{timestamp_str}]:\n\"{joined_text}\""
                chunks.append({
                    "content": content_text,
                    "metadata": {
                        "source": file_path,
                        "filename": filename,
                        "media_type": "audio",
                        "timestamp": timestamp_str,
                        "start_seconds": current_start_seconds or 0.0,
                        "file_size_kb": file_size_kb
                    }
                })
                
    except Exception as e:
        print(f"Error during Whisper transcription for {filename}: {e}")
        # Return a simple placeholder chunk so the document shows up in the sidebar
        chunks.append({
            "content": f"Audio file: {filename}\nTranscription unavailable due to error: {e}",
            "metadata": {
                "source": file_path,
                "filename": filename,
                "media_type": "audio",
                "timestamp": "00:00",
                "start_seconds": 0.0,
                "file_size_kb": file_size_kb
            }
        })
        
    return chunks
