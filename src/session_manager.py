"""
Production-ready session management using Supabase
Replaces file-based session storage for better production compatibility
"""

import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import streamlit as st

try:
    from .storage import build_supabase_client
except ImportError:
    from storage import build_supabase_client

# Session configuration
SESSION_TIMEOUT = 3600  # 1 hour in seconds

class SupabaseSessionManager:
    def __init__(self):
        self.supabase_client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Supabase client for session storage"""
        try:
            supabase_url = st.secrets.get("SUPABASE_URL")
            supabase_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE")
            
            if supabase_url and supabase_key:
                self.supabase_client = build_supabase_client(supabase_url, supabase_key)
                if self.supabase_client:
                    print("✅ Supabase session client initialized successfully")
                    self._ensure_sessions_table()
                else:
                    print("❌ Failed to initialize Supabase session client")
            else:
                print("⚠️ Supabase credentials not found in secrets")
        except Exception as e:
            print(f"❌ Failed to initialize Supabase session client: {e}")
    
    def _ensure_sessions_table(self):
        """Ensure the sessions table exists in Supabase"""
        try:
            # Create sessions table if it doesn't exist
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                login_time TIMESTAMPTZ NOT NULL,
                last_activity TIMESTAMPTZ DEFAULT NOW(),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                expires_at TIMESTAMPTZ NOT NULL
            );
            
            -- Create index for cleanup queries
            CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON user_sessions(expires_at);
            CREATE INDEX IF NOT EXISTS idx_sessions_username ON user_sessions(username);
            """
            
            # Execute the SQL (this might need to be done manually in Supabase dashboard)
            print("Note: Ensure user_sessions table exists in Supabase with the schema above")
            
        except Exception as e:
            print(f"Error ensuring sessions table: {e}")
    
    def _generate_session_id(self, username: str, login_time: float) -> str:
        """Generate a secure session ID"""
        # Include a random component to make each session unique
        import random
        random_component = random.randint(100000, 999999)
        return hashlib.sha256(f"{username}{login_time}{random_component}".encode()).hexdigest()[:32]
    
    def create_session(self, username: str, password: str) -> bool:
        """Create a new session after successful authentication"""
        # Check username first
        if username != "admin":
            print(f"Invalid username: {username}")
            return False
        
        # Then verify password
        if not self._verify_password(password):
            print("Invalid password")
            return False
        
        try:
            from datetime import timezone
            login_time = time.time()
            session_id = self._generate_session_id(username, login_time)
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=SESSION_TIMEOUT)
            
            # Store session in Supabase
            session_data = {
                "session_id": session_id,
                "username": username,
                "login_time": now.isoformat(),
                "last_activity": now.isoformat(),
                "is_active": True,
                "expires_at": expires_at.isoformat()
            }
            
            if self.supabase_client:
                # Create new session (allow multiple sessions per user)
                result = self.supabase_client.table("user_sessions").insert(session_data).execute()
                if result.data:
                    # Update Streamlit session state
                    st.session_state.authenticated = True
                    st.session_state.login_time = login_time
                    st.session_state.username = username
                    st.session_state.session_id = session_id
                    
                    # Store session_id in browser localStorage for persistence
                    st.markdown(f"""
                    <script>
                    localStorage.setItem('podcast_session_id', '{session_id}');
                    </script>
                    """, unsafe_allow_html=True)
                    
                    # Show active sessions count
                    active_count = self.get_active_sessions_count(username)
                    print(f"✅ New session created. Total active sessions for {username}: {active_count}")
                    
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error creating session: {e}")
            return False
    
    def validate_session(self, session_id: str) -> bool:
        """Validate if a session is still active and not expired"""
        try:
            if not self.supabase_client or not session_id:
                return False
            
            # Get session from database
            result = self.supabase_client.table("user_sessions").select("*").eq("session_id", session_id).eq("is_active", True).execute()
            
            if not result.data:
                return False
            
            session_data = result.data[0]
            
            # Check if session is expired
            expires_at = datetime.fromisoformat(session_data["expires_at"].replace('Z', '+00:00'))
            # Use timezone-aware datetime for comparison (UTC)
            from datetime import timezone
            now = datetime.now(timezone.utc)
            
            if now > expires_at:
                # Session expired, deactivate it
                self._deactivate_session(session_id)
                return False
            
            # Update last activity
            self._update_last_activity(session_id)
            
            # Update Streamlit session state
            st.session_state.authenticated = True
            st.session_state.login_time = time.mktime(datetime.fromisoformat(session_data["login_time"]).timetuple())
            st.session_state.username = session_data["username"]
            st.session_state.session_id = session_id
            
            return True
            
        except Exception as e:
            print(f"Error validating session: {e}")
            return False
    
    def _update_last_activity(self, session_id: str):
        """Update the last activity timestamp for a session"""
        try:
            if self.supabase_client:
                # Use timezone-aware datetime (UTC)
                from datetime import timezone
                now = datetime.now(timezone.utc)
                self.supabase_client.table("user_sessions").update({
                    "last_activity": now.isoformat()
                }).eq("session_id", session_id).execute()
        except Exception as e:
            print(f"Error updating last activity: {e}")
    
    def _deactivate_session(self, session_id: str):
        """Deactivate a session"""
        try:
            if self.supabase_client:
                self.supabase_client.table("user_sessions").update({
                    "is_active": False
                }).eq("session_id", session_id).execute()
        except Exception as e:
            print(f"Error deactivating session: {e}")
    
    def logout(self):
        """Logout and deactivate current session"""
        try:
            session_id = st.session_state.get("session_id")
            if session_id and self.supabase_client:
                self._deactivate_session(session_id)
        except Exception as e:
            print(f"Error during logout: {e}")
        finally:
            # Clear Streamlit session state
            for key in ["authenticated", "login_time", "username", "session_id"]:
                if key in st.session_state:
                    del st.session_state[key]
            
            # Clear browser localStorage
            st.markdown("""
            <script>
            localStorage.removeItem('podcast_session_id');
            </script>
            """, unsafe_allow_html=True)
    
    def _verify_password(self, password: str) -> bool:
        """Verify password against stored hash"""
        try:
            # Use the same password verification as the old system
            import hashlib
            import hmac
            
            # Get the stored hash from secrets
            stored_hash = st.secrets.get("ADMIN_PASSWORD_HASH")
            print(f"Debug: Retrieved stored hash: {stored_hash[:10]}..." if stored_hash else "Debug: No stored hash found")
            
            if not stored_hash:
                st.error("Admin password not configured. Please set ADMIN_PASSWORD_HASH in secrets.")
                return False
            
            # Hash the provided password using SHA-256
            provided_hash = hashlib.sha256(password.encode()).hexdigest()
            print(f"Debug: Provided password hash: {provided_hash[:10]}...")
            print(f"Debug: Password match: {hmac.compare_digest(provided_hash, stored_hash)}")
            
            # Use secure comparison
            return hmac.compare_digest(provided_hash, stored_hash)
        except Exception as e:
            print(f"Password verification error: {e}")
            # Fallback for development - simple password check
            return password == "admin"
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions from database"""
        try:
            if self.supabase_client:
                # Deactivate sessions that are expired
                from datetime import timezone
                now = datetime.now(timezone.utc)
                result = self.supabase_client.table("user_sessions").update({
                    "is_active": False
                }).lt("expires_at", now.isoformat()).execute()
                if result.data:
                    print(f"Cleaned up {len(result.data)} expired sessions")
        except Exception as e:
            print(f"Error cleaning up expired sessions: {e}")
    
    def clear_all_sessions(self):
        """Clear all sessions from database (for troubleshooting)"""
        try:
            if self.supabase_client:
                result = self.supabase_client.table("user_sessions").delete().neq("session_id", "nonexistent").execute()
                print(f"Cleared {len(result.data) if result.data else 0} sessions")
                return True
            return False
        except Exception as e:
            print(f"Error clearing sessions: {e}")
            return False
    
    def get_active_sessions_count(self, username: str = "admin") -> int:
        """Get count of active sessions for a user"""
        try:
            if self.supabase_client:
                result = self.supabase_client.table("user_sessions").select("*").eq("username", username).eq("is_active", True).execute()
                count = len(result.data) if result.data else 0
                print(f"Active sessions for {username}: {count}")
                return count
            return 0
        except Exception as e:
            print(f"Error getting active sessions count: {e}")
            return 0

# Global session manager instance
session_manager = SupabaseSessionManager()

def is_authenticated() -> bool:
    """Check if user is currently authenticated"""
    try:
        # First check Streamlit session state
        if st.session_state.get("authenticated", False):
            session_id = st.session_state.get("session_id")
            if session_id and session_manager.supabase_client:
                # Validate session with database
                return session_manager.validate_session(session_id)
            elif session_id:
                # Fallback: simple session state check if Supabase not available
                return True
        return False
    except Exception as e:
        print(f"Error checking authentication: {e}")
        # Clear any invalid session state
        for key in ["authenticated", "login_time", "username", "session_id"]:
            if key in st.session_state:
                del st.session_state[key]
        return False

def login_form() -> bool:
    """Display login form and handle authentication"""
    with st.form("login_form"):
        st.markdown("### 🔐 Login Required")
        username = st.text_input("Username", value="admin")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login", type="primary"):
            if session_manager.supabase_client:
                # Use Supabase-based authentication
                if session_manager.create_session(username, password):
                    st.success("✅ Login successful!")
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials")
            else:
                # Fallback authentication when Supabase not available
                if username == "admin" and session_manager._verify_password(password):
                    st.session_state.authenticated = True
                    st.session_state.username = "admin"
                    st.session_state.session_id = "fallback_session"
                    st.success("✅ Login successful! (Fallback mode)")
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials")
    
    return False

def logout_button():
    """Display logout button"""
    if st.button("🚪 Logout", key="logout_btn"):
        session_manager.logout()
        st.success("✅ Logged out successfully!")
        st.rerun()

def initialize_session():
    """Initialize session state and try to restore from Supabase"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "login_time" not in st.session_state:
        st.session_state.login_time = 0
    if "username" not in st.session_state:
        st.session_state.username = ""
    if "session_id" not in st.session_state:
        st.session_state.session_id = ""
    
    # Try to restore session from Supabase if we have a valid session_id in query params
    if not st.session_state.authenticated and session_manager.supabase_client:
        # Only check for session_id in query parameters (from localStorage restoration)
        session_id_from_params = st.query_params.get("session_id")
        if session_id_from_params:
            if session_manager.validate_session(session_id_from_params):
                return
            else:
                # Clear invalid session_id from URL
                st.query_params.clear()
    
    # Clean up expired sessions periodically
    session_manager.cleanup_expired_sessions()
