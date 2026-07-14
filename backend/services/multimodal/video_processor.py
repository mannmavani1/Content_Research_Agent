import os
import subprocess
import glob
from backend.config.settings import settings
from backend.services.multimodal.audio_processor import process_audio_file, format_timestamp
from backend.services.multimodal.image_processor import caption_image_with_vision

def process_video_file(file_path: str) -> list:
    """
    Ingests a video file, extracts mono audio and transcribes it via Whisper,
    extracts visual keyframes every 10 seconds and captions them via local BLIP,
    and returns a combined list of search-indexable chunk dicts.
    
    Returns:
        List of dicts, each with 'content' (str) and 'metadata' (dict).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Video file not found: {file_path}")
        
    filename = os.path.basename(file_path)
    file_size_kb = round(os.path.getsize(file_path) / 1024, 2)
    
    # 1. Setup paths inside the persistent storage
    temp_dir = os.path.join(settings.STORAGE_DIR, "temp")
    frames_dir = os.path.join(settings.STORAGE_DIR, "extracted_frames")
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(frames_dir, exist_ok=True)
    
    base_name_no_ext = os.path.splitext(filename)[0]
    temp_audio_path = os.path.join(temp_dir, f"{base_name_no_ext}_mono.wav")
    
    chunks = []
    
    # 2. Extract audio track using FFmpeg (Mono 16kHz WAV is fast and perfect for Whisper)
    try:
        print(f"Extracting audio from video: {filename}...")
        ffmpeg_audio_cmd = [
            "/opt/homebrew/bin/ffmpeg", "-y",
            "-i", file_path,
            "-vn",
            "-ar", "16000",
            "-ac", "1",
            temp_audio_path
        ]
        subprocess.run(ffmpeg_audio_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        # Transcribe using our audio processor
        audio_chunks = process_audio_file(temp_audio_path)
        
        # Rewrite the metadata to reference the original video
        for chunk in audio_chunks:
            chunk["metadata"]["source"] = file_path
            chunk["metadata"]["filename"] = filename
            chunk["metadata"]["media_type"] = "video"
            chunk["content"] = chunk["content"].replace(f"Audio Transcription ({base_name_no_ext}_mono.wav)", f"Video Transcription ({filename})")
        
        chunks.extend(audio_chunks)
            
    except Exception as e:
        print(f"Failed to extract/transcribe audio track for video {filename}: {e}")
        
    # Cleanup temp audio file
    if os.path.exists(temp_audio_path):
        try:
            os.remove(temp_audio_path)
        except Exception:
            pass

    # 3. Extract visual keyframes every 10 seconds using FFmpeg
    # Save the frame images in our public frames directory so the web UI can play/render them!
    try:
        print(f"Extracting visual keyframes from video: {filename}...")
        frame_pattern = os.path.join(frames_dir, f"{base_name_no_ext}_frame_%03d.jpg")
        
        ffmpeg_frame_cmd = [
            "/opt/homebrew/bin/ffmpeg", "-y",
            "-i", file_path,
            "-vf", "fps=1/10",  # Extract 1 frame every 10 seconds
            "-q:v", "2",        # High quality JPG
            frame_pattern
        ]
        subprocess.run(ffmpeg_frame_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        # 4. Describe frames using Groq Vision API
        extracted_frames = sorted(glob.glob(os.path.join(frames_dir, f"{base_name_no_ext}_frame_*.jpg")))
        
        for idx, frame_path in enumerate(extracted_frames):
            # Parse frame number to get timestamp (frame 1 = 0s, frame 2 = 10s, frame 3 = 20s, etc.)
            seconds = idx * 10
            timestamp_str = format_timestamp(seconds)
            
            try:
                print(f"Captioning frame {idx + 1} using Groq Vision API...")
                caption = caption_image_with_vision(frame_path)
            except Exception as e:
                print(f"Error describing frame {frame_path}: {e}")
                caption = "Visual scene."
                
            # Create a visual frame chunk
            from urllib.parse import quote
            relative_frame_url = f"/storage/extracted_frames/{quote(os.path.basename(frame_path))}"

            
            content_text = (
                f"Video Visual Frame ({filename}) at [{timestamp_str}]:\n"
                f"Visual Scene Description: \"{caption}\""
            )
            
            chunks.append({
                "content": content_text,
                "metadata": {
                    "source": file_path,
                    "filename": filename,
                    "media_type": "video",
                    "timestamp": timestamp_str,
                    "start_seconds": float(seconds),
                    "frame_idx": idx + 1,
                    "frame_path": frame_path,
                    "frame_url": relative_frame_url,
                    "caption": caption
                }
            })
            
    except Exception as e:
        print(f"Failed to extract/caption visual keyframes for video {filename}: {e}")
        
    # If both failed, ensure at least a base document index is created
    if not chunks:
        chunks.append({
            "content": f"Video File: {filename}\nIngestion complete. Transcripts and keyframes unavailable.",
            "metadata": {
                "source": file_path,
                "filename": filename,
                "media_type": "video",
                "timestamp": "00:00",
                "start_seconds": 0.0,
                "file_size_kb": file_size_kb
            }
        })
        
    print(f"Video {filename} processed into {len(chunks)} multimodal chunks.")
    return chunks
