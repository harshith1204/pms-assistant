#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import re
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple

from registry import (
    ENTITIES, ALIASES, ALLOWED_FIELDS,
    resolve_field_alias, validate_fields,
    build_lookup_stage, entity_collection,
    build_multi_entity_pipeline, get_query_pattern_suggestions,
    analyze_relationship_complexity,
)

# ---------- PIPELINE TEMPLATES ----------

PIPELINE_TEMPLATES = {
    "cross_entity_join": {
        "description": "Join multiple entities with complex relationships",
        "template": [
            {"$match": "{root_filters}"},
            {"$lookup": {
                "from": "{target_collection}",
                "let": {"root_id": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["{target_field}", "$$root_id"]}}},
                    {"$lookup": {
                        "from": "{secondary_collection}",
                        "let": {"target_id": "$_id"},
                        "pipeline": [
                            {"$match": {"$expr": {"$eq": ["{secondary_field}", "$$target_id"]}}}
                        ],
                        "as": "secondary_data"
                    }}
                ],
                "as": "target_data"
            }},
            {"$unwind": {"path": "$target_data", "preserveNullAndEmptyArrays": True}}
        ],
        "variables": ["root_filters", "target_collection", "target_field", "secondary_collection", "secondary_field"]
    },

    "workload_distribution": {
        "description": "Analyze workload distribution across team members",
        "template": [
            {"$match": "{project_filter}"},
            {"$lookup": {
                "from": "ProjectManagement.members",
                "let": {"project_id": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$project._id", "$$project_id"]}}},
                    {"$lookup": {
                        "from": "ProjectManagement.workItem",
                        "let": {"member_id": "$staff._id"},
                        "pipeline": [
                            {"$match": {"$expr": {"$in": ["$$member_id", {"$ifNull": ["$assignee._id", []]}]}}},
                            {"$group": {
                                "_id": "$status",
                                "count": {"$sum": 1},
                                "items": {"$push": {"title": "$title", "priority": "$priority"}}
                            }}
                        ],
                        "as": "work_items_by_status"
                    }},
                    {"$addFields": {
                        "total_work_items": {"$sum": "$work_items_by_status.count"},
                        "completed_items": {
                            "$sum": {
                                "$map": {
                                    "input": "$work_items_by_status",
                                    "as": "status_group",
                                    "in": {"$cond": {
                                        "if": {"$in": ["$$status_group._id", ["COMPLETED", "CLOSED", "RESOLVED"]]},
                                        "then": "$$status_group.count",
                                        "else": 0
                                    }}
                                }
                            }
                        }
                    }}
                ],
                "as": "team_members"
            }},
            {"$unwind": {"path": "$team_members", "preserveNullAndEmptyArrays": True}},
            {"$sort": {"team_members.total_work_items": -1}}
        ],
        "variables": ["project_filter"]
    },

    "content_network_analysis": {
        "description": "Analyze relationships between pages, modules, and cycles",
        "template": [
            {"$match": "{project_filter}"},
            {"$lookup": {
                "from": "ProjectManagement.page",
                "let": {"project_id": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$project._id", "$$project_id"]}}},
                    {"$lookup": {
                        "from": "ProjectManagement.module",
                        "let": {"module_ids": {"$ifNull": ["$linkedModule", []]}},
                        "pipeline": [
                            {"$match": {"$expr": {"$in": ["$_id", "$$module_ids"]}}}
                        ],
                        "as": "linked_modules"
                    }},
                    {"$lookup": {
                        "from": "ProjectManagement.cycle",
                        "let": {"cycle_ids": {"$ifNull": ["$linkedCycle", []]}},
                        "pipeline": [
                            {"$match": {"$expr": {"$in": ["$_id", "$$cycle_ids"]}}}
                        ],
                        "as": "linked_cycles"
                    }},
                    {"$addFields": {
                        "module_count": {"$size": "$linked_modules"},
                        "cycle_count": {"$size": "$linked_cycles"},
                        "total_connections": {"$add": [{"$size": "$linked_modules"}, {"$size": "$linked_cycles"}]}
                    }}
                ],
                "as": "pages"
            }},
            {"$unwind": {"path": "$pages", "preserveNullAndEmptyArrays": True}},
            {"$sort": {"pages.total_connections": -1}}
        ],
        "variables": ["project_filter"]
    },

    "progress_tracking": {
        "description": "Track progress across cycles and work items",
        "template": [
            {"$match": "{project_filter}"},
            {"$lookup": {
                "from": "ProjectManagement.cycle",
                "let": {"project_id": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$project._id", "$$project_id"]}}},
                    {"$lookup": {
                        "from": "ProjectManagement.workItem",
                        "let": {"cycle_id": "$_id"},
                        "pipeline": [
                            {"$match": {"$expr": {"$eq": ["$cycleId", "$$cycle_id"]}}},
                            {"$group": {
                                "_id": {"status": "$status", "priority": "$priority"},
                                "count": {"$sum": 1},
                                "items": {"$push": {"title": "$title", "assignee": "$assignee"}}
                            }}
                        ],
                        "as": "work_item_summary"
                    }},
                    {"$addFields": {
                        "total_items": {"$sum": "$work_item_summary.count"},
                        "completed_items": {
                            "$sum": {
                                "$map": {
                                    "input": "$work_item_summary",
                                    "as": "summary",
                                    "in": {"$cond": {
                                        "if": {"$in": ["$$summary._id.status", ["COMPLETED", "CLOSED", "RESOLVED"]]},
                                        "then": "$$summary.count",
                                        "else": 0
                                    }}
                                }
                            }
                        },
                        "completion_percentage": {
                            "$cond": {
                                "if": {"$gt": [{"$sum": "$work_item_summary.count"}, 0]},
                                "then": {"$multiply": [
                                    {"$divide": [
                                        {"$sum": {
                                            "$map": {
                                                "input": "$work_item_summary",
                                                "as": "summary",
                                                "in": {"$cond": {
                                                    "if": {"$in": ["$$summary._id.status", ["COMPLETED", "CLOSED", "RESOLVED"]]},
                                                    "then": "$$summary.count",
                                                    "else": 0
                                                }}
                                            }
                                        }},
                                        {"$sum": "$work_item_summary.count"}
                                    ]},
                                    100
                                ]},
                                "else": 0
                            }
                        }
                    }}
                ],
                "as": "cycles"
            }},
            {"$unwind": {"path": "$cycles", "preserveNullAndEmptyArrays": True}},
            {"$sort": {"cycles.completion_percentage": -1}}
        ],
        "variables": ["project_filter"]
    }
}

