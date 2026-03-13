from __future__ import annotations

"""
Quick helper to pull the latest 10 Latent Space podcast episodes
from the public archive page and save them into a JSON file.

Transcripts: when OPENAI_API_KEY is set, uses Whisper on the episode audio
(enclosure URL from RSS) to get spoken-word-only transcription. Otherwise
falls back to extracting text from the episode HTML (may include timestamps etc.).

Usage (from project root):

    set OPENAI_API_KEY=sk-...   # optional; enables Whisper transcription
    python -m src.latent_space_scraper

Result file:
    data/latent_space_latest_episodes.json
    data/latent_space_first_episode_transcript.txt
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup
import feedparser

# Load .env from project root so OPENAI_API_KEY is available
try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parent.parent
    load_dotenv(_root / ".env")
except ImportError:
    pass


# Latent Space Substack RSS feed – used as the canonical source.
RSS_URL = "https://www.latent.space/feed"
OUTPUT_EPISODES = Path(__file__).resolve().parent.parent / "data" / "latent_space_latest_episodes.json"
OUTPUT_TRANSCRIPT = Path(__file__).resolve().parent.parent / "data" / "latent_space_first_episode_transcript.txt"


def _get_enclosure_url(entry) -> Optional[str]:
    """Get the audio URL (enclosure) from a feedparser entry, same as Apple pipeline."""
    if getattr(entry, "enclosures", None) and isinstance(entry.enclosures, list):
        enc = entry.enclosures[0]
        if enc and (enc.get("href") or enc.get("url")):
            return enc.get("href") or enc.get("url")
    if getattr(entry, "links", None):
        for link in entry.links:
            if link.get("rel") == "enclosure" and (link.get("href") or link.get("url")):
                return link.get("href") or link.get("url")
    return None


def _get_audio_url_from_page_html(html: str) -> Optional[str]:
    """Try to find a direct audio URL in the episode page HTML (e.g. Substack player)."""
    soup = BeautifulSoup(html, "html.parser")
    # <audio src="...">
    audio = soup.find("audio", src=True)
    if audio and audio.get("src"):
        return audio["src"]
    # Links to common audio formats
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip().lower()
        if href.endswith(".mp3") or ".mp3?" in href or "audio" in href:
            return a["href"]
    # data-src or data-url sometimes used by players
    for tag in soup.find_all(attrs={"data-src": True}):
        val = tag.get("data-src", "")
        if "mp3" in val or "audio" in val:
            return val
    return None


def fetch_latest_episodes_from_rss(
    rss_url: str,
    limit: int = 10,
    openai_api_key: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Fetch latest `limit` episodes from RSS. When OPENAI_API_KEY is set and the
    feed has an audio enclosure, transcripts are obtained via Whisper (audio
    only). Otherwise transcripts are extracted from HTML (may include timestamps etc.).
    """
    api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
    feed = feedparser.parse(rss_url)
    episodes: List[Dict[str, str]] = []

    for entry in feed.entries[:limit]:
        content_html = ""
        if getattr(entry, "content", None):
            try:
                content_html = entry.content[0].get("value", "")  # type: ignore[attr-defined]
            except Exception:
                content_html = ""

        # 1) Prefer Whisper from RSS enclosure
        transcript_text = ""
        enclosure_url = _get_enclosure_url(entry)
        if enclosure_url and api_key:
            try:
                from .transcripts import transcribe_via_openai_whisper
                transcript_text = transcribe_via_openai_whisper(enclosure_url, api_key)
            except Exception as e:
                transcript_text = ""
                if "create audio chunks" in str(e) or "not valid audio" in str(e):
                    print("  📄 Whisper skipped; using transcript from episode page if available")

        # 2) Try "Transcript" section from RSS content
        if not transcript_text and content_html:
            try:
                transcript_text = extract_transcript_from_html(content_html)
                if transcript_text:
                    print("  📄 Using transcript from episode page (RSS)")
            except Exception:
                pass

        # 3) Fetch full episode page: try audio (Whisper) or Transcript section
        page_url = entry.get("link", "")
        if not transcript_text and page_url:
            try:
                page_html = fetch_transcript_html(page_url)
                if api_key and not enclosure_url:
                    audio_url = _get_audio_url_from_page_html(page_html)
                    if audio_url:
                        try:
                            from .transcripts import transcribe_via_openai_whisper
                            transcript_text = transcribe_via_openai_whisper(audio_url, api_key)
                        except Exception:
                            pass
                if not transcript_text:
                    transcript_text = extract_transcript_from_html(page_html)
                    if transcript_text:
                        print("  📄 Using transcript from episode page")
            except Exception:
                pass

        episodes.append(
            {
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "published": entry.get("published", "") or entry.get("updated", ""),
                "summary": entry.get("summary", ""),
                "content_html": content_html,
                "transcript": transcript_text,
            }
        )

    return episodes


