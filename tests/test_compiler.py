from planner import QueryIntent, compile_intent


def test_cycles_active_prefers_find():
    intent = QueryIntent(
        primary_entity="cycle",
        target_entities=[],
        filters={"cycle_status": "ACTIVE"},
        aggregations=[],
        group_by=[],
        projections=[],
        sort_order={"startDate": 1},
        limit=20,
        wants_details=True,
        wants_count=False,
    )
    compiled = compile_intent(intent)
    assert compiled.kind == "find"


def test_workitems_group_by_status_is_aggregate():
    intent = QueryIntent(
        primary_entity="workItem",
        target_entities=[],
        filters={},
        aggregations=["group"],
        group_by=["status"],
        projections=[],
        sort_order=None,
        limit=10,
        wants_details=False,
        wants_count=False,
    )
    compiled = compile_intent(intent)
    assert compiled.kind == "aggregate"
    assert compiled.pipeline and len(compiled.pipeline) <= 6


def test_members_by_project_name_uses_find_embedded():
    intent = QueryIntent(
        primary_entity="members",
        target_entities=[],
        filters={"project_name": "MCU"},
        aggregations=[],
        group_by=[],
        projections=["name", "email"],
        sort_order=None,
        limit=20,
        wants_details=True,
        wants_count=False,
    )
    compiled = compile_intent(intent)
    assert compiled.kind == "find"
