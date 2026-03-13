"""
FastAPI backend for Podcast AI Studio.
Run: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

Optional: set PULL_LATEST_ON_STARTUP=1 to pull newest episodes for all podcasts when the server starts.
"""
import os
import sys
import subprocess
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

scheduler = BackgroundScheduler()


def run_pull_script():
    """Run the pull_all_new script from inside the web process."""
    try:
        subprocess.run(
            [sys.executable, str(ROOT / "backend" / "scripts" / "pull_all_new.py")],
            cwd=str(ROOT),
            env=os.environ,
            timeout=60 * 60,
        )
    except Exception as e:
        print(f"Background pull_all_new.py failed: {e}")

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
    allow_origins=["*"],      # allow any origin
    allow_credentials=False,  # must be False with "*"
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
    """Startup hook: immediate pull, plus 6h scheduler."""
    max_per = os.getenv("PULL_LATEST_MAX_PER_PODCAST", "5").strip() or "5"
    if not max_per.isdigit():
        max_per = "5"
    print(
        "Startup: pulling newest episodes for all podcasts in background "
        f"(max {max_per} per podcast)."
    )
    try:
        subprocess.run(
            [sys.executable, str(ROOT / "backend" / "scripts" / "pull_all_new.py"), "--max-per-podcast", max_per],
            cwd=str(ROOT),
            env=os.environ,
            timeout=60 * 60,
        )
    except Exception as e:
        print(f"Initial pull_all_new.py on startup failed: {e}")

    if not scheduler.running:
        scheduler.start()
        scheduler.add_job(run_pull_script, "interval", hours=6)
        print("APScheduler started: pull_all_new.py scheduled every 6 hours.")


@app.on_event("shutdown")
def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
