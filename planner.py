#!/usr/bin/env python3
"""
Intelligent Query Planner for PMS System
Handles natural language queries and generates optimal MongoDB aggregation pipelines
based on the relationship registry
"""

import json
import re
from typing import Dict, List, Any, Optional, Set
import os
from dataclasses import dataclass

from registry import REL, ALLOWED_FIELDS, build_lookup_stage
from constants import mongodb_tools, DATABASE_NAME
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

# --- Synonym dictionaries to make user queries more forgiving ---
# Maps natural-language synonyms to canonical collection/entity names
ENTITY_SYNONYMS: Dict[str, List[str]] = {
    "workItem": [
        "work item", "work items", "issue", "issues", "bug", "bugs",
        "ticket", "tickets", "task", "tasks", "story", "stories"
    ],
    "project": ["project", "projects"],
    "cycle": ["cycle", "cycles", "sprint", "sprints", "iteration", "iterations", "milestone", "milestones"],
    "module": ["module", "modules", "component", "components", "feature", "features"],
    "page": ["page", "pages", "doc", "docs", "document", "documents", "note", "notes", "wiki", "wikis"],
    "members": ["member", "members", "user", "users", "assignee", "assignees", "developer", "developers", "engineer", "engineers", "owner", "owners", "teammate", "teammates"],
    "projectState": ["project state", "project states", "workflow", "workflows", "state machine", "states"]
}

# Maps field synonyms to canonical planner filter keys
FIELD_SYNONYMS: Dict[str, str] = {
    # state/status
    "status": "state",
    "workflow state": "state",
    # priority/severity
    "severity": "priority",
    # names
    "project": "project_name",
    "project name": "project_name",
    "cycle": "cycle_name",
    "cycle name": "cycle_name",
    "module": "module_name",
    "module name": "module_name",
    "assignee": "assignee_name",
    "assignee name": "assignee_name",
    "owner": "assignee_name",
}

# Phrases that imply each operation
COUNT_PHRASES: List[str] = [
    "how many", "count", "number of", "total", "totals", "what is the count"
]
GROUP_PHRASES: List[str] = [
    "group by", "grouped by", "breakdown by", "split by", "per ", "by "
]

def _text_has_any(text: str, phrases: List[str]) -> bool:
    q = text.lower()
    return any(p in q for p in phrases)

def _detect_primary_from_synonyms(query: str) -> Optional[str]:
    q = query.lower()
    for canonical, synonyms in ENTITY_SYNONYMS.items():
        for s in synonyms:
            if f" {s} " in f" {q} ":
                return canonical
    return None

def _normalize_field_key(raw_key: str) -> str:
    k = raw_key.strip().lower()
    return FIELD_SYNONYMS.get(k, raw_key)

@dataclass
class QueryIntent:
    """Represents the parsed intent of a user query"""
    primary_entity: str  # Main collection/entity (e.g., "workItem", "project")
    target_entities: List[str]  # Related entities to include
    filters: Dict[str, Any]  # Filter conditions
    aggregations: List[str]  # Aggregation operations (count, group, etc.)
    group_by: List[str]  # Grouping keys (e.g., ["cycle"]) when 'group by' present
    projections: List[str]  # Fields to return
    sort_order: Optional[Dict[str, int]]  # Sort specification
    limit: Optional[int]  # Result limit
    wants_details: bool  # Prefer detailed documents over counts
    wants_count: bool  # Whether the user asked for a count

@dataclass
class RelationshipPath:
    """Represents a traversal path through relationships"""
    start_collection: str
    end_collection: str
    path: List[str]  # List of relationship names
    cost: int  # Computational cost of this path
    filters: Dict[str, Any]  # Filters that can be applied at each step

class NaturalLanguageParser:
    def parse(self, query: str) -> "QueryIntent":
        """Minimal heuristic fallback when LLM intent parsing fails.

        Defaults to listing workItems, attempts to detect simple group-by and count prompts.
        """
        ql = (query or "").lower()
        # Detect explicit entity mentions for simple primary selection (with synonyms)
        primary_detected = _detect_primary_from_synonyms(ql)
        primary: str = primary_detected or "workItem"
        # Detect group-by tokens in simple phrasing
        group_tokens: List[str] = []
        raw_group_candidates = ["assignee", "owner", "project", "cycle", "state", "status", "priority", "severity", "module"]
        for token in raw_group_candidates:
            if (
                f"group by {token}" in ql or f"grouped by {token}" in ql or f"breakdown by {token}" in ql or
                (ql.startswith(f"by {token}") or f" by {token}" in ql)
            ):
                group_tokens.append(token)
        # Canonicalize group tokens
        canonical_group: List[str] = []
        for t in group_tokens:
            if t == "status":
                canonical_group.append("state")
            elif t == "severity":
                canonical_group.append("priority")
            elif t == "owner":
                canonical_group.append("assignee")
            else:
                canonical_group.append(t)

        # Detect count requests
        wants_count = _text_has_any(ql, COUNT_PHRASES)
        aggregations: List[str] = ["group"] if canonical_group else (["count"] if wants_count else [])

        # Simple synonyms → filters
        filters: Dict[str, Any] = {}
        if primary == "cycle":
            if "upcoming" in ql:
                filters["cycle_status"] = "UPCOMING"
            if any(w in ql for w in ["active", "running", "ongoing", "current"]):
                filters["cycle_status"] = "ACTIVE"
        if primary == "project":
            if any(w in ql for w in ["active", "running", "ongoing", "in progress"]):
                filters["project_status"] = "STARTED"
        if primary == "workItem":
            # map simple state synonyms
            if "open" in ql:
                filters["state"] = "Open"
            if any(w in ql for w in ["completed", "closed", "done", "finished"]):
                filters["state"] = "Completed"
            if any(w in ql for w in ["backlog", "todo"]):
                filters["state"] = "Backlog"
            if any(w in ql for w in ["re-raised", "re raised", "reraised", "reopened", "re-opened", "re opened"]):
                filters["state"] = "Re-Raised"
            if any(w in ql for w in ["in progress", "in-progress", "progressing", "wip"]):
                filters["state"] = "In-Progress"
            if any(w in ql for w in ["verified", "qa passed", "accepted"]):
                filters["state"] = "Verified"
            if "urgent" in ql:
                filters["priority"] = "URGENT"

        return QueryIntent(
            primary_entity=primary,
            target_entities=[],
            filters=filters,
            aggregations=aggregations,
            group_by=canonical_group,
            projections=[],
            sort_order=None,
            limit=20,
            # For grouped results, default to no details unless explicitly asked; here we assume details for list
            wants_details=(not aggregations) or (aggregations == ["group"]),
            wants_count=(aggregations == ["count"]),
        )

