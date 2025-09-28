"""
IR-based compiler for generalized filter + join + group + measure queries.

This module introduces a small Intermediate Representation (IR) and a reusable
compiler that maps IR → MongoDB aggregation pipelines using a centralized
dimension registry. It intentionally reuses the existing relationship registry
(`mongo.registry.REL`) and `$lookup` builder (`build_lookup_stage`).

Key concepts:
- IR: entity, filters, groupBy, measures, orderBy, limit
- Dimension registry: how to join and normalize each dimension across entities
- Generic compilers: relation join, scalar normalization, filters, groupBy
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta, timezone
import re

from .registry import REL, build_lookup_stage


# -------------------------------
# IR definition (dict structure)
# -------------------------------
# Example IR
# {
#   "entity": "workItem",
#   "filters": [
#     {"dim": "assignee", "op": "match", "value": "vikas"},
#     {"dim": "time(updated)", "op": "in_range", "value": "last week"}
#   ],
#   "groupBy": ["cycle", "module"],
#   "measures": ["count"],
#   "limit": 100,
#   "orderBy": [{"key": "count", "dir":"desc"}]
# }


# -----------------------------------------
# Schema registry (dimensions and measures)
# -----------------------------------------
# We rely on REL for actual join wiring. Here we describe how to project
# stable scalar ids/labels for generic grouping/filters.


SCHEMA: Dict[str, Any] = {
    "dimensions": {
        # People / assignee
        "assignee": {
            # For base workItem, REL uses key 'assignee' (many → alias 'assignees')
            "viaMap": {"workItem": "assignee", "module": "assignee", "project": "members"},
            "id": "assigneeId",
            "label": "assigneeName",
            "labelExpr": {"$ifNull": ["$assignee.name", {"$first": "$assignees.name"}]},
            "idExpr": {"$ifNull": ["$assignee._id", {"$first": "$assignees._id"}]},
        },

        # Project
        "project": {
            # For base workItem: REL key 'project' (alias 'projectDoc')
            # For other bases, this rel name may differ; viaMap handles it.
            "viaMap": {"workItem": "project", "cycle": "project", "module": "project", "page": "project", "members": "project", "projectState": "project"},
            "id": "projectId",
            "label": "projectName",
            "labelExpr": {"$ifNull": ["$project.name", {"$first": "$projectDoc.name"}]},
            "idExpr": {"$ifNull": ["$project._id", {"$first": "$projectDoc._id"}]},
        },

        # Cycle
        "cycle": {
            # For base workItem: REL key 'cycle' (alias 'cycleDoc')
            # For project: 'cycles' (array) → use $first after lookup
            "viaMap": {"workItem": "cycle", "project": "cycles", "page": "linkedCycle"},
            "id": "cycleId",
            "label": "cycleName",
            "labelExpr": {"$ifNull": ["$cycle.name", {"$ifNull": [{"$first": "$cycleDoc.title"}, {"$first": "$cycleDoc.name"}]}]},
            "idExpr": {"$ifNull": ["$cycle._id", {"$first": "$cycleDoc._id"}]},
        },

        # Module
        "module": {
            # For base workItem: REL key 'modules' (alias 'moduleDoc')
            # For project: 'modules' (array)
            "viaMap": {"workItem": "modules", "project": "modules", "page": "linkedModule"},
            "id": "moduleId",
            "label": "moduleName",
            "labelExpr": {"$ifNull": ["$modules.name", {"$ifNull": [{"$first": "$moduleDoc.title"}, {"$first": "$moduleDoc.name"}]}]},
            "idExpr": {"$ifNull": ["$modules._id", {"$first": "$moduleDoc._id"}]},
        },

        # Time dimensions
        "time(updated)": {"type": "time", "field": "updatedTimeStamp"},
        "time(created)": {"type": "time", "field": "createdTimeStamp"},

        # Direct fields as dimensions (simple equality/regex)
        "state": {"type": "field", "field": "state.name"},
        "priority": {"type": "field", "field": "priority"},
        "title": {"type": "field", "field": "title"},
        "label": {"type": "field", "field": "label"},
    },

    "measures": {
        "count": {"acc": {"$sum": 1}},
        # extensible: add sum/avg metrics when fields are present
    },
}


# -----------------------
# Utility time parsing
# -----------------------

def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)


def _end_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=59, microsecond=999000, tzinfo=timezone.utc)


def parse_time_phrase_to_utc(phrase: str) -> Tuple[str, str]:
    """Parse human phrases like 'last week', 'last 30 days', 'august' into ISO8601 strings.

    Returns (start_iso, end_iso) in UTC.
    """
    now = datetime.now(timezone.utc)
    s = phrase.strip().lower()

    # last N days
    m = re.match(r"last\s+(\d{1,3})\s+days?", s)
    if m:
        n = int(m.group(1))
        start = _start_of_day(now - timedelta(days=n))
        end = _end_of_day(now)
        return start.isoformat(), end.isoformat()

    # last week (Mon-Sun heuristic around current week)
    if s in {"last week", "previous week"}:
        # Go to start of current week (Mon=0)
        current_week_start = _start_of_day(now - timedelta(days=now.weekday()))
        last_week_start = current_week_start - timedelta(days=7)
        last_week_end = current_week_start - timedelta(seconds=1)
        return last_week_start.isoformat(), last_week_end.isoformat()

    # month name (simple: interpret as current year)
    months = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
    ]
    if s in months:
        idx = months.index(s) + 1
        start = datetime(now.year, idx, 1, tzinfo=timezone.utc)
        if idx == 12:
            end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        else:
            end = datetime(now.year, idx + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        return start.isoformat(), end.isoformat()

    # fallback: treat as last 30 days
    start = _start_of_day(now - timedelta(days=30))
    end = _end_of_day(now)
    return start.isoformat(), end.isoformat()


# -----------------------
# Join macro
# -----------------------

def _relation_for(base: str, via_key: str) -> Optional[Dict[str, Any]]:
    if base not in REL:
        return None
    return REL[base].get(via_key)


def add_relation_join(pipeline: List[Dict[str, Any]], base: str, via_key: str) -> List[Dict[str, Any]]:
    rel = _relation_for(base, via_key)
    if not rel:
        return pipeline
    target = rel.get("target")
    lookup = build_lookup_stage(target, rel, base)
    if lookup:
        pipeline.append(lookup)
        # optional: do not force unwind; use $first in scalarization
    return pipeline


# -----------------------
# Scalar normalization
# -----------------------

def add_dimension_scalars(pipeline: List[Dict[str, Any]], base: str, dims_used: Set[str]) -> List[Dict[str, Any]]:
    add_fields: Dict[str, Any] = {}
    for dim in dims_used:
        meta = SCHEMA["dimensions"].get(dim)
        if not meta:
            continue
        if "labelExpr" in meta and isinstance(meta["labelExpr"], dict):
            add_fields[meta["label"]] = meta["labelExpr"]
        if "idExpr" in meta and isinstance(meta["idExpr"], dict):
            add_fields[meta["id"]] = meta["idExpr"]
    if add_fields:
        pipeline.append({"$addFields": add_fields})
    return pipeline


# -----------------------
# Filter compiler
# -----------------------

def compile_filters(ir: Dict[str, Any]) -> List[Dict[str, Any]]:
    filters = ir.get("filters") or []
    if not filters:
        return []
    match_and: List[Dict[str, Any]] = []

    for f in filters:
        dim = (f.get("dim") or "").strip()
        op = f.get("op")
        value = f.get("value")
        meta = SCHEMA["dimensions"].get(dim)

        # Time ranges
        if meta and meta.get("type") == "time" and op == "in_range" and isinstance(value, str):
            start_iso, end_iso = parse_time_phrase_to_utc(value)
            field = meta["field"]
            match_and.append({field: {"$gte": start_iso, "$lte": end_iso}})
            continue

        # Text / id matching for people
        if dim == "assignee" and op == "match" and isinstance(value, str):
            # Best-effort: allow matching via embedded, joined alias, or normalized scalar
            match_and.append({"$or": [
                {"assignee._id": {"$in": []}},  # placeholder for ids resolver if added later
                {"assignee.name": {"$regex": re.escape(value), "$options": "i"}},
                {"assignees.name": {"$regex": re.escape(value), "$options": "i"}},
                {"assigneeName": {"$regex": re.escape(value), "$options": "i"}},
            ]})
            continue

        # Generic label-based match (projects/cycles/modules)
        if meta and op == "match" and isinstance(value, str) and meta.get("label"):
            match_and.append({"$or": [
                {meta["label"]: {"$regex": re.escape(value), "$options": "i"}},
            ]})
            continue

        # Field-based dimensions (state, priority, title, label)
        if meta and meta.get("type") == "field":
            field = meta["field"]
            if op in ("eq", "="):
                match_and.append({field: value})
            elif op == "match" and isinstance(value, str):
                match_and.append({field: {"$regex": re.escape(value), "$options": "i"}})
            continue

        # Fallback: ignore unknown filters gracefully

    return ([{"$match": {"$and": match_and}}] if match_and else [])


# -----------------------
# GroupBy compiler
# -----------------------

def compile_groupby(ir: Dict[str, Any]) -> List[Dict[str, Any]]:
    keys: List[Tuple[str, str]] = []
    for dim in ir.get("groupBy", []) or []:
        meta = SCHEMA["dimensions"].get(dim)
        if not meta:
            continue
        kid = meta.get("id")
        klabel = meta.get("label")
        if kid and klabel:
            keys.append((kid, klabel))

    if not keys:
        return []

    _id: Dict[str, Any] = {}
    for kid, klabel in keys:
        _id[kid] = f"${kid}"
        _id[klabel] = f"${klabel}"

    # Measures
    acc: Dict[str, Any] = {}
    for m in (ir.get("measures") or ["count"]):
        if m in SCHEMA["measures"]:
            acc[m] = SCHEMA["measures"][m]["acc"]

    stages: List[Dict[str, Any]] = [
        {"$group": {"_id": _id, **acc}},
        {"$sort": {k: 1 for k in _id.keys()}},
    ]
    return stages


# -----------------------
# Compiler: IR → pipeline
# -----------------------

def compile_pipeline(ir: Dict[str, Any]) -> List[Dict[str, Any]]:
    base = ir.get("entity") or "workItem"
    group_by = ir.get("groupBy") or []
    limit_val = int(ir.get("limit") or 20)

    # 1) Gather dimensions used anywhere
    dims_used: Set[str] = set(group_by)
    for f in ir.get("filters", []) or []:
        if isinstance(f, dict) and f.get("dim"):
            dims_used.add(f["dim"])  # type: ignore[index]

    # 2) Add only the relations we need (based on viaMap)
    pipeline: List[Dict[str, Any]] = []
    for dim in sorted(dims_used):
        meta = SCHEMA["dimensions"].get(dim)
        if not meta:
            continue
        via_map = meta.get("viaMap") or {}
        via_key = via_map.get(base)
        if isinstance(via_key, str):
            add_relation_join(pipeline, base, via_key)

    # 3) Normalize to stable scalars
    add_dimension_scalars(pipeline, base, dims_used)

    # 4) Generic unwinds for known arrays (do not duplicate unwinds if not present)
    # PreserveNull to keep unlinked docs in groups
    pipeline += [
        {"$unwind": {"path": "$assignee", "preserveNullAndEmptyArrays": True}},
        {"$unwind": {"path": "$modules", "preserveNullAndEmptyArrays": True}},
    ]

    # 5) Filters
    pipeline += compile_filters(ir)

    # 6) Grouping + measures
    if group_by:
        pipeline += compile_groupby(ir)
        # Present a tidy shape
        project_fields: Dict[str, Any] = {m: 1 for m in (ir.get("measures") or ["count"]) if isinstance(m, str)}
        project_fields["group"] = "$_id"
        pipeline.append({"$project": project_fields})
    else:
        # Non-grouped queries: keep it simple and project key fields if desired
        pass

    # 7) Order / limit
    order = (ir.get("orderBy") or [])
    if order:
        key = order[0].get("key")
        direction = -1 if (order[0].get("dir") or "").lower().startswith("desc") else 1
        if key:
            pipeline.append({"$sort": {key: direction}})
    if limit_val:
        pipeline.append({"$limit": min(limit_val, 100)})

    return pipeline


# -----------------------
# Intent → IR mapping (helper)
# -----------------------

def intent_to_ir(intent: Any) -> Dict[str, Any]:
    """Map the existing QueryIntent into the IR structure.

    Only uses a subset of fields (groupBy, count, common name filters). Other
    cases fall back to existing planner logic.
    """
    # intent is either a dataclass or dict-like
    entity = getattr(intent, "primary_entity", None) or intent.get("primary_entity") or "workItem"
    filters_dict = getattr(intent, "filters", None) or intent.get("filters") or {}
    group_by_list = getattr(intent, "group_by", None) or intent.get("group_by") or []
    aggs = getattr(intent, "aggregations", None) or intent.get("aggregations") or []
    limit_val = getattr(intent, "limit", None) or intent.get("limit") or 20
    sort_order = getattr(intent, "sort_order", None) or intent.get("sort_order") or None

    ir_filters: List[Dict[str, Any]] = []
    # Map common name filters → match
    name_map = {
        "assignee_name": "assignee",
        "project_name": "project",
        "cycle_name": "cycle",
        "module_name": "module",
    }
    for k, v in (filters_dict or {}).items():
        if k in name_map and isinstance(v, str) and v.strip():
            ir_filters.append({"dim": name_map[k], "op": "match", "value": v.strip()})
        elif k in {"state", "priority", "title", "label"}:
            # equality or regex match depending on type; default to match
            if isinstance(v, str):
                ir_filters.append({"dim": k, "op": "match", "value": v.strip()})
            else:
                ir_filters.append({"dim": k, "op": "eq", "value": v})

    # Infer time dim from sort hints or explicit date ranges in filters_dict
    # If user wants recency windows, this can be extended later

    # Measures
    measures: List[str] = []
    if "count" in aggs:
        measures.append("count")
    if not measures and group_by_list:
        # default measure for grouped queries
        measures = ["count"]

    # orderBy default for grouped results → by count desc; else by nothing
    order_by: List[Dict[str, Any]] = []
    if group_by_list and measures:
        order_by = [{"key": measures[0], "dir": "desc"}]
    elif isinstance(sort_order, dict) and sort_order:
        k, v = next(iter(sort_order.items()))
        order_by = [{"key": k, "dir": ("desc" if int(v) < 0 else "asc")}]

    return {
        "entity": entity,
        "filters": ir_filters,
        "groupBy": list(group_by_list) if isinstance(group_by_list, list) else [],
        "measures": measures or ["count"],
        "limit": int(limit_val) if limit_val else 20,
        "orderBy": order_by,
    }

