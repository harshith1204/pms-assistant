from registry import ENTITIES, build_lookup_stage

def test_project_to_workitems_lookup():
    stage = build_lookup_stage("project", "workItems")
    assert stage["$lookup"]["from"] == "ProjectManagement.workItem"
    assert "pipeline" in stage["$lookup"]
