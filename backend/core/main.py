from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import List

from .config import load_config
from .apple import extract_show_id_from_apple_url, lookup_feed_url_via_itunes, parse_feed_entries, fetch_feed_xml, sort_episodes, extract_episode_id_from_apple_url, lookup_episode_release_and_show_id, lookup_episode_release_by_show_and_episode
from .transcripts import get_transcript_text
from .posts import generate_linkedin_posts
from .storage import StateStore, build_supabase_client, ensure_tables_exist, store_transcript, store_posts, load_processed_guids_and_latest_from_supabase
from .config_manager import get_user_config


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("._") or "episode"


def _find_episodes_to_process(episodes_sorted: List, starting_dt, state: StateStore, max_episodes: int, min_date=None) -> List:
    """Find episodes to process: only those NEWER than the latest one already pulled.
    We never pull older episodes (e.g. 25 Feb) once we have a newer one (e.g. 12 March).
    """
    episodes_to_process = []

    # Cutoff: only consider episodes with published date STRICTLY after this.
    # Prefer "latest we already pulled" so we only ever add new ones after the last.
    cutoff = state.get_latest_published()
    if cutoff is None and starting_dt is not None:
        cutoff = starting_dt
        print(f"🔍 First run: using episode URL date as cutoff {cutoff.isoformat()}")
    elif cutoff is not None:
        print(f"🔍 Latest already pulled: {cutoff.isoformat()}; only episodes newer than that will be considered.")

    if cutoff is not None:
        # Episodes newer than or equal to cutoff; already-pulled ones are skipped by GUID below
        candidates = [e for e in episodes_sorted if e.published and e.published >= cutoff]
        if min_date is not None:
            candidates = [e for e in candidates if e.published >= min_date]
        print(f"📊 Found {len(candidates)} episode(s) newer than cutoff")
    else:
        # First run, no state and no URL date: consider all (newest first)
        candidates = episodes_sorted
        if min_date is not None:
            print(f"🔍 Looking for unprocessed episodes from {min_date.date().isoformat()} onwards...")
        else:
            print(f"🔍 Looking for unprocessed episodes (no previous run)...")

    for e in candidates:
        if state.is_processed(e.guid):
            continue
        if min_date is not None and (not e.published or e.published < min_date):
            continue
        episodes_to_process.append(e)
        if max_episodes > 0 and len(episodes_to_process) >= max_episodes:
            break

    if not episodes_to_process:
        print("ℹ️ No new episodes to process.")
    else:
        print(f"📋 Selected {len(episodes_to_process)} episode(s) to process (newest only, after last pulled):")
        for i, e in enumerate(episodes_to_process):
            print(f"  {i+1}. {e.title} ({e.published.isoformat() if e.published else 'No date'})")

    return episodes_to_process


