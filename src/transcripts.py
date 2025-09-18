from __future__ import annotations

import json
import re
import time
import tempfile
import os
from uuid import uuid4
from typing import Optional

import requests
from openai import OpenAI

from .apple import Episode, find_transcript_for_entry


def _strip_srt(srt_text: str) -> str:
    lines = []
    for line in srt_text.splitlines():
        if re.match(r"^\d+$", line.strip()):
            continue
        if re.match(r"^\d{2}:\d{2}:\d{2},\d{3} --> ", line):
            continue
        if line.strip() == "":
            continue
        lines.append(line)
    return "\n".join(lines)


def _fetch_text_from_url(url: str) -> str:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    
    # Check content length before processing
    content_length = resp.headers.get("Content-Length")
    if content_length and content_length.isdigit() and int(content_length) > 25_000_000:  # 25MB limit
        raise RuntimeError(f"Transcript file too large ({int(content_length)} bytes), exceeds processing limit")
    
    ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    
    # Get the content first to check its size
    content = resp.text
    if len(content.encode('utf-8')) > 25_000_000:  # 25MB limit
        raise RuntimeError(f"Transcript content too large ({len(content.encode('utf-8'))} bytes), exceeds processing limit")
    
    if ctype in {"text/plain", "text/vtt"}:
        return content
    if ctype in {"application/srt", "application/x-subrip"}:
        return _strip_srt(content)
    if ctype in {"application/json", "text/json"}:
        try:
            data = resp.json()
            # Try common shapes
            if isinstance(data, dict):
                if "results" in data and isinstance(data["results"], list):
                    return "\n".join([seg.get("text", "").strip() for seg in data["results"] if seg.get("text")])
                if "segments" in data and isinstance(data["segments"], list):
                    return "\n".join([seg.get("text", "").strip() for seg in data["segments"] if seg.get("text")])
                if "text" in data and isinstance(data["text"], str):
                    return data["text"].strip()
            if isinstance(data, list):
                return "\n".join([str(x) for x in data])
            # Fallback to raw
            return json.dumps(data)
        except Exception as e:
            raise RuntimeError(f"Failed to parse JSON transcript: {e}")
    # Fallback to treat as text
    return content


def _split_audio_file(input_path: str, chunk_duration_minutes: int = 15) -> list[str]:
    """Split audio file into chunks using ffmpeg. Returns list of chunk file paths."""
    try:
        import subprocess
    except ImportError:
        raise RuntimeError("ffmpeg not available for audio splitting")
    
    tmp_dir = os.path.dirname(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    chunk_paths = []
    
    # Get audio duration first
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'csv=p=0', input_path
        ], capture_output=True, text=True, timeout=30)
        duration = float(result.stdout.strip())
        print(f"  📊 Audio duration: {duration/60:.1f} minutes")
    except Exception as e:
        print(f"  ⚠️ Could not get audio duration: {e}")
        duration = 0
    
    if duration <= chunk_duration_minutes * 60:
        # File is small enough, return original
        return [input_path]
    
    chunk_count = int(duration / (chunk_duration_minutes * 60)) + 1
    print(f"  ✂️ Splitting into {chunk_count} chunks of {chunk_duration_minutes} minutes each")
    
    for i in range(chunk_count):
        start_time = i * chunk_duration_minutes * 60
        chunk_path = os.path.join(tmp_dir, f"{base_name}_chunk_{i+1}.mp3")
        
        try:
            subprocess.run([
                'ffmpeg', '-i', input_path, '-ss', str(start_time),
                '-t', str(chunk_duration_minutes * 60), '-c', 'copy',
                '-y', chunk_path
            ], capture_output=True, timeout=60)
            
            if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 0:
                chunk_paths.append(chunk_path)
                print(f"  ✅ Created chunk {i+1}: {os.path.getsize(chunk_path)/1024/1024:.1f}MB")
            else:
                print(f"  ⚠️ Chunk {i+1} is empty or failed")
        except Exception as e:
            print(f"  ❌ Failed to create chunk {i+1}: {e}")
    
    return chunk_paths