def get_pipeline_template(template_name: str, variables: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get a pipeline template and substitute variables.
    """
    if template_name not in PIPELINE_TEMPLATES:
        raise ValueError(f"Template '{template_name}' not found")

    template = PIPELINE_TEMPLATES[template_name]["template"]
    template_str = str(template)

    for var_name, var_value in variables.items():
        if isinstance(var_value, str):
            var_value = f'"{var_value}"'
        elif isinstance(var_value, dict):
            var_value = str(var_value)
        template_str = template_str.replace(f"{{{var_name}}}", var_value)

    return eval(template_str)

def suggest_pipeline_template(query_description: str) -> List[str]:
    """
    Suggest appropriate pipeline templates based on query description.
    """
    suggestions = []
    query_lower = query_description.lower()

    if any(word in query_lower for word in ["workload", "distribution", "team", "member", "assignment"]):
        suggestions.append("workload_distribution")

    if any(word in query_lower for word in ["progress", "completion", "status", "cycle", "sprint"]):
        suggestions.append("progress_tracking")

    if any(word in query_lower for word in ["network", "connection", "link", "relationship", "page", "module"]):
        suggestions.append("content_network_analysis")

    if any(word in query_lower for word in ["join", "multiple", "complex", "cross", "relationship"]):
        suggestions.append("cross_entity_join")

    return suggestions

from constants import mongodb_tools, DATABASE_NAME

# ----------------- Parsing helpers -----------------

ENTITY_SYNONYMS = {
    "project": ["project", "projects"],
    "workItem": ["work item", "work items", "ticket", "tickets", "bug", "bugs", "issue", "issues", "task", "tasks"],
    "cycle": ["cycle", "sprint", "sprints", "cycles"],
    "module": ["module", "modules"],
    "members": ["member", "members", "assignee", "assignees", "people", "teammates", "users"],
    "page": ["page", "pages", "doc", "docs", "document", "documents"],
    "projectState": ["state master", "workflow", "workflow states", "project states"],
}

DEFAULT_PRIMARY = "workItem"

# Priority order for entity detection - main subjects come first
ENTITY_PRIORITY = {
    "workItem": 1,    # Highest priority - main work items
    "members": 2,     # Team members
    "page": 3,        # Pages/documents
    "module": 4,      # Modules
    "cycle": 5,       # Cycles/sprints
    "project": 6,     # Lowest priority - often used as filter
    "projectState": 7 # Workflow states
}

PRIORITY_WORDS = {
    "p0": ["p0","blocker","critical","highest"],
    "p1": ["p1","high","urgent"],
    "p2": ["p2","medium","normal"],
    "p3": ["p3","low","minor"],
}

STATE_WORDS = {
    "todo": ["todo","to do","backlog","open"],
    "in progress": ["in progress","doing","active","wip"],
    "review": ["review","code review","testing","qa"],
    "done": ["done","completed","closed","resolved","finished","shipped"],
}

GROUP_BY_SYNONYMS = {
    "state.name": ["state","status","workflow state"],
    "priority": ["priority","prio"],
    "assignee": ["assignee","assignees","owner","owners"],
    "project.name": ["project","project name"],
}

DATE_RANGES = {
    "today": (0, 0),
    "yesterday": (1, 1),
    "this week": (6, 0),
    "last week": (13, 7),
    "this month": (31, 0),
    "last 7 days": (7, 0),
    "last 14 days": (14, 0),
    "last 30 days": (30, 0),
}

# ----------------- Intent -----------------

@dataclass
class QueryIntent:
    root_entity: str
    traversals: List[Tuple[str, str]] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    group_by: Optional[str] = None
    projections: List[str] = field(default_factory=list)
    sort: Optional[Tuple[str, int]] = None
    limit: Optional[int] = None
    # NEW: detect special composite patterns (members↔workItems, pages↔modules/cycles)
    special: Optional[str] = None           # "members_with_workitems", "pages_by_module", "pages_by_cycle"
    special_args: Dict[str, Any] = field(default_factory=dict)

# ----------------- Planner -----------------

class QueryPlanner:

    async def plan_and_execute(self, nl: str) -> Dict[str, Any]:
        intent = self.parse(nl)

        # Handle special patterns first (return early with custom pipeline)
        special = None
        if intent.special == "members_with_workitems":
            special = self._pipeline_members_with_workitems(intent)
        elif intent.special == "pages_by_module":
            special = self._pipeline_pages_by_module(intent)
        elif intent.special == "pages_by_cycle":
            special = self._pipeline_pages_by_cycle(intent)
        elif intent.special == "team_productivity_analysis":
            special = self._pipeline_team_productivity_analysis(intent)
        elif intent.special == "project_health_dashboard":
            special = self._pipeline_project_health_dashboard(intent)
        elif intent.special == "complex_multi_entity_query":
            special = self._pipeline_complex_multi_entity_query(intent)

        if special is not None:
            pipeline, collection = special
        else:
            pipeline, collection = self.build_pipeline(intent)

        try:
            docs = await mongodb_tools.execute_tool("aggregate", {
                "database": DATABASE_NAME,
                "collection": collection,
                "pipeline": pipeline
            })

            result = {"success": True, "pipeline": pipeline, "data": docs}

            # Add analysis and insights
            analysis = analyze_query_results(result, nl)
            if analysis:
                result["analysis"] = analysis
                result["formatted_analysis"] = format_analysis_for_response(analysis)

            return result
        except Exception as e:
            return {"success": False, "error": str(e), "pipeline": pipeline}

    # ---------- parse ----------

    def parse(self, nl: str) -> QueryIntent:
        text = nl.strip().lower()

        # 1) root entity
        root_entity = self._detect_entity(text) or DEFAULT_PRIMARY

        # 2) filters
        filters: Dict[str, Any] = {}
        filters.update(self._project_filter(text))
        filters.update(self._priority_filter(text))
        filters.update(self._state_filter(text))
        filters.update(self._date_filter(text))
        filters.update(self._visibility_filter(text))

        # 3) grouping/sort/limit
        group_by = self._group_by(text)
        limit = self._limit(text)
        sort = self._sort(text)

        # 4) traversals
        traversals = self._derive_traversals(root_entity, text)

        # 5) projections (whitelisted)
        projections = validate_fields(root_entity, self._default_projections(root_entity, group_by))

        # 6) special patterns
        special, special_args = self._detect_special_patterns(text, filters)

        return QueryIntent(
            root_entity=root_entity,
            traversals=traversals,
            filters=filters,
            group_by=group_by,
            projections=projections,
            sort=sort,
            limit=limit,
            special=special,
            special_args=special_args,
        )

    # ---------- general pipeline ----------

    def build_pipeline(self, intent: QueryIntent) -> Tuple[List[Dict[str, Any]], str]:
        p: List[Dict[str, Any]] = []

        root = intent.root_entity

        # local (root) filters only
        root_filters = {
            k: v for k, v in intent.filters.items()
            if not k.startswith(("project.", "assignee.", "stateMaster.", "state."))
            and k not in ("visibility",)  # visibility is for pages; avoid leaking to others
        }
        if root_filters:
            p.append({"$match": root_filters})

        # traversals ($lookup)
        for src, edge in intent.traversals:
            if src == root:
                p.append(build_lookup_stage(src, edge))
                many = ENTITIES[src]["edges"][edge]["many"]
                if not many:
                    p.append({"$unwind": {"path": f"${edge}", "preserveNullAndEmptyArrays": True}})

        # If project-scoped filter on non-project root, join to project and filter
        if root != "project" and any(k.startswith("project.") for k in intent.filters):
            if "project" in ENTITIES[root]["edges"]:
                p.append(build_lookup_stage(root, "project"))
                p.append({"$unwind": {"path": "$project", "preserveNullAndEmptyArrays": True}})
                proj_filters = {k: v for k, v in intent.filters.items() if k.startswith("project.")}
                p.append({"$match": proj_filters})

        # Post-join filters for joined fields
        joined_filters = {
            k: v for k, v in intent.filters.items()
            if any(k.startswith(prefix) for prefix in ["assignee.","state.","stateMaster.","visibility"])
        }
        if joined_filters:
            p.append({"$match": joined_filters})

        # Projection
        if intent.projections:
            p.append({"$project": {f: 1 for f in intent.projections}})

        # Grouping
        if intent.group_by:
            gb = intent.group_by
            p.append({
                "$group": {
                    "_id": f"${gb}",
                    "count": {"$sum": 1},
                    "items": {"$push": "$$ROOT"}
                }
            })
            if not intent.sort:
                p.append({"$sort": {"count": -1}})

        # Sort
        if intent.sort:
            field, direction = intent.sort
            p.append({"$sort": {field: direction}})

        # Limit
        if intent.limit:
            p.append({"$limit": intent.limit})

        return p, entity_collection(root)

    # ---------- special pattern detection ----------

    def _detect_special_patterns(self, text: str, filters: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        # MEMBERS WITH THEIR TASKS
        if (re.search(r"\bmembers?\b", text) and
            (re.search(r"\btheir (tasks|work items|tickets|issues)\b", text) or
             re.search(r"\bwith (tasks|work items|tickets|issues)\b", text) or
             re.search(r"\bassigned\b", text))):
            # choose root: project if we have a project filter; else members
            root = "project" if any(k.startswith("project.") for k in filters) else "members"
            return "members_with_workitems", {"root": root}

        # PAGES BY MODULE
        if re.search(r"\bpages?\b", text) and re.search(r"\bmodules?\b", text):
            return "pages_by_module", {"root": "project" if any(k.startswith("project.") for k in filters) else "project"}

        # PAGES BY CYCLE
        if re.search(r"\bpages?\b", text) and re.search(r"\bcycles?\b|\bsprints?\b", text):
            return "pages_by_cycle", {"root": "project" if any(k.startswith("project.") for k in filters) else "project"}

        # MEMBERS → open tasks this week
        if (re.search(r"\bmembers?\b", text) and
            (re.search(r"\bopen (tasks|tickets|issues|work items)\b", text) or "open tasks" in text) and
            ("this week" in text or "current week" in text)):
            root = "project" if any(k.startswith("project.") for k in filters) else "members"
            return "members_open_this_week", {"root": root}

        # MODULE → tickets grouped by state
        if (re.search(r"\bmodules?\b", text) and
            re.search(r"\b(tickets|work items|issues)\b", text) and
            re.search(r"group(?:ed)?\s+by\s+state", text)):
            return "module_tickets_by_state", {"root": "project" if any(k.startswith("project.") for k in filters) else "project"}

        # ADVANCED CROSS-ENTITY PATTERNS

        # TEAM PRODUCTIVITY ANALYSIS
        if (re.search(r"\b(team|member|people)\b", text) and
            re.search(r"\b(productivit|workload|performance|contribution)\b", text)):
            root = "project" if any(k.startswith("project.") for k in filters) else "members"
            return "team_productivity_analysis", {"root": root}

        # PROJECT HEALTH DASHBOARD
        if (re.search(r"\bproject\b", text) and
            re.search(r"\b(health|status|progress|overview|dashboard)\b", text)):
            return "project_health_dashboard", {"root": "project"}

        # CROSS-MODULE ANALYSIS
        if (re.search(r"\bmodules?\b", text) and
            re.search(r"\b(analysis|comparison|overview)\b", text)):
            return "module_cross_analysis", {"root": "project"}

        # WORKFLOW STATE ANALYSIS
        if (re.search(r"\b(workflow|state|status)\b", text) and
            re.search(r"\b(analysis|distribution|flow)\b", text)):
            return "workflow_state_analysis", {"root": "workItem"}

        # CONTENT COLLABORATION NETWORK
        if (re.search(r"\b(pages?|content|docs?)\b", text) and
            re.search(r"\b(collaboration|network|connections?|links?)\b", text)):
            return "content_collaboration_network", {"root": "page"}

        # RESOURCE ALLOCATION ANALYSIS
        if (re.search(r"\b(resource|allocation|assignment)\b", text) or
            (re.search(r"\bwho\b", text) and re.search(r"\bworking\s+on\b", text))):
            root = "project" if any(k.startswith("project.") for k in filters) else "workItem"
            return "resource_allocation_analysis", {"root": root}

        # COMPLEX MULTI-ENTITY QUERIES
        entity_count = sum(1 for entity in ENTITY_SYNONYMS.keys() if any(w in text for w in ENTITY_SYNONYMS[entity]))
        if entity_count >= 3:  # If 3+ entities mentioned, it's a complex query
            return "complex_multi_entity_query", {"entities_mentioned": entity_count}

        return None, {}

    # ---------- special pipelines ----------

    def _pipeline_members_with_workitems(self, intent: QueryIntent) -> Tuple[List[Dict[str, Any]], str]:
        """
        For a given project (if specified), list members and attach their work items.
        Match on either assignee[*]._id == members.staff._id (or memberId) OR createdBy._id == members.staff._id.
        """
        has_project_filter = any(k.startswith("project.") for k in intent.filters)
        project_match = [{ "$match": {k: v} } for k, v in intent.filters.items() if k.startswith("project.")]
        # choose collection
        if has_project_filter:
            # Root: Project → $lookup Members (nested $lookup → WorkItem)
            p: List[Dict[str, Any]] = []
            # If a project.name regex exists, it applies to joined project docs (we are already in project collection)
            # Convert "project.name" -> "name" for direct project filter
            direct_filters = {}
            for k, v in intent.filters.items():
                if k.startswith("project."):
                    direct_filters[k.replace("project.", "")] = v
            if direct_filters:
                p.append({"$match": direct_filters})

            p.append({
                "$lookup": {
                    "from": "ProjectManagement.members",
                    "let": { "pid": "$_id" },
                    "pipeline": [
                        { "$match": { "$expr": { "$eq": ["$project._id", "$$pid"] } } },
                        { "$project": {
                            "_id": 1, "name": 1, "email": 1, "role": 1,
                            "memberId": 1, "staff": 1
                        }},
                        {
                            "$lookup": {
                                "from": "ProjectManagement.workItem",
                                "let": { "mid": "$staff._id", "pid": "$$pid" },
                                "pipeline": [
                                    { "$match": { "$expr": {
                                        "$and": [
                                            { "$eq": ["$project._id", "$$pid"] },
                                            { "$or": [
                                                { "$in": ["$$mid", {"$ifNull": ["$assignee._id", []]}] },
                                                { "$eq": ["$createdBy._id", "$$mid"] }
                                            ]}
                                        ]
                                    }}},
                                    { "$project": {
                                        "_id": 1, "displayBugNo": 1, "title": 1,
                                        "priority": 1, "status": 1,
                                        "state": 1, "createdTimeStamp": 1
                                    }}
                                ],
                                "as": "workItems"
                            }
                        },
                        { "$addFields": { "workItemCount": { "$size": "$workItems" } } }
                    ],
                    "as": "members"
                }
            })
            # Optional sort members by workload desc
            p.extend([
                { "$unwind": { "path": "$members", "preserveNullAndEmptyArrays": True } },
                { "$sort": { "members.workItemCount": -1 } },
                { "$group": { "_id": "$_id", "project": { "$first": "$$ROOT" }, "members": { "$push": "$members" } } },
                { "$replaceRoot": { "newRoot": { "$mergeObjects": ["$project", { "members": "$members" }] } } }
            ])
            return p, entity_collection("project")
        else:
            # Root: Members → $lookup WorkItem (no project filter)
            p: List[Dict[str, Any]] = []
            p.append({
                "$lookup": {
                    "from": "ProjectManagement.workItem",
                    "let": { "mid": "$staff._id", "pid": "$project._id" },
                    "pipeline": [
                        { "$match": { "$expr": {
                            "$and": [
                                { "$eq": ["$project._id", "$$pid"] },
                                { "$or": [
                                    { "$in": ["$$mid", {"$ifNull": ["$assignee._id", []]}] },
                                    { "$eq": ["$createdBy._id", "$$mid"] }
                                ]}
                            ]
                        }}},
                        { "$project": {
                            "_id": 1, "displayBugNo": 1, "title": 1,
                            "priority": 1, "status": 1, "state": 1, "createdTimeStamp": 1
                        }}
                    ],
                    "as": "workItems"
                }
            })
            p.append({ "$addFields": { "workItemCount": { "$size": "$workItems" } } })
            p.append({ "$sort": { "workItemCount": -1 } })
            return p, entity_collection("members")

    def _pipeline_pages_by_module(self, intent: QueryIntent) -> Tuple[List[Dict[str, Any]], str]:
        """
        For a project, list modules with the pages that link to them via page.linkedModule[].
        """
        p: List[Dict[str, Any]] = []
        # Convert project.* filters for project collection
        direct_filters = {}
        for k, v in intent.filters.items():
            if k.startswith("project."):
                direct_filters[k.replace("project.", "")] = v
        if direct_filters:
            p.append({"$match": direct_filters})

        # modules + nested pages lookup
        p.append({
            "$lookup": {
                "from": "ProjectManagement.module",
                "let": { "pid": "$_id" },
                "pipeline": [
                    { "$match": { "$expr": { "$eq": ["$project._id", "$$pid"] } } },
                    { "$project": { "_id": 1, "title": 1, "assignee": 1 } },
                    {
                        "$lookup": {
                            "from": "ProjectManagement.page",
                            "let": { "mid": "$_id", "pid": "$$pid" },
                            "pipeline": [
                                { "$match": { "$expr": {
                                    "$and": [
                                        { "$eq": ["$project._id", "$$pid"] },
                                        { "$in": ["$$mid", {"$ifNull": ["$linkedModule", []]}] }
                                    ]
                                }}},
                                { "$project": { "_id": 1, "title": 1, "visibility": 1, "createdAt": 1, "createdBy": 1 } }
                            ],
                            "as": "pages"
                        }
                    },
                    { "$addFields": { "pageCount": { "$size": "$pages" } } }
                ],
                "as": "modules"
            }
        })
        # sort modules with most-linked pages first (optional)
        p.extend([
            { "$unwind": { "path": "$modules", "preserveNullAndEmptyArrays": True } },
            { "$sort": { "modules.pageCount": -1 } },
            { "$group": { "_id": "$_id", "project": { "$first": "$$ROOT" }, "modules": { "$push": "$modules" } } },
            { "$replaceRoot": { "newRoot": { "$mergeObjects": ["$project", { "modules": "$modules" }] } } }
        ])
        return p, entity_collection("project")

    def _pipeline_pages_by_cycle(self, intent: QueryIntent) -> Tuple[List[Dict[str, Any]], str]:
        """
        For a project, list cycles with the pages that link to them via page.linkedCycle[].
        """
        p: List[Dict[str, Any]] = []
        direct_filters = {}
        for k, v in intent.filters.items():
            if k.startswith("project."):
                direct_filters[k.replace("project.", "")] = v
        if direct_filters:
            p.append({"$match": direct_filters})

        p.append({
            "$lookup": {
                "from": "ProjectManagement.cycle",
                "let": { "pid": "$_id" },
                "pipeline": [
                    { "$match": { "$expr": { "$eq": ["$project._id", "$$pid"] } } },
                    { "$project": { "_id": 1, "title": 1, "status": 1, "startDate": 1, "endDate": 1 } },
                    {
                        "$lookup": {
                            "from": "ProjectManagement.page",
                            "let": { "cid": "$_id", "pid": "$$pid" },
                            "pipeline": [
                                { "$match": { "$expr": {
                                    "$and": [
                                        { "$eq": ["$project._id", "$$pid"] },
                                        { "$in": ["$$cid", {"$ifNull": ["$linkedCycle", []]}] }
                                    ]
                                }}},
                                { "$project": { "_id": 1, "title": 1, "visibility": 1, "createdAt": 1, "createdBy": 1 } }
                            ],
                            "as": "pages"
                        }
                    },
                    { "$addFields": { "pageCount": { "$size": "$pages" } } }
                ],
                "as": "cycles"
            }
        })
        p.extend([
            { "$unwind": { "path": "$cycles", "preserveNullAndEmptyArrays": True } },
            { "$sort": { "cycles.pageCount": -1 } },
            { "$group": { "_id": "$_id", "project": { "$first": "$$ROOT" }, "cycles": { "$push": "$cycles" } } },
            { "$replaceRoot": { "newRoot": { "$mergeObjects": ["$project", { "cycles": "$cycles" }] } } }
        ])
        return p, entity_collection("project")

    # ---------- ADVANCED SPECIAL PIPELINES ----------

    def _pipeline_team_productivity_analysis(self, intent: QueryIntent) -> Tuple[List[Dict[str, Any]], str]:
        """
        Analyze team productivity with work items, created content, and assignments.
        """
        root = intent.special_args.get("root", "members")

        if root == "members":
            p = [
                # Lookup work items assigned to each member
                {
                    "$lookup": {
                        "from": "ProjectManagement.workItem",
                        "let": { "member_id": "$staff._id", "project_id": "$project._id" },
                        "pipeline": [
                            { "$match": { "$expr": {
                                "$and": [
                                    { "$eq": ["$project._id", "$$project_id"] },
                                    { "$or": [
                                        { "$in": ["$$member_id", {"$ifNull": ["$assignee._id", []]}] },
                                        { "$eq": ["$createdBy._id", "$$member_id"] }
                                    ]}
                                ]
                            }}}
                        ],
                        "as": "work_items"
                    }
                },
                # Lookup pages created by each member
                {
                    "$lookup": {
                        "from": "ProjectManagement.page",
                        "let": { "member_id": "$staff._id", "project_id": "$project._id" },
                        "pipeline": [
                            { "$match": { "$expr": {
                                "$and": [
                                    { "$eq": ["$project._id", "$$project_id"] },
                                    { "$eq": ["$createdBy._id", "$$member_id"] }
                                ]
                            }}}
                        ],
                        "as": "created_pages"
                    }
                },
                # Add productivity metrics
                {
                    "$addFields": {
                        "total_work_items": { "$size": "$work_items" },
                        "total_pages": { "$size": "$created_pages" },
                        "productivity_score": {
                            "$add": [
                                { "$size": "$work_items" },
                                { "$multiply": [{ "$size": "$created_pages" }, 0.5] }
                            ]
                        }
                    }
                },
                { "$sort": { "productivity_score": -1 } }
            ]
            return p, entity_collection("members")
        else:
            # Project-based view
            return self._pipeline_members_with_workitems(intent)

    def _pipeline_project_health_dashboard(self, intent: QueryIntent) -> Tuple[List[Dict[str, Any]], str]:
        """
        Comprehensive project health dashboard with multiple metrics.
        """
        p = []

        # Apply project filters
        if any(k.startswith("project.") for k in intent.filters):
            proj_filters = {k.replace("project.", ""): v for k, v in intent.filters.items() if k.startswith("project.")}
            p.append({"$match": proj_filters})

        # Lookup work items with status breakdown
        p.append({
            "$lookup": {
                "from": "ProjectManagement.workItem",
                "let": { "project_id": "$_id" },
                "pipeline": [
                    { "$match": { "$expr": { "$eq": ["$project._id", "$$project_id"] } } },
                    {
                        "$group": {
                            "_id": "$status",
                            "count": { "$sum": 1 },
                            "items": { "$push": { "title": "$title", "priority": "$priority" } }
                        }
                    }
                ],
                "as": "work_item_status_breakdown"
            }
        })

        # Lookup members and their activity
        p.append({
            "$lookup": {
                "from": "ProjectManagement.members",
                "let": { "project_id": "$_id" },
                "pipeline": [
                    { "$match": { "$expr": { "$eq": ["$project._id", "$$project_id"] } } },
                    {
                        "$lookup": {
                            "from": "ProjectManagement.workItem",
                            "let": { "member_id": "$staff._id" },
                            "pipeline": [
                                { "$match": { "$expr": { "$in": ["$$member_id", {"$ifNull": ["$assignee._id", []]}] } } },
                                { "$count": "work_item_count" }
                            ],
                            "as": "workload"
                        }
                    },
                    {
                        "$addFields": {
                            "work_item_count": { "$ifNull": [{ "$arrayElemAt": ["$workload.work_item_count", 0] }, 0] }
                        }
                    }
                ],
                "as": "team_members"
            }
        })

        # Lookup cycles and their progress
        p.append({
            "$lookup": {
                "from": "ProjectManagement.cycle",
                "let": { "project_id": "$_id" },
                "pipeline": [
                    { "$match": { "$expr": { "$eq": ["$project._id", "$$project_id"] } } },
                    {
                        "$lookup": {
                            "from": "ProjectManagement.workItem",
                            "let": { "cycle_id": "$_id" },
                            "pipeline": [
                                { "$match": { "$expr": { "$eq": ["$cycleId", "$$cycle_id"] } } },
                                {
                                    "$group": {
                                        "_id": "$status",
                                        "count": { "$sum": 1 }
                                    }
                                }
                            ],
                            "as": "work_item_status"
                        }
                    }
                ],
                "as": "active_cycles"
            }
        })

        # Add health metrics
        p.append({
            "$addFields": {
                "total_work_items": {
                    "$sum": "$work_item_status_breakdown.count"
                },
                "completed_work_items": {
                    "$sum": {
                        "$map": {
                            "input": "$work_item_status_breakdown",
                            "as": "status_group",
                            "in": {
                                "$cond": {
                                    "if": { "$in": ["$$status_group._id", ["COMPLETED", "CLOSED", "RESOLVED"]] },
                                    "then": "$$status_group.count",
                                    "else": 0
                                }
                            }
                        }
                    }
                },
                "team_size": { "$size": "$team_members" },
                "active_cycles_count": { "$size": "$active_cycles" }
            }
        })

        return p, entity_collection("project")

    def _pipeline_complex_multi_entity_query(self, intent: QueryIntent) -> Tuple[List[Dict[str, Any]], str]:
        """
        Handle complex queries involving multiple entities using intelligent pipeline building.
        """
        # Determine the best root entity based on the query
        root_entity = intent.root_entity

        # Identify all entities mentioned in the query
        mentioned_entities = []
        for entity in ENTITY_SYNONYMS.keys():
            if any(word in intent.root_entity or word in str(intent.filters) for word in ENTITY_SYNONYMS[entity]):
                mentioned_entities.append(entity)

        # Use the advanced multi-entity pipeline builder
        pipeline = build_multi_entity_pipeline(root_entity, mentioned_entities, intent.filters)

        # Add intelligent aggregations based on the query intent
        if intent.group_by:
            pipeline.append({
                "$group": {
                    "_id": f"${intent.group_by}",
                    "count": { "$sum": 1 },
                    "entities": { "$push": "$$ROOT" }
                }
            })

        return pipeline, entity_collection(root_entity)

    # ---------- detectors (vanilla) ----------

    def _detect_entity(self, text: str) -> Optional[str]:
        # Find all entities mentioned in the text
        found_entities = []
        for ent, words in ENTITY_SYNONYMS.items():
            for w in words:
                if re.search(rf"\b{re.escape(w)}\b", text):
                    found_entities.append(ent)
                    break

        if not found_entities:
            return None

        # Return the entity with highest priority (lowest number)
        return min(found_entities, key=lambda e: ENTITY_PRIORITY.get(e, 999))

    def _project_filter(self, text: str) -> Dict[str, Any]:
        m = re.search(r"(?:for|in|on)\s+project\s+([a-z0-9 _\-./]+)", text)
        if m:
            name = m.group(1).strip()
            return {"project.name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
        m = re.search(r'project\s+"([^"]+)"', text)
        if m:
            return {"project.name": {"$regex": f'^{re.escape(m.group(1))}$', "$options": "i"}}
        return {}

    def _priority_filter(self, text: str) -> Dict[str, Any]:
        for key, words in PRIORITY_WORDS.items():
            for w in words:
                if re.search(rf"\b{re.escape(w)}\b", text):
                    return {"priority": key.upper()}
        return {}

    def _state_filter(self, text: str) -> Dict[str, Any]:
        for key, words in STATE_WORDS.items():
            for w in words:
                if re.search(rf"\b{re.escape(w)}\b", text):
                    return {"state.name": key}
        return {}

    def _date_filter(self, text: str) -> Dict[str, Any]:
        for label, (days, offset) in DATE_RANGES.items():
            if label in text:
                end = datetime.now(timezone.utc) - timedelta(days=offset)
                start = end - timedelta(days=days) if days else end.replace(hour=0, minute=0, second=0, microsecond=0)
                return {"createdTimeStamp": {"$gte": start.isoformat()}}
        m = re.search(r"last\s+(\d{1,3})\s+days", text)
        if m:
            n = int(m.group(1))
            start = datetime.now(timezone.utc) - timedelta(days=n)
            return {"createdTimeStamp": {"$gte": start.isoformat()}}
        return {}

    def _visibility_filter(self, text: str) -> Dict[str, Any]:
        if "public pages" in text:
            return {"visibility": "PUBLIC"}
        if "private pages" in text:
            return {"visibility": "PRIVATE"}
        return {}

    def _group_by(self, text: str) -> Optional[str]:
        m = re.search(r"group(?:ed)?\s+by\s+([a-z ._]+)", text)
        if m:
            token = m.group(1).strip()
            for field, words in GROUP_BY_SYNONYMS.items():
                if token in words or token == field or token == field.split(".")[-1]:
                    return field
            return token
        return None

    def _limit(self, text: str) -> Optional[int]:
        m = re.search(r"top\s+(\d+)", text) or re.search(r"limit\s+(\d+)", text)
        return int(m.group(1)) if m else None

    def _sort(self, text: str) -> Optional[Tuple[str, int]]:
        if "sort by priority" in text:
            return ("priority", -1)
        if "sort by created" in text or "recent" in text or "latest" in text:
            return ("createdTimeStamp", -1)
        return None

    def _derive_traversals(self, root: str, text: str) -> List[Tuple[str, str]]:
        trav: List[Tuple[str, str]] = []
        if root == "project":
            if any(w in text for w in ENTITY_SYNONYMS["workItem"]): trav.append(("project","workItems"))
            if any(w in text for w in ENTITY_SYNONYMS["cycle"]):    trav.append(("project","cycles"))
            if any(w in text for w in ENTITY_SYNONYMS["module"]):   trav.append(("project","modules"))
            if any(w in text for w in ENTITY_SYNONYMS["page"]):     trav.append(("project","pages"))
            if any(w in text for w in ENTITY_SYNONYMS["members"]):  trav.append(("project","members"))
            if any(w in text for w in ENTITY_SYNONYMS["projectState"]): trav.append(("project","projectState"))

        if root == "workItem":
            if "project" in text or "in project" in text or "for project" in text:
                trav.append(("workItem","project"))

        if root in ("page","cycle","module","members"):
            if "project" in text:
                trav.append((root,"project"))
        return trav

    def _default_projections(self, root: str, group_by: Optional[str]) -> List[str]:
        common = {
            "project": ["_id","projectDisplayId","name","status","business._id","createdTimeStamp","updatedTimeStamp"],
            "workItem": ["_id","displayBugNo","title","priority","status","state.name","createdTimeStamp","assignee","project._id","project.name"],
            "cycle": ["_id","title","status","startDate","endDate","project._id","project.name"],
            "module": ["_id","title","isFavourite","assignee","project._id","project.name"],
            "members": ["_id","name","email","role","memberId","staff._id","project._id","project.name"],
            "page": ["_id","title","visibility","linkedCycle","linkedModule","createdBy._id","createdBy.name","createdAt","project._id","project.name"],
            "projectState": ["_id","name","subStates","projectId"],
        }.get(root, [])
        if group_by and group_by not in common:
            common.append(group_by)
        return common

    # ---------- RESULT OBSERVATION & ANALYSIS ----------

def analyze_query_results(query_result: Dict[str, Any], original_query: str) -> Dict[str, Any]:
    """
    Analyze query results to provide insights and observations for better response generation.
    """
    analysis = {
        "insights": [],
        "patterns": [],
        "anomalies": [],
        "recommendations": [],
        "summary_stats": {},
        "key_findings": []
    }

    if not query_result.get("success", False) or "data" not in query_result:
        return analysis

    data = query_result["data"]

    # Analyze data structure and patterns
    if isinstance(data, list):
        analysis["summary_stats"]["total_records"] = len(data)

        if data:
            # Analyze first record structure
            first_record = data[0] if isinstance(data[0], dict) else {}

            # Look for common PMS metrics
            if "total_work_items" in first_record:
                work_items = [r.get("total_work_items", 0) for r in data if isinstance(r, dict)]
                analysis["summary_stats"]["avg_work_items"] = sum(work_items) / len(work_items) if work_items else 0
                analysis["summary_stats"]["max_work_items"] = max(work_items) if work_items else 0
                analysis["summary_stats"]["min_work_items"] = min(work_items) if work_items else 0

            if "productivity_score" in first_record:
                scores = [r.get("productivity_score", 0) for r in data if isinstance(r, dict)]
                analysis["summary_stats"]["avg_productivity"] = sum(scores) / len(scores) if scores else 0

            if "completion_percentage" in first_record:
                completion_rates = [r.get("completion_percentage", 0) for r in data if isinstance(r, dict)]
                analysis["summary_stats"]["avg_completion_rate"] = sum(completion_rates) / len(completion_rates) if completion_rates else 0

            # Generate insights based on patterns
            _generate_insights(data, analysis, original_query)

    return analysis

def _generate_insights(data: List[Dict[str, Any]], analysis: Dict[str, Any], original_query: str) -> None:
    """Generate specific insights based on data patterns and query context."""
    query_lower = original_query.lower()

    if "productivity" in query_lower or "workload" in query_lower:
        _analyze_productivity_insights(data, analysis)
    elif "progress" in query_lower or "completion" in query_lower:
        _analyze_progress_insights(data, analysis)
    elif "team" in query_lower or "member" in query_lower:
        _analyze_team_insights(data, analysis)
    elif "network" in query_lower or "relationship" in query_lower:
        _analyze_network_insights(data, analysis)

def _analyze_productivity_insights(data: List[Dict[str, Any]], analysis: Dict[str, Any]) -> None:
    """Analyze productivity-related insights."""
    if not data:
        return

    # Find top performers
    if "productivity_score" in data[0]:
        sorted_by_productivity = sorted(data, key=lambda x: x.get("productivity_score", 0), reverse=True)
        top_performer = sorted_by_productivity[0]
        analysis["key_findings"].append(f"Top performer: {top_performer.get('name', 'Unknown')} with productivity score {top_performer.get('productivity_score', 0):.1f}")

    # Identify workload imbalances
    if "total_work_items" in data[0]:
        work_items = [r.get("total_work_items", 0) for r in data]
        avg_workload = sum(work_items) / len(work_items)
        high_workload = [r for r in data if r.get("total_work_items", 0) > avg_workload * 1.5]
        low_workload = [r for r in data if r.get("total_work_items", 0) < avg_workload * 0.5]

        if high_workload:
            analysis["insights"].append(f"{len(high_workload)} team member(s) have significantly higher workload than average")
        if low_workload:
            analysis["insights"].append(f"{len(low_workload)} team member(s) have significantly lower workload than average")

def _analyze_progress_insights(data: List[Dict[str, Any]], analysis: Dict[str, Any]) -> None:
    """Analyze progress and completion-related insights."""
    if not data:
        return

    if "completion_percentage" in data[0]:
        completion_rates = [r.get("completion_percentage", 0) for r in data]
        avg_completion = sum(completion_rates) / len(completion_rates)

        high_completion = [r for r in data if r.get("completion_percentage", 0) > 80]
        low_completion = [r for r in data if r.get("completion_percentage", 0) < 50]

        analysis["summary_stats"]["avg_completion_rate"] = avg_completion

        if high_completion:
            analysis["insights"].append(f"{len(high_completion)} item(s) are nearly complete (>80%)")
        if low_completion:
            analysis["insights"].append(f"{len(low_completion)} item(s) have low completion rates (<50%)")

def _analyze_team_insights(data: List[Dict[str, Any]], analysis: Dict[str, Any]) -> None:
    """Analyze team-related insights."""
    if not data:
        return

    # Calculate team distribution
    if "name" in data[0]:
        analysis["summary_stats"]["team_size"] = len(data)

    # Look for collaboration patterns
    if "work_items" in data[0]:
        total_tasks = sum(len(r.get("work_items", [])) for r in data)
        analysis["summary_stats"]["total_team_tasks"] = total_tasks
        analysis["summary_stats"]["avg_tasks_per_member"] = total_tasks / len(data) if data else 0

def _analyze_network_insights(data: List[Dict[str, Any]], analysis: Dict[str, Any]) -> None:
    """Analyze network and relationship insights."""
    if not data:
        return

    if "total_connections" in data[0]:
        connections = [r.get("total_connections", 0) for r in data]
        max_connections = max(connections)
        avg_connections = sum(connections) / len(connections)

        analysis["summary_stats"]["max_connections"] = max_connections
        analysis["summary_stats"]["avg_connections"] = avg_connections

        # Find most connected items
        most_connected = max(data, key=lambda x: x.get("total_connections", 0))
        analysis["key_findings"].append(f"Most connected: {most_connected.get('title', 'Unknown')} with {most_connected.get('total_connections', 0)} connections")

def format_analysis_for_response(analysis: Dict[str, Any]) -> str:
    """Format analysis results into natural language response."""
    if not any(analysis.values()):
        return ""

    response_parts = []

    # Key findings
    if analysis["key_findings"]:
        response_parts.append("🔍 Key Findings:")
        for finding in analysis["key_findings"]:
            response_parts.append(f"  • {finding}")

    # Summary statistics
    if analysis["summary_stats"]:
        response_parts.append("\n📊 Summary Statistics:")
        for stat, value in analysis["summary_stats"].items():
            if isinstance(value, float):
                response_parts.append(f"  • {stat.replace('_', ' ').title()}: {value:.1f}")
            else:
                response_parts.append(f"  • {stat.replace('_', ' ').title()}: {value}")

    # Insights
    if analysis["insights"]:
        response_parts.append("\n💡 Insights:")
        for insight in analysis["insights"]:
            response_parts.append(f"  • {insight}")

    # Patterns
    if analysis["patterns"]:
        response_parts.append("\n🔄 Patterns Observed:")
        for pattern in analysis["patterns"]:
            response_parts.append(f"  • {pattern}")

    # Anomalies
    if analysis["anomalies"]:
        response_parts.append("\n⚠️ Notable Anomalies:")
        for anomaly in analysis["anomalies"]:
            response_parts.append(f"  • {anomaly}")

    # Recommendations
    if analysis["recommendations"]:
        response_parts.append("\n🎯 Recommendations:")
        for rec in analysis["recommendations"]:
            response_parts.append(f"  • {rec}")

    return "\n".join(response_parts)


# --------- module-level instance & entrypoint ----------

query_planner = QueryPlanner()

async def plan_and_execute_query(query: str) -> Dict[str, Any]:
    return await query_planner.plan_and_execute(query)

# --------- module-level instance & entrypoint ----------

query_planner = QueryPlanner()

async def plan_and_execute_query(query: str) -> Dict[str, Any]:
    return await query_planner.plan_and_execute(query)

# --------- module-level instance & entrypoint ----------

query_planner = QueryPlanner()

async def plan_and_execute_query(query: str) -> Dict[str, Any]:
    return await query_planner.plan_and_execute(query)
