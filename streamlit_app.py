import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime
import traceback
import hashlib
import hmac
import time

import streamlit as st

# Security configuration
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = "5ca659c9fa66d91be324e790e225f488e0dca8e954b770afdb2691f553d9ccf6"  # "password" hashed with SHA-256
SESSION_TIMEOUT = 3600  # 1 hour in seconds

def hash_password(password: str) -> str:
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash"""
    return hmac.compare_digest(hash_password(password), password_hash)

def is_authenticated() -> bool:
    """Check if user is authenticated and session is valid"""
    if "authenticated" not in st.session_state:
        return False
    
    if "login_time" not in st.session_state:
        return False
    
    # Check if session has expired
    if time.time() - st.session_state.login_time > SESSION_TIMEOUT:
        # Clear session
        for key in ["authenticated", "login_time", "username"]:
            if key in st.session_state:
                del st.session_state[key]
        return False
    
    return st.session_state.authenticated

def login_form():
    """Display login form"""
    st.title("🔐 Secure Access Required")
    st.markdown("---")
    
    with st.form("login_form"):
        st.subheader("Login to Podcast Transcript Puller")
        
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            login_button = st.form_submit_button("🔑 Login", use_container_width=True)
        with col2:
            if st.form_submit_button("❌ Cancel", use_container_width=True):
                st.stop()
        
        if login_button:
            if username == ADMIN_USERNAME and verify_password(password, ADMIN_PASSWORD_HASH):
                st.session_state.authenticated = True
                st.session_state.login_time = time.time()
                st.session_state.username = username
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid username or password")
    
    st.markdown("---")
    st.caption("🔒 This application is protected. Contact the administrator for access.")

def logout_button():
    """Display logout button in sidebar"""
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        # Clear all session state
        for key in ["authenticated", "login_time", "username"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

# Set page config first
st.set_page_config(
    page_title="Podcast Transcripts & Posts", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Main authentication check
if not is_authenticated():
    login_form()
    st.stop()

# User is authenticated - show logout button and continue with main app
logout_button()

st.title("🎙️ Podcast Transcripts & LinkedIn Drafts")
st.markdown("**Automatically pull podcast episodes, transcribe them, and generate LinkedIn post drafts**")

# Initialize session state
if "last_run_output" not in st.session_state:
    st.session_state["last_run_output"] = ""
if "last_run_success" not in st.session_state:
    st.session_state["last_run_success"] = False
if "last_run_time" not in st.session_state:
    st.session_state["last_run_time"] = ""

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
TRANSCRIPTS_DIR = Path(os.getenv("TRANSCRIPTS_DIR", DATA_DIR / "transcripts"))
POSTS_DIR = Path(os.getenv("POSTS_DIR", DATA_DIR / "posts"))

# Create directories
DATA_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
POSTS_DIR.mkdir(parents=True, exist_ok=True)

# Allow importing project modules
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Try to import modules with better error handling
load_config = None
lookup_feed_url_via_itunes = None
parse_feed_entries = None
sort_episodes = None
extract_show_id_from_apple_url = None
extract_episode_id_from_apple_url = None
lookup_episode_release_and_show_id = None
StateStore = None

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
    st.success("✅ All modules imported successfully!")
except Exception as e:
    st.error(f"❌ Import error: {str(e)}")
    st.code(traceback.format_exc())
    st.warning("Some features may not work. Check the error above.")

# Dialog to confirm pull
@st.dialog("Confirm Pull")
def confirm_pull_dialog(episodes_count: int, drafts_count: int, run_limit: int, show_id_override: str, url_override: str, openai_key: str):
    st.write(f"Episodes to pull now: {episodes_count}")
    st.write(f"LinkedIn drafts to generate: {drafts_count}")
    st.caption(f"This run limit: {run_limit}")
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
                # Apply per-run limit override
                env["MAX_EPISODES_PER_RUN"] = str(run_limit)
                # Apply required OpenAI key
                env["OPENAI_API_KEY"] = openai_key
                # Apply Supabase configuration from secrets
                if st.secrets.get("SUPABASE_URL"):
                    env["SUPABASE_URL"] = st.secrets["SUPABASE_URL"]
                if st.secrets.get("SUPABASE_SERVICE_ROLE_KEY"):
                    env["SUPABASE_SERVICE_ROLE_KEY"] = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
                # Apply ID/URL overrides
                if show_id_override:
                    env["SHOW_ID"] = show_id_override
                if url_override:
                    env["APPLE_EPISODE_URL"] = url_override
                
                # Create containers for real-time updates
                status_container = st.container()
                log_container = st.container()
                
                with status_container:
                    st.info("🚀 Starting podcast pull process...")
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    elapsed_text = st.empty()
                
                # Start the process
                process = subprocess.Popen(
                    [sys.executable, "-m", "src.main"], 
                    cwd=str(PROJECT_ROOT), 
                    env={**os.environ, **env}, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Initialize session state for logs if not exists
                if "current_logs" not in st.session_state:
                    st.session_state["current_logs"] = []
                if "process_start_time" not in st.session_state:
                    st.session_state["process_start_time"] = datetime.now()
                
                # Clear previous logs
                st.session_state["current_logs"] = []
                st.session_state["process_start_time"] = datetime.now()
                
                # Store process in session state for monitoring
                st.session_state["running_process"] = process
                st.session_state["process_env"] = env
                
                # Show initial status
                status_text.text("Process started...")
                elapsed_text.text("Elapsed: 0s")
                
                # Redirect to monitoring page
                st.rerun()
                    
            except subprocess.TimeoutExpired:
                st.session_state["last_run_output"] = "Run timed out after 30 minutes"
                st.session_state["last_run_success"] = False
                st.session_state["last_run_time"] = datetime.now().isoformat(timespec="seconds")
                st.error("❌ Run timed out!")
            except Exception as ex:
                st.session_state["last_run_output"] = f"Run failed: {ex}\n{traceback.format_exc()}"
                st.session_state["last_run_success"] = False
                st.session_state["last_run_time"] = datetime.now().isoformat(timespec="seconds")
                st.error(f"❌ Run failed: {ex}")
            finally:
                st.rerun()


def compute_pending_counts(run_limit: int, show_id_override: str = "", url_override: str = "", openai_key: str = "") -> tuple[int, int]:
    """Return (episodes_to_process, drafts_to_generate) for the specified number of episodes."""
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

        # Take the specified number of episodes (newest first)
        pending = episodes[:run_limit]

        episodes_count = len(pending)
        drafts_per_episode = 3  # OpenAI key is required, so drafts will be generated
        drafts_count = episodes_count * drafts_per_episode
        return (episodes_count, drafts_count)
    except Exception as e:
        st.error(f"Error computing pending counts: {e}")
        return (0, 0)

# Sidebar
with st.sidebar:
    st.header("🎛️ Controls")

    # Required OpenAI key for this run
    openai_key_input = st.text_input("OpenAI API Key", value="", type="password", help="Required to transcribe and generate posts.")
    
    # Supabase Configuration (optional)
    st.subheader("☁️ Supabase Storage (Optional)")
    # Check if Supabase is configured via secrets
    supabase_configured = bool(st.secrets.get("SUPABASE_URL") and st.secrets.get("SUPABASE_SERVICE_ROLE_KEY"))
    if supabase_configured:
        st.success("✅ Supabase configured via secrets")
    else:
        st.info("💡 Configure Supabase in Streamlit secrets for permanent storage")

    # Inputs for Apple episode URL and Show ID (either works; URL can derive ID)
    url_input = st.text_input("Apple episode URL (optional)", value="", help="Paste any Apple Podcasts episode URL; we'll derive the show id.")
    show_id_input = st.text_input("Show ID (optional)", value="", help="Overrides derived ID if provided.")

    # Diagnostics
    diag_feed_url = None
    try:
        if load_config:
            cfg_d = load_config()
            eff_id = (show_id_input or "").strip() or (extract_show_id_from_apple_url((url_input or "").strip()) if extract_show_id_from_apple_url else "")
            if eff_id and lookup_feed_url_via_itunes:
                diag_feed_url = lookup_feed_url_via_itunes(eff_id)
    except Exception as e:
        st.caption(f"Diagnostic error: {e}")

    if diag_feed_url:
        st.caption(f"Resolved feed: {diag_feed_url}")

    # Episode limit control
    run_limit = st.number_input("Episodes to pull now", min_value=1, value=1, step=1)
    st.caption(f"This run will pull {run_limit} episode(s).")

    disabled = not bool(openai_key_input)
    if st.button("🚀 Run Pull Now", disabled=disabled):
        if not openai_key_input:
            st.error("Please enter an OpenAI API key")
        else:
            eps, drafts = compute_pending_counts(run_limit, show_id_input, url_input, openai_key_input)
            confirm_pull_dialog(eps, drafts, run_limit, show_id_input, url_input, openai_key_input)
    
    # Clear Data Button
    st.divider()
    st.subheader("🗑️ Clear Data")
    if st.button("Clear All Local Data", type="secondary"):
        try:
            # Clear local files
            import shutil
            if TRANSCRIPTS_DIR.exists():
                shutil.rmtree(TRANSCRIPTS_DIR)
                TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
            if POSTS_DIR.exists():
                shutil.rmtree(POSTS_DIR)
                POSTS_DIR.mkdir(parents=True, exist_ok=True)
            
            # Clear state file
            state_file = DATA_DIR / "state.json"
            if state_file.exists():
                state_file.unlink()
            
            st.success("✅ All local data cleared! You can now test from scratch.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error clearing data: {e}")
    
    # Clear Supabase Data Button (if configured)
    if st.secrets.get("SUPABASE_URL") and st.secrets.get("SUPABASE_SERVICE_ROLE_KEY"):
        if st.button("Clear Supabase Data", type="secondary"):
            try:
                # Clear Supabase tables
                import subprocess
                import sys
                
                env = {
                    "SUPABASE_URL": st.secrets["SUPABASE_URL"],
                    "SUPABASE_SERVICE_ROLE_KEY": st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
                }
                
                # Run a script to clear Supabase data
                result = subprocess.run([
                    sys.executable, "-c", """
