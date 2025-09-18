from planner import PipelineGenerator, QueryIntent


def build_intent(
    primary_entity="project",
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


def test_project_primary_status_filter():
    gen = PipelineGenerator()
    intent = build_intent(filters={"project_status": "STARTED"}, wants_details=True)
    pipeline = gen.generate_pipeline(intent)
    assert {"$match": {"status": "STARTED"}} in pipeline


def test_project_group_by_status():
    gen = PipelineGenerator()
    intent = build_intent(aggregations=["group"], group_by=["status"])
    pipeline = gen.generate_pipeline(intent)
    groups = find_stage(pipeline, "$group")
    assert groups
    assert groups[0]["$group"]["_id"] == "$status"

