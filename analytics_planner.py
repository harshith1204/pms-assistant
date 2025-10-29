#!/usr/bin/env python3
"""
Analytics-focused query planner wrapper.

- Duplicates core planning flow without modifying the existing planner
- Applies safe high caps for analytics use cases
- Returns the same shape as planner.plan_and_execute for easy tooling
"""
from __future__ import annotations

import os
from dataclasses import replace
from typing import Any, Dict, List, Optional

from mongo.constants import mongodb_tools, DATABASE_NAME

# Reuse internals from the main planner without altering it
from planner import (
    LLMIntentParser,
    PipelineGenerator,
    Orchestrator,
    StepSpec,
    as_async,
    _serialize_pipeline_for_json,
    _format_pipeline_for_display,
    QueryIntent,
)

# Safe upper bound for analytics (avoids unbounded scans)
MAX_ANALYTICS_LIMIT: int = int(os.getenv("ANALYTICS_MAX_LIMIT", "10000"))
DEFAULT_SAMPLE_LIMIT: int = int(os.getenv("ANALYTICS_SAMPLE_LIMIT", "500"))


class AnalyticsPlanner:
    """Analytics-oriented planner that favors aggregated results and safe caps."""

    def __init__(self):
        self.generator = PipelineGenerator()
        self.llm_parser = LLMIntentParser()
        self.orchestrator = Orchestrator(tracer_name=__name__, max_parallel=5)

    def _enforce_caps_and_defaults(self, intent: QueryIntent) -> QueryIntent:
        """Clamp limits and prefer aggregated outputs when possible.

        Rules:
        - If grouping present → keep as-is; respect limit but clamp to MAX_ANALYTICS_LIMIT
        - If count-only → keep as-is (no limit)
        - If wants details without grouping → set a high but safe cap
        - If no grouping and no explicit limit → apply DEFAULT_SAMPLE_LIMIT to avoid huge payloads
        """
        # Count-only
        if ("count" in (intent.aggregations or [])) and not intent.group_by and not intent.wants_details:
            return intent

        # Clamp explicit limits (both grouped and ungrouped)
        if intent.limit is not None:
            return replace(intent, limit=min(intent.limit, MAX_ANALYTICS_LIMIT))

        # Prefer a sample limit for ungrouped detail queries
        if not intent.group_by and intent.wants_details:
            return replace(intent, limit=min(DEFAULT_SAMPLE_LIMIT, MAX_ANALYTICS_LIMIT))

        # No explicit limit and not grouped → sample to avoid huge payloads
        if not intent.group_by:
            return replace(intent, limit=min(DEFAULT_SAMPLE_LIMIT, MAX_ANALYTICS_LIMIT))

        # Grouped results but no limit specified → keep unlimited (Mongo will cap by memory/allowance)
        return intent

    async def plan_and_execute(self, query: str) -> Dict[str, Any]:
        """Plan and execute a natural language query for analytics scenarios."""
        try:
            async def _ensure_connection(ctx: Dict[str, Any]) -> bool:
                await mongodb_tools.connect()
                return True

            async def _parse_intent(ctx: Dict[str, Any]) -> Optional[QueryIntent]:
                return await self.llm_parser.parse(ctx["query"])  # type: ignore[index]

            def _parse_validator(result: Any, _ctx: Dict[str, Any]) -> bool:
                return result is not None

            def _generate_pipeline(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
                # Enforce analytics caps/defaults before pipeline generation
                capped_intent = self._enforce_caps_and_defaults(ctx["intent"])  # type: ignore[index]
                ctx["intent"] = capped_intent
                return self.generator.generate_pipeline(capped_intent)

            async def _execute(ctx: Dict[str, Any]) -> Any:
                intent: QueryIntent = ctx["intent"]  # type: ignore[assignment]
                args = {
                    "database": DATABASE_NAME,
                    "collection": intent.primary_entity,
                    "pipeline": ctx["pipeline"],
                }
                return await mongodb_tools.execute_tool("aggregate", args)

            steps: List[StepSpec] = [
                StepSpec(
                    name="ensure_connection",
                    coroutine=as_async(_ensure_connection),
                    requires=(),
                    provides="connected",
                    retries=2,
                    timeout_s=8.0,
                ),
                StepSpec(
                    name="parse_intent",
                    coroutine=as_async(_parse_intent),
                    requires=("query",),
                    provides="intent",
                    timeout_s=15.0,
                    retries=1,
                    validator=_parse_validator,
                ),
                StepSpec(
                    name="generate_pipeline",
                    coroutine=as_async(_generate_pipeline),
                    requires=("intent",),
                    provides="pipeline",
                    timeout_s=5.0,
                ),
                StepSpec(
                    name="execute_query",
                    coroutine=as_async(_execute),
                    requires=("intent", "pipeline"),
                    provides="result",
                    timeout_s=25.0,
                    retries=1,
                ),
            ]

            ctx = await self.orchestrator.run(
                steps,
                initial_context={"query": query},
                correlation_id=f"analytics_planner_{hash(query) & 0xFFFFFFFF:x}",
            )

            intent: QueryIntent = ctx["intent"]  # type: ignore[assignment]
            pipeline: List[Dict[str, Any]] = ctx["pipeline"]  # type: ignore[assignment]
            result = ctx.get("result")

            return {
                "success": True,
                "intent": intent.__dict__,
                "pipeline": _serialize_pipeline_for_json(pipeline),
                "pipeline_js": _format_pipeline_for_display(pipeline),
                "result": result,
                "planner": "analytics",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "query": query,
            }


# Global instance and convenience function
analytics_query_planner = AnalyticsPlanner()

async def plan_and_execute_analytics_query(query: str) -> Dict[str, Any]:
    return await analytics_query_planner.plan_and_execute(query)
