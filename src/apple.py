from __future__ import annotations

import re
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Tuple

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser


@dataclass
class Episode:
    guid: str
    link: str
    title: str
    published: Optional[datetime]
    enclosure_url: Optional[str]
    position: int  # index position in the feed (0 = top)


def extract_show_id_from_apple_url(url: str) -> Optional[str]:
    match = re.search(r"id(\d+)", url)
    return match.group(1) if match else None


def extract_episode_id_from_apple_url(url: str) -> Optional[str]:
    match = re.search(r"[?&]i=(\d+)", url)
    return match.group(1) if match else None


def lookup_feed_url_via_itunes(show_id: str) -> Optional[str]:
    # iTunes Lookup API
    resp = requests.get("https://itunes.apple.com/lookup", params={"id": show_id}, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    if not results:
        return None
    return results[0].get("feedUrl")


def lookup_episode_release_and_show_id(episode_id: str) -> Optional[Tuple[str, datetime]]:
    try:
        resp = requests.get("https://itunes.apple.com/lookup", params={"id": episode_id, "entity": "podcastEpisode"}, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            print(f"⚠️ Apple API returned no results for episode ID: {episode_id}")
            return None
        # The first result should be the episode metadata
        ep = results[0]
        # collectionId is the show id; releaseDate is ISO string
        show_id = str(ep.get("collectionId") or "")
        release_str = ep.get("releaseDate")
        if not show_id or not release_str:
            print(f"⚠️ Apple API result missing show_id or releaseDate for episode ID: {episode_id}")
            return None
        try:
            release_dt = dtparser.isoparse(release_str).replace(tzinfo=None)
        except Exception as e:
            print(f"⚠️ Could not parse release date '{release_str}' for episode ID: {episode_id}, error: {e}")
            return None
        return show_id, release_dt
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Network error looking up episode ID {episode_id}: {e}")
        return None
    except Exception as e:
        print(f"⚠️ Unexpected error looking up episode ID {episode_id}: {e}")
        return None


def parse_feed_entries(feed_url: str) -> List[Episode]:
    parsed = feedparser.parse(feed_url)
    episodes: List[Episode] = []
    for idx, e in enumerate(parsed.entries or []):
        enclosure_url: Optional[str] = None
        if getattr(e, "enclosures", None):
            if e.enclosures and isinstance(e.enclosures, list) and e.enclosures[0].get("href"):
                enclosure_url = e.enclosures[0]["href"]
        elif getattr(e, "links", None):
            for l in e.links:
                if l.get("rel") == "enclosure" and l.get("href"):
                    enclosure_url = l.get("href")
                    break

        guid = getattr(e, "id", None) or getattr(e, "guid", None) or e.get("link") or (enclosure_url or "")
        title = getattr(e, "title", "Untitled")
        link = getattr(e, "link", "")
        published_dt: Optional[datetime] = None
        if getattr(e, "published_parsed", None):
            published_dt = datetime(*e.published_parsed[:6])

        episodes.append(Episode(
            guid=str(guid),
            link=str(link),
            title=str(title),
            published=published_dt,
            enclosure_url=enclosure_url,
            position=idx,
        ))
    return episodes


def fetch_feed_xml(feed_url: str) -> str:
    resp = requests.get(feed_url, timeout=30)
    resp.raise_for_status()
    return resp.text


def _match_item_to_entry(item: "BeautifulSoup", entry: Episode) -> bool:
    guid_tag = item.find("guid")
    link_tag = item.find("link")
    enclosure_tag = item.find("enclosure")

    guid_val = guid_tag.text.strip() if guid_tag and guid_tag.text else None
    link_val = link_tag.text.strip() if link_tag and link_tag.text else None
    enclosure_val = enclosure_tag.get("url") if enclosure_tag else None

    candidates = [c for c in [guid_val, link_val, enclosure_val] if c]
    entry_values = {entry.guid, entry.link, entry.enclosure_url}
    return any(c in entry_values for c in candidates)


def find_transcript_for_entry(feed_xml: str, entry: Episode) -> Optional[Tuple[str, Optional[str]]]:
    soup = BeautifulSoup(feed_xml, "xml")
    for item in soup.find_all("item"):
        if _match_item_to_entry(item, entry):
            # Podcasting 2.0 transcript tag can be namespaced
            t = item.find("podcast:transcript") or item.find("transcript")
            if t:
                url = t.get("url") or t.text.strip()
                ttype = t.get("type")
                if url:
                    return url, ttype
    return None


def sort_episodes(episodes: List[Episode]) -> List[Episode]:
    """Newest-first stable sort: by publish timestamp desc; fallback to feed position (top first)."""
    return sorted(
        episodes,
        key=lambda ep: (1, ep.published.timestamp(), -ep.position) if ep.published else (0, 0.0, -ep.position),
        reverse=True,
    )
