"""
FastAPI backend for Podcast AI Studio.
Run: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

Optional: set PULL_LATEST_ON_STARTUP=1 to pull newest episodes for all podcasts when the server starts.
"""
import os
import sys
import subprocess
from pathlib import Path

# Load .env from project root
ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

# Ensure project root is on path (for backend.core and backend.routers)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import auth, config, pull, transcripts, posts, health

app = FastAPI(
    title="Podcast AI Studio API",
    description="API for podcast config, pull latest episodes, and transcripts",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "https://podcast-ai-studio-jjlp.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(pull.router, prefix="/api/pull", tags=["pull"])
app.include_router(transcripts.router, prefix="/api/transcripts", tags=["transcripts"])
app.include_router(posts.router, prefix="/api/posts", tags=["posts"])


@app.on_event("startup")
def startup_pull_latest():
    """If PULL_LATEST_ON_STARTUP=1, pull newest episodes for all podcasts in the background."""
    if os.getenv("PULL_LATEST_ON_STARTUP", "").strip() != "1":
        return
    max_per = os.getenv("PULL_LATEST_MAX_PER_PODCAST", "5").strip() or "5"
    if not max_per.isdigit():
        max_per = "5"
    print("PULL_LATEST_ON_STARTUP=1: pulling newest episodes for all podcasts in background (max %s per podcast)." % max_per)

    def run():
        try:
            subprocess.run(
                [sys.executable, str(ROOT / "backend" / "scripts" / "pull_all_new.py"), "--max-per-podcast", max_per],
                cwd=str(ROOT),
                env=os.environ,
                timeout=60 * 60,
            )
        except Exception:
            pass

    import threading
    t = threading.Thread(target=run, daemon=True)
    t.start()
