import os
import datetime as _dt
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel


JWT_ALGORITHM = "HS256"
JWT_ISSUER = "pms-assistant"
COOKIE_NAME = "access_token"


def _get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        # Development default; MUST be overridden in production via env
        secret = "change-me-dev-secret"
    return secret


def _is_cookie_secure() -> bool:
    # Default secure cookies in production
    env = (os.getenv("ENVIRONMENT") or os.getenv("NODE_ENV") or "development").lower()
    flag = os.getenv("COOKIE_SECURE")
    if flag is not None:
        return flag.lower() in {"1", "true", "yes"}
    return env in {"production", "prod"}


def create_access_token(
    subject: str,
    name: Optional[str] = None,
    is_admin: Optional[bool] = None,
    expires_minutes: int = 60,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    now = _dt.datetime.utcnow()
    expires = now + _dt.timedelta(minutes=expires_minutes)

    payload: Dict[str, Any] = {
        "iss": JWT_ISSUER,
        "sub": subject,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    if name is not None:
        payload["name"] = name
    if is_admin is not None:
        payload["admin"] = bool(is_admin)
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)
    # PyJWT returns str for >=2.0
    return token


def decode_access_token(token: str, verify: bool = True) -> Dict[str, Any]:
    if verify:
        return jwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM], options={"require": ["sub", "iat", "exp"]})
    # For non-verified/inspect-only decoding
    return jwt.decode(token, options={"verify_signature": False})


def set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_is_cookie_secure(),
        samesite="lax",
        path="/",
        max_age=None,  # let token's exp dictate validity; cookie itself session-scoped
    )


def clear_access_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")


class AdoptTokenRequest(BaseModel):
    token: str


class MeResponse(BaseModel):
    sub: str
    name: Optional[str] = None
    admin: Optional[bool] = None
    iat: int
    exp: Optional[int] = None


router = APIRouter(prefix="/auth", tags=["auth"])


async def get_current_user(request: Request) -> Dict[str, Any]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_access_token(token, verify=True)
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/adopt")
async def adopt_token(req: AdoptTokenRequest, response: Response) -> Dict[str, Any]:
    """
    Accept a provided JWT, inspect claims without trusting the signature,
    then mint a new access token signed with this server's secret and set
    it as an HttpOnly cookie. This avoids persisting tokens in localStorage.
    """
    try:
        provided_claims = decode_access_token(req.token, verify=False)
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed token")

    subject = str(provided_claims.get("sub") or "").strip()
    if not subject:
        raise HTTPException(status_code=400, detail="Token missing 'sub' claim")

    name = provided_claims.get("name")
    is_admin = provided_claims.get("admin")

    minted = create_access_token(subject=subject, name=name, is_admin=is_admin)
    set_access_cookie(response, minted)

    # Return minimal user profile; token is kept HttpOnly
    decoded = decode_access_token(minted, verify=True)
    user = {
        "sub": decoded.get("sub"),
        "name": decoded.get("name"),
        "admin": decoded.get("admin"),
        "iat": decoded.get("iat"),
        "exp": decoded.get("exp"),
    }
    return {"ok": True, "user": user}


@router.get("/me", response_model=MeResponse)
async def me(payload: Dict[str, Any] = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        sub=str(payload.get("sub")),
        name=payload.get("name"),
        admin=payload.get("admin"),
        iat=int(payload.get("iat")),
        exp=(int(payload["exp"]) if payload.get("exp") is not None else None),
    )


@router.post("/logout")
async def logout(response: Response) -> Dict[str, Any]:
    clear_access_cookie(response)
    return {"ok": True}
