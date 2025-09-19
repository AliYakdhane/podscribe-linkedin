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

# Helper functions
def load_transcripts_from_supabase():
    """Load transcripts from Supabase"""
    try:
        from src.storage import build_supabase_client
        supabase_url = st.secrets.get("SUPABASE_URL")
        supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")
        supabase_client = build_supabase_client(supabase_url, supabase_key)
        
        if supabase_client:
            # Fetch all transcripts
            result = supabase_client.table("podcast_transcripts").select("*").order("created_at", desc=True).execute()
            
            if result.data:
                # Group by original_guid or guid to handle chunked content
                grouped_transcripts = {}
                for record in result.data:
                    guid = record.get('original_guid') or record.get('guid')
                    if guid not in grouped_transcripts:
                        grouped_transcripts[guid] = {
                            'guid': guid,
                            'title': record['title'],
                            'published_at': record.get('published_at'),
                            'created_at': record.get('created_at'),
                            'transcript_content': '',
                            'chunks': []
                        }
                    
                    # Store chunk info
                    chunk_info = {
                        'chunk_index': record.get('chunk_index', 1),
                        'content': record['transcript_content']
                    }
                    grouped_transcripts[guid]['chunks'].append(chunk_info)
                
                # Reassemble content from chunks
                final_transcripts = []
                for guid, transcript in grouped_transcripts.items():
                    # Sort chunks by chunk_index
                    transcript['chunks'].sort(key=lambda x: x['chunk_index'])
                    
                    # Combine all chunks
                    transcript['transcript_content'] = ''.join([chunk['content'] for chunk in transcript['chunks']])
                    
                    # Remove chunks from final result
                    del transcript['chunks']
                    final_transcripts.append(transcript)
                
                return final_transcripts
            else:
                return []
        else:
            return []
    except Exception as e:
        st.error(f"Error loading transcripts: {e}")
        return []

def load_posts_from_supabase():
    """Load posts from Supabase"""
    try:
        from src.storage import build_supabase_client
        supabase_url = st.secrets.get("SUPABASE_URL")
        supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")
        supabase_client = build_supabase_client(supabase_url, supabase_key)
        
        if supabase_client:
            result = supabase_client.table("podcast_posts").select("*").order("created_at", desc=True).execute()
            return result.data if result.data else []
        else:
            return []
    except Exception as e:
        st.error(f"Error loading posts: {e}")
        return []

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

