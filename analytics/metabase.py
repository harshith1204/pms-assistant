import os
import time
from typing import Any, Dict, Optional

try:
    import jwt  # PyJWT
except Exception as exc:  # pragma: no cover - optional during cold start
    jwt = None  # type: ignore

METABASE_SITE_URL = os.getenv("METABASE_SITE_URL", "")
METABASE_EMBED_SECRET = os.getenv("METABASE_EMBED_SECRET", "")


def signed_dashboard_url(dashboard_id: int, params: Optional[Dict[str, Any]] = None, ttl_seconds: int = 600) -> str:
    if not METABASE_SITE_URL or not METABASE_EMBED_SECRET:
        raise RuntimeError("METABASE_SITE_URL or METABASE_EMBED_SECRET not configured")
    if jwt is None:
        raise RuntimeError("PyJWT is not installed on server")
    payload = {
        "resource": {"dashboard": int(dashboard_id)},
        "params": params or {},
        "exp": round(time.time()) + int(ttl_seconds),
    }
    token = jwt.encode(payload, METABASE_EMBED_SECRET, algorithm="HS256")
    return f"{METABASE_SITE_URL}/embed/dashboard/{token}#bordered=true&titled=true"
