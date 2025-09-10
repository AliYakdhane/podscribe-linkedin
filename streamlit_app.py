import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
TRANSCRIPTS_DIR = Path(os.getenv("TRANSCRIPTS_DIR", DATA_DIR / "transcripts"))
POSTS_DIR = Path(os.getenv("POSTS_DIR", DATA_DIR / "posts"))

# Allow importing project modules
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

try:
    from src.config import load_config
    from src.apple import (
        lookup_feed_url_via_itunes,
        parse_feed_entries,
        sort_episodes,
        extract_show_id_from_apple_url,
        extract_episode_id_from_apple_url,
        lookup_episode_release_and_show_id,
    )
    from src.storage import StateStore
except Exception:
    load_config = None

st.set_page_config(page_title="Podcast Transcripts & Posts", layout="wide")

st.title("🎙️ Podcast Transcripts & LinkedIn Drafts")
st.markdown("**Automatically pull podcast episodes, transcribe them, and generate LinkedIn post drafts**")

# Dialog to confirm pull
@st.dialog("Confirm Pull")
def confirm_pull_dialog(episodes_count: int, drafts_count: int, run_limit: int, show_id_override: str, url_override: str, openai_key: str):
    st.write(f"Episodes to pull now: {'All' if run_limit == 0 else episodes_count}")
    st.write(f"LinkedIn drafts to generate: {drafts_count if run_limit != 0 else episodes_count * 3}")
    st.caption(f"This run limit: {'All' if run_limit == 0 else run_limit}")
    if show_id_override:
        st.caption(f"Show ID: {show_id_override}")
    if url_override:
        st.caption(f"Apple URL: {url_override}")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancel"):
            st.rerun()
    with c2:
        if st.button("Run Now", type="primary"):
            try:
                env = {}
                # Apply per-run limit override (0 means unlimited)
                env["MAX_EPISODES_PER_RUN"] = "0" if run_limit == 0 else str(run_limit)
                # Apply required OpenAI key
                env["OPENAI_API_KEY"] = openai_key
                # Apply ID/URL overrides
                if show_id_override:
                    env["SHOW_ID"] = show_id_override
                if url_override:
                    env["APPLE_EPISODE_URL"] = url_override
                result = subprocess.run([sys.executable, "-m", "src.main"], cwd=str(PROJECT_ROOT), env={**os.environ, **env}, capture_output=True, text=True, timeout=60*30)
                st.session_state["last_run_output"] = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
                st.session_state["last_run_success"] = (result.returncode == 0)
                st.session_state["last_run_time"] = datetime.now().isoformat(timespec="seconds")
            except Exception as ex:
                st.session_state["last_run_output"] = f"Run failed: {ex}"
                st.session_state["last_run_success"] = False
                st.session_state["last_run_time"] = datetime.now().isoformat(timespec="seconds")
            finally:
                st.rerun()


def compute_pending_counts(run_limit: int | None = None, show_id_override: str = "", url_override: str = "", openai_key: str = "") -> tuple[int, int]:
    """Return (episodes_to_process, drafts_to_generate) using only episodes newer than the last processed publish date."""
    try:
        if load_config is None or not openai_key:
            return (0, 0)
        cfg = load_config()

        # Determine effective show id
        eff_show_id = (show_id_override or "").strip()
        eff_url = (url_override or "").strip()
        if not eff_show_id and eff_url:
            try:
                eff_show_id = extract_show_id_from_apple_url(eff_url) or ""
            except Exception:
                eff_show_id = ""
        if not eff_show_id:
            eff_show_id = (cfg.show_id or "").strip()

        if not eff_show_id:
            return (0, 0)

        feed_url = lookup_feed_url_via_itunes(eff_show_id)
        if not feed_url:
            return (0, 0)

        episodes = parse_feed_entries(feed_url)
        episodes = sort_episodes(episodes)
        state = StateStore(cfg.data_dir / "state.json")

        # Derive baseline from URL if provided
        url_baseline_dt = None
        if url_override:
            try:
                ep_id = extract_episode_id_from_apple_url(url_override)
                if ep_id:
                    info = lookup_episode_release_and_show_id(ep_id)
                    if info:
                        _, release_dt = info
                        url_baseline_dt = release_dt
            except Exception:
                url_baseline_dt = None

        latest_dt = state.get_latest_published()
        # Effective baseline is the max of stored baseline and URL baseline
        if latest_dt is None:
            effective_baseline = url_baseline_dt
        elif url_baseline_dt is None:
            effective_baseline = latest_dt
        else:
            effective_baseline = max(latest_dt, url_baseline_dt)

        if effective_baseline is None and not state.processed_guids:
            pending = episodes[:]  # nothing processed yet; consider newest first
        else:
            pending = [e for e in episodes if (effective_baseline is None or (e.published is not None and e.published > effective_baseline))]

        # Apply override first, else cfg limit
        if run_limit and run_limit > 0:
            pending = pending[: run_limit]
        elif run_limit == 0:
            pass  # unlimited for this preview
        elif cfg.max_episodes_per_run and cfg.max_episodes_per_run > 0:
            pending = pending[: cfg.max_episodes_per_run]

        episodes_count = len(pending)
        drafts_per_episode = 3  # OpenAI key is required, so drafts will be generated
        drafts_count = episodes_count * drafts_per_episode
        return (episodes_count, drafts_count)
    except Exception:
        return (0, 0)

