from __future__ import annotations

"""
Utility script to scaffold a new Apple podcast into this project.

Given:
  - a config_id (e.g. "lex_fridman")
  - an Apple Podcasts show URL

It will generate, under scripts/:
  - supabase_<config_id>_transcripts.sql
  - supabase_<config_id>_user_config.sql
  - pull_<config_id>_5.ps1

These match the pattern we already use for other shows.

Usage (from repo root):
  python -m src.register_apple_podcast --config-id lex_fridman \\
      --apple-url https://podcasts.apple.com/us/podcast/lex-fridman-podcast/id1434243584
"""

import argparse
import re
from pathlib import Path

from .apple import extract_show_id_from_apple_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def _sanitize_identifier(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = value.strip("_")
    return value or "podcast"


def generate_files(config_id: str, apple_url: str, max_episodes: int = 5) -> None:
    config_id_safe = _sanitize_identifier(config_id)
    table_name = f"{config_id_safe}_transcripts"

    show_id = extract_show_id_from_apple_url(apple_url)
    if not show_id:
        raise SystemExit(f"Could not extract show_id from Apple URL: {apple_url}")

    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1) transcripts table SQL
    transcripts_sql = f"""-- Run this in the Supabase SQL Editor to create a dedicated table for {config_id_safe} podcast transcripts.

CREATE TABLE IF NOT EXISTS {table_name} (
  id BIGSERIAL PRIMARY KEY,
  guid TEXT NOT NULL UNIQUE,
  title TEXT,
  published_at TIMESTAMPTZ,
  transcript_content TEXT,
  chunk_index INTEGER DEFAULT 1,
  total_chunks INTEGER DEFAULT 1,
  original_guid TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_{table_name}_created_at ON {table_name}(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_{table_name}_original_guid ON {table_name}(original_guid);
CREATE INDEX IF NOT EXISTS idx_{table_name}_chunk_order ON {table_name}(original_guid, chunk_index);

COMMENT ON TABLE {table_name} IS 'Transcripts for {config_id_safe} podcast ({config_id_safe}).';
"""
    (SCRIPTS_DIR / f"supabase_{config_id_safe}_transcripts.sql").write_text(
        transcripts_sql, encoding="utf-8"
    )

    # 2) user_config SQL
    user_config_sql = f"""-- Run this in the Supabase SQL Editor after creating {table_name}.
-- Adds config for {config_id_safe} so the app and pull script can use it.

INSERT INTO user_config (id, show_id, apple_episode_url, max_episodes_per_run, openai_api_key, updated_at)
VALUES (
  '{config_id_safe}',
  '{show_id}',
  '{apple_url}',
  {max_episodes},
  '',
  NOW()
)
ON CONFLICT (id) DO UPDATE SET
  show_id = EXCLUDED.show_id,
  apple_episode_url = EXCLUDED.apple_episode_url,
  max_episodes_per_run = EXCLUDED.max_episodes_per_run,
  updated_at = EXCLUDED.updated_at;
"""
    (SCRIPTS_DIR / f"supabase_{config_id_safe}_user_config.sql").write_text(
        user_config_sql, encoding="utf-8"
    )

    # 3) pull script
    pull_ps1 = f"""# Pull the {max_episodes} latest {config_id_safe} episodes: fetch transcripts and save to {table_name}.
# Run from repo root: .\\scripts\\pull_{config_id_safe}_5.ps1
# Requires: .env with SUPABASE_*, OPENAI_API_KEY.
# Run supabase_{config_id_safe}_transcripts.sql and supabase_{config_id_safe}_user_config.sql first.

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = Split-Path -Parent $scriptDir
$venvPy = Join-Path $project ".venv/Scripts/python.exe"
if (-Not (Test-Path $venvPy)) {{ $venvPy = "python" }}

$env:PODCAST_CONFIG_ID = "{config_id_safe}"
$env:MAX_EPISODES_PER_RUN = "{max_episodes}"
$env:SHOW_ID = "{show_id}"
$env:APPLE_EPISODE_URL = "{apple_url}"
$env:FEED_URL = ""
$env:RSS_FEED_URL = ""

Push-Location $project
try {{
    & $venvPy -m src.main
    exit $LASTEXITCODE
}} finally {{
    Pop-Location
}}
"""
    (SCRIPTS_DIR / f"pull_{config_id_safe}_5.ps1").write_text(
        pull_ps1, encoding="utf-8"
    )

    print(f"✅ Generated scripts for '{config_id_safe}' in {SCRIPTS_DIR}")
    print(f"  - supabase_{config_id_safe}_transcripts.sql")
    print(f"  - supabase_{config_id_safe}_user_config.sql")
    print(f"  - pull_{config_id_safe}_5.ps1")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold a new Apple podcast.")
    parser.add_argument("--config-id", required=True, help="Internal id (e.g. lex_fridman)")
    parser.add_argument(
        "--apple-url",
        required=True,
        help="Apple Podcasts show URL (e.g. https://podcasts.apple.com/.../id1234567890)",
    )
    parser.add_argument(
        "--max-episodes",
        type=int,
        default=5,
        help="How many episodes per pull script run (default: 5)",
    )
    args = parser.parse_args()
    generate_files(args.config_id, args.apple_url, args.max_episodes)


if __name__ == "__main__":
    main()

