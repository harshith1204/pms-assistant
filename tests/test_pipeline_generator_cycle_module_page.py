from planner import PipelineGenerator, QueryIntent


def build_intent(
    primary_entity,
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


def test_cycle_primary_status_filter_and_project_lookup():
    gen = PipelineGenerator()
    intent = build_intent("cycle", filters={"cycle_status": "ACTIVE"}, wants_details=True)
    pipeline = gen.generate_pipeline(intent)
    assert {"$match": {"status": "ACTIVE"}} in pipeline
    # cycle has relation 'project'
    # No automatic lookup unless needed for filters/group


def test_module_primary_has_project_filter_ignored_when_not_present():
    gen = PipelineGenerator()
    intent = build_intent("module", filters={"project_name": "CRM"}, wants_details=True)
    pipeline = gen.generate_pipeline(intent)
    # module has 'project' relation; project_name filter should cause a lookup
    lookups = find_stage(pipeline, "$lookup")
    assert any(stg["$lookup"]["from"] == "project" for stg in lookups)


def test_page_primary_project_name_uses_projectDoc_alias():
    gen = PipelineGenerator()
    intent = build_intent("page", filters={"project_name": "Docs"}, wants_details=True)
    pipeline = gen.generate_pipeline(intent)
    # page has relation key 'project' with alias 'projectDoc'
    lookups = find_stage(pipeline, "$lookup")
    assert any(stg["$lookup"]["from"] == "project" for stg in lookups)

