"""Backend config from environment (no Streamlit)."""
import os
from pathlib import Path

# Project root (parent of backend/) so subprocess cwd finds backend package
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def get_supabase_credentials():
    url = os.getenv("SUPABASE_URL", "").strip()
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE") or ""
    ).strip()
    return url, key


def get_openai_key():
    return (os.getenv("OPENAI_API_KEY") or "").strip()


def get_admin_password_hash():
    return (os.getenv("ADMIN_PASSWORD_HASH") or "").strip()
