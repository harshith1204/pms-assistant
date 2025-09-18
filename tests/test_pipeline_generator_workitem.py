import pytest

from planner import PipelineGenerator, QueryIntent


def build_intent(
    primary_entity="workItem",
    filters=None,
    aggregations=None,
    group_by=None,
    projections=None,
    sort_order=None,
    limit=10,
    wants_details=False,
    wants_count=False,
):
    return QueryIntent(
        primary_entity=primary_entity,
        target_entities=[],
        filters=filters or {},
        aggregations=aggregations or [],
        group_by=group_by or [],
        projections=projections or [],
        sort_order=sort_order,
        limit=limit,
        wants_details=wants_details,
        wants_count=wants_count,
    )


def find_stage(pipeline, op):
    return [stg for stg in pipeline if op in stg]


def test_count_only_no_filters():
    gen = PipelineGenerator()
    intent = build_intent(wants_count=True)
    pipeline = gen.generate_pipeline(intent)
    assert pipeline == [{"$count": "total"}]


def test_count_only_with_primary_filters():
    gen = PipelineGenerator()
    intent = build_intent(filters={"status": "COMPLETED"}, wants_count=True)
    pipeline = gen.generate_pipeline(intent)
    assert pipeline[0] == {"$match": {"status": "COMPLETED"}}
    assert pipeline[1] == {"$count": "total"}


def test_primary_filters_mapping_priority_and_status():
    gen = PipelineGenerator()
    intent = build_intent(filters={"status": "TODO", "priority": "HIGH"}, wants_details=True)
    pipeline = gen.generate_pipeline(intent)
    assert {"$match": {"status": "TODO", "priority": "HIGH"}} in pipeline


def test_secondary_filter_project_name_adds_match_and_allows_lookup():
    gen = PipelineGenerator()
    intent = build_intent(filters={"project_name": "CRM"}, wants_details=True)
    pipeline = gen.generate_pipeline(intent)
    matches = find_stage(pipeline, "$match")
    assert any(
        stg["$match"].get("$or")
        for stg in matches
    )
    # Either lookup 'project' may or may not be present; both are acceptable as we match embedded or joined


def test_secondary_filter_assignee_name_requires_lookup_and_unwind():
    gen = PipelineGenerator()
    intent = build_intent(filters={"assignee_name": "Alice"}, wants_details=True)
    pipeline = gen.generate_pipeline(intent)
    lookups = find_stage(pipeline, "$lookup")
    assert any(stg["$lookup"]["from"] == "members" for stg in lookups)
    unwinds = find_stage(pipeline, "$unwind")
    assert any("assignees" in stg["$unwind"]["path"] for stg in unwinds)
    # And a match on assignees.name
    assert {"$match": {"assignees.name": {"$regex": "Alice", "$options": "i"}}} in pipeline


def test_group_by_status_simple():
    gen = PipelineGenerator()
    intent = build_intent(group_by=["status"], aggregations=["group"], wants_details=False)
    pipeline = gen.generate_pipeline(intent)
    groups = find_stage(pipeline, "$group")
    assert groups, "Expected a $group stage"
    assert groups[0]["$group"]["_id"] == "$status"
    projects = find_stage(pipeline, "$project")
    assert any("count" in p["$project"] for p in projects)


def test_group_by_assignee_includes_lookup_and_unwind():
    gen = PipelineGenerator()
    intent = build_intent(group_by=["assignee"], aggregations=["group"], wants_details=True)
    pipeline = gen.generate_pipeline(intent)
    lookups = find_stage(pipeline, "$lookup")
    assert any(stg["$lookup"]["from"] == "members" for stg in lookups)
    unwinds = find_stage(pipeline, "$unwind")
    assert any("assignees" in stg["$unwind"]["path"] for stg in unwinds)
    groups = find_stage(pipeline, "$group")
    assert groups, "Expected a $group stage"


def test_sort_by_priority_adds_rank_and_unset_when_projecting_priority():
    gen = PipelineGenerator()
    intent = build_intent(
        projections=["title", "priority"],
        sort_order={"priority": -1},
        wants_details=True,
    )
    pipeline = gen.generate_pipeline(intent)
    assert any("$addFields" in stg and "_priorityRank" in stg["$addFields"] for stg in pipeline)
    assert any(stg.get("$sort") == {"_priorityRank": -1} for stg in pipeline)
    assert any(stg.get("$unset") == "_priorityRank" for stg in pipeline)


def test_details_default_projections_when_missing():
    gen = PipelineGenerator()
    intent = build_intent(wants_details=True)
    pipeline = gen.generate_pipeline(intent)
    projects = find_stage(pipeline, "$project")
    assert projects, "Expected a $project stage for details"
    # At least include _id field by default
    assert "_id" in projects[-1]["$project"]


def test_limit_applied_non_grouped():
    gen = PipelineGenerator()
    intent = build_intent(wants_details=True, limit=7)
    pipeline = gen.generate_pipeline(intent)
    assert pipeline[-1] == {"$limit": 7}


def test_grouped_limit_applied():
    gen = PipelineGenerator()
    intent = build_intent(group_by=["status"], aggregations=["group"], limit=5)
    pipeline = gen.generate_pipeline(intent)
    # Last or near-last should be $limit 5
    assert any(stg.get("$limit") == 5 for stg in pipeline)


def test_cycle_title_filter_ignored_for_workitem_without_relation():
    gen = PipelineGenerator()
    intent = build_intent(filters={"cycle_title": "Sprint"}, wants_details=True)
    pipeline = gen.generate_pipeline(intent)
    # No cycle.title match and no cycle lookup
    assert not any(
        stg.get("$match", {}).get("cycle.title") for stg in pipeline if "$match" in stg
    )
    assert not any(
        stg["$lookup"].get("from") == "cycle" for stg in pipeline if "$lookup" in stg
    )


def test_module_name_filter_ignored_for_workitem_without_relation():
    gen = PipelineGenerator()
    intent = build_intent(filters={"module_name": "Backend"}, wants_details=True)
    pipeline = gen.generate_pipeline(intent)
    assert not any(
        stg.get("$match", {}).get("module.title") for stg in pipeline if "$match" in stg
    )
    assert not any(
        stg["$lookup"].get("from") == "module" for stg in pipeline if "$lookup" in stg
    )


def test_sort_by_status_simple():
    gen = PipelineGenerator()
    intent = build_intent(sort_order={"status": 1}, wants_details=True)
    pipeline = gen.generate_pipeline(intent)
    assert any(stg.get("$sort") == {"status": 1} for stg in pipeline)


def test_projections_respected():
    gen = PipelineGenerator()
    intent = build_intent(wants_details=True, projections=["title", "priority", "nonexistent"])
    pipeline = gen.generate_pipeline(intent)
    projects = find_stage(pipeline, "$project")
    assert projects, "Expected a $project stage"
    proj = projects[-1]["$project"]
    assert "title" in proj and "priority" in proj
    assert "nonexistent" not in proj

