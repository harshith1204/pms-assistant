import os
import sys
import pytest

# Ensure project root is on path for direct module imports when running under various runners
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from planner import PipelineGenerator, QueryIntent


def make_intent(**overrides) -> QueryIntent:
    base = dict(
        primary_entity="workItem",
        target_entities=[],
        filters={},
        aggregations=[],
        group_by=[],
        projections=[],
        sort_order=None,
        limit=20,
        wants_details=True,
        wants_count=False,
    )
    base.update(overrides)
    return QueryIntent(**base)


def find_stage(pipeline, key):
    return next((s for s in pipeline if key in s), None)


def test_count_only_without_filters():
    gen = PipelineGenerator()
    intent = make_intent(wants_details=False, wants_count=True, aggregations=["count"])
    pipe = gen.generate_pipeline(intent)
    assert pipe == [{"$count": "total"}]


def test_count_only_with_primary_filters():
    gen = PipelineGenerator()
    intent = make_intent(
        wants_details=False,
        wants_count=True,
        aggregations=["count"],
        filters={"status": "ACCEPTED"},
    )
    pipe = gen.generate_pipeline(intent)
    assert pipe[0] == {"$match": {"status": "ACCEPTED"}}
    assert pipe[1] == {"$count": "total"}


def test_primary_filters_on_workitem():
    gen = PipelineGenerator()
    intent = make_intent(filters={"status": "ACCEPTED", "priority": "HIGH"})
    pipe = gen.generate_pipeline(intent)
    match = find_stage(pipe, "$match")
    assert match is not None
    assert match["$match"]["status"] == "ACCEPTED"
    assert match["$match"]["priority"] == "HIGH"


def test_secondary_filter_assignee_name_triggers_lookup_and_unwind():
    gen = PipelineGenerator()
    intent = make_intent(filters={"assignee_name": "vikas"})
    pipe = gen.generate_pipeline(intent)
    # Expect a $lookup for members (assignee relation) with alias 'assignees' then an $unwind
    lookup = find_stage(pipe, "$lookup")
    assert lookup is not None
    assert lookup["$lookup"]["from"] == "members"
    assert lookup["$lookup"]["as"] == "assignees"
    unwind = find_stage(pipe, "$unwind")
    assert unwind is not None
    assert unwind["$unwind"]["path"] == "$assignees"
    # And then a secondary $match using assignees.name
    matches = [s for s in pipe if "$match" in s]
    assert any("assignees.name" in m["$match"] for m in matches)


def test_filter_project_name_uses_or_paths():
    gen = PipelineGenerator()
    intent = make_intent(filters={"project_name": "TEST"})
    pipe = gen.generate_pipeline(intent)
    # There should be an $or on project.name and projectDoc.name
    sec_match = next((s for s in pipe if "$match" in s and "$or" in s["$match"]), None)
    assert sec_match is not None
    or_paths = [list(d.keys())[0] for d in sec_match["$match"]["$or"]]
    assert "project.name" in or_paths
    assert "projectDoc.name" in or_paths


def test_sort_by_priority_adds_rank_and_unsets():
    gen = PipelineGenerator()
    intent = make_intent(sort_order={"priority": -1})
    pipe = gen.generate_pipeline(intent)
    add_fields = find_stage(pipe, "$addFields")
    assert add_fields is not None
    assert "_priorityRank" in add_fields["$addFields"]
    s = find_stage(pipe, "$sort")
    assert s is not None
    assert s["$sort"] == {"_priorityRank": -1}
    # projection may be present
    unset = find_stage(pipe, "$unset")
    assert unset is not None
    assert unset["$unset"] == "_priorityRank"


def test_sort_by_created_timestamp():
    gen = PipelineGenerator()
    intent = make_intent(sort_order={"createdTimeStamp": -1})
    pipe = gen.generate_pipeline(intent)
    s = find_stage(pipe, "$sort")
    assert s is not None
    assert s["$sort"] == {"createdTimeStamp": -1}


def test_group_by_status_default():
    gen = PipelineGenerator()
    intent = make_intent(group_by=["status"], wants_details=False, limit=50)
    pipe = gen.generate_pipeline(intent)
    group = find_stage(pipe, "$group")
    assert group is not None
    assert group["$group"]["_id"] == "$status"
    assert group["$group"]["count"] == {"$sum": 1}
    s = find_stage(pipe, "$sort")
    assert s is not None
    assert s["$sort"] == {"count": -1}
    lim = find_stage(pipe, "$limit")
    assert lim is not None
    assert lim["$limit"] == 50


def test_group_by_project_uses_embedded_name():
    gen = PipelineGenerator()
    intent = make_intent(group_by=["project"], wants_details=False)
    pipe = gen.generate_pipeline(intent)
    group = find_stage(pipe, "$group")
    assert group is not None
    assert group["$group"]["_id"] == "$project.name"


def test_group_by_assignee_requires_lookup_and_unwind():
    gen = PipelineGenerator()
    intent = make_intent(group_by=["assignee"], wants_details=False)
    pipe = gen.generate_pipeline(intent)
    lookup = find_stage(pipe, "$lookup")
    assert lookup is not None and lookup["$lookup"]["from"] == "members"
    unwind = find_stage(pipe, "$unwind")
    assert unwind is not None and unwind["$unwind"]["path"] == "$assignees"
    group = find_stage(pipe, "$group")
    assert group is not None
    assert group["$group"]["_id"] == "$assignees.name"


