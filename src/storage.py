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
    print(f"  🔧 Supabase: Initializing client...")
    print(f"  🔧 Supabase: URL provided: {'Yes' if url else 'No'}")
    print(f"  🔧 Supabase: Key provided: {'Yes' if key else 'No'}")
    
    if not url or not key:
        print("  ❌ Supabase: missing SUPABASE_URL or key; skipping uploads")
        return None
    
    print(f"  🔧 Supabase: URL: {url}")
    print(f"  🔧 Supabase: Key: {key[:10]}... (length: {len(key)})")
    
    try:
        print("  🔧 Supabase: Importing supabase client...")
        from supabase import create_client
        print("  ✅ Supabase: Client imported successfully")
    except Exception as ex:
        print(f"  ❌ Supabase: failed to import client: {ex}")
        return None
    
    try:
        print("  🔧 Supabase: Creating client instance...")
        client = create_client(url, key)
        print("  ✅ Supabase: Client initialized successfully")
        return client
    except Exception as ex:
        print(f"  ❌ Supabase: failed to initialize client: {ex}")
        print(f"  ❌ Supabase: Error type: {type(ex).__name__}")
        import traceback
        print(f"  ❌ Supabase: Traceback: {traceback.format_exc()}")
        return None


def ensure_tables_exist(client) -> None:
    """Ensure required tables exist (no-op if they exist)."""
    print("  🔍 Supabase: Checking if tables exist...")
    try:
        print("  🔍 Supabase: Testing podcast_transcripts table...")
        client.table("podcast_transcripts").select("id").limit(1).execute()
        print("  ✅ Supabase: podcast_transcripts table is accessible")
        
        print("  🔍 Supabase: Testing podcast_posts table...")
        client.table("podcast_posts").select("id").limit(1).execute()
        print("  ✅ Supabase: podcast_posts table is accessible")
        
        print("  ✅ Supabase: All tables exist and are accessible")
    except Exception as ex:
        print(f"  ❌ Supabase: tables may not exist or are not accessible: {ex}")
        print(f"  ❌ Supabase: Error type: {type(ex).__name__}")
        print("  💡 Supabase: Please run the SQL schema to create the required tables")
        import traceback
        print(f"  ❌ Supabase: Traceback: {traceback.format_exc()}")


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


def store_transcript(client, table: str, guid: str, title: str, published_at: Optional[datetime], content: str) -> bool:
    """Store transcript content directly in Supabase table. Returns True on success."""
    try:
        print(f"  📤 Supabase: Preparing to store transcript for '{title}'")
        print(f"  📤 Supabase: GUID: {guid}")
        print(f"  📤 Supabase: Published: {published_at.isoformat() if published_at else 'None'}")
        print(f"  📤 Supabase: Content length: {len(content)} characters")
        
        # Check if content needs chunking
        MAX_CONTENT_SIZE = 20_000_000  # 20MB to be safe
        content_bytes = len(content.encode('utf-8'))
        
        if content_bytes > MAX_CONTENT_SIZE:
            print(f"  ⚠️ Supabase: Content too large ({content_bytes} bytes), splitting into chunks")
            chunks = _chunk_content(content, MAX_CONTENT_SIZE)
            print(f"  📤 Supabase: Split into {len(chunks)} chunks")
            
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
                
                print(f"  📤 Supabase: Storing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
                resp = client.table(table).upsert(row, on_conflict="guid").execute()
                
                if not (getattr(resp, "data", None) is not None or getattr(resp, "status_code", 200) in (200, 201)):
                    print(f"  ❌ Supabase: Failed to store chunk {i+1}")
                    return False
            
            print(f"  ✅ Supabase: Successfully stored {len(chunks)} chunks for '{title}'")
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
            }
            
            print(f"  📤 Supabase: Sending upsert request to table '{table}'")
            resp = client.table(table).upsert(row, on_conflict="guid").execute()
            
            print(f"  📤 Supabase: Response status: {getattr(resp, 'status_code', 'Unknown')}")
            print(f"  📤 Supabase: Response data: {getattr(resp, 'data', 'No data')}")
            
            if getattr(resp, "data", None) is not None or getattr(resp, "status_code", 200) in (200, 201):
                print(f"  ✅ Supabase: Successfully stored transcript for '{title}'")
                return True
            else:
                print(f"  ❌ Supabase: Failed to store transcript - invalid response")
                return False
    except Exception as ex:
        print(f"  ❌ Supabase transcript storage failed: {ex}")
        print(f"  ❌ Supabase: Error type: {type(ex).__name__}")
        import traceback
        print(f"  ❌ Supabase: Traceback: {traceback.format_exc()}")
    return False


def store_posts(client, table: str, guid: str, title: str, published_at: Optional[datetime], content: str, post_type: str = "linkedin") -> bool:
    """Store posts content directly in Supabase table. Returns True on success."""
    try:
        print(f"  📤 Supabase: Preparing to store posts for '{title}'")
        print(f"  📤 Supabase: GUID: {guid}")
        print(f"  📤 Supabase: Published: {published_at if published_at else 'None'}")
        print(f"  📤 Supabase: Post Type: {post_type}")
        print(f"  📤 Supabase: Content length: {len(content)} characters")
        
        # Check if content is too large (Supabase limit is ~26MB)
        MAX_CONTENT_SIZE = 25_000_000  # 25MB to be safe
        if len(content.encode('utf-8')) > MAX_CONTENT_SIZE:
            print(f"  ⚠️ Supabase: Content too large ({len(content.encode('utf-8'))} bytes), truncating to {MAX_CONTENT_SIZE} bytes")
            # Truncate content to fit within limits
            content = content[:MAX_CONTENT_SIZE]
            print(f"  📤 Supabase: Truncated content length: {len(content)} characters")
        
        # Handle published_at - it might be a string or datetime object
        if published_at:
            if isinstance(published_at, str):
                published_at_value = published_at
            else:
                published_at_value = published_at.isoformat()
        else:
            published_at_value = None
            
        # Create a unique identifier that combines guid and post_type
        unique_id = f"{guid}_{post_type}"
        
        row = {
            "guid": guid,
            "title": title,
            "published_at": published_at_value,
            "posts_content": content,
            "post_type": post_type,
            "unique_id": unique_id,  # Add unique identifier
        }
        
        print(f"  📤 Supabase: Sending upsert request to table '{table}'")
        print(f"  📤 Supabase: Unique ID: {unique_id}")
        # Use unique_id as the conflict resolution key
        resp = client.table(table).upsert(row, on_conflict="unique_id").execute()
        
        print(f"  📤 Supabase: Response status: {getattr(resp, 'status_code', 'Unknown')}")
        print(f"  📤 Supabase: Response data: {getattr(resp, 'data', 'No data')}")
        
        if getattr(resp, "data", None) is not None or getattr(resp, "status_code", 200) in (200, 201):
            print(f"  ✅ Supabase: Successfully stored posts for '{title}'")
            return True
        else:
            print(f"  ❌ Supabase: Failed to store posts - invalid response")
            return False
    except Exception as ex:
        print(f"  ❌ Supabase posts storage failed: {ex}")
        print(f"  ❌ Supabase: Error type: {type(ex).__name__}")
        import traceback
        print(f"  ❌ Supabase: Traceback: {traceback.format_exc()}")
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
