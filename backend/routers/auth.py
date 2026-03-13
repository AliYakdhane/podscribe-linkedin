import hashlib
import time
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional

from backend.config import get_admin_password_hash

router = APIRouter()

# In-memory valid tokens: token -> expiry timestamp (for multi-worker use Redis)
_valid_tokens: dict[str, float] = {}
TOKEN_TTL_SEC = 3600 * 24  # 24 hours


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    message: Optional[str] = None


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    """Validate admin credentials. Returns a token for Authorization: Bearer <token>."""
    if body.username != "admin":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    stored_hash = get_admin_password_hash()
    if not stored_hash:
        raise HTTPException(status_code=503, detail="ADMIN_PASSWORD_HASH not configured")
    if _hash_password(body.password) != stored_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = hashlib.sha256((body.password + str(time.time()) + "podcast-ai-studio").encode()).hexdigest()
    _valid_tokens[token] = time.time() + TOKEN_TTL_SEC
    return LoginResponse(success=True, token=token)


def require_auth(authorization: Optional[str] = Header(None)) -> str:
    """Dependency: require valid Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.replace("Bearer ", "").strip()
    now = time.time()
    if token not in _valid_tokens or _valid_tokens[token] < now:
        if token in _valid_tokens:
            del _valid_tokens[token]
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return token
