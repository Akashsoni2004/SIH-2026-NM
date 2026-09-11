import os
import json
import hmac
import base64
import hashlib
import time
from typing import Optional, List
from fastapi import Request, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.db import get_db, verify_password

# Secret key for HMAC token signing
AUTH_SECRET = os.environ.get("PAIMANA_AUTH_SECRET", "paimana-ai-sih-2026-secret-key-national-infrastructure")
TOKEN_EXPIRY_SECONDS = 86400 * 2 # 48 hours

security_scheme = HTTPBearer(auto_error=False)

def create_access_token(user_data: dict) -> str:
    """Generates an HMAC-SHA256 signed bearer token."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_data["id"]),
        "username": user_data["username"],
        "email": user_data["email"],
        "full_name": user_data["full_name"],
        "role": user_data["role"],
        "organization": user_data["organization"],
        "exp": int(time.time()) + TOKEN_EXPIRY_SECONDS
    }
    
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    
    data_to_sign = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(AUTH_SECRET.encode(), data_to_sign, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def verify_access_token(token: str) -> Optional[dict]:
    """Validates token signature and expiration."""
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            return None
        
        header_b64, payload_b64, sig_b64 = parts
        data_to_sign = f"{header_b64}.{payload_b64}".encode()
        
        # Verify signature
        expected_sig = hmac.new(AUTH_SECRET.encode(), data_to_sign, hashlib.sha256).digest()
        actual_sig = base64.urlsafe_b64decode(sig_b64 + "=" * (-len(sig_b64) % 4))
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
            
        # Parse payload
        payload_json = base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)).decode()
        payload = json.loads(payload_json)
        
        # Check expiration
        if payload.get("exp", 0) < time.time():
            return None
            
        return payload
    except Exception:
        return None

def get_current_user(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Security(security_scheme)
) -> dict:
    """FastAPI dependency to extract and authenticate current user."""
    token = None
    
    # 1. Try Bearer header
    if auth_header and auth_header.credentials:
        token = auth_header.credentials
        
    # 2. Try cookie or query param if not in header
    if not token:
        token = request.cookies.get("paimana_auth_token")
    if not token:
        token = request.query_params.get("token")
        
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please login with your credentials.",
            headers={"WWW-Authenticate": "Bearer"}
        )
        
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Session has expired or token is invalid. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )
        
    # Fetch live user record to verify account status
    conn = get_db()
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM users WHERE id = ?", (payload["sub"],)).fetchone()
    conn.close()
    
    if not row or not row["is_active"]:
        raise HTTPException(
            status_code=401,
            detail="User account is inactive or no longer exists."
        )
        
    user_dict = dict(row)
    del user_dict["password_hash"]
    del user_dict["salt"]
    return user_dict

def get_optional_current_user(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Security(security_scheme)
) -> Optional[dict]:
    """Optional user dependency that does not raise 401 if missing."""
    try:
        return get_current_user(request, auth_header)
    except HTTPException:
        return None

def require_roles(allowed_roles: List[str]):
    """Decorator / dependency factory for strict Role-Based Access Control (RBAC)."""
    def role_checker(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("role")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access Denied: Role '{user_role}' is not authorized to access this administrative resource."
            )
        return user
    return role_checker

def get_agency_scope(user: dict) -> Optional[str]:
    """
    Returns agency organization pattern if the user belongs to the AGENCY role.
    For ADMIN, POLICYMAKER, MONITORING, and PLANNING roles, returns None (full scope).
    """
    if user.get("role") == "AGENCY":
        org = user.get("organization", "")
        # If agency contains acronym like [NHAI] or [AAI], extract acronym for SQL LIKE
        if "[" in org and "]" in org:
            import re
            m = re.search(r'\[(.*?)\]', org)
            if m:
                return m.group(1)
        return org
    return None
