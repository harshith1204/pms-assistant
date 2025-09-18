import asyncio
import pytest

from planner import LLMIntentParser


@pytest.mark.asyncio
async def test_how_many_forces_count_only(monkeypatch):
    parser = LLMIntentParser()

    async def fake_ai(self, query: str):
        # Model attempts to group unnecessarily
        return {
            "primary_entity": "workItem",
            "target_entities": ["project"],
            "filters": {},
            "aggregations": ["group", "count"],
            "group_by": ["project"],
            "projections": [],
            "sort_order": {"status": -1},
            "limit": 50,
            "wants_details": False,
            "wants_count": True,
        }

    # Patch parse to bypass LLM call and feed fake
    async def fake_parse(self, query: str):
        data = await fake_ai(self, query)
        return self._sanitize_intent(data, original_query=query)

    monkeypatch.setattr(LLMIntentParser, "parse", fake_parse)

    intent = await parser.parse("how many work items are there")
    assert intent is not None
    # Count-only: no group_by, count aggregation only
    assert intent.wants_count is True
    assert intent.group_by == []
    assert intent.aggregations == ["count"]
    assert intent.wants_details is False