def transcribe_via_openai_whisper(audio_url: str, api_key: Optional[str] = None) -> str:
    # Whisper has a ~25MB file size limit. Check upfront when possible.
    file_size = None
    try:
        head = requests.head(audio_url, timeout=30, allow_redirects=True)
        if head.ok:
            cl = head.headers.get("Content-Length")
            if cl and cl.isdigit():
                file_size = int(cl)
                print(f"  📏 Audio file size: {file_size/1024/1024:.1f}MB")
    except Exception as e:
        print(f"  ⚠️ Could not check audio file size: {e}")

    tmp_dir = tempfile.gettempdir()
    tmp_path = os.path.join(tmp_dir, f"podcast_{uuid4().hex}.mp3")

    try:
        print(f"  📥 Downloading audio file...")
        downloaded_size = 0
        
        with requests.get(audio_url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(tmp_path, "wb") as out:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        downloaded_size += len(chunk)
                        out.write(chunk)
        
        print(f"  ✅ Audio downloaded ({downloaded_size/1024/1024:.1f}MB)")

        # Use provided API key or fall back to environment variable
        api_key_to_use = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key_to_use:
            raise RuntimeError("OpenAI API key not provided")
        
        client = OpenAI(api_key=api_key_to_use)
        
        # Check if file is too large for single transcription
        if downloaded_size > 20_000_000:  # 20MB limit
            print(f"  🔄 File too large ({downloaded_size/1024/1024:.1f}MB), splitting into chunks...")
            
            # Split audio file
            chunk_paths = _split_audio_file(tmp_path, chunk_duration_minutes=15)
            
            if not chunk_paths:
                raise RuntimeError("Failed to create audio chunks")
            
            # Transcribe each chunk
            all_transcripts = []
            for i, chunk_path in enumerate(chunk_paths):
                print(f"  🎤 Transcribing chunk {i+1}/{len(chunk_paths)}...")
                try:
                    with open(chunk_path, "rb") as f:
                        result = client.audio.transcriptions.create(model="whisper-1", file=f)
                    chunk_text = getattr(result, "text", "") or ""
                    if chunk_text.strip():
                        all_transcripts.append(chunk_text.strip())
                        print(f"  ✅ Chunk {i+1} transcribed ({len(chunk_text)} chars)")
                    else:
                        print(f"  ⚠️ Chunk {i+1} produced empty transcript")
                except Exception as e:
                    print(f"  ❌ Failed to transcribe chunk {i+1}: {e}")
                    continue
            
            # Clean up chunk files
            for chunk_path in chunk_paths:
                try:
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)
                except Exception:
                    pass
            
            if all_transcripts:
                combined_transcript = " ".join(all_transcripts)
                print(f"  ✅ Combined transcription completed ({len(combined_transcript)} chars)")
                return combined_transcript
            else:
                raise RuntimeError("All audio chunks failed transcription")
        
        else:
            # File is small enough for single transcription
            print(f"  🎤 Transcribing with Whisper...")
            with open(tmp_path, "rb") as f:
                result = client.audio.transcriptions.create(model="whisper-1", file=f)
            
            print(f"  ✅ Transcription completed")
            return getattr(result, "text", "") or ""
            
    except Exception as e:
        print(f"  ❌ Whisper transcription failed: {e}")
        raise
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def get_transcript_text(feed_xml: str, entry: Episode, openai_api_key: Optional[str]) -> str:
    # Try Podcasting 2.0 transcript first
    t = find_transcript_for_entry(feed_xml, entry)
    if t:
        url, _ttype = t
        try:
            return _fetch_text_from_url(url)
        except Exception:
            pass

    if not entry.enclosure_url:
        raise RuntimeError("No audio URL found for episode and no transcript provided in feed.")

    # Whisper fallback (requires OPENAI_API_KEY to be set in environment)
    if not (openai_api_key or os.getenv("OPENAI_API_KEY")):
        raise RuntimeError("OpenAI API key not provided; cannot transcribe audio.")

    return transcribe_via_openai_whisper(entry.enclosure_url, openai_api_key)