def save_episodes(episodes: List[Dict[str, str]]) -> None:
    OUTPUT_EPISODES.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_EPISODES.write_text(json.dumps(episodes, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch_transcript_html(url: str) -> str:
    """Fetch the raw HTML for a specific episode page."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def extract_transcript_from_html(html: str) -> str:
    """
    Extract the transcript section from a Latent Space episode page.
    Tries: (1) heading "Transcript" + following content, (2) id/class with "transcript",
    (3) full-page text: everything after the word "Transcript".
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1) Heading containing "Transcript" -> collect following siblings until next heading
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        text = (tag.get_text(strip=True) or "").lower()
        if "transcript" in text:
            chunks: List[str] = []
            for sib in tag.next_siblings:
                if getattr(sib, "name", None) in ("h1", "h2", "h3", "h4"):
                    break
                if isinstance(sib, str):
                    continue
                part = sib.get_text("\n", strip=True)
                if part:
                    chunks.append(part)
            if chunks:
                return "\n\n".join(chunks).strip()
            break

    # 2) Element with id or class containing "transcript"
    for attr in ("id", "class"):
        for tag in soup.find_all(attrs={attr: True}):
            val = tag.get(attr)
            if isinstance(val, list):
                val = " ".join(val)
            if val and "transcript" in (val or "").lower():
                text = tag.get_text("\n", strip=True)
                if len(text) > 100:
                    return text.strip()

    # 3) Fallback: full page text, take everything after "Transcript"
    for container in [soup.find("article"), soup.find("main"), soup.body, soup]:
        if container is None:
            continue
        full_text = container.get_text("\n", strip=True)
        idx = full_text.lower().find("transcript")
        if idx != -1:
            start = idx + len("transcript")
            while start < len(full_text) and full_text[start] in "\n\r\t: ":
                start += 1
            transcript = full_text[start:].strip()
            for stop in ("\nsubscribe", "\nshare this post", "\nread more", "\nrelated posts", "\n© ", "\nsign in"):
                pos = transcript.lower().find(stop)
                if pos > 100:
                    transcript = transcript[:pos].strip()
            if len(transcript) > 200:
                return transcript

    return ""


def save_transcript(text: str) -> None:
    OUTPUT_TRANSCRIPT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_TRANSCRIPT.write_text(text, encoding="utf-8")


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        print("Using Whisper for transcripts (OPENAI_API_KEY set).")
    else:
        print("OPENAI_API_KEY not set; transcripts will be extracted from HTML (may include timestamps etc.).")

    # 1) Use the Latent Space RSS feed as the canonical source for latest episodes.
    episodes = fetch_latest_episodes_from_rss(RSS_URL, limit=10, openai_api_key=api_key)
    save_episodes(episodes)

    # 2) Save the first (latest) episode's transcript to the .txt file.
    if episodes:
        transcript = episodes[0].get("transcript", "")
        save_transcript(transcript)
        print(
            f"Saved {len(episodes)} Latent Space episodes to {OUTPUT_EPISODES} "
            f"and transcript for first episode to {OUTPUT_TRANSCRIPT}"
        )
    else:
        print(f"Saved 0 Latent Space episodes to {OUTPUT_EPISODES} (no entries in RSS feed)")


if __name__ == "__main__":
    main()

