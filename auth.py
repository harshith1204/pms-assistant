import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel
import jwt  # PyJWT

# === Configuration ===
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "360"))

# Feature flags (default to disabled so existing dev flows continue working)
REQUIRE_AUTH_HTTP = os.getenv("REQUIRE_AUTH_HTTP", "false").lower() == "true"
REQUIRE_AUTH_WS = os.getenv("REQUIRE_AUTH_WS", "false").lower() == "true"
ALLOW_DEV_LOGIN = os.getenv("ALLOW_DEV_LOGIN", "true").lower() == "true"

# Canonical RBAC roles
CANONICAL_ROLES = {"ADMIN", "EDITOR", "VIEWER"}
ROLE_SYNONYMS = {
    "USER": "VIEWER",
    "MEMBER": "EDITOR",
    "MANAGER": "ADMIN",
}


class UserToken(BaseModel):
    sub: str
    email: Optional[str] = None
    roles: List[str] = []
    businessId: Optional[str] = None
    iat: Optional[int] = None
    exp: Optional[int] = None


def _normalize_roles(roles: Optional[List[str]]) -> List[str]:
    if not roles:
        return []
    result: List[str] = []
    for r in roles:
        if not r:
            continue
        name = str(r).strip().upper()
        # map synonyms
        name = ROLE_SYNONYMS.get(name, name)
        if name in CANONICAL_ROLES and name not in result:
            result.append(name)
    return result


def _has_any_role(user_roles: List[str], required_roles: List[str]) -> bool:
    roles_norm = _normalize_roles(user_roles)
    required_norm = _normalize_roles(required_roles)
    if not required_norm:
        return True
    # ADMIN is superuser
    if "ADMIN" in roles_norm:
        return True
    return any(r in roles_norm for r in required_norm)


def create_access_token(
    *,
    sub: str,
    email: Optional[str] = None,
    roles: Optional[List[str]] = None,
    business_id: Optional[str] = None,
    expires_minutes: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    now = datetime.utcnow()
    exp_minutes = expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES
    payload: Dict[str, Any] = {
        "sub": sub,
        "email": email,
        "roles": _normalize_roles(roles or ["VIEWER"]),
        "businessId": business_id,
        "iat": int(time.mktime(now.timetuple())),
        "exp": int(time.mktime((now + timedelta(minutes=exp_minutes)).timetuple())),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    # PyJWT returns str in v2, bytes in v1; ensure str
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def decode_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def _get_bearer_token_from_header(header_value: Optional[str]) -> Optional[str]:
    if not header_value:
        return None
    parts = header_value.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


async def require_user(request: Request) -> Dict[str, Any]:
    """Dependency: require a valid user when HTTP auth is enabled.

    If REQUIRE_AUTH_HTTP is false, returns an anonymous viewer user for dev.
    """
    if not REQUIRE_AUTH_HTTP:
        return {"sub": "anonymous", "roles": ["VIEWER"], "email": None}

    token = _get_bearer_token_from_header(request.headers.get("authorization"))
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return decode_token(token)


def roles_required(*required_roles: str) -> Callable[..., Any]:
    """Dependency factory: require that current user has any of the required roles.

    ADMIN always passes.
    """

    async def _dep(user: Dict[str, Any] = Depends(require_user)) -> Dict[str, Any]:
        if not REQUIRE_AUTH_HTTP:
            return user
        user_roles = _normalize_roles(user.get("roles", []))
        if not _has_any_role(user_roles, list(required_roles)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return _dep


def verify_ws_token(token: Optional[str], required_roles: Optional[List[str]] = None) -> Dict[str, Any]:
    """Verify a WebSocket token when WS auth is enabled.

    Returns decoded claims; raises ValueError on failure (handled by caller).
    When auth is disabled, returns an anonymous viewer.
    """
    if not REQUIRE_AUTH_WS:
        return {"sub": "anonymous", "roles": ["VIEWER"], "email": None}
    if not token:
        raise ValueError("Missing token")
    try:
        payload = decode_token(token)
    except HTTPException as e:
        # Convert to ValueError for WS handler
        raise ValueError(e.detail)
    if required_roles and not _has_any_role(_normalize_roles(payload.get("roles", [])), required_roles):
        raise ValueError("Insufficient role")
    return payload
