from __future__ import annotations

import json
import os
import re
import tempfile
from uuid import uuid4
from typing import Optional, Tuple

import requests
import httpx
from openai import OpenAI

from .apple import Episode, find_transcript_for_entry


def _find_ffmpeg() -> Tuple[str, str]:
    """Return (ffmpeg_exe, ffprobe_exe). Uses PATH, or FFMPEG_PATH env (folder or full path to ffmpeg)."""
    import shutil
    ext = ".exe" if os.name == "nt" else ""
    path_env = os.environ.get("FFMPEG_PATH", "").strip()
    if path_env:
        if os.path.isdir(path_env):
            return (
                os.path.join(path_env, f"ffmpeg{ext}"),
                os.path.join(path_env, f"ffprobe{ext}"),
            )
        if os.path.isfile(path_env):
            base = os.path.dirname(path_env)
            return (path_env, os.path.join(base, f"ffprobe{ext}"))
    return (shutil.which("ffmpeg") or "ffmpeg", shutil.which("ffprobe") or "ffprobe")


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

    content_length = resp.headers.get("Content-Length")
    if content_length and content_length.isdigit() and int(content_length) > 25_000_000:
        raise RuntimeError(f"Transcript file too large ({int(content_length)} bytes), exceeds processing limit")

    ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    content = resp.text
    if len(content.encode('utf-8')) > 25_000_000:
        raise RuntimeError(f"Transcript content too large ({len(content.encode('utf-8'))} bytes), exceeds processing limit")

    if ctype in {"text/plain", "text/vtt"}:
        return content
    if ctype in {"application/srt", "application/x-subrip"}:
        return _strip_srt(content)
    if ctype in {"application/json", "text/json"}:
        try:
            data = resp.json()
            if isinstance(data, dict):
                if "results" in data and isinstance(data["results"], list):
                    return "\n".join([seg.get("text", "").strip() for seg in data["results"] if seg.get("text")])
                if "segments" in data and isinstance(data["segments"], list):
                    return "\n".join([seg.get("text", "").strip() for seg in data["segments"] if seg.get("text")])
                if "text" in data and isinstance(data["text"], str):
                    return data["text"].strip()
            if isinstance(data, list):
                return "\n".join([str(x) for x in data])
            return json.dumps(data)
        except Exception as e:
            raise RuntimeError(f"Failed to parse JSON transcript: {e}")
    return content


def _is_likely_audio(file_path: str) -> bool:
    try:
        with open(file_path, "rb") as f:
            head = f.read(512)
        if not head:
            return False
        if head.startswith(b"ID3"):
            return True
        if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
            return True
        if head.startswith(b"RIFF") or head.startswith(b"OggS") or (len(head) >= 8 and head[4:8] == b"ftyp"):
            return True
        if head.lstrip(b" \t\n\r").startswith(b"<"):
            return False
        if b"<!DOCTYPE" in head or b"<html" in head.lower() or b"<HTML" in head:
            return False
        if head.startswith(b"{") or head.startswith(b"["):
            return False
        return False
    except Exception:
        return False