with st.sidebar:
    st.header("🎛️ Controls")

    # Required OpenAI key for this run
    openai_key_input = st.text_input("OpenAI API Key", value="", type="password", help="Required to transcribe and generate posts.")
    
    # AssemblyAI key (optional)
    assemblyai_key_input = st.text_input("AssemblyAI API Key (optional)", value="", type="password", help="Alternative transcription service.")

    # Inputs for Apple episode URL and Show ID (either works; URL can derive ID)
    url_input = st.text_input("Apple episode URL (optional)", value="", help="Paste any Apple Podcasts episode URL; we'll derive the show id.")
    show_id_input = st.text_input("Show ID (optional)", value="", help="Overrides derived ID if provided.")

    # Diagnostics
    diag_feed_url = None
    diag_latest = None
    try:
        cfg_d = load_config() if load_config else None
        eff_id = (show_id_input or "").strip() or (extract_show_id_from_apple_url((url_input or "").strip()) or "")
        if eff_id:
            diag_feed_url = lookup_feed_url_via_itunes(eff_id)
        if cfg_d is not None:
            s = StateStore(cfg_d.data_dir / "state.json")
            dt = s.get_latest_published()
            diag_latest = dt.isoformat() if dt else "None"
    except Exception:
        pass

    if diag_feed_url:
        st.caption(f"Resolved feed: {diag_feed_url}")
    st.caption(f"Latest processed publish date: {diag_latest or 'None'}")

    # New toggle: pull all newer than baseline
    pull_all = st.checkbox("Pull all newer than baseline", value=True)

    # Per-run limit control (disabled when pull_all)
    if pull_all:
        run_limit = 0
        st.caption("This run will pull all newer episodes.")
    else:
        run_limit = st.number_input("Episodes to pull now", min_value=1, value=1, step=1)

    disabled = not bool(openai_key_input)
    if st.button("🚀 Run Pull Now", disabled=disabled):
        eps, drafts = compute_pending_counts(run_limit, show_id_input, url_input, openai_key_input)
        confirm_pull_dialog(eps, drafts, run_limit, show_id_input, url_input, openai_key_input)

cols = st.columns(2)

# Left: transcripts list
with cols[0]:
    st.subheader("📝 Transcripts")
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    transcript_files = sorted(TRANSCRIPTS_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not transcript_files:
        st.info("No transcripts yet.")
    else:
        selected = st.selectbox("Select transcript", [p.name for p in transcript_files])
        if selected:
            path = TRANSCRIPTS_DIR / selected
            meta = path.stat()
            st.caption(f"Saved: {datetime.fromtimestamp(meta.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
            st.code(path.read_text(encoding="utf-8")[:20000])

# Right: posts list
with cols[1]:
    st.subheader("📱 LinkedIn Drafts")
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    post_files = sorted(POSTS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not post_files:
        st.info("No drafts yet.")
    else:
        selected_post = st.selectbox("Select draft", [p.name for p in post_files])
        if selected_post:
            p = POSTS_DIR / selected_post
            meta = p.stat()
            st.caption(f"Saved: {datetime.fromtimestamp(meta.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
            st.markdown(p.read_text(encoding="utf-8")[:20000])

# Run logs (persisted)
st.divider()
st.subheader("📊 Last Run Output")
if "last_run_output" in st.session_state:
    status_icon = "✅" if st.session_state.get("last_run_success") else "❌"
    ts = st.session_state.get("last_run_time") or ""
    st.caption(f"{status_icon} {ts}")
    st.code(st.session_state.get("last_run_output", ""))
else:
    st.caption("No runs yet.")

# Footer
st.divider()
st.markdown("""
### 🚀 How to Use

1. **Get API Keys**: 
   - [OpenAI API Key](https://platform.openai.com/api-keys) (required for transcription and post generation)
   - [AssemblyAI API Key](https://www.assemblyai.com/) (optional, for faster transcription)

2. **Configure Podcast**:
   - Enter an Apple Podcasts episode URL, or
   - Enter a Show ID directly

3. **Run**: Click "Run Pull Now" to fetch new episodes and generate LinkedIn drafts

### 📋 Features

- ✅ Automatic podcast episode detection
- ✅ Multiple transcription methods (Podcasting 2.0, AssemblyAI, OpenAI Whisper)
- ✅ AI-generated LinkedIn post drafts
- ✅ Progress tracking to avoid duplicates
- ✅ Cloud storage support (Supabase)

### 🔧 For Developers

This app can be deployed on [Streamlit Community Cloud](https://streamlit.io/cloud) or run locally.
""")