def test_group_by_multiple_tokens():
    gen = PipelineGenerator()
    intent = make_intent(group_by=["status", "priority"], wants_details=False)
    pipe = gen.generate_pipeline(intent)
    group = find_stage(pipe, "$group")
    assert group is not None
    _id = group["$group"]["_id"]
    assert isinstance(_id, dict)
    assert _id["status"] == "$status"
    assert _id["priority"] == "$priority"


def test_group_by_with_details_pushes_items():
    gen = PipelineGenerator()
    intent = make_intent(group_by=["status"], wants_details=True)
    pipe = gen.generate_pipeline(intent)
    group = find_stage(pipe, "$group")
    assert group is not None
    assert "items" in group["$group"]
    assert set(group["$group"]["items"]["$push"].keys()) >= {"_id", "title", "priority"}


def test_projection_defaults_when_details():
    gen = PipelineGenerator()
    intent = make_intent(wants_details=True)
    pipe = gen.generate_pipeline(intent)
    proj = find_stage(pipe, "$project")
    assert proj is not None
    # ensure at least id and some known allowed fields are present or default fallback
    assert proj["$project"]["_id"] == 1


def test_target_entities_projection_inclusion():
    gen = PipelineGenerator()
    intent = make_intent(wants_details=True, target_entities=["project", "assignee"], projections=["title", "priority"])
    pipe = gen.generate_pipeline(intent)
    proj = find_stage(pipe, "$project")
    assert proj is not None
    assert proj["$project"]["title"] == 1
    assert proj["$project"]["priority"] == 1
    # target entity keys should be projected if valid relations
    assert proj["$project"].get("project") == 1
    assert proj["$project"].get("assignee") == 1 or proj["$project"].get("assignees") is None


def test_skip_count_when_details_requested():
    gen = PipelineGenerator()
    intent = make_intent(aggregations=["count"], wants_details=True)
    pipe = gen.generate_pipeline(intent)
    assert not any("$count" in s for s in pipe)


def test_extract_primary_filters_for_other_collections():
    gen = PipelineGenerator()
    # project
    intent = make_intent(primary_entity="project", filters={"project_status": "NOT_STARTED"})
    pipe = gen.generate_pipeline(intent)
    match = find_stage(pipe, "$match")
    assert match is not None and match["$match"] == {"status": "NOT_STARTED"}
    # cycle
    intent = make_intent(primary_entity="cycle", filters={"cycle_status": "ACTIVE"})
    pipe = gen.generate_pipeline(intent)
    match = find_stage(pipe, "$match")
    assert match is not None and match["$match"] == {"status": "ACTIVE"}
    # page
    intent = make_intent(primary_entity="page", filters={"page_visibility": "PUBLIC"})
    pipe = gen.generate_pipeline(intent)
    match = find_stage(pipe, "$match")
    assert match is not None and match["$match"] == {"visibility": "PUBLIC"}


def test_secondary_filters_cycle_and_module_paths_present_when_used():
    gen = PipelineGenerator()
    intent = make_intent(filters={"cycle_title": "sprint", "module_name": "backend"})
    pipe = gen.generate_pipeline(intent)
    sec = next((s for s in pipe if "$match" in s and "cycle.title" in s["$match"]), None)
    assert sec is not None
    assert "module.title" in sec["$match"]


def test_group_sorting_respects_group_key_sort():
    gen = PipelineGenerator()
    intent = make_intent(group_by=["status"], wants_details=False, sort_order={"status": 1})
    pipe = gen.generate_pipeline(intent)
    sort = find_stage(pipe, "$sort")
    assert sort is not None and sort["$sort"] == {"_id": 1}


def test_group_sorting_defaults_to_count_desc():
    gen = PipelineGenerator()
    intent = make_intent(group_by=["status"], wants_details=False)
    pipe = gen.generate_pipeline(intent)
    sort = find_stage(pipe, "$sort")
    assert sort is not None and sort["$sort"] == {"count": -1}


def test_limit_applied_for_non_grouped():
    gen = PipelineGenerator()
    intent = make_intent(limit=7)
    pipe = gen.generate_pipeline(intent)
    lim = pipe[-1]
    assert "$limit" in lim and lim["$limit"] == 7


def test_projection_respects_allowed_fields_only():
    gen = PipelineGenerator()
    intent = make_intent(projections=["title", "priority", "nonexistent"], wants_details=True)
    pipe = gen.generate_pipeline(intent)
    proj = find_stage(pipe, "$project")
    assert proj is not None
    assert "nonexistent" not in proj["$project"]


def test_group_by_priority_and_details_pushes_items():
    gen = PipelineGenerator()
    intent = make_intent(group_by=["priority"], wants_details=True)
    pipe = gen.generate_pipeline(intent)
    group = find_stage(pipe, "$group")
    assert group is not None and "items" in group["$group"]


def test_sort_ignored_inside_group_when_not_group_key():
    gen = PipelineGenerator()
    intent = make_intent(group_by=["status"], wants_details=False, sort_order={"createdTimeStamp": -1})
    pipe = gen.generate_pipeline(intent)
    # Should default to count desc when sort key not in group_by
    sort = find_stage(pipe, "$sort")
    assert sort is not None and sort["$sort"] == {"count": -1}

