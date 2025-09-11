#!/usr/bin/env python3
"""
API endpoint for triggering podcast puller via external cron services
This can be used with services like cron-job.org, EasyCron, etc.
"""

import os
import subprocess
import json
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def trigger_podcast_pull(openai_key: str, max_episodes: int = 3) -> dict:
    """
    Trigger the podcast puller with given parameters
    
    Args:
        openai_key: OpenAI API key for transcription and post generation
        max_episodes: Maximum number of episodes to pull (default: 3)
    
    Returns:
        dict: Result of the podcast pull operation
    """
    try:
        logger.info(f"🤖 Starting automated podcast pull at {datetime.now()}")
        
        # Set up environment variables
        env = os.environ.copy()
        env["OPENAI_API_KEY"] = openai_key
        env["MAX_EPISODES_PER_RUN"] = str(max_episodes)
        
        # Add Supabase credentials if available
        if os.getenv("SUPABASE_URL"):
            env["SUPABASE_URL"] = os.getenv("SUPABASE_URL")
        if os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
            env["SUPABASE_SERVICE_ROLE_KEY"] = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        # Run the main podcast puller
        result = subprocess.run(
            ["python", "-m", "src.main"],
            env=env,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutes timeout
        )
        
        logger.info(f"✅ Podcast pull completed with return code: {result.returncode}")
        
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "output": result.stdout,
            "error": result.stderr if result.stderr else None,
            "timestamp": datetime.now().isoformat()
        }
        
    except subprocess.TimeoutExpired:
        logger.error("❌ Podcast puller timed out after 30 minutes")
        return {
            "success": False,
            "error": "Timeout: Process took longer than 30 minutes",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Podcast puller failed with error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

def main():
    """Main function for testing the API trigger"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python api_trigger.py <OPENAI_API_KEY> [MAX_EPISODES]")
        sys.exit(1)
    
    openai_key = sys.argv[1]
    max_episodes = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    
    result = trigger_podcast_pull(openai_key, max_episodes)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
