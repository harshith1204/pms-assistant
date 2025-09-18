import pytest

from planner import PipelineGenerator, QueryIntent


def test_count_with_assignee_secondary_filter_includes_lookup():
    gen = PipelineGenerator()
    intent = QueryIntent(
        primary_entity="workItem",
        target_entities=[],
        filters={"assignee_name": "raghav"},
        aggregations=["count"],
        group_by=[],
        projections=[],
        sort_order=None,
        limit=20,
        wants_details=False,
        wants_count=True,
    )
    pipeline = gen.generate_pipeline(intent)
    # Should not return immediately; should include lookup to members and match on assignees
    assert any("$lookup" in stg and stg["$lookup"]["from"] == "members" for stg in pipeline)
    assert any("$match" in stg and stg["$match"].get("assignees.name") for stg in pipeline)
    assert pipeline[-1] == {"$count": "total"}

