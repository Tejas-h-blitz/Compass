import os
import secrets
import hmac
import logging
from typing import Optional, Set
from fastapi import Request, HTTPException, status

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "compass_session"
COMPASS_DISABLE_AUTH = os.environ.get("COMPASS_DISABLE_AUTH", "0") == "1"

if COMPASS_DISABLE_AUTH:
    print("\n" + "=" * 60)
    print("⚠️  WARNING: COMPASS_DISABLE_AUTH=1 IS ENABLED!")
    print("   API AUTHENTICATION AND SESSION CHECKS ARE DISABLED.")
    print("   DO NOT USE IN PRODUCTION.")
    print("=" * 60 + "\n")

# In-memory storage for one-time launch codes and active session tokens
_active_launch_codes: Set[str] = set()
_active_sessions: Set[str] = set()

def generate_launch_code() -> str:
    """
    Generates a secure, random one-time launch code.
    """
    code = secrets.token_urlsafe(32)
    _active_launch_codes.add(code)
    return code

def mint_launch_url(port: int = 8000) -> str:
    """
    Mints a fresh single-use launch code and constructs the corresponding launch URL
    for the specified runtime port.
    """
    code = generate_launch_code()
    return f"http://127.0.0.1:{port}/?launch={code}"

def consume_launch_code(code: str) -> Optional[str]:
    """
    Validates the launch code using constant-time comparison.
    If valid, consumes it (single-use) and returns a newly created session token.
    Otherwise returns None.
    """
    if not code:
        return None
        
    matched_code = None
    for c in list(_active_launch_codes):
        if hmac.compare_digest(c, code):
            matched_code = c
            break
            
    if matched_code is not None:
        _active_launch_codes.discard(matched_code)
        session_token = secrets.token_urlsafe(32)
        _active_sessions.add(session_token)
        return session_token
        
    return None

def is_valid_session(token: Optional[str]) -> bool:
    """
    Validates a session token using constant-time comparison against active sessions.
    """
    if not token:
        return False
        
    for s in _active_sessions:
        if hmac.compare_digest(s, token):
            return True
    return False

def verify_session(request: Request) -> bool:
    """
    FastAPI dependency that enforces session authentication.
    Checks cookie 'compass_session' with constant-time comparison.
    Returns True if authenticated, otherwise raises HTTPException 401.
    """
    if COMPASS_DISABLE_AUTH:
        return True
        
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie_token or not is_valid_session(cookie_token):
        logger.warning(f"Unauthorized API access attempt to {request.url.path}: missing or invalid session cookie")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: invalid or missing session cookie. Open Compass from the app window."
        )
    return True

def reset_auth_state_for_testing():
    """
    Helper for automated tests to clear active launch codes and sessions.
    """
    _active_launch_codes.clear()
    _active_sessions.clear()