import os
from supabase import create_client

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
client = create_client(url, key)

# Clear tables
client.table('podcast_transcripts').delete().neq('id', 0).execute()
client.table('podcast_posts').delete().neq('id', 0).execute()

print('Supabase data cleared successfully')
"""
                ], env={**os.environ, **env}, capture_output=True, text=True)
                
                if result.returncode == 0:
                    st.success("✅ Supabase data cleared! All transcripts and posts removed from database.")
                else:
                    st.error(f"❌ Error clearing Supabase data: {result.stderr}")
                    
            except Exception as e:
                st.error(f"❌ Error clearing Supabase data: {e}")

# Process monitoring section
if "running_process" in st.session_state and st.session_state["running_process"]:
    st.divider()
    st.subheader("🔄 Process Monitoring")
    
    process = st.session_state["running_process"]
    start_time = st.session_state.get("process_start_time", datetime.now())
    current_time = datetime.now()
    elapsed = (current_time - start_time).total_seconds()
    
    # Check if process is still running
    if process.poll() is None:
        # Process is still running
        st.info(f"🚀 Process is running... ({elapsed:.0f}s elapsed)")
        progress_bar = st.progress(min(elapsed / 300, 1.0))  # 5 min max progress
        
        # Try to read output (simplified approach)
        try:
            # Read available output
            if process.stdout.readable():
                line = process.stdout.readline()
                if line:
                    if "current_logs" not in st.session_state:
                        st.session_state["current_logs"] = []
                    st.session_state["current_logs"].append(line.strip())
        except:
            pass
        
        # Show recent logs
        if "current_logs" in st.session_state and st.session_state["current_logs"]:
            st.subheader("📊 Real-time Logs")
            recent_logs = st.session_state["current_logs"][-10:]  # Show last 10 lines
            for log_line in recent_logs:
                st.text(log_line)
        
        # Auto-refresh every 2 seconds
        import time
        time.sleep(2)
        st.rerun()
    else:
        # Process completed
        return_code = process.returncode
        final_output = "\n".join(st.session_state.get("current_logs", []))
        
        st.session_state["last_run_output"] = final_output
        st.session_state["last_run_success"] = (return_code == 0)
        st.session_state["last_run_time"] = datetime.now().isoformat(timespec="seconds")
        
        # Clean up
        del st.session_state["running_process"]
        if "current_logs" in st.session_state:
            del st.session_state["current_logs"]
        if "process_start_time" in st.session_state:
            del st.session_state["process_start_time"]
        
        if return_code == 0:
            st.success("✅ Process completed successfully!")
        else:
            st.error(f"❌ Process failed with return code: {return_code}")
        
        st.rerun()

# Supabase Status
if st.secrets.get("SUPABASE_URL") and st.secrets.get("SUPABASE_SERVICE_ROLE_KEY"):
    st.success("☁️ Supabase storage enabled - files will be permanently stored")
else:
    st.info("💾 Local storage only - files will be lost when instance restarts")

# Main content
cols = st.columns(2)

# Left: transcripts list
with cols[0]:
    st.subheader("📝 Transcripts")
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
if st.session_state.get("last_run_output"):
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

1. **Get API Key**: 
   - [OpenAI API Key](https://platform.openai.com/api-keys) (required for transcription and post generation)

2. **Configure Podcast**:
   - Enter an Apple Podcasts episode URL, or
   - Enter a Show ID directly

3. **Run**: Click "Run Pull Now" to fetch new episodes and generate LinkedIn drafts

### 📋 Features

- ✅ Automatic podcast episode detection
- ✅ Multiple transcription methods (Podcasting 2.0, OpenAI Whisper)
- ✅ AI-generated LinkedIn post drafts
- ✅ Progress tracking to avoid duplicates
- ✅ Cloud storage support (Supabase)

### 🔧 For Developers

This app can be deployed on [Streamlit Community Cloud](https://streamlit.io/cloud) or run locally.
""")

# Debug information
with st.expander("🔍 Debug Information"):
    st.write("**Project Root:**", PROJECT_ROOT)
    st.write("**Data Directory:**", DATA_DIR)
    st.write("**Transcripts Directory:**", TRANSCRIPTS_DIR)
    st.write("**Posts Directory:**", POSTS_DIR)
    st.write("**Python Path:**", sys.path[:3])  # Show first 3 paths
    st.write("**Environment Variables:**")
    env_vars = {k: v for k, v in os.environ.items() if k.startswith(('OPENAI', 'ASSEMBLYAI', 'SHOW_ID', 'APPLE'))}
    st.json(env_vars)