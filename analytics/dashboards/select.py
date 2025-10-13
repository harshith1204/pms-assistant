from __future__ import annotations
from typing import Dict, Any, List
import re

from .catalog import CATALOG, DashboardMeta
from analytics.metabase import signed_dashboard_url


def extract_query_semantics(prompt: str) -> Dict[str, Any]:
    p = (prompt or "").lower().strip()
    # naive heuristics; can be upgraded to LLM classification
    measure = None
    if any(k in p for k in ["revenue", "sales"]):
        measure = "revenue"
    elif "retention" in p:
        measure = "retention_rate"
    elif "orders" in p:
        measure = "orders"

    breakdown = None
    if "by region" in p or "per region" in p:
        breakdown = "region"
    if "by product" in p:
        breakdown = "product"

    # extract region simple
    filters: Dict[str, Any] = {}
    m = re.search(r"region\s+(\w+)", p)
    if m:
        filters["region"] = m.group(1).upper()

    # crude date range: last month/quarter/week
    time_range = None
    if "last quarter" in p:
        time_range = {"preset": "last_quarter"}
    elif "last month" in p:
        time_range = {"preset": "last_month"}
    elif "last week" in p:
        time_range = {"preset": "last_week"}

    compare = "compare" in p or "vs" in p

    return {
        "measure": measure,
        "breakdown": breakdown,
        "filters": filters,
        "time_range": time_range,
        "compare": compare,
    }


def compute_fit_score(meta: DashboardMeta, q: Dict[str, Any]) -> float:
    score = 0.0
    if q.get("measure") and q["measure"] in meta.get("measures", []):
        score += 4
    if q.get("breakdown") and q["breakdown"] in meta.get("dimensions", []):
        score += 3
    if q.get("compare") and meta.get("supports_compare"):
        score += 1
    needed_filters = set((q.get("filters") or {}).keys())
    score += len(needed_filters.intersection(set(meta.get("filter_keys", [])))) * 0.5
    # small bonus for tag keyword overlap
    text = " ".join(meta.get("tags", []) + meta.get("measures", []) + meta.get("dimensions", []))
    if q.get("measure") and q["measure"] in text:
        score += 0.5
    return score


def map_params(meta: DashboardMeta, q: Dict[str, Any]) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    for key, val in (q.get("filters") or {}).items():
        if key in meta.get("filter_keys", []):
            params[key] = val
    # map date presets if available
    tr = q.get("time_range")
    if tr and "date" in meta.get("filter_keys", []):
        params["date"] = tr
    if q.get("breakdown") and "breakdown" in meta.get("filter_keys", []):
        params["breakdown"] = q["breakdown"]
    return params


def select_best_dashboard(prompt: str) -> Dict[str, Any]:
    q = extract_query_semantics(prompt)
    ranked: List[DashboardMeta] = sorted(CATALOG, key=lambda m: compute_fit_score(m, q), reverse=True)
    best = ranked[0] if ranked else None
    if not best or compute_fit_score(best, q) < 2.0:
        return {
            "type": "table_preview_fallback",
            "reason": "no_good_dashboard_match",
            "alternatives": [m.get("dashboard_id") for m in ranked[:3]],
        }
    params = map_params(best, q)
    url = signed_dashboard_url(int(best["dashboard_id"]), params)
    return {
        "type": "dashboard_embed_url",
        "dashboard_id": best["dashboard_id"],
        "embed_url": url,
        "params": params,
        "explanations": {
            "chosen_for": [q.get("measure"), q.get("breakdown")],
            "alternatives": [m.get("dashboard_id") for m in ranked[1:3]],
        },
    }
