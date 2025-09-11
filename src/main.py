from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List

from .config import load_config
from .apple import extract_show_id_from_apple_url, lookup_feed_url_via_itunes, parse_feed_entries, fetch_feed_xml, sort_episodes, extract_episode_id_from_apple_url, lookup_episode_release_and_show_id
from .transcripts import get_transcript_text
from .posts import generate_linkedin_posts
from .storage import StateStore, build_supabase_client, ensure_tables_exist, store_transcript, store_posts


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("._") or "episode"


def _find_episodes_to_process(episodes_sorted: List, starting_dt, state: StateStore, max_episodes: int) -> List:
    """Find episodes to process based on intelligent selection logic."""
    episodes_to_process = []
    
    if starting_dt is not None:
        # If we have a starting date (from Apple episode URL), find episodes between that date and newest
        print(f"🔍 Looking for episodes between {starting_dt.isoformat()} and newest...")
        
        # Find episodes newer than the starting date
        newer_episodes = [e for e in episodes_sorted if e.published and e.published > starting_dt]
        print(f"📊 Found {len(newer_episodes)} episodes newer than the specified episode URL")
        
        if not newer_episodes:
            print("ℹ️ No episodes found newer than the specified episode URL.")
            return []
        
        # Debug: Show which episodes are newer
        print("📋 Episodes newer than specified URL:")
        for i, e in enumerate(newer_episodes[:10]):  # Show first 10
            processed_status = "✅ Processed" if state.is_processed(e.guid) else "❌ Unprocessed"
            print(f"  {i+1}. {e.title} ({e.published.isoformat() if e.published else 'No date'}) - {processed_status}")
        
        # Filter out already processed episodes
        unprocessed_newer = [e for e in newer_episodes if not state.is_processed(e.guid)]
        print(f"📊 Found {len(unprocessed_newer)} unprocessed episodes newer than the specified episode URL")
        
        if not unprocessed_newer:
            print("ℹ️ All episodes newer than the specified episode URL have already been processed.")
            print("🔄 Falling back to newest unprocessed episodes...")
            
            # Fallback: look for any unprocessed episodes (not just newer than the URL)
            for e in episodes_sorted:
                if not state.is_processed(e.guid):
                    episodes_to_process.append(e)
                    if len(episodes_to_process) >= max_episodes:
                        break
            
            if episodes_to_process:
                print(f"📋 Found {len(episodes_to_process)} unprocessed episodes (fallback mode):")
                for i, e in enumerate(episodes_to_process):
                    print(f"  {i+1}. {e.title} ({e.published.isoformat() if e.published else 'No date'})")
            else:
                print("ℹ️ No unprocessed episodes found anywhere.")
            
            return episodes_to_process
        
        # Take up to max_episodes
        episodes_to_process = unprocessed_newer[:max_episodes]
        print(f"📋 Selected {len(episodes_to_process)} episodes to process:")
        for i, e in enumerate(episodes_to_process):
            print(f"  {i+1}. {e.title} ({e.published.isoformat() if e.published else 'No date'})")
        
    else:
        # No starting date - use the old logic (newest episodes)
        print("🔍 Looking for newest unprocessed episodes...")
        
        for e in episodes_sorted:
            if not state.is_processed(e.guid):
                episodes_to_process.append(e)
                if len(episodes_to_process) >= max_episodes:
                    break
        
        if not episodes_to_process:
            print("ℹ️ No new episodes to process.")
        else:
            print(f"📋 Found {len(episodes_to_process)} unprocessed episodes:")
            for i, e in enumerate(episodes_to_process):
                print(f"  {i+1}. {e.title} ({e.published.isoformat() if e.published else 'No date'})")
    
    return episodes_to_process


def run() -> None:
    cfg = load_config()

    # If APPLE_EPISODE_URL is provided, set starting baseline from that episode's release date
    starting_show_id = cfg.show_id
    starting_dt = None
    if cfg.apple_episode_url:
        print(f"🔍 Parsing Apple episode URL: {cfg.apple_episode_url}")
        ep_id = extract_episode_id_from_apple_url(cfg.apple_episode_url)
        print(f"📋 Extracted episode ID: {ep_id}")
        if ep_id:
            print(f"🔍 Looking up episode info from Apple...")
            info = lookup_episode_release_and_show_id(ep_id)
            if info:
                show_id_from_url, release_dt = info
                print(f"✅ Found episode info - Show ID: {show_id_from_url}, Release Date: {release_dt}")
                starting_show_id = starting_show_id or show_id_from_url
                starting_dt = release_dt
            else:
                print(f"❌ Could not lookup episode info from Apple for ID: {ep_id}")
                print(f"🔄 Will use fallback logic to find unprocessed episodes")
        else:
            print(f"❌ Could not extract episode ID from URL: {cfg.apple_episode_url}")
            print(f"🔄 Will use fallback logic to find unprocessed episodes")

    if not starting_show_id:
        raise RuntimeError("SHOW_ID not found. Set SHOW_ID or provide APPLE_EPISODE_URL with an id.")

    feed_url = lookup_feed_url_via_itunes(starting_show_id)
    if not feed_url:
        raise RuntimeError("Could not resolve RSS feed URL from iTunes lookup.")

    episodes = parse_feed_entries(feed_url)
    if not episodes:
        print("No episodes found in feed.")
        return

    # Fetch feed XML once for transcript tags
    feed_xml = fetch_feed_xml(feed_url)

    state = StateStore(cfg.data_dir / "state.json")

    # Initialize Supabase if configured
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

    # Process newest first
    episodes_sorted = sort_episodes(episodes)

    # Use intelligent episode selection
    episodes_to_process = _find_episodes_to_process(episodes_sorted, starting_dt, state, cfg.max_episodes_per_run)

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

        # Save transcript using full episode title
        base_name = _sanitize_filename(e.title)
        transcript_path = cfg.transcripts_dir / f"{base_name}.txt"
        transcript_path.write_text(transcript_text, encoding="utf-8")
        print(f"  Transcript saved: {transcript_path}")

        # Store transcript in Supabase table
        if supabase_client is not None:
            print(f"  📤 Supabase: Attempting to store transcript for '{e.title}'")
            success = store_transcript(
                supabase_client,
                cfg.supabase_table_transcripts,
                e.guid,
                e.title,
                e.published,
                transcript_text
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
                posts = generate_linkedin_posts(cfg.openai_api_key, transcript_text, e.title)
                if posts:
                    posts_path = cfg.posts_dir / f"{base_name}.md"
                    posts_content = "\n\n---\n\n".join(posts)
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