# Three column layout: transcripts, LinkedIn posts, and blog posts
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<h5 class="form-title">📝 Podcast Transcripts</h5>', unsafe_allow_html=True)
    
    # Show transcript count at the top
    if transcripts:
        st.metric("Total Transcripts", len(transcripts))
        st.markdown("---")
    
    if transcripts:
        # Transcript selector
        transcript_options = []
        for i, transcript in enumerate(transcripts):
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
                    date_str = dt.strftime('%Y-%m-%d')
                except Exception:
                    date_str = 'Unknown date'
            else:
                date_str = 'Unknown date'
            
            # Create a truncated title for the dropdown
            title = transcript['title']
            if len(title) > 50:
                title = title[:47] + "..."
            
            transcript_options.append(f"{title} ({date_str})")
        
        selected_transcript_idx = st.selectbox(
            "Select Transcript:",
            range(len(transcript_options)),
            format_func=lambda x: transcript_options[x],
            key="transcript_selector"
        )
        
        if selected_transcript_idx is not None:
            selected_transcript = transcripts[selected_transcript_idx]
            
            # Parse date for display
            created_at = selected_transcript.get('created_at', '')
            published_at = selected_transcript.get('published_at', '')
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
            
            # Display selected transcript
            st.markdown(f"""
            <div class="content-display">
                <div class="content-title">{selected_transcript['title']}</div>
                <div class="content-meta">Saved: {date_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Show transcript content with expand/collapse
            transcript_content = selected_transcript['transcript_content']
            content_key = f"transcript_expanded_{selected_transcript_idx}"
            
            if content_key not in st.session_state:
                st.session_state[content_key] = False
            
            # Show preview or full content
            if len(transcript_content) > 1000:
                if not st.session_state[content_key]:
                    preview = transcript_content[:1000] + "..."
                    st.markdown(f'<div class="content-text">{preview}</div>', unsafe_allow_html=True)
                    if st.button(f"See More", key=f"expand_{selected_transcript_idx}"):
                        st.session_state[content_key] = True
                        st.rerun()
                else:
                    st.markdown(f'<div class="content-text">{transcript_content}</div>', unsafe_allow_html=True)
                    if st.button(f"See Less", key=f"collapse_{selected_transcript_idx}"):
                        st.session_state[content_key] = False
                        st.rerun()
            else:
                st.markdown(f'<div class="content-text">{transcript_content}</div>', unsafe_allow_html=True)
        
    else:
        st.info("No transcripts available. Pull some episodes first!")

with col2:
    st.markdown('<h5 class="form-title">📱 LinkedIn Posts</h5>', unsafe_allow_html=True)
    
    # Organize posts by type
    linkedin_posts = [p for p in posts if p.get('post_type') == 'linkedin']
    
    # Show LinkedIn post count at the top
    if linkedin_posts:
        st.metric("LinkedIn Posts", len(linkedin_posts))
        st.markdown("---")
    
    if linkedin_posts:
        # LinkedIn posts selector
        linkedin_options = []
        for i, post in enumerate(linkedin_posts):
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
                    date_str = dt.strftime('%Y-%m-%d')
                except Exception:
                    date_str = 'Unknown date'
            else:
                date_str = 'Unknown date'
            
            # Create a truncated title for the dropdown
            title = post['title']
            if len(title) > 40:
                title = title[:37] + "..."
            
            linkedin_options.append(f"{title} ({date_str})")
        
        selected_linkedin_idx = st.selectbox(
            "Select LinkedIn Post:",
            range(len(linkedin_options)),
            format_func=lambda x: linkedin_options[x],
            key="linkedin_post_selector"
        )
        
        if selected_linkedin_idx is not None:
            selected_post = linkedin_posts[selected_linkedin_idx]
            
            # Display selected LinkedIn post
            created_at = selected_post.get('created_at', '')
            published_at = selected_post.get('published_at', '')
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
            
            st.markdown(f"""
            <div class="content-display">
                <div class="content-title">{selected_post['title']}</div>
                <div class="content-meta">Saved: {date_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Parse and display individual LinkedIn posts
            posts_content = selected_post['posts_content']
            
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

with col3:
    st.markdown('<h5 class="form-title">📝 Blog Posts</h5>', unsafe_allow_html=True)
    
    # Organize posts by type
    blog_posts = [p for p in posts if p.get('post_type') == 'blog']
    
    # Show blog post count at the top
    if blog_posts:
        st.metric("Blog Posts", len(blog_posts))
        st.markdown("---")
    
    if blog_posts:
        # Blog posts selector
        blog_options = []
        for i, post in enumerate(blog_posts):
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
                    date_str = dt.strftime('%Y-%m-%d')
                except Exception:
                    date_str = 'Unknown date'
            else:
                date_str = 'Unknown date'
            
            # Create a truncated title for the dropdown
            title = post['title']
            if len(title) > 40:
                title = title[:37] + "..."
            
            blog_options.append(f"{title} ({date_str})")
        
        selected_blog_idx = st.selectbox(
            "Select Blog Post:",
            range(len(blog_options)),
            format_func=lambda x: blog_options[x],
            key="blog_post_selector"
        )
        
        if selected_blog_idx is not None:
            selected_post = blog_posts[selected_blog_idx]
            
            # Display selected blog post
            created_at = selected_post.get('created_at', '')
            published_at = selected_post.get('published_at', '')
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
            
            st.markdown(f"""
            <div class="content-display">
                <div class="content-title">{selected_post['title']}</div>
                <div class="content-meta">Saved: {date_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Display blog content
            blog_content = selected_post['posts_content']
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