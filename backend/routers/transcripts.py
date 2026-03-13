import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from postgrest.exceptions import APIError

from backend.config import get_supabase_credentials
from backend.routers.auth import require_auth

router = APIRouter()

TRANSCRIPTS_TABLE_SECOND = os.getenv("SUPABASE_TABLE_TRANSCRIPTS_SECOND_PODCAST", "latent_space_transcripts")
TRANSCRIPTS_TABLE_TWIML = os.getenv("SUPABASE_TABLE_TRANSCRIPTS_TWIML", "twiml_transcripts")
TRANSCRIPTS_TABLE_PRACTICAL_AI = os.getenv("SUPABASE_TABLE_TRANSCRIPTS_PRACTICAL_AI", "practical_ai_transcripts")
TRANSCRIPTS_TABLE_A16Z = os.getenv("SUPABASE_TABLE_TRANSCRIPTS_A16Z", "a16z_transcripts")
TRANSCRIPTS_TABLE_COGNITIVE_REV = os.getenv("SUPABASE_TABLE_TRANSCRIPTS_COGNITIVE_REV", "cognitive_revolution_transcripts")
TRANSCRIPTS_TABLE_HARD_FORK = os.getenv("SUPABASE_TABLE_TRANSCRIPTS_HARD_FORK", "hard_fork_transcripts")
TRANSCRIPTS_TABLE_LEX_FRIDMAN = os.getenv("SUPABASE_TABLE_TRANSCRIPTS_LEX_FRIDMAN", "lex_fridman_transcripts")
TRANSCRIPTS_TABLE_DWARKESH = os.getenv("SUPABASE_TABLE_TRANSCRIPTS_DWARKESH", "dwarkesh_transcripts")
TRANSCRIPTS_TABLE_NVIDIA_AI = os.getenv("SUPABASE_TABLE_TRANSCRIPTS_NVIDIA_AI", "nvidia_ai_transcripts")


def _load_transcripts(config_id: Optional[str] = None):
    url, key = get_supabase_credentials()
    if not url or not key:
        return []
    from backend.core.storage import build_supabase_client
    client = build_supabase_client(url, key)
    if not client:
        return []

    if config_id == "second_podcast":
        table = client.table(TRANSCRIPTS_TABLE_SECOND)
        try:
            result = table.select("*").order("created_at", desc=True).execute()
        except APIError:
            return []
    elif config_id == "twiml":
        table = client.table(TRANSCRIPTS_TABLE_TWIML)
        try:
            result = table.select("*").order("created_at", desc=True).execute()
        except APIError:
            return []
    elif config_id == "practical_ai":
        table = client.table(TRANSCRIPTS_TABLE_PRACTICAL_AI)
        try:
            result = table.select("*").order("created_at", desc=True).execute()
        except APIError:
            return []
    elif config_id == "a16z":
        table = client.table(TRANSCRIPTS_TABLE_A16Z)
        try:
            result = table.select("*").order("created_at", desc=True).execute()
        except APIError:
            return []
    elif config_id == "cognitive_rev":
        table = client.table(TRANSCRIPTS_TABLE_COGNITIVE_REV)
        try:
            result = table.select("*").order("created_at", desc=True).execute()
        except APIError:
            return []
    elif config_id == "hard_fork":
        table = client.table(TRANSCRIPTS_TABLE_HARD_FORK)
        try:
            result = table.select("*").order("created_at", desc=True).execute()
        except APIError:
            return []
    elif config_id == "lex_fridman":
        table = client.table(TRANSCRIPTS_TABLE_LEX_FRIDMAN)
        try:
            result = table.select("*").order("created_at", desc=True).execute()
        except APIError:
            return []
    elif config_id == "dwarkesh":
        table = client.table(TRANSCRIPTS_TABLE_DWARKESH)
        try:
            result = table.select("*").order("created_at", desc=True).execute()
        except APIError:
            return []
    elif config_id == "nvidia_ai":
        table = client.table(TRANSCRIPTS_TABLE_NVIDIA_AI)
        try:
            result = table.select("*").order("created_at", desc=True).execute()
        except APIError:
            return []
    else:
        table = client.table("podcast_transcripts")
        try:
            if config_id:
                result = table.select("*").eq("config_id", config_id).order("created_at", desc=True).execute()
            else:
                result = table.select("*").order("created_at", desc=True).execute()
        except APIError:
            result = table.select("*").order("created_at", desc=True).execute()
    if not result.data:
        return []
    grouped = {}
    for record in result.data:
        guid = record.get("original_guid") or record.get("guid")
        if guid not in grouped:
            grouped[guid] = {
                "guid": guid,
                "title": record["title"],
                "published_at": record.get("published_at"),
                "created_at": record.get("created_at"),
                "transcript_content": "",
                "chunks": [],
            }
        grouped[guid]["chunks"].append({
            "chunk_index": record.get("chunk_index", 1),
            "content": record.get("transcript_content", ""),
        })
    final = []
    for guid, t in grouped.items():
        t["chunks"].sort(key=lambda x: x["chunk_index"])
        t["transcript_content"] = "".join(c["content"] for c in t["chunks"])
        del t["chunks"]
        final.append(t)
    def sort_key(item):
        s = item.get("published_at") or item.get("created_at") or ""
        if not s:
            return datetime.min
        try:
            if "T" in s:
                s = s.replace("Z", "+00:00")
            return datetime.fromisoformat(s)
        except Exception:
            return datetime.min
    final.sort(key=sort_key, reverse=True)
    return final
@router.get("")
def list_transcripts(
    config_id: Optional[str] = Query(None),
    _: str = Depends(require_auth),
):
    """List all transcripts (grouped by guid) for a given config_id (podcast) if provided."""
    return _load_transcripts(config_id=config_id)
