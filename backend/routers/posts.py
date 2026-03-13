from fastapi import APIRouter, Depends

from backend.config import get_supabase_credentials
from backend.routers.auth import require_auth

router = APIRouter()


def _load_posts():
    url, key = get_supabase_credentials()
    if not url or not key:
        return []
    from backend.core.storage import build_supabase_client
    client = build_supabase_client(url, key)
    if not client:
        return []
    all_posts = []
    for table in ("linkedin_posts", "blog_posts"):
        try:
            r = client.table(table).select("*").order("created_at", desc=True).execute()
            if r.data:
                all_posts.extend(r.data)
        except Exception:
            pass
    if not all_posts:
        try:
            r = client.table("podcast_posts").select("*").order("created_at", desc=True).execute()
            if r.data:
                all_posts.extend(r.data)
        except Exception:
            pass
    return all_posts


@router.get("")
def list_posts(_: str = Depends(require_auth)):
    """List all posts (LinkedIn + blog)."""
    return _load_posts()
