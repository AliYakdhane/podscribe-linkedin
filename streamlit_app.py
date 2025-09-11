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
    page_title="Podcast AI Studio", 
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1f4e79 0%, #2d5aa0 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
    }
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        border-left: 4px solid #1f4e79;
        margin-bottom: 1rem;
    }
    .section-header {
        color: #1f4e79;
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e6f3ff;
    }
    .status-success {
        background: #e8f5e8;
        color: #2d5d2d;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        border-left: 4px solid #4caf50;
        margin: 0.5rem 0;
    }
    .status-warning {
        background: #fff3cd;
        color: #856404;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        border-left: 4px solid #ffc107;
        margin: 0.5rem 0;
    }
    .content-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
    }
    .sidebar .sidebar-content {
        background: #f8f9fa;
    }
    .stButton > button {
        background: linear-gradient(90deg, #1f4e79 0%, #2d5aa0 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(31, 78, 121, 0.3);
    }
    .stTextInput > div > div > input {
        border-radius: 8px;
        border: 2px solid #e1e5e9;
    }
    .stTextInput > div > div > input:focus {
        border-color: #1f4e79;
        box-shadow: 0 0 0 3px rgba(31, 78, 121, 0.1);
    }
</style>
""", unsafe_allow_html=True)

# Main authentication check
if not is_authenticated():
    login_form()
    st.stop()

# User is authenticated - show logout button and continue with main app
logout_button()

# Professional Header
st.markdown("""
<div class="main-header">
    <h1 style="margin: 0; font-size: 2.5rem;">🎙️ Podcast AI Studio</h1>
    <p style="margin: 0.5rem 0 0 0; font-size: 1.2rem; opacity: 0.9;">
        Automated podcast transcription and LinkedIn content generation
    </p>
</div>
""", unsafe_allow_html=True)

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
    from src.config_manager import save_user_config
    st.success("✅ All modules imported successfully!")
except Exception as e:
    st.error(f"❌ Import error: {str(e)}")
    st.code(traceback.format_exc())
    st.warning("Some features may not work. Check the error above.")

def load_transcripts_from_supabase():
    """Load transcripts from Supabase"""
    try:
        from src.storage import build_supabase_client
        
        # Check if Supabase is configured
        supabase_url = st.secrets.get("SUPABASE_URL")
        supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")
        
        if not (supabase_url and supabase_key):
            return []
        
        # Build Supabase client
        supabase_client = build_supabase_client(supabase_url, supabase_key)
        if not supabase_client:
            return []
        
        # Load transcripts from Supabase
        result = supabase_client.table("podcast_transcripts").select("*").order("created_at", desc=True).execute()
        
        if result.data:
            return result.data
        else:
            return []
            
    except Exception as e:
        st.error(f"❌ Error loading transcripts from Supabase: {e}")
        return []

def load_posts_from_supabase():
    """Load posts from Supabase"""
    try:
        from src.storage import build_supabase_client
        
        # Check if Supabase is configured
        supabase_url = st.secrets.get("SUPABASE_URL")
        supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")
        
        if not (supabase_url and supabase_key):
            return []
        
        # Build Supabase client
        supabase_client = build_supabase_client(supabase_url, supabase_key)
        if not supabase_client:
            return []
        
        # Load posts from Supabase
        result = supabase_client.table("podcast_posts").select("*").order("created_at", desc=True).execute()
        
        if result.data:
            return result.data
        else:
            return []
            
    except Exception as e:
        st.error(f"❌ Error loading posts from Supabase: {e}")
        return []

def save_configuration_to_supabase(show_id: str, apple_url: str, max_episodes: int, openai_key: str):
    """Save user configuration to Supabase"""
    try:
        from src.storage import build_supabase_client
        
        # Check if Supabase is configured
        supabase_url = st.secrets.get("SUPABASE_URL")
        supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")
        
        if not (supabase_url and supabase_key):
            st.warning("⚠️ Supabase not configured - configuration not saved")
            st.info(f"🔍 Found SUPABASE_URL: {'Yes' if supabase_url else 'No'}")
            st.info(f"🔍 Found SUPABASE_SERVICE_ROLE_KEY: {'Yes' if supabase_key else 'No'}")
            return False
        
        # Validate URL format
        if not supabase_url.startswith("https://") or not supabase_url.endswith(".supabase.co"):
            st.error(f"❌ Invalid Supabase URL format: {supabase_url}")
            st.info("💡 URL should be: https://your-project-id.supabase.co")
            return False
        
        # Validate key format (JWT tokens start with eyJ)
        if not supabase_key.startswith("eyJ"):
            st.error(f"❌ Invalid Supabase service role key format")
            st.info("💡 Service role key should be a JWT token starting with 'eyJ'")
            return False
        
        # Build Supabase client
        st.info(f"🔧 Building Supabase client...")
        st.info(f"🔧 URL: {supabase_url[:20]}..." if supabase_url else "🔧 URL: None")
        st.info(f"🔧 Key: {supabase_key[:20]}..." if supabase_key else "🔧 Key: None")
        
        try:
            supabase_client = build_supabase_client(
                supabase_url,
                supabase_key
            )
            
            if not supabase_client:
                st.error("❌ Failed to connect to Supabase - build_supabase_client returned None")
                st.info("🔍 This usually means there was an error creating the Supabase client")
                st.info("💡 Check the Streamlit logs for detailed error information")
                st.info("🔧 Common issues:")
                st.info("   - Invalid Supabase URL format")
                st.info("   - Invalid service role key")
                st.info("   - Network connectivity issues")
                st.info("   - Supabase service down")
                return False
            else:
                st.info("✅ Supabase client built successfully")
                
        except Exception as e:
            st.error(f"❌ Exception building Supabase client: {str(e)}")
            return False
        
        # Test Supabase connection first
        try:
            st.info("🔍 Testing Supabase connection...")
            # Try to query a simple table to test connection
            result = supabase_client.table("podcast_transcripts").select("id").limit(1).execute()
            st.info("✅ Supabase connection test successful")
        except Exception as e:
            st.warning(f"⚠️ Supabase connection test failed: {str(e)}")
            st.info("🔧 This might be normal if tables don't exist yet")
        
        # Save configuration
        success = save_user_config(
            supabase_client,
            show_id=show_id,
            apple_episode_url=apple_url,
            max_episodes_per_run=max_episodes,
            openai_api_key=openai_key
        )
        
        if success:
            st.success("✅ Configuration saved to Supabase")
            return True
        else:
            st.error("❌ Failed to save configuration")
            return False
            
    except Exception as e:
        st.error(f"❌ Error saving configuration: {str(e)}")
        return False

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


def compute_pending_counts(run_limit: int, show_id_override: str = "", url_override: str = "", openai_key: str = "") -> tuple[int, int, str]:
    """Return (episodes_to_process, drafts_to_generate, status_message) for the specified number of episodes."""
    try:
        if load_config is None or not openai_key:
            return (0, 0, "OpenAI key required")
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
            return (0, 0, "Show ID required")

        feed_url = lookup_feed_url_via_itunes(eff_show_id)
        if not feed_url:
            return (0, 0, "Could not resolve feed URL")

        episodes = parse_feed_entries(feed_url)
        episodes = sort_episodes(episodes)

        # Check if we have an Apple episode URL
        if eff_url:
            try:
                ep_id = extract_episode_id_from_apple_url(eff_url)
                if ep_id:
                    info = lookup_episode_release_and_show_id(ep_id)
                    if info:
                        _, release_dt = info
                        # Find episodes newer than the specified episode
                        newer_episodes = [e for e in episodes if e.published and e.published > release_dt]
                        if not newer_episodes:
                            return (0, 0, "No episodes newer than the specified episode URL")
                        
                        # Check if any are unprocessed (simplified check)
                        pending = newer_episodes[:run_limit]
                        status_msg = f"Found {len(pending)} episodes newer than the specified episode URL"
                    else:
                        pending = episodes[:run_limit]
                        status_msg = f"Could not lookup episode info from Apple (ID: {ep_id}), using newest {len(pending)} episodes"
                else:
                    pending = episodes[:run_limit]
                    status_msg = f"Could not extract episode ID from URL, using newest {len(pending)} episodes"
            except Exception as e:
                pending = episodes[:run_limit]
                status_msg = f"Error parsing episode URL: {str(e)}, using newest {len(pending)} episodes"
        else:
            # No episode URL - use newest episodes
            pending = episodes[:run_limit]
            status_msg = f"Using newest {len(pending)} episodes"

        episodes_count = len(pending)
        drafts_per_episode = 3  # OpenAI key is required, so drafts will be generated
        drafts_count = episodes_count * drafts_per_episode
        return (episodes_count, drafts_count, status_msg)
    except Exception as e:
        return (0, 0, f"Error: {e}")

# Sidebar
with st.sidebar:
    st.markdown("""
    <div style="background: linear-gradient(90deg, #1f4e79 0%, #2d5aa0 100%); padding: 1rem; border-radius: 10px; margin-bottom: 1rem; color: white;">
        <h2 style="margin: 0; text-align: center;">🎛️ Control Panel</h2>
    </div>
    """, unsafe_allow_html=True)

    # Required OpenAI key for this run
    openai_key_input = st.text_input("OpenAI API Key", value="", type="password", help="Required to transcribe and generate posts.")
    
    # Supabase Configuration (optional) - hidden from UI
    supabase_configured = bool(st.secrets.get("SUPABASE_URL") and st.secrets.get("SUPABASE_SERVICE_ROLE_KEY"))

    # Show ID input (Apple episode URL is stored in Supabase configuration)
    show_id_input = st.text_input("Show ID (optional)", value="", help="Overrides the Show ID stored in Supabase if provided.")

    # Diagnostics
    diag_feed_url = None
    try:
        if load_config:
            cfg_d = load_config()
            eff_id = (show_id_input or "").strip()
            if eff_id and lookup_feed_url_via_itunes:
                diag_feed_url = lookup_feed_url_via_itunes(eff_id)
    except Exception as e:
        st.caption(f"Diagnostic error: {e}")

    if diag_feed_url:
        st.caption(f"Resolved feed: {diag_feed_url}")

    # Episode limit control - removed, now stored in Supabase
    run_limit = 1  # Default value for manual runs
    
    # Show intelligent episode selection status
    if openai_key_input and show_id_input:
        try:
            eps, drafts, status_msg = compute_pending_counts(run_limit, show_id_input, "", openai_key_input)
            if eps > 0:
                st.success(f"✅ {status_msg}")
            else:
                st.info(f"ℹ️ {status_msg}")
        except Exception as e:
            st.warning(f"⚠️ Could not check episode status: {e}")
    else:
        st.caption("Configuration stored in Supabase. Manual runs will pull 1 episode.")

    # Save Configuration Button
    if st.button("💾 Save Configuration", help="Save your settings to Supabase for the cron job to use"):
        if openai_key_input and show_id_input:
            success = save_configuration_to_supabase(
                show_id=show_id_input,
                apple_url="",  # Apple URL is managed separately in Supabase
                max_episodes=1,  # Default episodes per run
                openai_key=openai_key_input
            )
            if success:
                st.rerun()
        else:
            st.error("Please enter OpenAI API key and Show ID")

    disabled = not bool(openai_key_input)
    if st.button("🚀 Run Pull Now", disabled=disabled):
        if not openai_key_input:
            st.error("Please enter an OpenAI API key")
        else:
            eps, drafts, status_msg = compute_pending_counts(run_limit, show_id_input, "", openai_key_input)
            confirm_pull_dialog(eps, drafts, run_limit, show_id_input, "", openai_key_input)
    
    # Clear Data Button
    st.divider()
    st.markdown("""
    <div style="background: #fff3cd; padding: 1rem; border-radius: 10px; margin: 1rem 0; border-left: 4px solid #ffc107;">
        <h3 style="margin: 0; color: #856404;">🗑️ Data Management</h3>
        <p style="margin: 0.5rem 0 0 0; color: #856404; font-size: 0.9rem;">Use these tools to clear local or cloud data for testing purposes.</p>
    </div>
    """, unsafe_allow_html=True)
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

# Process monitoring section removed for cleaner UI

# System Status Dashboard
st.markdown('<h2 class="section-header">📊 System Status</h2>', unsafe_allow_html=True)

supabase_url = st.secrets.get("SUPABASE_URL")
supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")

# Create status cards
col1, col2, col3 = st.columns(3)

with col1:
    if supabase_url and supabase_key:
        st.markdown("""
        <div class="metric-card">
            <h3 style="margin: 0; color: #4caf50;">☁️ Cloud Storage</h3>
            <p style="margin: 0.5rem 0 0 0; color: #666;">Active & Synchronized</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="metric-card">
            <h3 style="margin: 0; color: #ff9800;">⚠️ Local Only</h3>
            <p style="margin: 0.5rem 0 0 0; color: #666;">Data will be lost on restart</p>
        </div>
        """, unsafe_allow_html=True)

with col2:
    try:
        transcripts = load_transcripts_from_supabase()
        st.markdown(f"""
        <div class="metric-card">
            <h3 style="margin: 0; color: #1f4e79;">📝 Transcripts</h3>
            <p style="margin: 0.5rem 0 0 0; color: #666; font-size: 1.5rem; font-weight: bold;">{len(transcripts)}</p>
        </div>
        """, unsafe_allow_html=True)
    except:
        st.markdown("""
        <div class="metric-card">
            <h3 style="margin: 0; color: #1f4e79;">📝 Transcripts</h3>
            <p style="margin: 0.5rem 0 0 0; color: #666; font-size: 1.5rem; font-weight: bold;">0</p>
        </div>
        """, unsafe_allow_html=True)

with col3:
    try:
        posts = load_posts_from_supabase()
        st.markdown(f"""
        <div class="metric-card">
            <h3 style="margin: 0; color: #1f4e79;">📱 LinkedIn Posts</h3>
            <p style="margin: 0.5rem 0 0 0; color: #666; font-size: 1.5rem; font-weight: bold;">{len(posts)}</p>
        </div>
        """, unsafe_allow_html=True)
    except:
        st.markdown("""
        <div class="metric-card">
            <h3 style="margin: 0; color: #1f4e79;">📱 LinkedIn Posts</h3>
            <p style="margin: 0.5rem 0 0 0; color: #666; font-size: 1.5rem; font-weight: bold;">0</p>
        </div>
        """, unsafe_allow_html=True)

# Main Content Section
st.markdown('<h2 class="section-header">📚 Content Library</h2>', unsafe_allow_html=True)

cols = st.columns(2)

# Left: transcripts list
with cols[0]:
    st.markdown('<h3 class="section-header" style="font-size: 1.3rem; margin-bottom: 1rem;">📝 Podcast Transcripts</h3>', unsafe_allow_html=True)
    
    # Load transcripts from Supabase
    transcripts = load_transcripts_from_supabase()
    
    if not transcripts:
        st.info("No transcripts yet.")
    else:
        # Create options for selectbox
        transcript_options = []
        for transcript in transcripts:
            episode_title = transcript.get('title', 'Unknown Episode')
            created_at = transcript.get('created_at', '')
            if created_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    date_str = created_at
            else:
                date_str = 'Unknown date'
            
            transcript_options.append(f"{episode_title} ({date_str})")
        
        selected_idx = st.selectbox("Select transcript", range(len(transcript_options)), format_func=lambda x: transcript_options[x])
        
        if selected_idx is not None and selected_idx < len(transcripts):
            selected_transcript = transcripts[selected_idx]
            episode_title = selected_transcript.get('title', 'Unknown Episode')
            transcript_content = selected_transcript.get('transcript_content', 'No content available')
            created_at = selected_transcript.get('created_at', '')
            
            if created_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    date_str = created_at
            else:
                date_str = 'Unknown date'
            
            st.caption(f"Episode: {episode_title}")
            st.caption(f"Saved: {date_str}")
            st.code(transcript_content[:20000])

# Right: posts list
with cols[1]:
    st.markdown('<h3 class="section-header" style="font-size: 1.3rem; margin-bottom: 1rem;">📱 LinkedIn Drafts</h3>', unsafe_allow_html=True)
    
    # Load posts from Supabase
    posts = load_posts_from_supabase()
    
    if not posts:
        st.info("No drafts yet.")
    else:
        # Create options for selectbox
        post_options = []
        for post in posts:
            episode_title = post.get('title', 'Unknown Episode')
            created_at = post.get('created_at', '')
            if created_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    date_str = created_at
            else:
                date_str = 'Unknown date'
            
            post_options.append(f"{episode_title} ({date_str})")
        
        selected_post_idx = st.selectbox("Select draft", range(len(post_options)), format_func=lambda x: post_options[x])
        
        if selected_post_idx is not None and selected_post_idx < len(posts):
            selected_post = posts[selected_post_idx]
            episode_title = selected_post.get('title', 'Unknown Episode')
            posts_content = selected_post.get('posts_content', 'No content available')
            created_at = selected_post.get('created_at', '')
            
            if created_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    date_str = created_at
            else:
                date_str = 'Unknown date'
            
            st.caption(f"Episode: {episode_title}")
            st.caption(f"Saved: {date_str}")
            
            # Split posts content and display each post separately
            if posts_content and posts_content != 'No content available':
                posts_list = posts_content.split('---')
                for i, post in enumerate(posts_list, 1):
                    if post.strip():
                        st.subheader(f"Post {i}")
                        st.markdown(post.strip())
                        if i < len(posts_list):
                            st.divider()
            else:
                st.markdown("No content available")

# Run logs section removed for cleaner UI

# Footer
st.divider()
st.markdown("""
<div style="background: #f8f9fa; padding: 2rem; border-radius: 10px; margin-top: 2rem; border-left: 4px solid #1f4e79;">
    <h3 style="color: #1f4e79; margin-top: 0;">🚀 Quick Start Guide</h3>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem;">
        <div>
            <h4 style="color: #1f4e79;">Setup</h4>
            <ol style="color: #666; line-height: 1.6;">
                <li>Get your <a href="https://platform.openai.com/api-keys" target="_blank">OpenAI API Key</a></li>
                <li>Enter Show ID in the sidebar</li>
                <li>Click "Save Configuration"</li>
                <li>Click "Run Pull Now" to start</li>
            </ol>
        </div>
        <div>
            <h4 style="color: #1f4e79;">Features</h4>
            <ul style="color: #666; line-height: 1.6;">
                <li>✅ Automated episode detection</li>
                <li>✅ AI-powered transcription</li>
                <li>✅ LinkedIn post generation</li>
                <li>✅ Cloud storage & sync</li>
                <li>✅ Scheduled automation</li>
            </ul>
        </div>
    </div>
    <div style="text-align: center; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #dee2e6;">
        <p style="color: #666; margin: 0; font-size: 0.9rem;">
            🎙️ <strong>Podcast AI Studio</strong> - Powered by OpenAI & Supabase
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

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