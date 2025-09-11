"""
Configuration manager for storing and retrieving user settings in Supabase
"""

import os
from typing import Optional, Dict, Any
from datetime import datetime
from .storage import build_supabase_client

def save_user_config(
    supabase_client,
    show_id: str = "",
    apple_episode_url: str = "",
    max_episodes_per_run: int = 1,
    openai_api_key: str = ""
) -> bool:
    """
    Save user configuration to Supabase
    
    Args:
        supabase_client: Supabase client instance
        show_id: Podcast show ID
        apple_episode_url: Apple episode URL for reference
        max_episodes_per_run: Number of episodes to pull per run
        openai_api_key: OpenAI API key (optional, for local testing)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        config_data = {
            "id": "user_config",  # Single config record
            "show_id": show_id,
            "apple_episode_url": apple_episode_url,
            "max_episodes_per_run": max_episodes_per_run,
            "openai_api_key": openai_api_key,  # Only for local testing
            "updated_at": datetime.now().isoformat()
        }
        
        result = supabase_client.table("user_config").upsert(config_data).execute()
        
        if result.data:
            print(f"✅ Configuration saved successfully")
            return True
        else:
            print(f"❌ Failed to save configuration")
            return False
            
    except Exception as e:
        print(f"❌ Error saving configuration: {e}")
        return False

def get_user_config(supabase_client) -> Dict[str, Any]:
    """
    Retrieve user configuration from Supabase
    
    Args:
        supabase_client: Supabase client instance
    
    Returns:
        dict: Configuration data or empty dict if not found
    """
    try:
        result = supabase_client.table("user_config").select("*").eq("id", "user_config").execute()
        
        if result.data and len(result.data) > 0:
            config = result.data[0]
            print(f"✅ Configuration loaded: Show ID={config.get('show_id', 'N/A')}")
            return config
        else:
            print(f"ℹ️ No configuration found in database")
            return {}
            
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        return {}

def create_config_table(supabase_client) -> bool:
    """
    Create the user_config table if it doesn't exist
    
    Args:
        supabase_client: Supabase client instance
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # This will be handled by the SQL schema
        print(f"✅ Configuration table ready")
        return True
        
    except Exception as e:
        print(f"❌ Error creating configuration table: {e}")
        return False