class LLMIntentParser:
    """LLM-backed intent parser that produces a structured plan compatible with QueryIntent.

    The LLM proposes:
    - primary_entity
    - target_entities (relations to join)
    - filters (normalized keys: status, priority, project_status, cycle_status, page_visibility,
      project_name, cycle_name, assignee_name, module_name)
    - aggregations: ["count"|"group"|"summary"]
    - group_by tokens: ["cycle","project","assignee","status","priority","module"]
    - projections (subset of allow-listed fields for the primary entity)
    - sort_order (field -> 1|-1), supported keys: createdTimeStamp, priority, status
    - limit (int)
    - wants_details, wants_count

    Safety: we filter LLM output against REL and ALLOWED_FIELDS before use.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.environ.get("QUERY_PLANNER_MODEL", "qwen3:0.6b-fp16")
        # Keep the model reasonably deterministic for planning
        self.llm = ChatOllama(
            model=self.model_name,
            temperature=0.1,
            num_ctx=4096,
            num_predict=768,
            top_p=0.9,
            top_k=40,
        )

        # Precompute compact schema context to keep prompts short
        self.entities: List[str] = list(REL.keys())
        self.entity_relations: Dict[str, List[str]] = {
            entity: list(REL.get(entity, {}).keys()) for entity in self.entities
        }
        self.allowed_fields: Dict[str, List[str]] = {
            entity: sorted(list(ALLOWED_FIELDS.get(entity, set()))) for entity in self.entities
        }

    def _is_placeholder(self, v) -> bool:
        if v is None:
            return True
        if not isinstance(v, str):
            return False
        s = v.strip().lower()
        return (
            s == "" or
            "?" in s or
            s.startswith("string") or
            s in {"none?", "todo?", "n/a", "<none>", "<unknown>"}
        )

    async def parse(self, query: str) -> Optional[QueryIntent]:
        """Use the LLM to produce a structured intent. Returns None on failure."""
        system = (
            "You are an expert planner that converts a user's PM query into a SIMPLE JSON intent. "
            "Your job: decide the target entity, the operation (count | list | group), minimal filters, and optional sort/limit. "
            "Do NOT return a pipeline; ONLY a compact intent JSON.\n\n"
            "Entities (use exactly these canonical names): " + ", ".join(self.entities) + "\n"
            "Allowed group-by tokens: cycle, project, assignee, state, priority, module.\n"
            "Filters use these keys only: state, priority, project_status, cycle_status, page_visibility, project_name, cycle_name, assignee_name, module_name.\n"
            "Operations:\n"
            "- Count: if the user asks 'how many', 'count', 'number of', 'total'. Keep it minimal: no group_by, no target_entities.\n"
            "- List (details): if the user asks to show/list/display items. aggregations: [] and wants_details: true.\n"
            "- Group: if the user says 'group by'/'breakdown by' <token>. aggregations: ['group'], group_by: [tokens].\n\n"
            "Synonyms to understand (map to canonical):\n"
            "- Entities: work items = issues/bugs/tickets/tasks/stories; cycles = sprints/iterations/milestones; members = users/assignees/owners; modules = features/components.\n"
            "- Fields: status -> state, severity -> priority, owner -> assignee_name.\n\n"
            "Keep target_entities minimal: include relations only if needed for filters or group_by.\n"
            "Default entity: use workItem unless the question is clearly about projects/cycles/pages/modules/members/projectState.\n"
            "Always output ALL top-level keys in the JSON (include empty values when unknown)."
        )

        schema = {
            "primary_entity": "string; one of " + ", ".join(self.entities),
            "target_entities": "string[]; relations to join for primary, from the allowed list above",
            "filters": {
                "state": "Open|Completed|Backlog|Re-Raised|In-Progress|Verified?",
                "priority": "URGENT|HIGH|MEDIUM|LOW|NONE?",
                "project_status": "NOT_STARTED|STARTED|COMPLETED|OVERDUE?",
                "cycle_status": "ACTIVE|UPCOMING|COMPLETED?",
                "page_visibility": "PUBLIC|PRIVATE|ARCHIVED?",
                "project_name": "string? (free text, used as case-insensitive regex)",
                "cycle_name": "string?",
                "assignee_name": "string?",
                "module_name": "string?"
            },
            "aggregations": "string[]; subset of [count, group, summary]",
            "group_by": "string[]; subset of [cycle, project, assignee, state, status, priority, module]",
            "projections": "string[]; subset of allow-listed fields for primary_entity",
            "sort_order": "object?; single key among allowed sort keys mapping to 1 or -1",
            "limit": "integer <= 100; default 20",
            "wants_details": "boolean",
            "wants_count": "boolean"
        }

        user = (
            "TASK: Convert the user's request into a strict JSON intent object.\n"
            "Rules:\n"
            "- Only use allowed entities, relations, and fields.\n"
            "- If both details and count are implied, set wants_details true and wants_count false.\n"
            "- Keep target_entities minimal but sufficient to support filters and group_by.\n"
            "- Only include project_name/cycle_name/module_name if the query explicitly mentions project/cycle/module.\n"
            "- Never assign the same name to multiple entity filters; if unclear, prefer assignee_name.\n"
            "- Do NOT include any explanations or prose. Output JSON ONLY.\n\n"
            f"Schema (for reference, keys only): {json.dumps(schema)}\n\n"
            f"User Query: {query}"
        )

        try:
            ai = await self.llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
            content = ai.content.strip()
            # Remove <think></think> tags and their content
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
            # Some models wrap JSON in code fences; strip if present
            if content.startswith("```"):
                content = content.strip("`\n").split("\n", 1)[-1]
                if content.startswith("json\n"):
                    content = content[5:]
            data = json.loads(content)
        except Exception:
            return None

        try:
            return await self._sanitize_intent(data, query)
        except Exception:
            return None

    async def _sanitize_intent(self, data: Dict[str, Any], original_query: str = "") -> QueryIntent:
        # Primary entity (prefer workItem; flip to workItem if cross-entity grouping is requested)
        requested_primary = (data.get("primary_entity") or "").strip()
        primary = requested_primary if requested_primary in self.entities else "workItem"

        # Heuristic override: detect explicit entity in count-style or simple queries
        oq_hint = (original_query or "").lower()
        raw_group_by = data.get("group_by") or []
        wants_count_pre = ("count" in (data.get("aggregations") or [])) or _text_has_any(oq_hint, COUNT_PHRASES)

        # Map common nouns to entities - stronger override for count queries
        explicit_primary = None
        explicit_primary = _detect_primary_from_synonyms(oq_hint)

        # For count queries, always override LLM's primary entity if we detect an explicit entity
        # This prevents the LLM from incorrectly setting workItem as primary for "how many cycles"
        if explicit_primary and wants_count_pre:
            primary = explicit_primary
        elif explicit_primary and not raw_group_by:
            # Also override for non-grouped queries with explicit entity
            primary = explicit_primary

        # Allowed relations for primary
        allowed_rels = set(self.entity_relations.get(primary, []))
        target_entities: List[str] = []
        for rel in (data.get("target_entities") or []):
            if isinstance(rel, str) and rel.split(".")[0] in allowed_rels:
                target_entities.append(rel)

        # Filters: keep only known keys and drop placeholders
        raw_filters = data.get("filters") or {}
        # Map legacy 'status' to 'state' for workItem if present
        if primary == "workItem" and isinstance(raw_filters, dict) and "status" in raw_filters and "state" not in raw_filters:
            raw_filters["state"] = raw_filters.pop("status")
        known_filter_keys = {
            "state", "priority", "project_status", "cycle_status", "page_visibility",
            "project_name", "cycle_name", "assignee_name", "module_name",
            # extended keys
            "member_role",
        }
        filters: Dict[str, Any] = {}
        # Canonicalize workItem state values
        state_canonical: Dict[str, str] = {
            "open": "Open",
            "completed": "Completed",
            "backlog": "Backlog",
            "re-raised": "Re-Raised",
            "re raised": "Re-Raised",
            "reraised": "Re-Raised",
            "reopened": "Re-Raised",
            "re-opened": "Re-Raised",
            "re opened": "Re-Raised",
            "in-progress": "In-Progress",
            "in progress": "In-Progress",
            "wip": "In-Progress",
            "verified": "Verified",
        }
        for k, v in raw_filters.items():
            # normalize user/LLM-proposed field key to canonical
            k_norm = _normalize_field_key(k)
            if k_norm in known_filter_keys and isinstance(v, (str, int)) and not self._is_placeholder(v):
                if isinstance(v, str):
                    vs = v.strip()
                else:
                    vs = v
                if k_norm == "state" and isinstance(vs, str):
                    canon = state_canonical.get(vs.lower())
                    if not canon:
                        # if not recognized, skip state filter
                        continue
                    filters["state"] = canon
                    continue
                # legacy normalize (no longer expected but kept for safety)
                if k_norm == "cycle_title":
                    filters["cycle_name"] = vs
                    continue
                # enforce uppercase for enum-like others
                if k_norm in {"project_status", "cycle_status", "page_visibility"} and isinstance(vs, str):
                    if "?" in vs or not vs.isupper():
                        continue
                filters[k_norm] = vs

        # Enforce entity mention policy for name filters; prefer assignee on ambiguity
        oq_sanitize = (original_query or "").lower()
        def _mentions(entity_key: str) -> bool:
            synonyms = ENTITY_SYNONYMS.get(entity_key, [])
            return any(f" {s} " in f" {oq_sanitize} " for s in synonyms)
        mentions_project = _mentions("project")
        mentions_cycle = _mentions("cycle")
        mentions_module = _mentions("module")
        # Assignee/owner synonyms
        mentions_assignee = _mentions("members") or ("assigned to" in oq_sanitize) or ("assigned" in oq_sanitize and " to " in oq_sanitize) or ("owner" in oq_sanitize)

        # Auto-detect status/priority filters and special intents based on query keywords
        if primary == "cycle" and "upcoming" in oq_sanitize and "cycle_status" not in filters:
            filters["cycle_status"] = "UPCOMING"
        elif primary == "cycle" and any(w in oq_sanitize for w in ["active", "running", "ongoing", "current"]) and "cycle_status" not in filters:
            filters["cycle_status"] = "ACTIVE"
        elif primary == "project" and any(w in oq_sanitize for w in ["active", "running", "ongoing", "in progress"]) and "project_status" not in filters:
            filters["project_status"] = "STARTED"

        # Open/closed/state synonyms for work items
        if primary == "workItem":
            # Only set state if not already present from filters
            if ("open" in oq_sanitize) and ("state" not in filters):
                filters["state"] = "Open"
            if ("closed" in oq_sanitize or "completed" in oq_sanitize) and ("state" not in filters):
                filters["state"] = "Completed"
            if ("backlog" in oq_sanitize or "todo" in oq_sanitize) and ("state" not in filters):
                filters["state"] = "Backlog"
            if any(w in oq_sanitize for w in ["re-raised", "re raised", "reraised", "reopened", "re-opened", "re opened"]) and ("state" not in filters):
                filters["state"] = "Re-Raised"
            if any(w in oq_sanitize for w in ["in progress", "in-progress", "wip"]) and ("state" not in filters):
                filters["state"] = "In-Progress"
            if ("verified" in oq_sanitize) and ("state" not in filters):
                filters["state"] = "Verified"
            if ("urgent" in oq_sanitize) and ("priority" not in filters):
                filters["priority"] = "URGENT"
            # priority adjectives
            if ("high priority" in oq_sanitize) and ("priority" not in filters):
                filters["priority"] = "HIGH"
            if ("medium priority" in oq_sanitize) and ("priority" not in filters):
                filters["priority"] = "MEDIUM"
            if ("low priority" in oq_sanitize) and ("priority" not in filters):
                filters["priority"] = "LOW"

        # Member role detection (e.g., 'lead')
        if ("lead" in oq_sanitize) and ("member_role" not in filters):
            filters["member_role"] = "LEAD"

        # Recent/latest sorting intent
        if any(w in oq_sanitize for w in ["recent", "latest", "newly added", "recently added", "recent project"]):
            so_pre = {"createdTimeStamp": -1}
            if data.get("sort_order") is None:
                data["sort_order"] = so_pre
            # If asking about a single most recent, cap results unless count requested
            if not wants_count_pre:
                try:
                    limit_val = int(data.get("limit") or 0)
                except Exception:
                    limit_val = 0
                if not limit_val or limit_val > 1:
                    data["limit"] = 1

        # "who created" intent → project creator projection
        if ("who" in oq_sanitize and "created" in oq_sanitize and primary == "project"):
            # Seed projections to surface creator
            data.setdefault("projections", [])
            if "createdBy.name" not in data["projections"]:
                data["projections"].append("createdBy.name")

        # Only keep project/cycle/module name filters if the entity is explicitly mentioned
        if "project_name" in filters and not mentions_project:
            filters.pop("project_name", None)
        if "cycle_name" in filters and not mentions_cycle:
            filters.pop("cycle_name", None)
        if "module_name" in filters and not mentions_module:
            filters.pop("module_name", None)

        # Hybrid DB-backed disambiguation for free-text names when no entity is explicitly mentioned.
        # If the LLM proposed any name filters but we removed them due to missing mentions, use DB counts
        # to infer the most likely entity (members/project/cycle/module). Keep assignee preference on ties.
        try:
            proposed_name_values: Dict[str, str] = {}
            for key in ("assignee_name", "project_name", "cycle_name", "module_name"):
                val = raw_filters.get(key)
                if isinstance(val, str) and not self._is_placeholder(val):
                    proposed_name_values[key] = val

            no_explicit_mentions = not (mentions_assignee or mentions_project or mentions_cycle or mentions_module)
            # Trigger disambiguation if we have at least one proposed name and no explicit entity mentions
            if proposed_name_values and no_explicit_mentions:
                chosen_key = await self._disambiguate_name_entity(proposed_name_values)
                if chosen_key:
                    # Reset to only the chosen name filter
                    for k in ["assignee_name", "project_name", "cycle_name", "module_name"]:
                        if k != chosen_key and k in filters:
                            filters.pop(k, None)
                    # If chosen not present (because we earlier dropped), re-add it
                    if chosen_key not in filters and chosen_key in proposed_name_values:
                        filters[chosen_key] = proposed_name_values[chosen_key]
        except Exception:
            # Best-effort; ignore disambiguation failures
            pass

        # Aggregations
        allowed_aggs = {"count", "group", "summary"}
        aggregations = [a for a in (data.get("aggregations") or []) if a in allowed_aggs]

        # Group by tokens
        allowed_group = {"cycle", "project", "assignee", "state", "priority", "module"}
        group_by = [g for g in (data.get("group_by") or []) if g in allowed_group]

        # If user grouped by cross-entity tokens, force workItem as base (entity lock)
        cross_tokens = {"assignee", "project", "cycle", "module"}
        if any(g in cross_tokens for g in group_by):
            primary = "workItem"

        # Aggregations & group_by coherence
        if group_by and "group" not in aggregations:
            aggregations.insert(0, "group")
        if not group_by:
            # drop stray 'group'
            aggregations = [a for a in aggregations if a != "group"]

        # Projections limited to allow-listed fields for primary
        allowed_projection_set = set(self.allowed_fields.get(primary, []))
        projections = [p for p in (data.get("projections") or []) if p in allowed_projection_set][:10]

        # Sort order
        sort_order = None
        so = data.get("sort_order") or {}
        if isinstance(so, dict) and so:
            key, val = next(iter(so.items()))
            if key in {"createdTimeStamp", "priority", "state", "status"} and val in (1, -1):
                sort_order = {key: val}

        # Limit
        limit_val = data.get("limit")
        try:
            limit = int(limit_val) if limit_val is not None else 20
            if limit <= 0:
                limit = 20
            limit = min(limit, 100)
        except Exception:
            limit = 20

        # Details vs count (mutually exclusive) + heuristic for "how many"
        oq = (original_query or "").lower()
        wants_details_raw = data.get("wants_details")
        wants_count_raw = data.get("wants_count")
        wants_details = bool(wants_details_raw) if wants_details_raw is not None else False
        wants_count = bool(wants_count_raw) if wants_count_raw is not None else False
        wants_count = wants_count or _text_has_any(oq, COUNT_PHRASES)

        # Drop status/visibility filters that do not belong to the chosen primary entity
        primary_allowed_status_filters = {
            "workItem": {"state", "priority"},
            "project": {"project_status"},
            "cycle": {"cycle_status"},
            "page": {"page_visibility"},
            "module": set(),
            "members": set(),
            "projectState": set(),
        }.get(primary, set())
        for k in list(filters.keys()):
            if k in {"state", "status", "priority", "project_status", "cycle_status", "page_visibility"} and k not in primary_allowed_status_filters:
                filters.pop(k, None)

        # Enforce state/priority demand: if both present for workItem, keep only those explicitly mentioned
        if primary == "workItem" and "state" in filters and "priority" in filters:
            mentions_state_terms = any(t in oq for t in ["state", "open", "completed", "backlog", "re-raised", "re raised", "in-progress", "in progress", "verified", "wip"])
            mentions_priority_terms = any(t in oq for t in ["priority", "urgent", "high", "medium", "low", "none"])
            if mentions_state_terms and not mentions_priority_terms:
                filters.pop("priority", None)
            elif mentions_priority_terms and not mentions_state_terms:
                filters.pop("state", None)
            elif not mentions_state_terms and not mentions_priority_terms:
                # if neither explicitly mentioned, drop both to avoid over-filtering
                filters.pop("state", None)
                filters.pop("priority", None)

        # If it's a broad count question and the user did not specify a status/priority/visibility,
        # drop those filters to avoid unintended narrowing by LLM guesses.
        if wants_count:
            status_terms = [
                "active", "upcoming", "completed", "not started", "started", "overdue",
                "public", "private", "archived", "urgent", "high", "medium", "low", "none"
            ]
            mentions_status_like = any(term in oq for term in status_terms)
            if not mentions_status_like:
                for k in ["state", "status", "priority", "project_status", "cycle_status", "page_visibility"]:
                    filters.pop(k, None)

        # If user asked a count-style question, force count-only intent
        if wants_count:
            group_by = []
            aggregations = ["count"]
            wants_details = False
            # Drop target entities to avoid unnecessary lookups for pure counts
            target_entities = []
            # Sorting is irrelevant for counts
            sort_order = None
            # Clear projections for count queries
            projections = []
        else:
            # If group_by present, details default to False unless explicitly requested
            if group_by and wants_details_raw is None:
                wants_details = False

            # Never have both; count wins if user explicitly asked
            if wants_details and wants_count:
                wants_details = False
            if wants_count and not group_by:
                aggregations = ["count"]

        return QueryIntent(
            primary_entity=primary,
            target_entities=target_entities,
            filters=filters,
            aggregations=aggregations,
            group_by=group_by,
            projections=projections,
            sort_order=sort_order,
            limit=limit,
            wants_details=wants_details,
            wants_count=wants_count,
        )

    async def _disambiguate_name_entity(self, proposed: Dict[str, str]) -> Optional[str]:
        """Use DB counts across collections to decide which name filter is most plausible.

        Preference order on ties: assignee -> project -> cycle -> module.
        Returns the chosen filter key or None if inconclusive.
        """
        # Build candidate lookups: mapping filter key -> (collection, field)
        candidates = {
            "assignee_name": ("members", "name"),
            "project_name": ("project", "name"),
            "cycle_name": ("cycle", "name"),
            "module_name": ("module", "name"),
        }
        counts: Dict[str, int] = {}
        for key, (collection, field) in candidates.items():
            if key not in proposed:
                continue
            value = proposed[key]
            try:
                cnt = await self._aggregate_count(collection, {field: {"$regex": value, "$options": "i"}})
            except Exception:
                cnt = 0
            counts[key] = cnt

        if not counts:
            return None

        # Pick the key with the highest positive count
        positive = {k: v for k, v in counts.items() if v and v > 0}
        if not positive:
            # No evidence; prefer assignee if proposed
            if "assignee_name" in proposed:
                return "assignee_name"
            return None

        # Sort keys by count desc then by preference order
        preference = {"assignee_name": 0, "project_name": 1, "cycle_name": 2, "module_name": 3}
        chosen = sorted(positive.items(), key=lambda kv: (-kv[1], preference.get(kv[0], 99)))[0][0]
        return chosen

    async def _aggregate_count(self, collection: str, match_filter: Dict[str, Any]) -> int:
        """Run a count via aggregation to avoid needing a dedicated count tool."""
        try:
            result = await mongodb_tools.execute_tool("aggregate", {
                "database": DATABASE_NAME,
                "collection": collection,
                "pipeline": [{"$match": match_filter}, {"$count": "total"}]
            })
            if isinstance(result, list) and result and isinstance(result[0], dict) and "total" in result[0]:
                return int(result[0]["total"])  # type: ignore
        except Exception:
            pass
        return 0

class PipelineGenerator:
    """Generates MongoDB aggregation pipelines based on query intent and relationships"""

    def __init__(self):
        self.relationship_cache = {}  # Cache for computed relationship paths

    def generate_pipeline(self, intent: QueryIntent) -> List[Dict[str, Any]]:
        """Generate MongoDB aggregation pipeline for the given intent"""
        pipeline: List[Dict[str, Any]] = []

        # Start with the primary collection
        collection = intent.primary_entity

        # Build sanitized filters once
        primary_filters = self._extract_primary_filters(intent.filters, collection) if intent.filters else {}
        secondary_filters = self._extract_secondary_filters(intent.filters, collection) if intent.filters else {}

        # COUNT-ONLY: no group_by, no details → do not add lookups
        if (("count" in intent.aggregations) or intent.wants_count) and not intent.group_by and not intent.wants_details:
            # Combine all filters for optimal count query
            all_filters = {}
            if primary_filters:
                all_filters.update(primary_filters)
            if secondary_filters:
                all_filters.update(secondary_filters)

            if all_filters:
                return [{"$match": all_filters}, {"$count": "total"}]
            else:
                return [{"$count": "total"}]

        # Add filters for the primary collection
        if primary_filters:
            pipeline.append({"$match": primary_filters})

        # Ensure lookups needed by secondary filters or grouping are included
        required_relations: Set[str] = set()

        # Determine relation tokens per primary collection
        relation_alias_by_token = {
            'workItem': {
                # All are embedded on workItem; no lookup needed for filters/grouping
                'project': None,
                'assignee': None,
                'module': None,
                'cycle': None,
            },
            'project': {
                'cycle': 'cycles',
                'module': 'modules',
                'assignee': 'members',
                'page': 'pages',
                'project': None,
            },
            'cycle': {
                'project': 'project',
            },
            'module': {
                'project': 'project',
                'assignee': 'assignee',
            },
            'page': {
                'project': 'project',  # key in REL is 'project', alias is 'projectDoc'
                'cycle': 'linkedCycle',
                'module': 'linkedModule',
            },
            'members': {
                'project': 'project',
            },
            'projectState': {
                'project': 'project',
            },
        }.get(collection, {})

        # Include explicit target entities requested by the intent (supports multi-hop like "project.cycles")
        for rel in (intent.target_entities or []):
            if not isinstance(rel, str) or not rel:
                continue
            first_hop = rel.split(".")[0]
            if first_hop in REL.get(collection, {}):
                required_relations.add(rel)

        # Filters → relations (map filter tokens to relation alias for this primary)
        if intent.filters:
            # For workItem, project/assignee/cycle/modules are embedded; no lookups needed for name filters
            if collection != 'workItem':
                if 'project_name' in intent.filters and relation_alias_by_token.get('project') in REL.get(collection, {}):
                    required_relations.add(relation_alias_by_token['project'])
                if 'cycle_name' in intent.filters and relation_alias_by_token.get('cycle') in REL.get(collection, {}):
                    required_relations.add(relation_alias_by_token['cycle'])
                if 'assignee_name' in intent.filters and relation_alias_by_token.get('assignee') in REL.get(collection, {}):
                    required_relations.add(relation_alias_by_token['assignee'])
                if 'module_name' in intent.filters and relation_alias_by_token.get('module') in REL.get(collection, {}):
                    required_relations.add(relation_alias_by_token['module'])
            if 'member_role' in intent.filters:
                # Require member join depending on collection
                if collection == 'workItem' and 'assignee' in REL.get(collection, {}):
                    required_relations.add('assignee')
                if collection == 'project' and 'members' in REL.get('project', {}):
                    required_relations.add('members')
                if collection == 'module' and 'assignee' in REL.get('module', {}):
                    required_relations.add('assignee')

            # Multi-hop fallbacks for cycle/module via project when direct relations are absent
            if 'cycle_name' in intent.filters and ('cycle' not in REL.get(collection, {}) and 'cycles' not in REL.get(collection, {}) and 'linkedCycle' not in REL.get(collection, {})):
                if 'project' in REL.get(collection, {}) and 'cycles' in REL.get('project', {}):
                    required_relations.add('project')
                    required_relations.add('project.cycles')
            if 'module_name' in intent.filters and ('module' not in REL.get(collection, {}) and 'modules' not in REL.get(collection, {}) and 'linkedModule' not in REL.get(collection, {})):
                if 'project' in REL.get(collection, {}) and 'modules' in REL.get('project', {}):
                    required_relations.add('project')
                    required_relations.add('project.modules')

        # Group-by → relations
        for token in (intent.group_by or []):
            # Map grouping token to relation alias for this primary
            rel_alias = relation_alias_by_token.get(token)
            if rel_alias and rel_alias in REL.get(collection, {}):
                required_relations.add(rel_alias)
            # Multi-hop fallback for grouping keys that require project hop (e.g., cycle/module on workItem)
            if token == 'cycle' and ('cycle' not in REL.get(collection, {}) and 'cycles' not in REL.get(collection, {})):
                if 'project' in REL.get(collection, {}) and 'cycles' in REL.get('project', {}):
                    required_relations.add('project')
                    required_relations.add('project.cycles')
            if token == 'module' and ('module' not in REL.get(collection, {}) and 'modules' not in REL.get(collection, {})):
                if 'project' in REL.get(collection, {}) and 'modules' in REL.get('project', {}):
                    required_relations.add('project')
                    required_relations.add('project.modules')

        # Add relationship lookups (supports multi-hop via dot syntax like project.states)
        for target_entity in sorted(required_relations):
            # Allow multi-hop relation names like "project.cycles"
            hops = target_entity.split(".")
            current_collection = collection
            local_prefix = None
            for hop in hops:
                if hop not in REL.get(current_collection, {}):
                    break
                relationship = REL[current_collection][hop]
                lookup = build_lookup_stage(relationship["target"], relationship, current_collection, local_field_prefix=local_prefix)
                if lookup:
                    pipeline.append(lookup)
                    # If array relation, unwind the alias used in $lookup
                    is_many = bool(relationship.get("isArray") or relationship.get("many", False))
                    alias_name = relationship.get("as") or relationship.get("alias") or relationship.get("target")
                    if is_many:
                        pipeline.append({
                            "$unwind": {"path": f"${alias_name}", "preserveNullAndEmptyArrays": True}
                        })
                    # Set local prefix to the alias for chaining next hop
                    local_prefix = alias_name
                current_collection = relationship["target"]

        # Add secondary filters (on joined collections)
        if secondary_filters:
            pipeline.append({"$match": secondary_filters})

        # Add grouping if requested
        if intent.group_by:
            group_id_expr: Any
            id_fields: Dict[str, Any] = {}
            for token in intent.group_by:
                field_path = self._resolve_group_field(intent.primary_entity, token)
                if field_path:
                    id_fields[token] = f"${field_path}"
            if not id_fields:
                # Fallback: do nothing if we can't resolve
                pass
            else:
                group_id_expr = list(id_fields.values())[0] if len(id_fields) == 1 else id_fields
                group_stage: Dict[str, Any] = {
                    "$group": {
                        "_id": group_id_expr,
                        "count": {"$sum": 1},
                    }
                }
                if intent.wants_details:
                    group_stage["$group"]["items"] = {
                        "$push": {
                            "_id": "$_id",
                            "displayBugNo": "$displayBugNo",
                            "title": "$title",
                            "priority": "$priority",
                        }
                    }
                pipeline.append(group_stage)
                # Sorting for grouped results: default to count desc, allow sorting by grouped keys
                if intent.sort_order:
                    sort_key, sort_dir = next(iter(intent.sort_order.items()))
                    if sort_key in intent.group_by:
                        # Sort by the grouped key inside _id
                        if len(id_fields) == 1:
                            pipeline.append({"$sort": {"_id": sort_dir}})
                        else:
                            pipeline.append({"$sort": {f"_id.{sort_key}": sort_dir}})
                    else:
                        pipeline.append({"$sort": {"count": -1}})
                else:
                    pipeline.append({"$sort": {"count": -1}})
                # Present a tidy shape
                project_shape: Dict[str, Any] = {"count": 1}
                if intent.wants_details:
                    project_shape["items"] = 1
                project_shape["group"] = "$_id"
                pipeline.append({"$project": project_shape})
                # Respect limit on grouped results
                if intent.limit:
                    pipeline.append({"$limit": intent.limit})

        # Add aggregations like count (skip count when details are requested)
        if intent.aggregations and not intent.wants_details and not intent.group_by:
            for agg in intent.aggregations:
                if agg == 'count':
                    pipeline.append({"$count": "total"})
                    return pipeline  # Count is terminal

        # Determine projections for details (skip when grouping since we reshape after $group)
        effective_projections: List[str] = intent.projections
        if intent.wants_details and not intent.group_by and not effective_projections:
            effective_projections = self._get_default_projections(intent.primary_entity)

        # Add sorting (handle custom priority order) — skip if already grouped
        added_priority_rank = False
        if intent.sort_order and not intent.group_by:
            if 'priority' in intent.sort_order:
                # Only compute rank if priority is part of projections to avoid surprising invisible sorts
                if (effective_projections and 'priority' in effective_projections) or (not effective_projections):
                    added_priority_rank = True
                    pipeline.append({
                        "$addFields": {
                            "_priorityRank": {
                                "$switch": {
                                    "branches": [
                                        {"case": {"$eq": ["$priority", "URGENT"]}, "then": 5},
                                        {"case": {"$eq": ["$priority", "HIGH"]}, "then": 4},
                                        {"case": {"$eq": ["$priority", "MEDIUM"]}, "then": 3},
                                        {"case": {"$eq": ["$priority", "LOW"]}, "then": 2},
                                        {"case": {"$eq": ["$priority", "NONE"]}, "then": 1}
                                    ],
                                    "default": 0
                                }
                            }
                        }
                    })
                    # Use computed rank for sorting direction provided
                    direction = intent.sort_order.get('priority', -1)
                    pipeline.append({"$sort": {"_priorityRank": direction}})
                else:
                    pipeline.append({"$sort": intent.sort_order})
            elif 'state' in intent.sort_order and collection == 'workItem':
                # Sort by state via embedded state.name.
                pipeline.append({"$sort": {"state.name": intent.sort_order.get('state', 1)}})
            else:
                pipeline.append({"$sort": intent.sort_order})

        # Compute projected aliases for joined relations so projections include them when needed
        projected_aliases: Set[str] = set()
        if required_relations:
            for rel_path in sorted(required_relations):
                hops = rel_path.split(".")
                current_collection = collection
                for hop in hops:
                    if hop not in REL.get(current_collection, {}):
                        break
                    relationship = REL[current_collection][hop]
                    alias_name = relationship.get("as") or relationship.get("alias") or relationship.get("target")
                    if alias_name:
                        projected_aliases.add(alias_name)
                    current_collection = relationship["target"]

        # Add projections after sorting so computed fields can be hidden
        if effective_projections and not intent.group_by:
            projection = self._generate_projection(effective_projections, sorted(list(projected_aliases)), intent.primary_entity)
            # Ensure we exclude helper fields from output
            pipeline.append({"$project": projection})
        # Always remove priority rank helper if it was added
        if added_priority_rank:
            pipeline.append({"$unset": "_priorityRank"})

        # Add limit (only for non-grouped queries; grouped handled above)
        if intent.limit and not intent.group_by:
            pipeline.append({"$limit": intent.limit})

        return pipeline

    def _extract_primary_filters(self, filters: Dict[str, Any], collection: str) -> Dict[str, Any]:
        """Extract filters that apply to the primary collection"""
        primary_filters = {}

        if collection == "workItem":
            if 'status' in filters:
                primary_filters['status'] = filters['status']
            if 'priority' in filters:
                primary_filters['priority'] = filters['priority']
            if 'state' in filters:
                # Map logical state filter to embedded field
                primary_filters['state.name'] = filters['state']

        elif collection == "project":
            if 'project_status' in filters:
                primary_filters['status'] = filters['project_status']

        elif collection == "cycle":
            if 'cycle_status' in filters:
                primary_filters['status'] = filters['cycle_status']

        elif collection == "page":
            if 'page_visibility' in filters:
                primary_filters['visibility'] = filters['page_visibility']

        return primary_filters

    def _extract_secondary_filters(self, filters: Dict[str, Any], collection: str) -> Dict[str, Any]:
        """Extract filters that apply to joined collections, guarded by available relations."""
        s: Dict[str, Any] = {}

        # Project name: allow both embedded project.name and joined alias projectDoc.name
        if 'project_name' in filters:
            s['$or'] = [
                {'project.name': {'$regex': filters['project_name'], '$options': 'i'}},
                {'projectDoc.name': {'$regex': filters['project_name'], '$options': 'i'}},
            ]

        # Assignee name via joined alias 'assignees' (only if relation exists)
        if 'assignee_name' in filters and 'assignee' in REL.get(collection, {}):
            # Prefer embedded assignee names when present; joined alias may be 'assignees'
            s['$or'] = s.get('$or', []) + [
                {'assignee.name': {'$regex': filters['assignee_name'], '$options': 'i'}},
                {'assignees.name': {'$regex': filters['assignee_name'], '$options': 'i'}},
            ]
        # Member role filter when relation exists
        if 'member_role' in filters:
            # For workItem: embedded assignee or joined members
            if collection == 'workItem' and 'assignee' in REL.get(collection, {}):
                s['$or'] = s.get('$or', []) + [
                    {'assignee.role': {'$regex': f"^{filters['member_role']}$", '$options': 'i'}},
                    {'assignees.role': {'$regex': f"^{filters['member_role']}$", '$options': 'i'}},
                ]
            # For project: through members join
            if collection == 'project' and 'members' in REL.get('project', {}):
                s['members.role'] = {'$regex': f"^{filters['member_role']}$", '$options': 'i'}
            # For module: embedded assignee or joined members
            if collection == 'module' and 'assignee' in REL.get('module', {}):
                s['$or'] = s.get('$or', []) + [
                    {'assignee.role': {'$regex': f"^{filters['member_role']}$", '$options': 'i'}},
                    {'assignees.role': {'$regex': f"^{filters['member_role']}$", '$options': 'i'}},
                ]

        # Cycle name filter: prefer embedded cycle.name; support joined aliases
        if 'cycle_name' in filters:
            if collection == 'workItem':
                s['cycle.name'] = {'$regex': filters['cycle_name'], '$options': 'i'}
            elif 'cycle' in REL.get(collection, {}):
                s['cycle.name'] = {'$regex': filters['cycle_name'], '$options': 'i'}
            elif 'cycles' in REL.get(collection, {}):
                s['cycles.name'] = {'$regex': filters['cycle_name'], '$options': 'i'}
            elif collection == 'page' and 'linkedCycle' in REL.get('page', {}):
                s['linkedCycleDocs.name'] = {'$regex': filters['cycle_name'], '$options': 'i'}

        # Module name filter: prefer embedded modules.name; support joined aliases
        if 'module_name' in filters:
            if collection == 'workItem':
                s['modules.name'] = {'$regex': filters['module_name'], '$options': 'i'}
            elif 'module' in REL.get(collection, {}):
                s['module.name'] = {'$regex': filters['module_name'], '$options': 'i'}
            elif 'modules' in REL.get(collection, {}):
                s['modules.name'] = {'$regex': filters['module_name'], '$options': 'i'}
            elif collection == 'page' and 'linkedModule' in REL.get('page', {}):
                s['linkedModuleDocs.name'] = {'$regex': filters['module_name'], '$options': 'i'}

        return s

    def _generate_lookup_stage(self, from_collection: str, target_entity: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        # Deprecated in favor of build_lookup_stage imported from registry
        if from_collection not in REL or target_entity not in REL[from_collection]:
            return {}
        relationship = REL[from_collection][target_entity]
        return build_lookup_stage(relationship["target"], relationship, from_collection)

    def _generate_projection(self, projections: List[str], target_entities: List[str], primary_entity: str) -> Dict[str, Any]:
        """Generate projection object"""
        projection = {"_id": 1}  # Always include ID

        # Add requested projections
        for field in projections:
            if field in ALLOWED_FIELDS.get(primary_entity, {}):
                projection[field] = 1

        # Add target entity fields
        for entity in target_entities:
            if entity in REL.get(primary_entity, {}):
                projection[entity] = 1

        return projection

    def _get_default_projections(self, primary_entity: str) -> List[str]:
        """Return sensible default fields for detail queries per collection.
        Only returns fields that are allow-listed for the given collection.
        """
        defaults_map: Dict[str, List[str]] = {
            "workItem": [
                "displayBugNo", "title", "priority",
                "state.name", "assignee",
                "project.name", "cycle.name", "modules.name",
                "createdTimeStamp"
            ],
            "project": [
                "projectDisplayId", "name", "status", "isActive", "isArchived", "createdTimeStamp",
                "createdBy.name"
            ],
            "cycle": [
                "title", "status", "startDate", "endDate"
            ],
            "members": [
                "name", "email", "role", "joiningDate"
            ],
            "page": [
                "title", "visibility", "createdAt"
            ],
            "module": [
                "title", "description", "isFavourite", "createdTimeStamp"
            ],
            "projectState": [
                "name", "subStates.name", "subStates.order"
            ],
        }

        candidates = defaults_map.get(primary_entity, ["_id"])  # fallback _id

        # Validate against allow-listed fields for safety
        allowed = ALLOWED_FIELDS.get(primary_entity, set())
        validated: List[str] = []
        for field in candidates:
            # Keep only fields that are explicitly allow-listed for primary entity
            if field in allowed:
                validated.append(field)

        # After computing validated, if it's empty, fall back to a minimal safe set
        if not validated:
            minimal = ["title", "priority", "createdTimeStamp"]
            validated = [f for f in minimal if f in allowed]
        return validated

    def _resolve_group_field(self, primary_entity: str, token: str) -> Optional[str]:
        """Map a grouping token to a concrete field path in the current pipeline."""
        mapping = {
            'workItem': {
                # Only relations that exist in REL for workItem
                'project': 'project.name',
                'assignee': 'assignee.name',
                'cycle': 'cycle.name',
                'module': 'modules.name',
                'state': 'state.name',
                'priority': 'priority',
            },
            'project': {
                'status': 'status',  # project status unchanged
            },
            'cycle': {
                'project': 'project.name',
                'status': 'status',  # cycle status unchanged
            },
            'page': {
                'project': 'projectDoc.name',
                'cycle': 'linkedCycleDocs.name',
                'module': 'linkedModuleDocs.name',
            },
        }
        entity_map = mapping.get(primary_entity, {})
        return entity_map.get(token)

class Planner:
    """Main query planner that orchestrates the entire process"""

    def __init__(self):
        self.generator = PipelineGenerator()
        self.llm_parser = LLMIntentParser()
        self.rule_parser = NaturalLanguageParser()

    async def plan_and_execute(self, query: str) -> Dict[str, Any]:
        """Plan and execute a natural language query"""
        try:
            # Ensure MongoDB connection
            await mongodb_tools.connect()

            # Parse intent via LLM (single source of truth)
            intent_source = "llm"
            intent: Optional[QueryIntent] = await self.llm_parser.parse(query)
            if not intent:
                # Fallback to rule-based parser
                intent = self.rule_parser.parse(query)
                intent_source = "rules"

            # Generate the pipeline
            pipeline = self.generator.generate_pipeline(intent)

            # Execute the query
            result = await mongodb_tools.execute_tool("aggregate", {
                "database": DATABASE_NAME,
                "collection": intent.primary_entity,
                "pipeline": pipeline
            })

            return {
                "success": True,
                "intent": intent.__dict__,
                "pipeline": pipeline,
                "result": result,
                "planner": intent_source
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "query": query
            }

# Global instance
query_planner = Planner()

async def plan_and_execute_query(query: str) -> Dict[str, Any]:
    """Convenience function to plan and execute queries"""
    return await query_planner.plan_and_execute(query)