def run() -> None:
    cfg = load_config()

    # Initialize Supabase first to get user configuration
    supabase_client = None
    print(f"🔧 Supabase: Checking configuration...")
    print(f"🔧 Supabase: URL configured: {'Yes' if cfg.supabase_url else 'No'}")
    print(f"🔧 Supabase: Key configured: {'Yes' if cfg.supabase_key else 'No'}")
    print(f"🔧 Supabase: Enabled: {cfg.supabase_enabled}")

    if getattr(cfg, "supabase_enabled", False):
        key_src = "SERVICE_ROLE" if (os.getenv("SUPABASE_SERVICE_ROLE") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")) else ("ANON" if os.getenv("SUPABASE_ANON_KEY") else "UNKNOWN")
        print(f"✅ Supabase: enabled in config (key={key_src})")
        supabase_client = build_supabase_client(cfg.supabase_url, cfg.supabase_key)
        if supabase_client is not None:
            ensure_tables_exist(supabase_client)
        else:
            print("  ❌ Supabase: client not initialized; uploads will be skipped")
    else:
        print("❌ Supabase: not configured; set SUPABASE_URL and key in .env to enable uploads")

    # Load user configuration from Supabase (optionally for a specific podcast when run by cron)
    config_id = os.getenv("PODCAST_CONFIG_ID")  # e.g. "apple", "second_podcast"
    user_config = {}
    if supabase_client:
        user_config = get_user_config(supabase_client, config_id=config_id) if config_id else get_user_config(supabase_client)
        if user_config:
            print(f"📋 Using user configuration from Supabase")
        else:
            print(f"⚠️ No user configuration found in Supabase, using environment variables")

    # Determine configuration values (env override for this run, then Supabase, then config)
    starting_show_id = (os.getenv("SHOW_ID") or "").strip() or user_config.get('show_id') or cfg.show_id
    apple_episode_url = (os.getenv("APPLE_EPISODE_URL") or "").strip() or user_config.get('apple_episode_url') or cfg.apple_episode_url
    env_max = os.getenv("MAX_EPISODES_PER_RUN", "").strip()
    if env_max and env_max.isdigit():
        max_episodes = int(env_max)
    else:
        max_episodes = user_config.get('max_episodes_per_run') or cfg.max_episodes_per_run

    print(f"📋 Configuration: Show ID={starting_show_id}, Max Episodes={max_episodes}")

    # If APPLE_EPISODE_URL is provided, set starting baseline from that episode's release date
    starting_dt = None
    if apple_episode_url:
        print(f"🔍 Parsing Apple episode URL: {apple_episode_url}")
        show_id_from_url = extract_show_id_from_apple_url(apple_episode_url)
        ep_id = extract_episode_id_from_apple_url(apple_episode_url)
        print(f"📋 Extracted show ID: {show_id_from_url}, episode ID: {ep_id}")
        if ep_id:
            if show_id_from_url:
                print(f"🔍 Looking up episode release date (show + episode)...")
                release_dt = lookup_episode_release_by_show_and_episode(show_id_from_url, ep_id)
                if release_dt is not None:
                    print(f"✅ Found release date: {release_dt}")
                    starting_show_id = starting_show_id or show_id_from_url
                    starting_dt = release_dt
                else:
                    print(f"🔄 Episode not in show list, trying legacy lookup...")
            if starting_dt is None:
                info = lookup_episode_release_and_show_id(ep_id)
                if info:
                    sid, release_dt = info
                    print(f"✅ Found episode info - Show ID: {sid}, Release Date: {release_dt}")
                    starting_show_id = starting_show_id or sid
                    starting_dt = release_dt
            if starting_dt is None:
                if show_id_from_url:
                    starting_show_id = starting_show_id or show_id_from_url
                print(f"🔄 Will use fallback logic to find unprocessed episodes")
        else:
            if show_id_from_url:
                starting_show_id = starting_show_id or show_id_from_url
            print(f"❌ Could not extract episode ID from URL: {apple_episode_url}")
            print(f"🔄 Will use fallback logic to find unprocessed episodes")

    if not starting_show_id:
        raise RuntimeError("SHOW_ID not found. Set SHOW_ID or provide APPLE_EPISODE_URL with an id.")

    # Resolve feed: env, then user_config (feed_url / rss_feed_url), then iTunes lookup only if show_id is numeric
    feed_url = (os.getenv("FEED_URL") or os.getenv("RSS_FEED_URL") or "").strip()
    if not feed_url and user_config:
        feed_url = (user_config.get("feed_url") or user_config.get("rss_feed_url") or "").strip()
    if not feed_url and str(starting_show_id).isdigit():
        feed_url = lookup_feed_url_via_itunes(starting_show_id)
    if not feed_url:
        if not str(starting_show_id).isdigit():
            raise RuntimeError(
                f"SHOW_ID '{starting_show_id}' is not a numeric Apple Podcast ID; "
                "set FEED_URL in env or add feed_url to user_config for this podcast."
            )
        raise RuntimeError("Could not resolve RSS feed URL. Set FEED_URL in env or fix iTunes lookup.")

    episodes = parse_feed_entries(feed_url)
    if not episodes:
        print("No episodes found in feed.")
        return

    # Fetch feed XML once for transcript tags
    feed_xml = fetch_feed_xml(feed_url)

    # Per-podcast state and table
    _state_files = {
        "second_podcast": "state_second_podcast.json",
        "twiml": "state_twiml.json",
        "practical_ai": "state_practical_ai.json",
        "a16z": "state_a16z.json",
        "cognitive_rev": "state_cognitive_rev.json",
        "hard_fork": "state_hard_fork.json",
        "lex_fridman": "state_lex_fridman.json",
        "dwarkesh": "state_dwarkesh.json",
        "nvidia_ai": "state_nvidia_ai.json",
    }
    _transcript_tables = {
        "second_podcast": cfg.supabase_table_transcripts_second_podcast,
        "twiml": cfg.supabase_table_transcripts_twiml,
        "practical_ai": cfg.supabase_table_transcripts_practical_ai,
        "a16z": cfg.supabase_table_transcripts_a16z,
        "cognitive_rev": cfg.supabase_table_transcripts_cognitive_rev,
        "hard_fork": cfg.supabase_table_transcripts_hard_fork,
        "lex_fridman": cfg.supabase_table_transcripts_lex_fridman,
        "dwarkesh": cfg.supabase_table_transcripts_dwarkesh,
        "nvidia_ai": cfg.supabase_table_transcripts_nvidia_ai,
    }
    state_file = cfg.data_dir / (_state_files.get(config_id, "state.json"))
    transcripts_table = _transcript_tables.get(config_id, cfg.supabase_table_transcripts)
    state = StateStore(state_file)

    # Always sync state from Supabase when available so local state matches DB
    # (e.g. if you delete an episode in Supabase, we re-pull it on next run)
    if supabase_client is not None:
        supabase_guids, supabase_latest_iso = load_processed_guids_and_latest_from_supabase(
            supabase_client, transcripts_table, config_id=None
        )
        state.processed_guids = supabase_guids
        state.latest_published_iso = supabase_latest_iso
        state._save()
        if supabase_guids:
            print(f"✅ Synced state from Supabase: {len(supabase_guids)} processed episodes, latest: {supabase_latest_iso or 'None'}")
        else:
            print("ℹ️ No processed episodes in Supabase for this podcast, starting fresh")

    # Process newest first
    episodes_sorted = sort_episodes(episodes)

    # If we have processed GUIDs but no latest_published (e.g. after Supabase sync), derive it from the feed
    # so we only pull episodes newer than the last one we have
    if state.processed_guids and state.get_latest_published() is None:
        max_pub = None
        for e in episodes_sorted:
            if e.guid in state.processed_guids and e.published:
                if max_pub is None or e.published > max_pub:
                    max_pub = e.published
        if max_pub is not None:
            state.latest_published_iso = max_pub.isoformat()
            state._save()
            print(f"📅 Derived latest pulled date from feed: {max_pub.isoformat()}")

    # Optional: only consider episodes on or after this date (set MIN_EPISODE_DATE=2025-11-22 in env to restrict)
    min_date = None
    min_date_str = (os.getenv("MIN_EPISODE_DATE") or "").strip()
    if min_date_str:
        try:
            min_date = datetime.fromisoformat(min_date_str.replace("Z", "+00:00"))
            print(f"📅 Using minimum episode date: {min_date.date().isoformat()}")
        except ValueError:
            pass
    episodes_to_process = _find_episodes_to_process(episodes_sorted, starting_dt, state, max_episodes, min_date)

    if not episodes_to_process:
        print("No new episodes to process.")
        return

    processed_count = 0
    for e in episodes_to_process:
        print(f"Processing: {e.title}")

        try:
            transcript_text = get_transcript_text(feed_xml, e, cfg.openai_api_key)
        except Exception as ex:
            print(f"  Failed to get transcript: {ex}")
            continue

        if not transcript_text or not transcript_text.strip():
            print("  ⚠️ Transcript text is empty; skipping Supabase storage and state update for this episode.")
            continue

        # Save transcript using full episode title
        base_name = _sanitize_filename(e.title)
        transcript_path = cfg.transcripts_dir / f"{base_name}.txt"
        transcript_path.write_text(transcript_text, encoding="utf-8")
        print(f"  Transcript saved: {transcript_path}")

        # Store transcript in Supabase table (second_podcast uses latent_space_transcripts)
        if supabase_client is not None:
            print(f"  📤 Supabase: Attempting to store transcript for '{e.title}'")
            success = store_transcript(
                supabase_client,
                transcripts_table,
                e.guid,
                e.title,
                e.published,
                transcript_text,
                config_id=None,
            )
            if success:
                print(f"  ✅ Supabase: Transcript storage completed successfully")
            else:
                print(f"  ❌ Supabase: Transcript storage failed")
        else:
            print(f"  ⏭️ Supabase: Skipping transcript storage (client not available)")

        # Generate posts if OpenAI configured
        if cfg.openai_api_key:
            try:
                posts_list = generate_linkedin_posts(cfg.openai_api_key, transcript_text, e.title)
                if posts_list:
                    posts_path = cfg.posts_dir / f"{base_name}.md"
                    posts_content = "\n\n---\n\n".join(posts_list)
                    posts_path.write_text(posts_content, encoding="utf-8")
                    print(f"  LinkedIn drafts saved: {posts_path}")
                    if supabase_client is not None:
                        print(f"  📤 Supabase: Attempting to store posts for '{e.title}'")
                        success = store_posts(
                            supabase_client,
                            cfg.supabase_table_posts,
                            e.guid,
                            e.title,
                            e.published,
                            posts_content
                        )
                        if success:
                            print(f"  ✅ Supabase: Posts storage completed successfully")
                        else:
                            print(f"  ❌ Supabase: Posts storage failed")
                    else:
                        print(f"  ⏭️ Supabase: Skipping posts storage (client not available)")
            except Exception as ex:
                print(f"  Failed to generate posts: {ex}")
        else:
            print("  OPENAI_API_KEY not set; skipping LinkedIn draft generation.")

        state.mark_processed(e.guid, e.published)
        processed_count += 1

    print(f"Processed {processed_count} new episode(s).")


if __name__ == "__main__":
    run()
