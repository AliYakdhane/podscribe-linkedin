#!/usr/bin/env python3
"""
Recovery script to pull all missed episodes since November 22nd, 2024.
This script will process all episodes that were published after November 22nd
and haven't been processed yet.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path (for backend.core)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.core.config import load_config
from backend.core.apple import lookup_feed_url_via_itunes, parse_feed_entries, fetch_feed_xml, sort_episodes
from backend.core.transcripts import get_transcript_text
from backend.core.posts import generate_linkedin_posts
from backend.core.storage import StateStore, build_supabase_client, ensure_tables_exist, store_transcript, store_posts
from backend.core.config_manager import get_user_config
import re


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("._") or "episode"


def main():
    print("=" * 80)
    print("🚨 RECOVERY MODE: Pulling all missed episodes since November 22nd, 2024")
    print("=" * 80)
    
    # Set the cutoff date: November 22nd, 2024
    cutoff_date = datetime(2024, 11, 22)
    print(f"📅 Cutoff date: {cutoff_date.isoformat()}")
    print()
    
    cfg = load_config()
    
    # Initialize Supabase
    supabase_client = None
    if getattr(cfg, "supabase_enabled", False):
        print("🔧 Initializing Supabase...")
        supabase_client = build_supabase_client(cfg.supabase_url, cfg.supabase_key)
        if supabase_client is not None:
            ensure_tables_exist(supabase_client)
            print("✅ Supabase initialized")
        else:
            print("⚠️ Supabase client not available, will use local storage only")
    else:
        print("ℹ️ Supabase not configured, using local storage only")
    
    # Load user configuration from Supabase
    user_config = {}
    if supabase_client:
        user_config = get_user_config(supabase_client)
        if user_config:
            print(f"📋 Using user configuration from Supabase")
        else:
            print(f"⚠️ No user configuration found in Supabase, using environment variables")
    
    # Determine configuration values
    show_id = user_config.get('show_id') or cfg.show_id
    max_episodes = user_config.get('max_episodes_per_run') or cfg.max_episodes_per_run
    
    if not show_id:
        print("❌ ERROR: SHOW_ID not found. Set SHOW_ID in environment or Supabase config.")
        sys.exit(1)
    
    print(f"📋 Configuration: Show ID={show_id}, Max Episodes={max_episodes if max_episodes > 0 else 'Unlimited'}")
    print()
    
    # Get feed URL
    print("🔍 Looking up RSS feed...")
    feed_url = lookup_feed_url_via_itunes(show_id)
    if not feed_url:
        print("❌ ERROR: Could not resolve RSS feed URL from iTunes lookup.")
        sys.exit(1)
    print(f"✅ Found feed URL: {feed_url}")
    print()
    
    # Parse episodes
    print("📥 Fetching episodes from feed...")
    episodes = parse_feed_entries(feed_url)
    if not episodes:
        print("❌ No episodes found in feed.")
        sys.exit(1)
    print(f"✅ Found {len(episodes)} total episodes in feed")
    print()
    
    # Fetch feed XML for transcript tags
    feed_xml = fetch_feed_xml(feed_url)
    
    # Load state
    state = StateStore(cfg.data_dir / "state.json")
    print(f"📊 Current state: {len(state.processed_guids)} episodes already processed")
    if state.latest_published_iso:
        latest = state.get_latest_published()
        print(f"📅 Latest processed episode date: {latest.isoformat() if latest else 'Unknown'}")
    print()
    
    # Sort episodes (newest first)
    episodes_sorted = sort_episodes(episodes)
    
    # Find episodes published after November 22nd that haven't been processed
    print("🔍 Finding missed episodes...")
    missed_episodes = []
    for e in episodes_sorted:
        if e.published and e.published > cutoff_date:
            if not state.is_processed(e.guid):
                missed_episodes.append(e)
    
    print(f"📊 Found {len(missed_episodes)} missed episodes since November 22nd:")
    for i, e in enumerate(missed_episodes[:20], 1):  # Show first 20
        print(f"  {i}. {e.title} ({e.published.isoformat() if e.published else 'No date'})")
    if len(missed_episodes) > 20:
        print(f"  ... and {len(missed_episodes) - 20} more")
    print()
    
    if not missed_episodes:
        print("✅ No missed episodes found! All episodes since November 22nd have been processed.")
        return
    
    # Apply max_episodes limit if set
    if max_episodes > 0 and len(missed_episodes) > max_episodes:
        print(f"⚠️ Limiting to {max_episodes} episodes (MAX_EPISODES_PER_RUN={max_episodes})")
        episodes_to_process = missed_episodes[:max_episodes]
    else:
        episodes_to_process = missed_episodes
    
    print(f"🚀 Processing {len(episodes_to_process)} episode(s)...")
    print()
    
    processed_count = 0
    failed_count = 0
    
    for i, e in enumerate(episodes_to_process, 1):
        print(f"[{i}/{len(episodes_to_process)}] Processing: {e.title}")
        print(f"  📅 Published: {e.published.isoformat() if e.published else 'Unknown'}")
        
        try:
            # Get transcript
            transcript_text = get_transcript_text(feed_xml, e, cfg.openai_api_key)
            print(f"  ✅ Transcript retrieved ({len(transcript_text)} characters)")
            
            # Save transcript locally
            base_name = _sanitize_filename(e.title)
            transcript_path = cfg.transcripts_dir / f"{base_name}.txt"
            transcript_path.write_text(transcript_text, encoding="utf-8")
            print(f"  💾 Transcript saved: {transcript_path}")
            
            # Store transcript in Supabase
            if supabase_client is not None:
                print(f"  📤 Uploading transcript to Supabase...")
                success = store_transcript(
                    supabase_client,
                    cfg.supabase_table_transcripts,
                    e.guid,
                    e.title,
                    e.published,
                    transcript_text,
                    config_id=os.getenv("PODCAST_CONFIG_ID") or "apple",
                )
                if success:
                    print(f"  ✅ Transcript uploaded to Supabase")
                else:
                    print(f"  ⚠️ Failed to upload transcript to Supabase")
            
            # Generate LinkedIn posts
            if cfg.openai_api_key:
                try:
                    posts = generate_linkedin_posts(cfg.openai_api_key, transcript_text, e.title)
                    if posts:
                        posts_path = cfg.posts_dir / f"{base_name}.md"
                        posts_content = "\n\n---\n\n".join(posts)
                        posts_path.write_text(posts_content, encoding="utf-8")
                        print(f"  💾 LinkedIn drafts saved: {posts_path}")
                        
                        # Store posts in Supabase
                        if supabase_client is not None:
                            print(f"  📤 Uploading posts to Supabase...")
                            success = store_posts(
                                supabase_client,
                                cfg.supabase_table_posts,
                                e.guid,
                                e.title,
                                e.published,
                                posts_content
                            )
                            if success:
                                print(f"  ✅ Posts uploaded to Supabase")
                            else:
                                print(f"  ⚠️ Failed to upload posts to Supabase")
                except Exception as ex:
                    print(f"  ❌ Failed to generate posts: {ex}")
            else:
                print("  ⚠️ OPENAI_API_KEY not set; skipping LinkedIn draft generation")
            
            # Mark as processed
            state.mark_processed(e.guid, e.published)
            processed_count += 1
            print(f"  ✅ Episode processed successfully")
            
        except Exception as ex:
            print(f"  ❌ Failed to process episode: {ex}")
            import traceback
            print(f"  📋 Traceback: {traceback.format_exc()}")
            failed_count += 1
        
        print()
    
    print("=" * 80)
    print(f"✅ Recovery complete!")
    print(f"   Processed: {processed_count} episode(s)")
    if failed_count > 0:
        print(f"   Failed: {failed_count} episode(s)")
    print(f"   Remaining: {len(missed_episodes) - len(episodes_to_process)} episode(s) not processed (due to limit)")
    print("=" * 80)
    
    if len(missed_episodes) > len(episodes_to_process):
        print()
        print("💡 TIP: Run this script again to process remaining episodes, or set MAX_EPISODES_PER_RUN=0 to process all at once")


if __name__ == "__main__":
    main()
