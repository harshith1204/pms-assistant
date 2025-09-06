import json
import hashlib
from datetime import datetime
from typing import Any, Dict

from pymongo import MongoClient

from constants import MONGODB_CONNECTION_STRING, DATABASE_NAME


_client: MongoClient | None = None


def _get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_CONNECTION_STRING)
    return _client


def _db():
    return _get_client()[DATABASE_NAME]


def _hash_args(args: Dict[str, Any]) -> str:
    try:
        return hashlib.sha256(json.dumps(args, sort_keys=True, default=str).encode()).hexdigest()
    except Exception:
        return hashlib.sha256(str(args).encode()).hexdigest()


def make_preview(raw: Any, max_len: int = 800) -> str:
    try:
        if isinstance(raw, (dict, list)):
            text = json.dumps(raw)[:max_len]
            return text
        text = str(raw)
        return text[:max_len]
    except Exception:
        return ""


def persist_result(tool: str, args: Dict[str, Any], raw: Any) -> Dict[str, Any]:
    db = _db()
    args_hash = _hash_args(args)
    doc = {
        "tool": tool,
        "args_hash": args_hash,
        "created_at": datetime.utcnow(),
        "meta": {
            "size": len(json.dumps(raw, default=str)) if isinstance(raw, (dict, list)) else None,
        },
        "preview": make_preview(raw),
        "raw": raw if isinstance(raw, (dict, list, str, int, float, bool, type(None))) else str(raw),
    }
    _id = db["results"].insert_one(doc).inserted_id
    return {"_id": str(_id), "tool": tool}


def get_result(result_id: str) -> Dict[str, Any] | None:
    from bson import ObjectId
    db = _db()
    try:
        doc = db["results"].find_one({"_id": ObjectId(result_id)})
        if not doc:
            return None
        doc["_id"] = str(doc["_id"])  # normalize
        return doc
    except Exception:
        return None

