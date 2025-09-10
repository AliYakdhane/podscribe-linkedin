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


def ensure_bucket(client, bucket_name: str) -> None:
    """Create bucket if it does not exist (no-op on exists)."""
    try:
        buckets = client.storage.list_buckets()
        names = {b.get("name") for b in (buckets or [])}
        if bucket_name not in names:
            # Avoid API differences; do not auto-create. Ask user to create or set correct name.
            print(f"  Supabase: bucket '{bucket_name}' not found. Please create it in Supabase Storage or set SUPABASE_BUCKET to an existing bucket name.")
            return
    except Exception:
        # Best effort; ignore if already exists or no permission
        print(f"  Supabase: could not list buckets (insufficient permissions or API change)")


def upload_file(client, bucket_name: str, path_in_bucket: str, local_path: Path, content_type: str = "text/plain") -> Optional[str]:
    """Upload a local file to Supabase Storage. Returns public URL if bucket is public, else None."""
    try:
        # Use upsert to overwrite if re-run
        with open(local_path, "rb") as f:
            client.storage.from_(bucket_name).upload(
                path_in_bucket,
                f,
                file_options={"content-type": content_type, "upsert": "true", "x-upsert": "true"},
            )
        print(f"  Supabase: uploaded '{path_in_bucket}' to bucket '{bucket_name}'")
        # Try to get a public URL (works if bucket or file is public)
        try:
            url = client.storage.from_(bucket_name).get_public_url(path_in_bucket)
            return getattr(url, "get", lambda k, d=None: None)("publicUrl", None) if hasattr(url, "get") else url
        except Exception:
            return None
    except Exception as ex:
        print(f"  Supabase upload failed for '{path_in_bucket}': {ex}")
        return None


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
