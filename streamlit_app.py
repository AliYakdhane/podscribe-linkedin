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

# Add the src directory to the Python path
sys.path.append(str(Path(__file__).parent / "src"))

# Import new session manager
try:
    from src.session_manager import initialize_session, is_authenticated, login_form, logout_button
    USE_SUPABASE_SESSIONS = True
    print("✅ Using Supabase-based session management")
except ImportError as e:
    # Fallback to old session management if new one not available
    USE_SUPABASE_SESSIONS = False
    print(f"⚠️ Warning: Using fallback session management. Error: {e}")

# Security configuration (fallback)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = "5ca659c9fa66d91be324e790e225f488e0dca8e954b770afdb2691f553d9ccf6"  # "password" hashed with SHA-256
SESSION_TIMEOUT = 3600  # 1 hour in seconds

# Set page config first - must be before any other Streamlit commands
st.set_page_config(
    page_title="Podcast AI Studio", 
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply global CSS immediately for consistent theming across entire app
st.markdown("""
<style>
    /* Global styles - applied to entire app including login */
    .main {
        padding-top: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
        background: #f8fafc !important;
    }
    
    /* Force light theme on all elements */
    .stApp {
        background: #f8fafc !important;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Top navigation bar */
    .top-nav {
        position: fixed;
        top: 0;
        right: 0;
        left: 0;
        background: #ffffff;
        padding: 0.75rem 1rem;
        border-bottom: 2px solid #e2e8f0;
        z-index: 999;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .nav-title {
        color: #1e293b;
        font-size: 1.5rem;
        font-weight: 700;
        margin: 0;
    }
    
    /* Main content area */
    .main-content {
        margin-top: 80px;
        padding: 1rem;
    }
    
    /* Status dashboard */
    .status-dashboard {
        display: flex;
        gap: 1rem;
        margin-bottom: 0.5rem;
        flex-wrap: wrap;
    }
    
    .status-card {
        background: #ffffff;
        border: 2px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
        flex: 1;
        min-width: 200px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .status-title {
        color: #64748b;
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin: 0 0 0.5rem 0;
    }
    
    .status-value {
        color: #1e293b;
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
    }
    
    /* Content sections */
    .content-section {
        background: #ffffff;
        border: 2px solid #e2e8f0;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .section-title {
        color: #1e293b;
        font-size: 1.25rem;
        font-weight: 700;
        margin: 0 0 0.5rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 3px solid #3b82f6;
    }
    
    /* Form elements */
    .transcript-selector, .generation-form {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    
    .form-title {
        color: #1e293b;
        font-size: 1rem;
        font-weight: 600;
        margin: 0 0 0.5rem 0;
    }
    
    /* Buttons */
    .stButton > button {
        background: #3b82f6 !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3) !important;
        transition: all 0.2s !important;
    }
    
    .stButton > button:hover {
        background: #2563eb !important;
        box-shadow: 0 4px 8px rgba(59, 130, 246, 0.4) !important;
        transform: translateY(-1px) !important;
    }
    
    /* Input fields */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > select {
        background: #ffffff !important;
        color: #1e293b !important;
        border: 2px solid #e2e8f0 !important;
        border-radius: 6px !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stSelectbox > div > div > select:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
    }
    
    /* Selectbox text color fix */
    .stSelectbox label,
    .stSelectbox div[data-baseweb="select"] {
        color: #1e293b !important;
    }
    
    .stSelectbox div[data-baseweb="select"] > div {
        color: #1e293b !important;
        background: #ffffff !important;
    }
    
    /* Content display */
    .content-display {
        background: #ffffff;
        border-left: 4px solid #3b82f6;
        padding: 0.5rem;
        margin: 0.25rem 0;
        border-radius: 0 6px 6px 0;
    }
    
    .content-title {
        color: #1e293b;
        font-size: 1.125rem;
        font-weight: 600;
        margin: 0 0 0.5rem 0;
    }
    
    .content-meta {
        color: #64748b;
        font-size: 0.875rem;
        margin: 0 0 0.5rem 0;
    }
    
    .content-text {
        color: #374151;
        line-height: 1.6;
        white-space: pre-wrap;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: #f8fafc;
        border-radius: 8px 8px 0 0;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: #f1f5f9;
        color: #64748b;
        border-radius: 6px 6px 0 0;
        margin-right: 0.25rem;
    }
    
    .stTabs [aria-selected="true"] {
        background: #3b82f6 !important;
        color: white !important;
    }
    
    /* Login form styling - force light theme */
    .stForm {
        background: #ffffff !important;
        border: 2px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 2rem !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
        margin: 2rem auto !important;
        max-width: 400px !important;
    }
    
    .stForm h3 {
        color: #1e293b !important;
        text-align: center !important;
        margin-bottom: 1.5rem !important;
    }
    
    /* Force light theme on all text elements */
    h1, h2, h3, h4, h5, h6, p, span, div, label {
        color: #1e293b !important;
    }
    
    /* Override any dark theme styles */
    [data-testid="stApp"] {
        background: #f8fafc !important;
    }
    
    /* Ensure all containers have light background */
    .element-container {
        background: transparent !important;
    }
    
    .block-container {
        background: #f8fafc !important;
    }
    
    /* Force light theme on login page specifically */
    .stApp > div:first-child {
        background: #f8fafc !important;
    }
    
    /* Override Streamlit's default dark theme */
    .stApp[data-theme="dark"] {
        background: #f8fafc !important;
    }
    
    .stApp[data-theme="dark"] .main {
        background: #f8fafc !important;
    }
    
    /* Force light theme on login page specifically */
    .stApp > div:first-child {
        background: #f8fafc !important;
    }
    
    /* Override any remaining dark theme elements */
    .stApp * {
        color: #1e293b !important;
    }
    
    /* Ensure login form has light theme */
    .stForm, .stForm * {
        background: #ffffff !important;
        color: #1e293b !important;
    }
    
    /* Force light theme on all text elements */
    p, span, div, label, input, textarea, select {
        color: #1e293b !important;
    }
</style>
""", unsafe_allow_html=True)

def hash_password(password: str) -> str:
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash"""
    return hmac.compare_digest(hash_password(password), password_hash)

# Old is_authenticated function removed - now using Supabase-based session manager

# Old session management functions removed - now using Supabase-based session manager

# Old session initialization removed - now handled by new session manager

# Old login_form and logout functions removed - now using Supabase-based session manager

# Main authentication check
# Check authentication using new session manager or fallback
if USE_SUPABASE_SESSIONS:
    # Use new Supabase-based session management
    initialize_session()
    
    if not is_authenticated():
        # Try to restore session from localStorage
        st.markdown("""
        <script>
        // Try to restore session from localStorage
        const savedSessionId = localStorage.getItem('podcast_session_id');
        if (savedSessionId && !window.sessionRestored) {
            window.sessionRestored = true;
            // Redirect with session_id to restore session
            const url = new URL(window.location);
            url.searchParams.set('session_id', savedSessionId);
            window.location.href = url.toString();
        }
        </script>
        """, unsafe_allow_html=True)
        
        login_form()
        st.stop()
else:
    # Fallback to old session management
    if not is_authenticated():
        login_form()
        st.stop()

# User is authenticated - continue with main app

# Top Navigation Bar with Logout
st.markdown("""
<div class="top-nav">
    <div class="nav-title">🎙️ Podcast AI Studio</div>
    <div class="nav-logout-container">
        <button class="nav-logout" onclick="logoutFunction()">🚪 Logout</button>
    </div>
</div>
""", unsafe_allow_html=True)

# Main Content
st.markdown('<div class="main-content">', unsafe_allow_html=True)

# Initialize session state
if "last_run_output" not in st.session_state:
    st.session_state["last_run_output"] = ""
if "last_run_success" not in st.session_state:
    st.session_state["last_run_success"] = False
if "last_run_time" not in st.session_state:
    st.session_state["last_run_time"] = ""

# Load data from Supabase
transcripts = load_transcripts_from_supabase()
posts = load_posts_from_supabase()

# Status Dashboard
st.markdown("""
<div class="status-dashboard">
    <div class="status-card">
        <div class="status-title">☁️ Cloud Storage</div>
        <div class="status-value">Connected</div>
    </div>
    <div class="status-card">
        <div class="status-title">📝 Transcripts</div>
        <div class="status-value">{}</div>
    </div>
    <div class="status-card">
        <div class="status-title">📱 LinkedIn Posts</div>
        <div class="status-value">{}</div>
    </div>
</div>
""".format(len(transcripts), len(posts)), unsafe_allow_html=True)

# Content Generation Section
st.markdown('<h4 class="section-title">🎯 Content Generation</h4>', unsafe_allow_html=True)

# Voice and tone input
st.markdown('<div class="generation-form">', unsafe_allow_html=True)
st.markdown('<div class="form-title">Voice & Tone</div>', unsafe_allow_html=True)
custom_voice = st.text_area(
    "Describe your desired voice and tone for content generation:",
    placeholder="e.g., Professional, friendly, authoritative, conversational...",
    key="custom_voice_global"
)

# Additional instructions
st.markdown('<div class="form-title">Additional Instructions</div>', unsafe_allow_html=True)
custom_instructions = st.text_area(
    "Any specific instructions for content generation:",
    placeholder="e.g., Focus on key takeaways, include call-to-action, use specific examples...",
    key="custom_instructions_global"
)

# Transcript selector
st.markdown('<div class="form-title">Select Transcript</div>', unsafe_allow_html=True)
if transcripts:
    transcript_options = [f"{t['title']} - {t.get('published_at', t.get('created_at', 'Unknown date'))}" for t in transcripts]
    selected_transcript_idx = st.selectbox(
        "Select transcript to generate content from:",
        range(len(transcript_options)),
        format_func=lambda x: transcript_options[x],
        key="transcript_selector_global"
    )
else:
    st.info("No transcripts available. Pull some episodes first!")
    selected_transcript_idx = None

# Generate content buttons
st.markdown('<div class="form-actions">', unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)

with col1:
    generate_linkedin = st.button("📱 Generate LinkedIn Posts", key="generate_linkedin_global")

with col2:
    generate_blog = st.button("📝 Generate Blog Post", key="generate_blog_global")

with col3:
    generate_both = st.button("🚀 Generate Both", key="generate_both_global")

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)  # Close generation-form

# Content generation logic
if selected_transcript_idx is not None and (generate_linkedin or generate_blog or generate_both):
    if not custom_voice.strip():
        st.error("Please enter your desired voice and tone before generating content.")
    else:
        selected_transcript = transcripts[selected_transcript_idx]
        transcript_content = selected_transcript['transcript_content']
        
        # Check if OpenAI key is available
        openai_key = st.secrets.get("OPENAI_API_KEY")
        if not openai_key:
            st.error("OpenAI API key not found in secrets. Please configure it first.")
        else:
            try:
                from src.content_generator import ContentGenerator
                generator = ContentGenerator(openai_key)
                
                if generate_linkedin or generate_both:
                    with st.spinner("Generating LinkedIn posts..."):
                        linkedin_posts = generator.generate_linkedin_posts_custom(
                            transcript_content, custom_voice, custom_instructions
                        )
                        
                        # Store LinkedIn posts in Supabase
                        from src.storage import store_posts, build_supabase_client
                        supabase_url = st.secrets.get("SUPABASE_URL")
                        supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")
                        supabase_client = build_supabase_client(supabase_url, supabase_key)
                        
                        if supabase_client:
                            posts_content = "---POST_BREAK---".join(linkedin_posts)
                            store_posts(
                                supabase_client,
                                "podcast_posts",
                                selected_transcript['guid'],
                                selected_transcript['title'],
                                selected_transcript.get('published_at', ''),
                                posts_content,
                                "linkedin"
                            )
                            st.success("LinkedIn posts generated and saved!")
                        else:
                            st.error("Could not connect to Supabase to save posts.")
                
                if generate_blog or generate_both:
                    with st.spinner("Generating blog post..."):
                        blog_post = generator.generate_blog_post_custom(
                            transcript_content, custom_voice, custom_instructions
                        )
                        
                        # Store blog post in Supabase
                        from src.storage import store_posts, build_supabase_client
                        supabase_url = st.secrets.get("SUPABASE_URL")
                        supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")
                        supabase_client = build_supabase_client(supabase_url, supabase_key)
                        
                        if supabase_client:
                            store_posts(
                                supabase_client,
                                "podcast_posts",
                                selected_transcript['guid'],
                                selected_transcript['title'],
                                selected_transcript.get('published_at', ''),
                                blog_post['content'],
                                "blog"
                            )
                            st.success("Blog post generated and saved!")
                        else:
                            st.error("Could not connect to Supabase to save posts.")
                
                st.rerun()  # Refresh the page to show new content
                
            except Exception as e:
                st.error(f"Error generating content: {e}")
                st.code(traceback.format_exc())

# Content Library
st.markdown('<h4 class="section-title">📚 Content Library</h4>', unsafe_allow_html=True)

# Two column layout for transcripts and generated content
col1, col2 = st.columns(2)

with col1:
    st.markdown('<h5 class="form-title">📝 Transcripts</h5>', unsafe_allow_html=True)
    
    if transcripts:
        for i, transcript in enumerate(transcripts):
            # Parse date
            created_at = transcript.get('created_at', '')
            published_at = transcript.get('published_at', '')
            date_to_use = published_at or created_at
            
            if date_to_use:
                try:
                    from datetime import datetime
                    if 'T' in date_to_use:
                        if date_to_use.endswith('Z'):
                            dt = datetime.fromisoformat(date_to_use.replace('Z', '+00:00'))
                        else:
                            dt = datetime.fromisoformat(date_to_use)
                    else:
                        dt = datetime.fromisoformat(date_to_use)
                    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    date_str = date_to_use or 'Unknown date'
            else:
                date_str = 'Unknown date'
            
            # Display transcript
            st.markdown(f"""
            <div class="content-display">
                <div class="content-title">{transcript['title']}</div>
                <div class="content-meta">Saved: {date_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Show transcript content with expand/collapse
            transcript_content = transcript['transcript_content']
            content_key = f"transcript_expanded_{i}"
            
            if content_key not in st.session_state:
                st.session_state[content_key] = False
            
            # Show preview or full content
            if len(transcript_content) > 1000:
                if not st.session_state[content_key]:
                    preview = transcript_content[:1000] + "..."
                    st.markdown(f'<div class="content-text">{preview}</div>', unsafe_allow_html=True)
                    if st.button(f"See More", key=f"expand_{i}"):
                        st.session_state[content_key] = True
                        st.rerun()
                else:
                    st.markdown(f'<div class="content-text">{transcript_content}</div>', unsafe_allow_html=True)
                    if st.button(f"See Less", key=f"collapse_{i}"):
                        st.session_state[content_key] = False
                        st.rerun()
            else:
                st.markdown(f'<div class="content-text">{transcript_content}</div>', unsafe_allow_html=True)
    else:
        st.info("No transcripts available. Pull some episodes first!")

with col2:
    st.markdown('<h5 class="form-title">📱 LinkedIn Posts</h5>', unsafe_allow_html=True)
    
    linkedin_posts = [p for p in posts if p.get('post_type') == 'linkedin']
    
    if linkedin_posts:
        for i, post in enumerate(linkedin_posts):
            # Parse date
            created_at = post.get('created_at', '')
            published_at = post.get('published_at', '')
            date_to_use = published_at or created_at
            
            if date_to_use:
                try:
                    from datetime import datetime
                    if 'T' in date_to_use:
                        if date_to_use.endswith('Z'):
                            dt = datetime.fromisoformat(date_to_use.replace('Z', '+00:00'))
                        else:
                            dt = datetime.fromisoformat(date_to_use)
                    else:
                        dt = datetime.fromisoformat(date_to_use)
                    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    date_str = date_to_use or 'Unknown date'
            else:
                date_str = 'Unknown date'
            
            # Display post
            st.markdown(f"""
            <div class="content-display">
                <div class="content-title">{post['title']}</div>
                <div class="content-meta">Saved: {date_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Parse and display LinkedIn posts
            posts_content = post['posts_content']
            
            # Try to split by POST_BREAK first, then fallback to ---
            if '---POST_BREAK---' in posts_content:
                individual_posts = posts_content.split('---POST_BREAK---')
            else:
                individual_posts = posts_content.split('---')
            
            for j, individual_post in enumerate(individual_posts):
                if individual_post.strip():
                    st.markdown(f'<div class="content-text">{individual_post.strip()}</div>', unsafe_allow_html=True)
                    if j < len(individual_posts) - 1:
                        st.markdown('---')
    else:
        st.info("No LinkedIn posts available. Generate some content first!")

# Blog Posts Section
st.markdown('<h5 class="form-title">📝 Blog Posts</h5>', unsafe_allow_html=True)

blog_posts = [p for p in posts if p.get('post_type') == 'blog']

if blog_posts:
    for i, post in enumerate(blog_posts):
        # Parse date
        created_at = post.get('created_at', '')
        published_at = post.get('published_at', '')
        date_to_use = published_at or created_at
        
        if date_to_use:
            try:
                from datetime import datetime
                if 'T' in date_to_use:
                    if date_to_use.endswith('Z'):
                        dt = datetime.fromisoformat(date_to_use.replace('Z', '+00:00'))
                    else:
                        dt = datetime.fromisoformat(date_to_use)
                else:
                    dt = datetime.fromisoformat(date_to_use)
                date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                date_str = date_to_use or 'Unknown date'
        else:
            date_str = 'Unknown date'
        
        # Display post
        st.markdown(f"""
        <div class="content-display">
            <div class="content-title">{post['title']}</div>
            <div class="content-meta">Saved: {date_str}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Display blog content
        blog_content = post['posts_content']
        st.markdown(f'<div class="content-text">{blog_content}</div>', unsafe_allow_html=True)
else:
    st.info("No blog posts available. Generate some content first!")

# Close main content div
st.markdown('</div>', unsafe_allow_html=True)  # Close main-content

# Logout functionality
if st.query_params.get("logout_trigger"):
    # Clear session state
    for key in ["authenticated", "login_time", "username", "session_id"]:
        if key in st.session_state:
            del st.session_state[key]
    
    # Remove session file
    try:
        Path("session_data.json").unlink(missing_ok=True)
    except Exception:
        pass
    
    # Clear query params and rerun
    st.query_params.clear()
    st.rerun()

# JavaScript for logout function
st.markdown("""
<script>
function logoutFunction() {
    // Create a hidden form to submit logout trigger
    const form = document.createElement('form');
    form.method = 'GET';
    form.action = window.location.href;
    
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'logout_trigger';
    input.value = 'true';
    
    form.appendChild(input);
    document.body.appendChild(form);
    form.submit();
}
</script>
""", unsafe_allow_html=True)

# Footer
st.markdown("""
<div style="text-align: center; padding: 2rem; color: #6b7280; font-size: 0.9rem;">
    🎙️ <strong>Podcast AI Studio</strong> - Powered by FullCortex
</div>
""", unsafe_allow_html=True)
            const url = new URL(window.location);
            url.searchParams.set('session_id', savedSessionId);
            window.location.href = url.toString();
        }
        </script>
        """, unsafe_allow_html=True)
        
        login_form()
        st.stop()
else:
    # Fallback to old session management
    if not is_authenticated():
        login_form()
        st.stop()

# User is authenticated - continue with main app

# Duplicate CSS removed - using global CSS at top of file

# Top Navigation Bar with Logout
st.markdown("""
<div class="top-nav">
    <div class="nav-title">🎙️ Podcast AI Studio</div>
    <div class="nav-logout-container">
        <button class="nav-logout" onclick="logoutFunction()">🚪 Logout</button>
    </div>
</div>
""", unsafe_allow_html=True)
# Main Content
st.markdown('<div class="main-content">', unsafe_allow_html=True)

# Initialize session state
if "last_run_output" not in st.session_state:
    st.session_state["last_run_output"] = ""
if "last_run_success" not in st.session_state:
    st.session_state["last_run_success"] = False
if "last_run_time" not in st.session_state:
    st.session_state["last_run_time"] = ""

# Load data from Supabase
def load_transcripts_from_supabase():
    """Load transcripts from Supabase and reassemble chunked content"""
    try:
        from src.storage import build_supabase_client
        
        # Check if Supabase is configured
        supabase_url = st.secrets.get("SUPABASE_URL")
        supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")
        
        if not supabase_url or not supabase_key:
            return []
        
        # Build Supabase client
        supabase_client = build_supabase_client(supabase_url, supabase_key)
        
        if not supabase_client:
            return []
        
        # Get all transcripts from Supabase
        response = supabase_client.table("podcast_transcripts").select("*").execute()
        
        if not response.data:
            return []
        
        # Group transcripts by original_guid to handle chunked content
        transcripts_dict = {}
        
        for transcript in response.data:
            # Use original_guid if available (for chunked content), otherwise use guid
            key = transcript.get('original_guid') or transcript.get('guid')
            
            if key not in transcripts_dict:
                transcripts_dict[key] = {
                    'title': transcript.get('title', ''),
                    'transcript_content': '',
                    'published_at': transcript.get('published_at', ''),
                    'created_at': transcript.get('created_at', ''),
                    'chunks': []
                }
            
            # Add chunk information
            chunk_index = transcript.get('chunk_index', 1)
            total_chunks = transcript.get('total_chunks', 1)
            chunk_content = transcript.get('transcript_content', '')
            
            transcripts_dict[key]['chunks'].append({
                'chunk_index': chunk_index,
                'total_chunks': total_chunks,
                'content': chunk_content
            })
        
        # Reassemble chunked content and return final transcripts
        final_transcripts = []
        for key, transcript_data in transcripts_dict.items():
            # Sort chunks by chunk_index
            chunks = sorted(transcript_data['chunks'], key=lambda x: x['chunk_index'])
            
            # Reassemble content
            full_content = ''.join([chunk['content'] for chunk in chunks])
            
            final_transcript = {
                'guid': key,
                'title': transcript_data['title'],
                'transcript_content': full_content,
                'published_at': transcript_data['published_at'],
                'created_at': transcript_data['created_at'],
                'total_chunks': chunks[0]['total_chunks'] if chunks else 1
            }
            
            final_transcripts.append(final_transcript)
        
        # Sort by published_at or created_at (newest first)
        final_transcripts.sort(key=lambda x: x.get('published_at') or x.get('created_at') or '', reverse=True)
        
        return final_transcripts
        
    except Exception as e:
        print(f"Error loading transcripts from Supabase: {e}")
        return []

def load_posts_from_supabase():
    """Load posts from Supabase"""
    try:
        from src.storage import build_supabase_client
        
        # Check if Supabase is configured
        supabase_url = st.secrets.get("SUPABASE_URL")
        supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")
        
        if not supabase_url or not supabase_key:
            return []
        
        # Build Supabase client
        supabase_client = build_supabase_client(supabase_url, supabase_key)
        
        if not supabase_client:
            return []
        
        # Get all posts from Supabase
        response = supabase_client.table("podcast_posts").select("*").execute()
        
        if not response.data:
            return []
        
        # Sort by published_at or created_at (newest first)
        posts = sorted(response.data, key=lambda x: x.get('published_at') or x.get('created_at') or '', reverse=True)
        
        return posts
        
    except Exception as e:
        print(f"Error loading posts from Supabase: {e}")
        return []

# Load data from Supabase
transcripts = load_transcripts_from_supabase()
posts = load_posts_from_supabase()

# Status Dashboard
st.markdown("""
<div class="status-dashboard">
    <div class="status-card">
        <div class="status-title">☁️ Cloud Storage</div>
        <div class="status-value">Connected</div>
    </div>
    <div class="status-card">
        <div class="status-title">📝 Transcripts</div>
        <div class="status-value">{}</div>
    </div>
    <div class="status-card">
        <div class="status-title">📱 LinkedIn Posts</div>
        <div class="status-value">{}</div>
    </div>
</div>
""".format(len(transcripts), len(posts)), unsafe_allow_html=True)

# Content Generation Section
st.markdown('<h4 class="section-title">🎯 Content Generation</h4>', unsafe_allow_html=True)

# Voice and tone input
st.markdown('<div class="generation-form">', unsafe_allow_html=True)
st.markdown('<div class="form-title">Voice & Tone</div>', unsafe_allow_html=True)
custom_voice = st.text_area(
    "Describe your desired voice and tone for content generation:",
    placeholder="e.g., Professional, friendly, authoritative, conversational...",
    key="custom_voice_global"
)

# Additional instructions
st.markdown('<div class="form-title">Additional Instructions</div>', unsafe_allow_html=True)
custom_instructions = st.text_area(
    "Any specific instructions for content generation:",
    placeholder="e.g., Focus on key takeaways, include call-to-action, use specific examples...",
    key="custom_instructions_global"
)

# Transcript selector
st.markdown('<div class="form-title">Select Transcript</div>', unsafe_allow_html=True)
if transcripts:
    transcript_options = [f"{t['title']} - {t.get('published_at', t.get('created_at', 'Unknown date'))}" for t in transcripts]
    selected_transcript_idx = st.selectbox(
        "Select transcript to generate content from:",
        range(len(transcript_options)),
        format_func=lambda x: transcript_options[x],
        key="transcript_selector_global"
    )
else:
    st.info("No transcripts available. Pull some episodes first!")
    selected_transcript_idx = None

# Generate content buttons
st.markdown('<div class="form-actions">', unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)

with col1:
    generate_linkedin = st.button("📱 Generate LinkedIn Posts", key="generate_linkedin_global")

with col2:
    generate_blog = st.button("📝 Generate Blog Post", key="generate_blog_global")

with col3:
    generate_both = st.button("🚀 Generate Both", key="generate_both_global")

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)  # Close generation-form

# Content generation logic
if selected_transcript_idx is not None and (generate_linkedin or generate_blog or generate_both):
    if not custom_voice.strip():
        st.error("Please enter your desired voice and tone before generating content.")
    else:
        selected_transcript = transcripts[selected_transcript_idx]
        transcript_content = selected_transcript['transcript_content']
        
        # Check if OpenAI key is available
        openai_key = st.secrets.get("OPENAI_API_KEY")
        if not openai_key:
            st.error("OpenAI API key not found in secrets. Please configure it first.")
        else:
            try:
                from src.content_generator import ContentGenerator
                generator = ContentGenerator(openai_key)
                
                if generate_linkedin or generate_both:
                    with st.spinner("Generating LinkedIn posts..."):
                        linkedin_posts = generator.generate_linkedin_posts_custom(
                            transcript_content, custom_voice, custom_instructions
                        )
                        
                        # Store LinkedIn posts in Supabase
                        from src.storage import store_posts, build_supabase_client
                        supabase_url = st.secrets.get("SUPABASE_URL")
                        supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")
                        supabase_client = build_supabase_client(supabase_url, supabase_key)
                        
                        if supabase_client:
                            posts_content = "---POST_BREAK---".join(linkedin_posts)
                            store_posts(
                                supabase_client,
                                "podcast_posts",
                                selected_transcript['guid'],
                                selected_transcript['title'],
                                selected_transcript.get('published_at', ''),
                                posts_content,
                                "linkedin"
                            )
                            st.success("LinkedIn posts generated and saved!")
                        else:
                            st.error("Could not connect to Supabase to save posts.")
                
                if generate_blog or generate_both:
                    with st.spinner("Generating blog post..."):
                        blog_post = generator.generate_blog_post_custom(
                            transcript_content, custom_voice, custom_instructions
                        )
                        
                        # Store blog post in Supabase
                        from src.storage import store_posts, build_supabase_client
                        supabase_url = st.secrets.get("SUPABASE_URL")
                        supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")
                        supabase_client = build_supabase_client(supabase_url, supabase_key)
                        
                        if supabase_client:
                            store_posts(
                                supabase_client,
                                "podcast_posts",
                                selected_transcript['guid'],
                                selected_transcript['title'],
                                selected_transcript.get('published_at', ''),
                                blog_post['content'],
                                "blog"
                            )
                            st.success("Blog post generated and saved!")
                        else:
                            st.error("Could not connect to Supabase to save posts.")
                
                st.rerun()  # Refresh the page to show new content
                
            except Exception as e:
                st.error(f"Error generating content: {e}")
                st.code(traceback.format_exc())

# Content Library
st.markdown('<h4 class="section-title">📚 Content Library</h4>', unsafe_allow_html=True)

# Two column layout for transcripts and generated content
col1, col2 = st.columns(2)

with col1:
    st.markdown('<h5 class="form-title">📝 Transcripts</h5>', unsafe_allow_html=True)
    
    if transcripts:
        for i, transcript in enumerate(transcripts):
            # Parse date
            created_at = transcript.get('created_at', '')
            published_at = transcript.get('published_at', '')
            date_to_use = published_at or created_at
            
            if date_to_use:
                try:
                    from datetime import datetime
                    if 'T' in date_to_use:
                        if date_to_use.endswith('Z'):
                            dt = datetime.fromisoformat(date_to_use.replace('Z', '+00:00'))
                        else:
                            dt = datetime.fromisoformat(date_to_use)
                    else:
                        dt = datetime.fromisoformat(date_to_use)
                    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    date_str = date_to_use or 'Unknown date'
            else:
                date_str = 'Unknown date'
            
            # Display transcript
            st.markdown(f"""
            <div class="content-display">
                <div class="content-title">{transcript['title']}</div>
                <div class="content-meta">Saved: {date_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Show transcript content with expand/collapse
            transcript_content = transcript['transcript_content']
            content_key = f"transcript_expanded_{i}"
            
            if content_key not in st.session_state:
                st.session_state[content_key] = False
            
            # Show preview or full content
            if len(transcript_content) > 1000:
                if not st.session_state[content_key]:
                    preview = transcript_content[:1000] + "..."
                    st.markdown(f'<div class="content-text">{preview}</div>', unsafe_allow_html=True)
                    if st.button(f"See More", key=f"expand_{i}"):
                        st.session_state[content_key] = True
                        st.rerun()
                else:
                    st.markdown(f'<div class="content-text">{transcript_content}</div>', unsafe_allow_html=True)
                    if st.button(f"See Less", key=f"collapse_{i}"):
                        st.session_state[content_key] = False
                        st.rerun()
            else:
                st.markdown(f'<div class="content-text">{transcript_content}</div>', unsafe_allow_html=True)
    else:
        st.info("No transcripts available. Pull some episodes first!")

with col2:
    st.markdown('<h5 class="form-title">📱 LinkedIn Posts</h5>', unsafe_allow_html=True)
    
    linkedin_posts = [p for p in posts if p.get('post_type') == 'linkedin']
    
    if linkedin_posts:
        for i, post in enumerate(linkedin_posts):
            # Parse date
            created_at = post.get('created_at', '')
            published_at = post.get('published_at', '')
            date_to_use = published_at or created_at
            
            if date_to_use:
                try:
                    from datetime import datetime
                    if 'T' in date_to_use:
                        if date_to_use.endswith('Z'):
                            dt = datetime.fromisoformat(date_to_use.replace('Z', '+00:00'))
                        else:
                            dt = datetime.fromisoformat(date_to_use)
                    else:
                        dt = datetime.fromisoformat(date_to_use)
                    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    date_str = date_to_use or 'Unknown date'
            else:
                date_str = 'Unknown date'
            
            # Display post
            st.markdown(f"""
            <div class="content-display">
                <div class="content-title">{post['title']}</div>
                <div class="content-meta">Saved: {date_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Parse and display LinkedIn posts
            posts_content = post['posts_content']
            
            # Try to split by POST_BREAK first, then fallback to ---
            if '---POST_BREAK---' in posts_content:
                individual_posts = posts_content.split('---POST_BREAK---')
            else:
                individual_posts = posts_content.split('---')
            
            for j, individual_post in enumerate(individual_posts):
                if individual_post.strip():
                    st.markdown(f'<div class="content-text">{individual_post.strip()}</div>', unsafe_allow_html=True)
                    if j < len(individual_posts) - 1:
                        st.markdown('---')
    else:
        st.info("No LinkedIn posts available. Generate some content first!")

# Blog Posts Section
st.markdown('<h5 class="form-title">📝 Blog Posts</h5>', unsafe_allow_html=True)

blog_posts = [p for p in posts if p.get('post_type') == 'blog']

if blog_posts:
    for i, post in enumerate(blog_posts):
        # Parse date
        created_at = post.get('created_at', '')
        published_at = post.get('published_at', '')
        date_to_use = published_at or created_at
        
        if date_to_use:
            try:
                from datetime import datetime
                if 'T' in date_to_use:
                    if date_to_use.endswith('Z'):
                        dt = datetime.fromisoformat(date_to_use.replace('Z', '+00:00'))
                    else:
                        dt = datetime.fromisoformat(date_to_use)
                else:
                    dt = datetime.fromisoformat(date_to_use)
                date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                date_str = date_to_use or 'Unknown date'
        else:
            date_str = 'Unknown date'
        
        # Display post
        st.markdown(f"""
        <div class="content-display">
            <div class="content-title">{post['title']}</div>
            <div class="content-meta">Saved: {date_str}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Display blog content
        blog_content = post['posts_content']
        st.markdown(f'<div class="content-text">{blog_content}</div>', unsafe_allow_html=True)
else:
    st.info("No blog posts available. Generate some content first!")

# Close main content div
st.markdown('</div>', unsafe_allow_html=True)  # Close main-content

# Logout functionality
if st.query_params.get("logout_trigger"):
    # Clear session state
    for key in ["authenticated", "login_time", "username", "session_id"]:
        if key in st.session_state:
            del st.session_state[key]
    
    # Remove session file
    try:
        Path("session_data.json").unlink(missing_ok=True)
    except Exception:
        pass
    
    # Clear query params and rerun
    st.query_params.clear()
    st.rerun()

# JavaScript for logout function
st.markdown("""
<script>
function logoutFunction() {
    // Create a hidden form to submit logout trigger
    const form = document.createElement('form');
    form.method = 'GET';
    form.action = window.location.href;
    
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'logout_trigger';
    input.value = 'true';
    
    form.appendChild(input);
    document.body.appendChild(form);
    form.submit();
}
</script>
""", unsafe_allow_html=True)

# Footer
st.markdown("""
<div style="text-align: center; padding: 2rem; color: #6b7280; font-size: 0.9rem;">
    🎙️ <strong>Podcast AI Studio</strong> - Powered by FullCortex
</div>
""", unsafe_allow_html=True)

# JavaScript to force selectbox text color - Nuclear approach
st.markdown("""
<script>
// Nuclear function to fix ALL selectbox text colors
function fixSelectboxTextColor() {
    console.log('Fixing selectbox colors...');
    
    // Target every possible selectbox element
    const allSelectboxes = document.querySelectorAll('*');
    
    allSelectboxes.forEach(element => {
        // Check if this element is part of a selectbox
        const isSelectbox = element.closest('[data-testid="stSelectbox"]') || 
                           element.closest('.stSelectbox') ||
                           element.hasAttribute('data-baseweb') ||
                           element.classList.contains('stSelectbox');
        
        if (isSelectbox) {
            // Force dark color on this element
            element.style.setProperty('color', '#1e293b', 'important');
            element.style.setProperty('font-weight', '600', 'important');
            
            // Also fix any child elements
            const children = element.querySelectorAll('*');
            children.forEach(child => {
                child.style.setProperty('color', '#1e293b', 'important');
                child.style.setProperty('font-weight', '600', 'important');
            });
        }
    });
    
    // Specifically target the problematic elements from the console
    const specificTargets = [
        'h4[id*="gpt"]',
        'h4[style*="rgb(243, 244, 246)"]',
        'p[style*="rgb(156, 163, 175)"]'
    ];
    
    specificTargets.forEach(selector => {
        const elements = document.querySelectorAll(selector);
        elements.forEach(el => {
            el.style.setProperty('color', '#1e293b', 'important');
            el.style.setProperty('font-weight', '600', 'important');
            console.log('Fixed element:', el);
        });
    });
}

// Run immediately and continuously
fixSelectboxTextColor();

// Run on page load
document.addEventListener('DOMContentLoaded', fixSelectboxTextColor);
window.addEventListener('load', fixSelectboxTextColor);

// Aggressive MutationObserver
const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
        if (mutation.type === 'childList' || mutation.type === 'attributes') {
            setTimeout(fixSelectboxTextColor, 50);
        }
    });
});

observer.observe(document.body, { 
    childList: true, 
    subtree: true, 
    attributes: true,
    attributeFilter: ['style', 'class', 'id']
});

// Run every 500ms to catch stubborn elements
setInterval(fixSelectboxTextColor, 500);
</script>
""", unsafe_allow_html=True)

# Top Navigation Bar with Logout
st.markdown("""
<div class="top-nav">
    <div class="nav-title">🎙️ Podcast AI Studio</div>
    <div class="nav-logout-container">
        <button class="logout-btn" onclick="logoutFunction()">🚪 Logout</button>
    </div>
</div>

<script>
function logoutFunction() {
    // Create a hidden form to submit logout
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = window.location.href;
    
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'logout_trigger';
    input.value = 'true';
    
    form.appendChild(input);
    document.body.appendChild(form);
    form.submit();
}
</script>
""", unsafe_allow_html=True)

# Handle logout via query parameters
if st.query_params.get("logout_trigger"):
    if USE_SUPABASE_SESSIONS:
        # Use new session manager logout
        from src.session_manager import session_manager
        session_manager.logout()
    else:
        # Fallback logout
        for key in ["authenticated", "login_time", "username"]:
            if key in st.session_state:
                del st.session_state[key]
        
        # Remove session file
        try:
            Path("session_data.json").unlink(missing_ok=True)
        except Exception:
            pass
    
    st.rerun()

# Main Content
st.markdown('<div class="main-content">', unsafe_allow_html=True)

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
except Exception as e:
    st.error(f"❌ Import error: {str(e)}")
    st.code(traceback.format_exc())
    st.warning("Some features may not work. Check the error above.")

def load_transcripts_from_supabase():
    """Load transcripts from Supabase and reassemble chunked content"""
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
        
        if not result.data:
            return []
        
        # Group chunks by original_guid and reassemble
        transcripts_by_guid = {}
        for record in result.data:
            original_guid = record.get('original_guid', record.get('guid'))
            chunk_index = record.get('chunk_index', 1)
            total_chunks = record.get('total_chunks', 1)
            
            # If this is a chunked transcript (total_chunks > 1)
            if total_chunks > 1:
                if original_guid not in transcripts_by_guid:
                    # Clean title by removing chunk info
                    clean_title = record.get('title', '')
                    if ' (Part ' in clean_title:
                        clean_title = clean_title.split(' (Part ')[0]
                    
                    transcripts_by_guid[original_guid] = {
                        'guid': original_guid,
                        'title': clean_title,
                        'published_at': record.get('published_at'),
                        'transcript_content': '',
                        'chunks': []
                    }
                
                # Store chunk info
                chunk_content = record.get('transcript_content', '')
                transcripts_by_guid[original_guid]['chunks'].append({
                    'index': chunk_index,
                    'total': total_chunks,
                    'content': chunk_content
                })
            else:
                # This is a non-chunked transcript, treat as individual record
                clean_title = record.get('title', '')
                if ' (Part ' in clean_title:
                    clean_title = clean_title.split(' (Part ')[0]
                
                transcripts_by_guid[record.get('guid')] = {
                    'guid': record.get('guid'),
                    'title': clean_title,
                    'published_at': record.get('published_at'),
                    'transcript_content': record.get('transcript_content', ''),
                    'chunks': []
                }
        
        # Reassemble chunks in correct order
        reassembled_transcripts = []
        for guid, transcript_data in transcripts_by_guid.items():
            if transcript_data['chunks']:
                # This is a chunked transcript, reassemble
                chunks = transcript_data['chunks']
                chunks.sort(key=lambda x: x['index'])  # Sort by chunk index
                
                # Reassemble content
                full_content = ' '.join([chunk['content'] for chunk in chunks])
                transcript_data['transcript_content'] = full_content
            
            # Remove chunks info for display
            del transcript_data['chunks']
            reassembled_transcripts.append(transcript_data)
        
        return reassembled_transcripts
            
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
# Process monitoring section removed for cleaner UI

# System Status Dashboard
supabase_url = st.secrets.get("SUPABASE_URL")
supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")

# Load data counts
try:
    transcripts = load_transcripts_from_supabase()
    transcript_count = len(transcripts)
except:
    transcript_count = 0

try:
    posts = load_posts_from_supabase()
    posts_count = len(posts)
except:
    posts_count = 0

# Status dashboard
st.markdown("""
<div class="status-dashboard">
    <div class="status-card">
        <div class="status-icon">☁️</div>
        <div class="status-title">Cloud Storage</div>
        <div class="status-value">{cloud_status}</div>
    </div>
    <div class="status-card">
        <div class="status-icon">📝</div>
        <div class="status-title">Transcripts</div>
        <div class="status-value">{transcript_count}</div>
    </div>
    <div class="status-card">
        <div class="status-icon">📱</div>
        <div class="status-title">Generated Content</div>
        <div class="status-value">{posts_count}</div>
    </div>
</div>
""".format(
    cloud_status="✅ Connected" if (supabase_url and supabase_key) else "❌ Disconnected",
    transcript_count=transcript_count,
    posts_count=posts_count
), unsafe_allow_html=True)
# Main Content Section
st.markdown('<h2 class="section-title">📚 Content Library</h2>', unsafe_allow_html=True)

# Content Generation Section (Always Visible)
st.markdown('<div class="generation-form">', unsafe_allow_html=True)
st.markdown('<h3 class="form-title">🎨 Generate Content</h3>', unsafe_allow_html=True)

# Voice and tone input
st.markdown('<div class="form-row">', unsafe_allow_html=True)

# Custom voice and tone input
custom_voice = st.text_area(
    "Voice & Tone Description", 
    placeholder="Describe your desired voice and tone. For example:\n• Professional and authoritative\n• Friendly and conversational\n• Expert and technical\n• Inspiring and motivational\n• Analytical and data-driven",
    height=100,
    key="custom_voice_global",
    help="Describe how you want the content to sound and feel. Be specific about the style, tone, and approach you want."
)

# Additional custom instructions
custom_instructions = st.text_area(
    "Additional Instructions (Optional)", 
    placeholder="Add any specific requirements:\n• Use more technical terms\n• Include specific examples\n• Focus on certain topics\n• Target a specific audience",
    height=100,
    key="custom_instructions_global",
    help="Add any specific requirements or guidelines for the content generation."
)

st.markdown('</div>', unsafe_allow_html=True)

# Content generation buttons
st.markdown('<div class="form-actions">', unsafe_allow_html=True)

# Get selected transcript for generation
transcripts = load_transcripts_from_supabase()
if transcripts:
    transcript_options = []
    for i, transcript in enumerate(transcripts):
        episode_title = transcript.get('title', 'Unknown Episode')
        created_at = transcript.get('created_at', '')
        published_at = transcript.get('published_at', '')
        date_to_use = published_at or created_at
        
        if date_to_use:
            try:
                from datetime import datetime
                if 'T' in date_to_use:
                    if date_to_use.endswith('Z'):
                        dt = datetime.fromisoformat(date_to_use.replace('Z', '+00:00'))
                    else:
                        dt = datetime.fromisoformat(date_to_use)
                else:
                    dt = datetime.fromisoformat(date_to_use)
                date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                print(f"Date parsing error: {e}, raw date: {date_to_use}")
                date_str = date_to_use or 'Unknown date'
        else:
            date_str = 'Unknown date'
        
        transcript_options.append(f"{episode_title} ({date_str})")
    
    selected_transcript_idx = st.selectbox("Select transcript to generate content from", range(len(transcript_options)), format_func=lambda x: transcript_options[x], key="global_transcript_selector")
    
    if selected_transcript_idx is not None and selected_transcript_idx < len(transcripts):
        selected_transcript = transcripts[selected_transcript_idx]
        transcript_content = selected_transcript.get('transcript_content', 'No content available')
        episode_title = selected_transcript.get('title', 'Unknown Episode')
        
        # Prepare voice and instructions for generation
        voice_to_use = custom_voice.strip() if custom_voice.strip() else "Professional and authoritative"
        additional_instructions = custom_instructions.strip() if custom_instructions.strip() else ""
        
        # Show transcript length info
        st.info(f"📊 Transcript length: {len(transcript_content):,} characters (will be processed using intelligent chunking if needed)")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📱 Generate LinkedIn Posts", key="global_linkedin", type="primary", use_container_width=True):
                try:
                    from src.content_generator import ContentGenerator
                    generator = ContentGenerator()
                    
                    with st.spinner("Generating LinkedIn posts..."):
                        st.write(f"Using voice: {voice_to_use[:50]}...")
                        st.write(f"Instructions: {additional_instructions[:50] if additional_instructions else 'None'}...")
                        
                        posts = generator.generate_linkedin_posts_custom(transcript_content, voice_to_use, additional_instructions, 3)
                    
                    if posts:
                        st.success(f"Generated {len(posts)} LinkedIn posts!")
                        
                        # Display the generated posts
                        for i, post in enumerate(posts, 1):
                            st.markdown(f"**LinkedIn Post {i}:**")
                            st.markdown(post)
                            st.markdown("---")
                        
                        # Store posts in Supabase
                        from src.storage import build_supabase_client, store_posts
                        supabase_url = st.secrets.get("SUPABASE_URL")
                        supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")
                        
                        if supabase_url and supabase_key:
                            supabase_client = build_supabase_client(supabase_url, supabase_key)
                            if supabase_client:
                                posts_text = "\n\n---\n\n".join(posts)
                                store_posts(supabase_client, "podcast_posts", 
                                          f"{selected_transcript.get('guid')}_linkedin", 
                                          f"{episode_title} - LinkedIn Posts",
                                          None, posts_text, "linkedin")
                                st.success("LinkedIn posts saved to database!")
                    else:
                        st.error("No posts were generated. Please check your input and try again.")
                except Exception as e:
                    st.error(f"Error generating LinkedIn posts: {e}")
                    import traceback
                    st.code(traceback.format_exc())
                    
                    # Additional debugging
                    st.write("Debug info:")
                    st.write(f"Transcript content length: {len(transcript_content)}")
                    st.write(f"Voice: {voice_to_use}")
                    st.write(f"Instructions: {additional_instructions}")
                    
                    # Check if OpenAI API key is available
                    try:
                        openai_key = st.secrets.get("OPENAI_API_KEY")
                        if openai_key:
                            st.write(f"OpenAI API key found: {openai_key[:10]}...")
                        else:
                            st.error("OpenAI API key not found in secrets!")
                    except Exception as key_error:
                        st.error(f"Error checking API key: {key_error}")
        
        with col2:
            if st.button("📝 Generate Blog Post", key="global_blog", type="primary", use_container_width=True):
                try:
                    from src.content_generator import ContentGenerator
                    generator = ContentGenerator()
                    
                    with st.spinner("Generating blog post..."):
                        st.write(f"Using voice: {voice_to_use[:50]}...")
                        st.write(f"Instructions: {additional_instructions[:50] if additional_instructions else 'None'}...")
                        
                        blog_data = generator.generate_blog_post_custom(transcript_content, voice_to_use, additional_instructions)
                    
                    if blog_data:
                        st.success("Blog post generated!")
                        
                        # Display the generated blog post
                        st.markdown(f"## {blog_data['title']}")
                        st.markdown(blog_data['content'])
                        st.markdown(f"**Tags:** {', '.join(blog_data['tags'])}")
                        
                        # Store blog post in Supabase
                        from src.storage import build_supabase_client, store_posts
                        supabase_url = st.secrets.get("SUPABASE_URL")
                        supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")
                        
                        if supabase_url and supabase_key:
                            supabase_client = build_supabase_client(supabase_url, supabase_key)
                            if supabase_client:
                                blog_content = f"# {blog_data['title']}\n\n{blog_data['content']}\n\n**Tags:** {', '.join(blog_data['tags'])}"
                                store_posts(supabase_client, "podcast_posts", 
                                          f"{selected_transcript.get('guid')}_blog", 
                                          blog_data['title'],
                                          None, blog_content, "blog")
                                st.success("Blog post saved to database!")
                    else:
                        st.error("No blog post was generated. Please check your input and try again.")
                except Exception as e:
                    st.error(f"Error generating blog post: {e}")
                    import traceback
                    st.code(traceback.format_exc())
                    
                    # Additional debugging
                    st.write("Debug info:")
                    st.write(f"Transcript content length: {len(transcript_content)}")
                    st.write(f"Voice: {voice_to_use}")
                    st.write(f"Instructions: {additional_instructions}")
                    
                    # Check if OpenAI API key is available
                    try:
                        openai_key = st.secrets.get("OPENAI_API_KEY")
                        if openai_key:
                            st.write(f"OpenAI API key found: {openai_key[:10]}...")
                        else:
                            st.error("OpenAI API key not found in secrets!")
                    except Exception as key_error:
                        st.error(f"Error checking API key: {key_error}")
        
        with col3:
            if st.button("🚀 Generate Both", key="global_both", type="primary", use_container_width=True):
                try:
                    from src.content_generator import ContentGenerator
                    generator = ContentGenerator()
                    
                    with st.spinner("Generating both LinkedIn posts and blog post..."):
                        st.write(f"Using voice: {voice_to_use[:50]}...")
                        st.write(f"Instructions: {additional_instructions[:50] if additional_instructions else 'None'}...")
                        
                        posts = generator.generate_linkedin_posts_custom(transcript_content, voice_to_use, additional_instructions, 3)
                        blog_data = generator.generate_blog_post_custom(transcript_content, voice_to_use, additional_instructions)
                    
                    if posts and blog_data:
                        st.success("Both LinkedIn posts and blog post generated!")
                        
                        # Display LinkedIn posts
                        st.markdown("### 📱 LinkedIn Posts")
                        for i, post in enumerate(posts, 1):
                            st.markdown(f"**Post {i}:**")
                            st.markdown(post)
                            st.markdown("---")
                        
                        # Display blog post
                        st.markdown("### 📝 Blog Post")
                        st.markdown(f"## {blog_data['title']}")
                        st.markdown(blog_data['content'])
                        st.markdown(f"**Tags:** {', '.join(blog_data['tags'])}")
                        
                        # Store both in Supabase
                        from src.storage import build_supabase_client, store_posts
                        supabase_url = st.secrets.get("SUPABASE_URL")
                        supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")
                        
                        if supabase_url and supabase_key:
                            supabase_client = build_supabase_client(supabase_url, supabase_key)
                            if supabase_client:
                                # Store LinkedIn posts
                                posts_text = "\n\n---\n\n".join(posts)
                                store_posts(supabase_client, "podcast_posts", 
                                          f"{selected_transcript.get('guid')}_linkedin", 
                                          f"{episode_title} - LinkedIn Posts",
                                          None, posts_text, "linkedin")
                                
                                # Store blog post
                                blog_content = f"# {blog_data['title']}\n\n{blog_data['content']}\n\n**Tags:** {', '.join(blog_data['tags'])}"
                                store_posts(supabase_client, "podcast_posts", 
                                          f"{selected_transcript.get('guid')}_blog", 
                                          blog_data['title'],
                                          None, blog_content, "blog")
                                
                                st.success("Both saved to database!")
                    else:
                        st.error("Failed to generate content. Please check your input and try again.")
                except Exception as e:
                    st.error(f"Error generating content: {e}")
                    import traceback
                    st.code(traceback.format_exc())
                    
                    # Additional debugging
                    st.write("Debug info:")
                    st.write(f"Transcript content length: {len(transcript_content)}")
                    st.write(f"Voice: {voice_to_use}")
                    st.write(f"Instructions: {additional_instructions}")
                    
                    # Check if OpenAI API key is available
                    try:
                        openai_key = st.secrets.get("OPENAI_API_KEY")
                        if openai_key:
                            st.write(f"OpenAI API key found: {openai_key[:10]}...")
                        else:
                            st.error("OpenAI API key not found in secrets!")
                    except Exception as key_error:
                        st.error(f"Error checking API key: {key_error}")
else:
    st.info("No transcripts available for content generation.")

st.markdown('</div>', unsafe_allow_html=True)  # Close form-actions
st.markdown('</div>', unsafe_allow_html=True)  # Close generation-form

# Two column layout for transcripts and content
st.markdown('<div class="two-column">', unsafe_allow_html=True)

# Left: transcripts list
st.markdown('<div>', unsafe_allow_html=True)
st.markdown('<h3 class="section-title" style="font-size: 1.1rem; margin-bottom: 1rem;">📝 Podcast Transcripts</h3>', unsafe_allow_html=True)

# Load transcripts from Supabase
transcripts = load_transcripts_from_supabase()

if not transcripts:
    st.info("No transcripts yet.")
else:
    # Create options for selectbox
    transcript_options = []
    for transcript in transcripts:
        episode_title = transcript.get('title', 'Unknown Episode')
        # Try different date fields
        created_at = transcript.get('created_at', '')
        published_at = transcript.get('published_at', '')
        
        # Use published_at if available, otherwise created_at
        date_to_use = published_at or created_at
        
        if date_to_use:
            try:
                from datetime import datetime
                # Handle different date formats
                if 'T' in date_to_use:
                    # ISO format with T
                    if date_to_use.endswith('Z'):
                        dt = datetime.fromisoformat(date_to_use.replace('Z', '+00:00'))
                    else:
                        dt = datetime.fromisoformat(date_to_use)
                else:
                    # Try parsing as regular date
                    dt = datetime.fromisoformat(date_to_use)
                date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                print(f"Date parsing error: {e}, raw date: {date_to_use}")
                date_str = date_to_use or 'Unknown date'
        else:
            date_str = 'Unknown date'
        
        transcript_options.append(f"{episode_title} ({date_str})")
    
    selected_idx = st.selectbox("Select transcript", range(len(transcript_options)), format_func=lambda x: transcript_options[x])
    
    if selected_idx is not None and selected_idx < len(transcripts):
        selected_transcript = transcripts[selected_idx]
        episode_title = selected_transcript.get('title', 'Unknown Episode')
        transcript_content = selected_transcript.get('transcript_content', 'No content available')
        # Try different date fields
        created_at = selected_transcript.get('created_at', '')
        published_at = selected_transcript.get('published_at', '')
        
        # Use published_at if available, otherwise created_at
        date_to_use = published_at or created_at
        
        if date_to_use:
            try:
                from datetime import datetime
                # Handle different date formats
                if 'T' in date_to_use:
                    # ISO format with T
                    if date_to_use.endswith('Z'):
                        dt = datetime.fromisoformat(date_to_use.replace('Z', '+00:00'))
                    else:
                        dt = datetime.fromisoformat(date_to_use)
                else:
                    # Try parsing as regular date
                    dt = datetime.fromisoformat(date_to_use)
                date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                print(f"Date parsing error: {e}, raw date: {date_to_use}")
                date_str = date_to_use or 'Unknown date'
        else:
            date_str = 'Unknown date'
        
        st.markdown(f"""
        <div class="content-display" style="position: relative;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <h4 style="margin: 0 0 0.25rem 0; color: #1e293b; font-weight: 600; font-size: 0.9rem;">{episode_title}</h4>
                    <p style="margin: 0; color: #1e293b; font-size: 0.75rem;">Saved: {date_str}</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Create a unique key for this transcript's expand/collapse state
        transcript_key = f"transcript_expanded_{selected_idx}"
        
        # Check if transcript is expanded
        is_expanded = st.session_state.get(transcript_key, False)
        
        # Format transcript content with proper paragraphs
        formatted_content = transcript_content.replace('\n\n', '\n\n').replace('\n', ' ')
        
        # Show preview or full content
        if len(formatted_content) > 1000 and not is_expanded:
            preview_content = formatted_content[:1000] + "..."
            st.markdown(f"""
            <div style="background: #1f2937; padding: 1rem; border-radius: 8px; margin: 0.5rem 0; 
                       border-left: 3px solid #3b82f6; font-family: 'Courier New', monospace; 
                       white-space: pre-wrap; line-height: 1.6; color: #f3f4f6; font-size: 0.85rem;">
            {preview_content}
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("See More", key=f"expand_{selected_idx}", type="secondary", use_container_width=False):
                st.session_state[transcript_key] = True
                st.rerun()
        else:
            st.markdown(f"""
            <div style="background: #1f2937; padding: 1rem; border-radius: 8px; margin: 0.5rem 0; 
                       border-left: 3px solid #3b82f6; font-family: 'Courier New', monospace; 
                       white-space: pre-wrap; line-height: 1.6; color: #f3f4f6; font-size: 0.85rem;">
            {formatted_content}
            </div>
            """, unsafe_allow_html=True)
            
            if len(formatted_content) > 1000:
                if st.button("See Less", key=f"collapse_{selected_idx}", type="secondary", use_container_width=False):
                    st.session_state[transcript_key] = False
                    st.rerun()


st.markdown('</div>', unsafe_allow_html=True)  # Close left column

# Right: posts list
st.markdown('<div>', unsafe_allow_html=True)
st.markdown('<h3 class="section-header" style="font-size: 1.3rem; margin-bottom: 1rem;">📝 Generated Content</h3>', unsafe_allow_html=True)

# LinkedIn Posts Section
st.markdown('<h4 class="section-subtitle" style="font-size: 1.1rem; margin: 1.5rem 0 1rem 0; color: #1e293b; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem;">📱 LinkedIn Posts</h4>', unsafe_allow_html=True)

# Load LinkedIn posts from Supabase
posts = load_posts_from_supabase()

# Filter for LinkedIn posts
linkedin_posts = [p for p in posts if p.get('post_type', 'linkedin') == 'linkedin']

if not linkedin_posts:
    st.info("No LinkedIn posts yet.")
else:
    # Create options for selectbox
    post_options = []
    for post in linkedin_posts:
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
    
    selected_post_idx = st.selectbox("Select LinkedIn post", range(len(post_options)), format_func=lambda x: post_options[x])
    
    if selected_post_idx is not None and selected_post_idx < len(linkedin_posts):
        selected_post = linkedin_posts[selected_post_idx]
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
        
        st.markdown(f"""
        <div class="content-display">
            <h4 style="margin: 0 0 0.25rem 0; color: #1e293b; font-weight: 600; font-size: 0.9rem;">{episode_title}</h4>
            <p style="margin: 0; color: #1e293b; font-size: 0.75rem;">Saved: {date_str}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Split posts content and display each post separately
        if posts_content and posts_content != 'No content available':
            # Try both separators to handle different formats
            if '---POST_BREAK---' in posts_content:
                posts_list = posts_content.split('---POST_BREAK---')
            else:
                posts_list = posts_content.split('---')
            
            for i, post in enumerate(posts_list, 1):
                if post.strip():
                    st.markdown(f"""
                    <div style="background: #374151; padding: 0.75rem; border-radius: 6px; margin: 0.5rem 0; border-left: 3px solid #c4b5fd;">
                        <h4 style="margin: 0 0 0.5rem 0; color: #c4b5fd; font-weight: 600; font-size: 0.9rem;">Post {i}</h4>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(post.strip())
                    if i < len(posts_list):
                        st.markdown("---")
        else:
            st.markdown("No content available")

# Blog Posts Section
st.markdown('<h4 class="section-subtitle" style="font-size: 1.1rem; margin: 1.5rem 0 1rem 0; color: #1e293b; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem;">📝 Blog Posts</h4>', unsafe_allow_html=True)

# Load blog posts from Supabase
posts = load_posts_from_supabase()

# Filter for blog posts
blog_posts = [p for p in posts if p.get('post_type', 'linkedin') == 'blog']

if not blog_posts:
    st.info("No blog posts yet.")
else:
    # Create options for selectbox
    blog_options = []
    for post in blog_posts:
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
        
        blog_options.append(f"{episode_title} ({date_str})")
    
    selected_blog_idx = st.selectbox("Select blog post", range(len(blog_options)), format_func=lambda x: blog_options[x])
    
    if selected_blog_idx is not None and selected_blog_idx < len(blog_posts):
        selected_blog = blog_posts[selected_blog_idx]
        episode_title = selected_blog.get('title', 'Unknown Episode')
        blog_content = selected_blog.get('posts_content', 'No content available')
        created_at = selected_blog.get('created_at', '')
        
        if created_at:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                date_str = created_at
        else:
            date_str = 'Unknown date'
        
        st.markdown(f"""
        <div class="content-display">
            <h4 style="margin: 0 0 0.25rem 0; color: #1e293b; font-weight: 600; font-size: 0.9rem;">{episode_title}</h4>
            <p style="margin: 0; color: #1e293b; font-size: 0.75rem;">Saved: {date_str}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Display blog content
        if blog_content and blog_content != 'No content available':
            # Try to parse as JSON first, then extract content
            try:
                import json
                # Clean the content - remove any leading/trailing whitespace
                cleaned_content = blog_content.strip()
                
                # Try to parse as JSON
                blog_data = json.loads(cleaned_content)
                
                if isinstance(blog_data, dict) and 'content' in blog_data:
                    # Display the parsed content as markdown
                    st.markdown(blog_data['content'])
                    
                    # Also show title if available
                    if 'title' in blog_data and blog_data['title']:
                        st.markdown(f"**Title:** {blog_data['title']}")
                    
                    # Show excerpt if available
                    if 'excerpt' in blog_data and blog_data['excerpt']:
                        st.markdown(f"**Excerpt:** {blog_data['excerpt']}")
                    
                    # Show tags if available
                    if 'tags' in blog_data and blog_data['tags']:
                        tags_str = ", ".join(blog_data['tags'])
                        st.markdown(f"**Tags:** {tags_str}")
                else:
                    # If it's not a dict with content, display as is
                    st.markdown(blog_content)
            except (json.JSONDecodeError, TypeError):
                # If it's not valid JSON, display as plain text (which is what we want)
                st.markdown(blog_content)
        else:
            st.markdown("No content available")

st.markdown('</div>', unsafe_allow_html=True)  # Close right column
st.markdown('</div>', unsafe_allow_html=True)  # Close two-column layout
st.markdown('</div>', unsafe_allow_html=True)  # Close main-content

# Footer
st.markdown("""
<div style="text-align: center; padding: 2rem; color: #6b7280; font-size: 0.9rem;">
    🎙️ <strong>Podcast AI Studio</strong> - Powered by FullCortex
</div>
""", unsafe_allow_html=True)