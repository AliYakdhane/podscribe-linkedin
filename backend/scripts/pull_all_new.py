#!/usr/bin/env python3
"""
Run pull for all podcasts. Each podcast only processes NEW episodes
(not already in state/Supabase). Uses per-podcast config from Supabase.

Usage (from project root):
  python backend/scripts/pull_all_new.py
  python backend/scripts/pull_all_new.py --max-per-podcast 10

Requires: .env with SUPABASE_*, OPENAI_API_KEY. Each podcast must have user_config in Supabase.
"""
import os
import subprocess
import sys
from pathlib import Path

CONFIG_IDS = [
    "apple",
    "second_podcast",
    "twiml",
    "practical_ai",
    "a16z",
    "cognitive_rev",
    "hard_fork",
    "lex_fridman",
    "dwarkesh",
    "nvidia_ai",
]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pull newest episodes for all podcasts.")
    parser.add_argument(
        "--max-per-podcast",
        type=int,
        default=5,
        help="Max new episodes to pull per podcast per run (default: 5)",
    )
    args = parser.parse_args()

    # backend/scripts/pull_all_new.py -> project root = parent of backend
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent

    env_base = dict(os.environ)
    for key in ("SHOW_ID", "APPLE_EPISODE_URL", "FEED_URL", "RSS_FEED_URL"):
        env_base.pop(key, None)

    failed = []
    ok = 0
    for cid in CONFIG_IDS:
        print(f"\n========== {cid} (up to {args.max_per_podcast} new episodes) ==========")
        env = dict(env_base)
        env["PODCAST_CONFIG_ID"] = cid
        env["MAX_EPISODES_PER_RUN"] = str(args.max_per_podcast)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "backend.core.main"],
                cwd=str(project_root),
                env=env,
                timeout=60 * 30,
            )
            if result.returncode != 0:
                failed.append(cid)
                print(f"  [FAIL] {cid} exit code {result.returncode}")
            else:
                ok += 1
                print(f"  [OK] {cid}")
        except subprocess.TimeoutExpired:
            failed.append(cid)
            print(f"  [FAIL] {cid} timed out")
        except Exception as e:
            failed.append(cid)
            print(f"  [FAIL] {cid}: {e}")

    print(f"\nDone: {ok} succeeded, {len(failed)} failed.")
    if failed:
        print(f"Failed: {', '.join(failed)}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
