import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from backend.config import get_supabase_credentials, get_openai_key, PROJECT_ROOT
from backend.routers.auth import require_auth

router = APIRouter()

# Store last run output per config_id for GET (optional)
_last_run: dict = {"output": "", "success": False, "config_id": None}


class PullBody(BaseModel):
    config_id: str  # apple | second_podcast | twiml
    show_id: Optional[str] = None
    apple_episode_url: Optional[str] = None
    run_limit: int = 10  # 0 = unlimited


def _run_pull_sync(config_id: str, show_id: str, url: str, run_limit: int):
    """Run backend.core.main with env. Blocks."""
    env = dict(os.environ)
    env["MAX_EPISODES_PER_RUN"] = "0" if run_limit == 0 else str(run_limit)
    env["PODCAST_CONFIG_ID"] = config_id
    if get_openai_key():
        env["OPENAI_API_KEY"] = get_openai_key()
    url_sup, key_sup = get_supabase_credentials()
    if url_sup:
        env["SUPABASE_URL"] = url_sup
    if key_sup:
        env["SUPABASE_SERVICE_ROLE_KEY"] = key_sup
    if show_id:
        env["SHOW_ID"] = show_id
    if url:
        env["APPLE_EPISODE_URL"] = url
    try:
        result = subprocess.run(
            [sys.executable, "-m", "backend.core.main"],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=60 * 30,
        )
        out = (result.stdout or "") + "\n" + (result.stderr or "")
        _last_run["output"] = out
        _last_run["success"] = result.returncode == 0
        _last_run["config_id"] = config_id
    except Exception as e:
        _last_run["output"] = str(e)
        _last_run["success"] = False
        _last_run["config_id"] = config_id


@router.post("/run")
def run_pull(body: PullBody, background_tasks: BackgroundTasks, _: str = Depends(require_auth)):
    """Trigger pull. Runs in background; use GET /pull/status for output."""
    if body.config_id not in ("apple", "second_podcast", "twiml", "practical_ai", "a16z", "cognitive_rev", "hard_fork", "lex_fridman", "dwarkesh", "nvidia_ai"):
        raise HTTPException(status_code=400, detail="config_id must be one of the known podcasts (including lex_fridman, dwarkesh, nvidia_ai)")
    openai_key = get_openai_key()
    if not openai_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured")
    show_id = (body.show_id or "").strip()
    url = (body.apple_episode_url or "").strip()
    if not show_id and not url:
        # Load from Supabase config
        client = None
        url_sup, key_sup = get_supabase_credentials()
        if url_sup and key_sup:
            from backend.core.storage import build_supabase_client
            from backend.core.config_manager import get_user_config
            client = build_supabase_client(url_sup, key_sup)
            if client:
                cfg = get_user_config(client, config_id=body.config_id)
                show_id = (cfg.get("show_id") or "").strip()
                url = (cfg.get("apple_episode_url") or "").strip()
        if not show_id and not url:
            raise HTTPException(status_code=400, detail="Configure show_id or apple_episode_url first")
    background_tasks.add_task(_run_pull_sync, body.config_id, show_id, url, body.run_limit)
    return {"success": True, "message": "Pull started in background", "config_id": body.config_id}


def _run_both_sync():
    """Run pull for apple then second_podcast in sequence. Blocks."""
    env_base = dict(os.environ)
    if get_openai_key():
        env_base["OPENAI_API_KEY"] = get_openai_key()
    url_sup, key_sup = get_supabase_credentials()
    if url_sup:
        env_base["SUPABASE_URL"] = url_sup
    if key_sup:
        env_base["SUPABASE_SERVICE_ROLE_KEY"] = key_sup
    out_parts = []
    for cid in ("apple", "second_podcast", "twiml", "practical_ai", "a16z", "cognitive_rev", "hard_fork", "lex_fridman", "dwarkesh", "nvidia_ai"):
        env = dict(env_base)
        env["PODCAST_CONFIG_ID"] = cid
        try:
            result = subprocess.run(
                [sys.executable, "-m", "backend.core.main"],
                cwd=str(PROJECT_ROOT),
                env=env,
                capture_output=True,
                text=True,
                timeout=60 * 30,
            )
            out_parts.append(f"=== {cid} ===\n{(result.stdout or '')}\n{(result.stderr or '')}")
            if result.returncode != 0:
                _last_run["output"] = "\n".join(out_parts)
                _last_run["success"] = False
                _last_run["config_id"] = "run_all"
                return
        except Exception as e:
            _last_run["output"] = "\n".join(out_parts) + "\n" + str(e)
            _last_run["success"] = False
            _last_run["config_id"] = "run_all"
            return
    _last_run["output"] = "\n".join(out_parts)
    _last_run["success"] = True
    _last_run["config_id"] = "run_all"


@router.post("/run-all")
def run_pull_all(background_tasks: BackgroundTasks, _: str = Depends(require_auth)):
    """Run pull for both podcasts (apple then second_podcast) in sequence. Runs in background."""
    if not get_openai_key():
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured")
    background_tasks.add_task(_run_both_sync)
    return {"success": True, "message": "Run all podcasts started in background", "config_id": "run_all"}


@router.get("/status")
def pull_status(_: str = Depends(require_auth)):
    """Last run output (from any config_id or run_all)."""
    return {
        "output": _last_run.get("output", ""),
        "success": _last_run.get("success", False),
        "config_id": _last_run.get("config_id"),
    }
