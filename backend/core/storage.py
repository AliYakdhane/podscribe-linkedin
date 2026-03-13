from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Set, Dict, Any, Tuple


def _log(msg: str) -> None:
    """Print without UnicodeEncodeError on Windows (cp1252)."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), file=sys.stderr)


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
            dt = datetime.fromisoformat(self.latest_published_iso.replace("Z", "+00:00"))
            # Return naive so it compares with feed dates (feedparser gives naive UTC)
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            return dt
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
    _log("  [Supabase] Initializing client...")
    _log(f"  [Supabase] URL provided: {'Yes' if url else 'No'}")
    _log(f"  [Supabase] Key provided: {'Yes' if key else 'No'}")
    
    if not url or not key:
        _log("  [Supabase] missing SUPABASE_URL or key; skipping uploads")
        return None
    
    _log(f"  [Supabase] URL: {url}")
    _log(f"  [Supabase] Key: {key[:10]}... (length: {len(key)})")
    
    try:
        _log("  [Supabase] Importing supabase client...")
        from supabase import create_client
        _log("  [Supabase] Client imported successfully")
    except Exception as ex:
        _log(f"  [Supabase] failed to import client: {ex}")
        return None
    
    try:
        _log("  [Supabase] Creating client instance...")
        client = create_client(url, key)
        _log("  [Supabase] Client initialized successfully")
        return client
    except Exception as ex:
        _log(f"  [Supabase] failed to initialize client: {ex}")
        _log(f"  [Supabase] Error type: {type(ex).__name__}")
        import traceback
        _log(f"  [Supabase] Traceback: {traceback.format_exc()}")
        return None


def ensure_tables_exist(client) -> None:
    """Ensure required tables exist (no-op if they exist)."""
    _log("  [Supabase] Checking if tables exist...")
    try:
        _log("  [Supabase] Testing podcast_transcripts table...")
        client.table("podcast_transcripts").select("id").limit(1).execute()
        _log("  [Supabase] podcast_transcripts table is accessible")
        
        _log("  [Supabase] Testing podcast_posts table...")
        client.table("podcast_posts").select("id").limit(1).execute()
        _log("  [Supabase] podcast_posts table is accessible")
        
        _log("  [Supabase] All tables exist and are accessible")
    except Exception as ex:
        _log(f"  [Supabase] tables may not exist or are not accessible: {ex}")
        _log(f"  [Supabase] Error type: {type(ex).__name__}")
        _log("  [Supabase] Please run the SQL schema to create the required tables")
        import traceback
        _log(f"  [Supabase] Traceback: {traceback.format_exc()}")


def load_processed_guids_from_supabase(client, table: str = "podcast_transcripts", config_id: Optional[str] = None) -> Set[str]:
    """Load processed episode GUIDs from Supabase for one podcast (or all if config_id is None).
    
    This is useful when state.json doesn't exist (e.g., in GitHub Actions).
    Returns a set of GUIDs that have been processed. If config_id is set, only GUIDs
    for that podcast are returned (requires config_id column on the table).
    """
    try:
        _log(f"  [Supabase] Loading processed episode GUIDs from '{table}' table...")
        # Get all unique GUIDs from transcripts table (excluding chunks)
        # Chunks have guid like "original_guid_chunk_1", so we filter those out
        sel = client.table(table).select("guid, original_guid")
        if config_id:
            try:
                response = sel.eq("config_id", config_id).execute()
            except Exception:
                response = client.table(table).select("guid, original_guid").execute()
        else:
            response = sel.execute()
        
        processed_guids = set()
        for row in response.data:
            guid = row.get("guid", "")
            original_guid = row.get("original_guid", "")
            
            # Use original_guid if available (for chunks), otherwise use guid
            if original_guid and original_guid != guid:
                processed_guids.add(original_guid)
            elif guid:
                # Only add if it's not a chunk (chunks have "_chunk_" in the guid)
                if "_chunk_" not in guid:
                    processed_guids.add(guid)
        
        _log(f"  [Supabase] Found {len(processed_guids)} processed episodes in database")
        return processed_guids
    except Exception as ex:
        _log(f"  [Supabase] Failed to load processed GUIDs: {ex}")
        return set()


def load_processed_guids_and_latest_from_supabase(
    client, table: str = "podcast_transcripts", config_id: Optional[str] = None
) -> Tuple[Set[str], Optional[str]]:
    """Load processed GUIDs and the latest published_at from Supabase.
    Returns (set of GUIDs, latest_published_iso or None). Used to sync local state
    with DB so that if episodes are deleted in Supabase, we re-pull them.
    """
    try:
        _log(f"  [Supabase] Loading processed GUIDs and latest published from '{table}'...")
        sel = client.table(table).select("guid, original_guid, published_at")
        if config_id:
            try:
                response = sel.eq("config_id", config_id).execute()
            except Exception:
                response = client.table(table).select("guid, original_guid, published_at").execute()
        else:
            response = sel.execute()

        processed_guids = set()
        latest_iso: Optional[str] = None
        for row in response.data:
            raw_guid = (row.get("guid") or "").strip()
            original = (row.get("original_guid") or "").strip()
            if "_chunk_" in raw_guid:
                if original:
                    processed_guids.add(original)
            else:
                if raw_guid:
                    processed_guids.add(raw_guid)
            pub = row.get("published_at")
            if pub:
                pub_str = pub if isinstance(pub, str) else (pub.isoformat() if hasattr(pub, "isoformat") else str(pub))
                if pub_str and (latest_iso is None or pub_str > latest_iso):
                    latest_iso = pub_str

        _log(f"  [Supabase] Found {len(processed_guids)} processed episodes, latest published: {latest_iso or 'None'}")
        return processed_guids, latest_iso
    except Exception as ex:
        _log(f"  [Supabase] Failed to load state from Supabase: {ex}")
        return set(), None


def _chunk_content(content: str, max_size: int = 20_000_000) -> list[str]:
    """Split content into chunks that fit within size limits."""
    if len(content.encode('utf-8')) <= max_size:
        return [content]
    
    chunks = []
    current_chunk = ""
    
    # Split by sentences to avoid breaking mid-word
    sentences = content.split('. ')
    
    for sentence in sentences:
        test_chunk = current_chunk + sentence + '. '
        
        if len(test_chunk.encode('utf-8')) > max_size:
            if current_chunk:
                chunks.append(current_chunk.rstrip())
                current_chunk = sentence + '. '
            else:
                # Single sentence is too large, split by words
                words = sentence.split(' ')
                for word in words:
                    test_word = current_chunk + word + ' '
                    if len(test_word.encode('utf-8')) > max_size:
                        if current_chunk:
                            chunks.append(current_chunk.rstrip())
                            current_chunk = word + ' '
                        else:
                            # Single word is too large, force split
                            chunks.append(word[:max_size//2])
                            current_chunk = word[max_size//2:] + ' '
                    else:
                        current_chunk = test_word
        else:
            current_chunk = test_chunk
    
    if current_chunk:
        chunks.append(current_chunk.rstrip())
    
    return chunks


def store_transcript(client, table: str, guid: str, title: str, published_at: Optional[datetime], content: str, config_id: Optional[str] = None) -> bool:
    """Store transcript content directly in Supabase table. Returns True on success."""
    try:
        _log(f"  [Supabase] Preparing to store transcript for '{title}'")
        _log(f"  [Supabase] GUID: {guid}")
        _log(f"  [Supabase] Published: {published_at.isoformat() if published_at else 'None'}")
        _log(f"  [Supabase] Content length: {len(content)} characters")
        
        # Check if content needs chunking
        MAX_CONTENT_SIZE = 20_000_000  # 20MB to be safe
        content_bytes = len(content.encode('utf-8'))
        
        if content_bytes > MAX_CONTENT_SIZE:
            _log(f"  [Supabase] Content too large ({content_bytes} bytes), splitting into chunks")
            chunks = _chunk_content(content, MAX_CONTENT_SIZE)
            _log(f"  [Supabase] Split into {len(chunks)} chunks")
            
            # Store each chunk with a chunk identifier
            for i, chunk in enumerate(chunks):
                chunk_guid = f"{guid}_chunk_{i+1}"
                row = {
                    "guid": chunk_guid,
                    "title": f"{title} (Part {i+1}/{len(chunks)})",
                    "published_at": published_at.isoformat() if published_at else None,
                    "transcript_content": chunk,
                    "chunk_index": i + 1,
                    "total_chunks": len(chunks),
                    "original_guid": guid,
                }
                
                _log(f"  [Supabase] Storing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
                resp = client.table(table).upsert(row, on_conflict="guid").execute()
                
                if not (getattr(resp, "data", None) is not None or getattr(resp, "status_code", 200) in (200, 201)):
                    _log(f"  [Supabase] Failed to store chunk {i+1}")
                    return False
            
            _log(f"  [Supabase] Successfully stored {len(chunks)} chunks for '{title}'")
            return True
        else:
            # Store as single record
            row = {
                "guid": guid,
                "title": title,
                "published_at": published_at.isoformat() if published_at else None,
                "transcript_content": content,
                "chunk_index": 1,
                "total_chunks": 1,
                "original_guid": guid,
                **({"config_id": config_id} if config_id else {}),
            }
            
            _log(f"  [Supabase] Sending upsert request to table '{table}'")
            resp = client.table(table).upsert(row, on_conflict="guid").execute()
            
            _log(f"  [Supabase] Response status: {getattr(resp, 'status_code', 'Unknown')}")
            _log(f"  [Supabase] Response data: {getattr(resp, 'data', 'No data')}")
            
            if getattr(resp, "data", None) is not None or getattr(resp, "status_code", 200) in (200, 201):
                _log(f"  [Supabase] Successfully stored transcript for '{title}'")
                return True
            else:
                _log(f"  [Supabase] Failed to store transcript - invalid response")
                return False
    except Exception as ex:
        _log(f"  [Supabase] transcript storage failed: {ex}")
        _log(f"  [Supabase] Error type: {type(ex).__name__}")
        import traceback
        _log(f"  [Supabase] Traceback: {traceback.format_exc()}")
    return False


def store_posts(client, table: str, guid: str, title: str, published_at: Optional[datetime], content: str, post_type: str = "linkedin") -> bool:
    """Store posts content directly in Supabase table. Returns True on success."""
    try:
        _log(f"  [Supabase] Preparing to store posts for '{title}'")
        _log(f"  [Supabase] GUID: {guid}")
        _log(f"  [Supabase] Published: {published_at if published_at else 'None'}")
        _log(f"  [Supabase] Post Type: {post_type}")
        _log(f"  [Supabase] Content length: {len(content)} characters")
        
        # Check if content is too large (Supabase limit is ~26MB)
        MAX_CONTENT_SIZE = 25_000_000  # 25MB to be safe
        if len(content.encode('utf-8')) > MAX_CONTENT_SIZE:
            _log(f"  [Supabase] Content too large ({len(content.encode('utf-8'))} bytes), truncating to {MAX_CONTENT_SIZE} bytes")
            # Truncate content to fit within limits
            content = content[:MAX_CONTENT_SIZE]
            _log(f"  [Supabase] Truncated content length: {len(content)} characters")
        
        # Handle published_at - it might be a string or datetime object
        if published_at:
            if isinstance(published_at, str):
                published_at_value = published_at
            else:
                published_at_value = published_at.isoformat()
        else:
            published_at_value = None
            
        # Don't specify ID - let Supabase auto-generate it
        row = {
            "guid": guid,   # Original transcript GUID for linking
            "title": title,
            "published_at": published_at_value,
            "posts_content": content,
            "post_type": post_type,
            "created_at": datetime.now().isoformat(),  # Timestamp when post was created
        }
        
        _log(f"  [Supabase] Sending upsert request to table '{table}'")
        _log(f"  [Supabase] Row data: {row}")
        
        # Use upsert to handle duplicates (update if exists, insert if new)
        try:
            resp = client.table(table).upsert(row, on_conflict="guid").execute()
            _log(f"  [Supabase] Upsert successful")
            _log(f"  [Supabase] Response data: {getattr(resp, 'data', 'No data')}")
            _log(f"  [Supabase] Successfully stored posts for '{title}'")
            return True
        except Exception as upsert_error:
            _log(f"  [Supabase] Upsert failed: {upsert_error}")
            return False
    except Exception as ex:
        _log(f"  [Supabase] posts storage failed: {ex}")
        _log(f"  [Supabase] Error type: {type(ex).__name__}")
        import traceback
        _log(f"  [Supabase] Traceback: {traceback.format_exc()}")
    return False


def upsert_row(client, table: str, row: Dict[str, Any]) -> bool:
    """Upsert a row into a Supabase table. Returns True on success."""
    try:
        # Attempt upsert; if not supported, fall back to insert
        resp = client.table(table).upsert(row, on_conflict="guid").execute()
        if getattr(resp, "data", None) is not None or getattr(resp, "status_code", 200) in (200, 201):
            _log(f"  [Supabase] upserted into '{table}'")
            return True
    except Exception:
        try:
            resp = client.table(table).insert(row).execute()
            if getattr(resp, "data", None) is not None or getattr(resp, "status_code", 200) in (200, 201):
                _log(f"  [Supabase] inserted into '{table}'")
                return True
        except Exception as ex:
            _log(f"  [Supabase] table write failed for '{table}': {ex}")
    return False
