from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from backend.config import get_supabase_credentials
from backend.routers.auth import require_auth

router = APIRouter()


class ConfigBody(BaseModel):
    show_id: str = ""
    apple_episode_url: str = ""
    max_episodes_per_run: int = 10


def _supabase_client():
    url, key = get_supabase_credentials()
    if not url or not key:
        return None
    from backend.core.storage import build_supabase_client
    return build_supabase_client(url, key)


@router.get("/{config_id}")
def get_config(config_id: str, _: str = Depends(require_auth)):
    """Get podcast config for apple, second_podcast, or twiml. Returns defaults when missing so UI never fails."""
    if config_id not in ("apple", "second_podcast", "twiml", "practical_ai", "a16z", "cognitive_rev", "hard_fork", "lex_fridman", "dwarkesh", "nvidia_ai"):
        raise HTTPException(status_code=400, detail="config_id must be one of the known podcasts (including lex_fridman, dwarkesh, nvidia_ai)")
    client = _supabase_client()
    if not client:
        # Return defaults instead of 503 so Latent Space tab can still show transcripts
        return {
            "show_id": "",
            "apple_episode_url": "",
            "max_episodes_per_run": 10,
        }
    try:
        from backend.core.config_manager import get_user_config
        data = get_user_config(client, config_id=config_id) or {}
    except Exception:
        data = {}
    raw_max = data.get("max_episodes_per_run")
    max_episodes = 10
    if isinstance(raw_max, int) and raw_max >= 0:
        max_episodes = raw_max
    return {
        "show_id": (data.get("show_id") or "").strip(),
        "apple_episode_url": (data.get("apple_episode_url") or "").strip(),
        "max_episodes_per_run": max_episodes,
    }


@router.put("/{config_id}")
def put_config(config_id: str, body: ConfigBody, _: str = Depends(require_auth)):
    """Save podcast config."""
    if config_id not in ("apple", "second_podcast", "twiml", "practical_ai", "a16z", "cognitive_rev", "hard_fork", "lex_fridman", "dwarkesh", "nvidia_ai"):
        raise HTTPException(status_code=400, detail="config_id must be one of the known podcasts (including lex_fridman, dwarkesh, nvidia_ai)")
    client = _supabase_client()
    if not client:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    from backend.core.config_manager import save_user_config
    ok = save_user_config(
        client,
        show_id=body.show_id.strip(),
        apple_episode_url=body.apple_episode_url.strip(),
        max_episodes_per_run=body.max_episodes_per_run,
        openai_api_key="",
        config_id=config_id,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save config")
    return {"success": True}


