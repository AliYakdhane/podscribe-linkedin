import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Config:
    openai_api_key: Optional[str]
    assemblyai_api_key: Optional[str]
    apple_episode_url: Optional[str]
    show_id: Optional[str]
    data_dir: Path
    transcripts_dir: Path
    posts_dir: Path
    max_episodes_per_run: int
    # Supabase
    supabase_url: Optional[str]
    supabase_key: Optional[str]
    supabase_bucket: str
    supabase_enabled: bool
    supabase_table_transcripts: str
    supabase_table_posts: str


def load_config() -> Config:
    # Load .env if present
    load_dotenv()

    project_root = Path(__file__).resolve().parents[1]

    data_dir = Path(os.getenv("DATA_DIR", project_root / "data"))
    transcripts_dir = Path(os.getenv("TRANSCRIPTS_DIR", data_dir / "transcripts"))
    posts_dir = Path(os.getenv("POSTS_DIR", data_dir / "posts"))

    # Create directories
    data_dir.mkdir(parents=True, exist_ok=True)
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    posts_dir.mkdir(parents=True, exist_ok=True)

    openai_api_key = os.getenv("OPENAI_API_KEY")
    assemblyai_api_key = os.getenv("ASSEMBLYAI_API_KEY")
    apple_episode_url = os.getenv("APPLE_EPISODE_URL")

    # Derive show_id either from env or from apple URL
    show_id = os.getenv("SHOW_ID")
    if not show_id and apple_episode_url:
        import re
        match = re.search(r"id(\d+)", apple_episode_url)
        if match:
            show_id = match.group(1)

    # Limit processing per run (0 = unlimited)
    env_val = (os.getenv("MAX_EPISODES_PER_RUN", "") or "").strip()
    if env_val == "":
        max_episodes_per_run = 0
    else:
        try:
            max_episodes_per_run = int(env_val)
        except ValueError:
            max_episodes_per_run = 0

    # Supabase configuration (URL + key from env only)
    supabase_url = os.getenv("SUPABASE_URL")
    # Prefer service role for server-side scripts, else fall back to anon
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    supabase_bucket = os.getenv("SUPABASE_BUCKET", "podcasts")
    supabase_enabled = bool((supabase_url or "").strip() and (supabase_key or "").strip())
    supabase_table_transcripts = os.getenv("SUPABASE_TABLE_TRANSCRIPTS", "podcast_transcripts")
    supabase_table_posts = os.getenv("SUPABASE_TABLE_POSTS", "podcast_posts")

    return Config(
        openai_api_key=openai_api_key,
        assemblyai_api_key=assemblyai_api_key,
        apple_episode_url=apple_episode_url,
        show_id=show_id,
        data_dir=Path(data_dir),
        transcripts_dir=Path(transcripts_dir),
        posts_dir=Path(posts_dir),
        max_episodes_per_run=max_episodes_per_run,
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        supabase_bucket=supabase_bucket,
        supabase_enabled=supabase_enabled,
        supabase_table_transcripts=supabase_table_transcripts,
        supabase_table_posts=supabase_table_posts,
    )