def _split_audio_file(input_path: str, chunk_duration_minutes: int = 15) -> list[str]:
    try:
        import subprocess
    except ImportError:
        raise RuntimeError("ffmpeg not available for audio splitting")

    ffmpeg_exe, ffprobe_exe = _find_ffmpeg()
    if not os.path.isfile(ffmpeg_exe) and ffmpeg_exe == "ffmpeg":
        try:
            subprocess.run([ffmpeg_exe, "-version"], capture_output=True, timeout=5)
        except FileNotFoundError:
            print("  ⚠️ FFmpeg not found. Install from https://ffmpeg.org/download.html and add to PATH,")
            print("     or set FFMPEG_PATH in .env to the folder containing ffmpeg.exe (e.g. C:\\ffmpeg\\bin)")
            return []

    tmp_dir = os.path.dirname(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    chunk_paths = []
    file_size = os.path.getsize(input_path)
    must_split = file_size > 20_000_000

    duration = 0.0
    try:
        result = subprocess.run(
            [ffprobe_exe, "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", input_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            duration = float(result.stdout.strip())
            print(f"  📊 Audio duration: {duration/60:.1f} minutes")
    except FileNotFoundError:
        print("  ⚠️ ffprobe not found. Set FFMPEG_PATH to the folder containing ffprobe.exe")
    except Exception as e:
        print(f"  ⚠️ Could not get audio duration: {e}")

    if duration <= 0 and file_size > 0:
        duration = max(chunk_duration_minutes * 60 * 2, (file_size / (1024 * 1024)) * 60)
        print(f"  📊 Estimated duration: {duration/60:.1f} minutes (from file size)")

    if duration <= chunk_duration_minutes * 60 and not must_split:
        return [input_path]

    if duration <= 0:
        duration = chunk_duration_minutes * 60 * 2
    chunk_count = max(2, int(duration / (chunk_duration_minutes * 60)) + 1)
    print(f"  ✂️ Splitting into {chunk_count} chunks of {chunk_duration_minutes} minutes each")

    for i in range(chunk_count):
        start_time = i * chunk_duration_minutes * 60
        chunk_path = os.path.join(tmp_dir, f"{base_name}_chunk_{i+1}.mp3")

        try:
            result = subprocess.run(
                [
                    ffmpeg_exe, "-y",
                    "-i", input_path,
                    "-ss", str(start_time),
                    "-t", str(chunk_duration_minutes * 60),
                    "-acodec", "libmp3lame", "-q:a", "5",
                    chunk_path,
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0 or not (os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 0):
                if result.stderr:
                    print(f"  ⚠️ ffmpeg (re-encode) chunk {i+1}: {result.stderr.strip()[-400:]}")
                result2 = subprocess.run(
                    [ffmpeg_exe, "-y", "-ss", str(start_time), "-i", input_path, "-t", str(chunk_duration_minutes * 60), "-c", "copy", chunk_path],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result2.returncode != 0 and result2.stderr:
                    print(f"  ⚠️ ffmpeg (copy) chunk {i+1}: {result2.stderr.strip()[-400:]}")
            if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 0:
                chunk_paths.append(chunk_path)
                print(f"  ✅ Created chunk {i+1}: {os.path.getsize(chunk_path)/1024/1024:.1f}MB")
            else:
                print(f"  ⚠️ Chunk {i+1} is empty or failed")
        except FileNotFoundError:
            if i == 0:
                print("  ⚠️ FFmpeg not found. Install from https://ffmpeg.org/download.html and add to PATH,")
                print("     or set FFMPEG_PATH in .env to the folder containing ffmpeg.exe")
            return []
        except Exception as e:
            print(f"  ❌ Failed to create chunk {i+1}: {e}")

    return chunk_paths


def transcribe_via_openai_whisper(audio_url: str, api_key: Optional[str] = None) -> str:
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

        if not _is_likely_audio(tmp_path):
            return ""

        api_key_to_use = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key_to_use:
            raise RuntimeError("OpenAI API key not provided")

        with httpx.Client(timeout=120.0) as http_client:
            client = OpenAI(api_key=api_key_to_use, http_client=http_client)

            if downloaded_size > 20_000_000:
                print(f"  🔄 File too large ({downloaded_size/1024/1024:.1f}MB), splitting into chunks...")
                chunk_paths = _split_audio_file(tmp_path, chunk_duration_minutes=15)
                if not chunk_paths:
                    return ""

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
                        err_msg = getattr(e, "message", str(e)) or repr(e)
                        if hasattr(e, "response") and getattr(e.response, "text", None):
                            err_msg = f"{err_msg} | {e.response.text[:200]}"
                        print(f"  ❌ Failed to transcribe chunk {i+1}: {err_msg}")
                        continue

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
                print(f"  🎤 Transcribing with Whisper...")
                with open(tmp_path, "rb") as f:
                    result = client.audio.transcriptions.create(model="whisper-1", file=f)
                print(f"  ✅ Transcription completed")
                return getattr(result, "text", "") or ""

    except Exception as e:
        err_msg = getattr(e, "message", str(e)) or repr(e)
        if hasattr(e, "response") and getattr(e.response, "text", None):
            err_msg = f"{err_msg} | {e.response.text[:300]}"
        print(f"  ❌ Whisper transcription failed: {err_msg}")
        raise
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def get_transcript_text(feed_xml: str, entry: Episode, openai_api_key: Optional[str]) -> str:
    t = find_transcript_for_entry(feed_xml, entry)
    if t:
        url, _ttype = t
        try:
            return _fetch_text_from_url(url)
        except Exception:
            pass

    if not entry.enclosure_url:
        raise RuntimeError("No audio URL found for episode and no transcript provided in feed.")

    if not (openai_api_key or os.getenv("OPENAI_API_KEY")):
        raise RuntimeError("OpenAI API key not provided; cannot transcribe audio.")

    return transcribe_via_openai_whisper(entry.enclosure_url, openai_api_key)
