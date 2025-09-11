from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Set, Dict, Any


class StateStore:
    def __init__(self, state_file: Path) -> None:
        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.processed_guids: Set[str] = set()
        self.latest_published_iso: Optional[str] = None
        self._load()

    def _load(self) -> None:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                guids = data.get("processed_guids", [])
                if isinstance(guids, list):
                    self.processed_guids = set(str(g) for g in guids)
                self.latest_published_iso = data.get("latest_published_iso")
            except Exception:
                self.processed_guids = set()
                self.latest_published_iso = None

    def _save(self) -> None:
        data = {
            "processed_guids": sorted(self.processed_guids),
            "latest_published_iso": self.latest_published_iso,
        }
        self.state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def is_processed(self, guid: str) -> bool:
        return guid in self.processed_guids

    def get_latest_published(self) -> Optional[datetime]:
        if not self.latest_published_iso:
            return None
        try:
            return datetime.fromisoformat(self.latest_published_iso)
        except Exception:
            return None

    def mark_processed(self, guid: str, published: Optional[datetime]) -> None:
        self.processed_guids.add(guid)
        # Update the latest published if newer
        if published is not None:
            current = self.get_latest_published()
            if current is None or published > current:
                # Store as ISO without timezone (naive local time)
                self.latest_published_iso = published.isoformat()
        self._save()


# ----------------------- Supabase helpers -----------------------

def build_supabase_client(url: Optional[str], key: Optional[str]):
    """Return a supabase client if configured, else None.

    We import lazily to avoid hard dependency when not configured.
    """
    if not url or not key:
        print("  Supabase: missing SUPABASE_URL or key; skipping uploads")
        return None
    try:
        from supabase import create_client
    except Exception as ex:
        print(f"  Supabase: failed to import client: {ex}")
        return None
    try:
        client = create_client(url, key)
        print("  Supabase: client initialized")
        return client
    except Exception as ex:
        print(f"  Supabase: failed to initialize client: {ex}")
        return None


def ensure_tables_exist(client) -> None:
    """Ensure required tables exist (no-op if they exist)."""
    try:
        # Test if tables exist by trying to query them
        client.table("podcast_transcripts").select("id").limit(1).execute()
        client.table("podcast_posts").select("id").limit(1).execute()
        print("  Supabase: tables exist and are accessible")
    except Exception as ex:
        print(f"  Supabase: tables may not exist or are not accessible: {ex}")
        print("  Please run the SQL schema in supabase_schema.sql to create the required tables")


def store_transcript(client, table: str, guid: str, title: str, published_at: Optional[datetime], content: str) -> bool:
    """Store transcript content directly in Supabase table. Returns True on success."""
    try:
        row = {
            "guid": guid,
            "title": title,
            "published_at": published_at.isoformat() if published_at else None,
            "transcript_content": content,
        }
        resp = client.table(table).upsert(row, on_conflict="guid").execute()
        if getattr(resp, "data", None) is not None or getattr(resp, "status_code", 200) in (200, 201):
            print(f"  Supabase: stored transcript for '{title}'")
            return True
    except Exception as ex:
        print(f"  Supabase transcript storage failed: {ex}")
    return False


def store_posts(client, table: str, guid: str, title: str, published_at: Optional[datetime], content: str) -> bool:
    """Store posts content directly in Supabase table. Returns True on success."""
    try:
        row = {
            "guid": guid,
            "title": title,
            "published_at": published_at.isoformat() if published_at else None,
            "posts_content": content,
        }
        resp = client.table(table).upsert(row, on_conflict="guid").execute()
        if getattr(resp, "data", None) is not None or getattr(resp, "status_code", 200) in (200, 201):
            print(f"  Supabase: stored posts for '{title}'")
            return True
    except Exception as ex:
        print(f"  Supabase posts storage failed: {ex}")
    return False


def upsert_row(client, table: str, row: Dict[str, Any]) -> bool:
    """Upsert a row into a Supabase table. Returns True on success."""
    try:
        # Attempt upsert; if not supported, fall back to insert
        resp = client.table(table).upsert(row, on_conflict="guid").execute()
        if getattr(resp, "data", None) is not None or getattr(resp, "status_code", 200) in (200, 201):
            print(f"  Supabase: upserted into '{table}'")
            return True
    except Exception:
        try:
            resp = client.table(table).insert(row).execute()
            if getattr(resp, "data", None) is not None or getattr(resp, "status_code", 200) in (200, 201):
                print(f"  Supabase: inserted into '{table}'")
                return True
        except Exception as ex:
            print(f"  Supabase table write failed for '{table}': {ex}")
    return False
