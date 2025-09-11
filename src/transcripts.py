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
    ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if ctype in {"text/plain", "text/vtt"}:
        return resp.text
    if ctype in {"application/srt", "application/x-subrip"}:
        return _strip_srt(resp.text)
    if ctype in {"application/json", "text/json"}:
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
    # Fallback to treat as text
    try:
        return resp.text
    except Exception:
        return ""


def transcribe_via_openai_whisper(audio_url: str, api_key: Optional[str] = None) -> str:
    # Whisper has a ~25MB file size limit. Check upfront when possible.
    try:
        head = requests.head(audio_url, timeout=30, allow_redirects=True)
        if head.ok:
            cl = head.headers.get("Content-Length")
            if cl and cl.isdigit() and int(cl) > 24_000_000:
                raise RuntimeError("Audio file exceeds Whisper size limit (~25MB).")
    except Exception:
        # If HEAD fails, continue and let upload attempt handle errors
        pass

    tmp_dir = tempfile.gettempdir()
    tmp_path = os.path.join(tmp_dir, f"podcast_{uuid4().hex}.mp3")

    try:
        with requests.get(audio_url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(tmp_path, "wb") as out:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        out.write(chunk)

        # Use provided API key or fall back to environment variable
        api_key_to_use = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key_to_use:
            raise RuntimeError("OpenAI API key not provided")
        client = OpenAI(api_key=api_key_to_use)
        with open(tmp_path, "rb") as f:
            result = client.audio.transcriptions.create(model="whisper-1", file=f)
        return getattr(result, "text", "") or ""
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
