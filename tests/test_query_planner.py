import asyncio
from query_planner import query_planner

def test_parse_group_by_state():
    intent = query_planner.parse("show work items for project Test PMS grouped by state")
    assert intent.root_entity == "workItem"
    assert intent.group_by == "state.name"
    assert any(k.startswith("project.") for k in intent.filters.keys())

def test_parse_members_with_their_tasks():
    intent = query_planner.parse("members in project Test PMS and their tasks")
    assert intent.special == "members_with_workitems"
    assert intent.special_args["root"] == "project"
    assert any(k.startswith("project.") for k in intent.filters.keys())

def test_parse_members_with_assigned():
    intent = query_planner.parse("list members and assigned tickets for project Test PMS")
    assert intent.special == "members_with_workitems"
    assert intent.special_args["root"] == "project"

def test_parse_members_all_projects():
    intent = query_planner.parse("show members and their work items")
    assert intent.special == "members_with_workitems"
    assert intent.special_args["root"] == "members"

def test_parse_pages_by_module():
    intent = query_planner.parse("show pages linked to modules for project Test PMS")
    assert intent.special == "pages_by_module"
    assert intent.special_args["root"] == "project"
    assert any(k.startswith("project.") for k in intent.filters.keys())

def test_parse_pages_by_cycle():
    intent = query_planner.parse("show pages per cycle in project Test PMS")
    assert intent.special == "pages_by_cycle"
    assert intent.special_args["root"] == "project"

def test_parse_members_open_this_week():
    intent = query_planner.parse("members in project TEST PMS and their open tasks this week")
    assert intent.special == "members_open_this_week"
    assert intent.special_args["root"] == "project"
    assert any(k.startswith("project.") for k in intent.filters.keys())

def test_parse_members_open_current_week():
    intent = query_planner.parse("show members and open tickets current week")
    assert intent.special == "members_open_this_week"
    assert intent.special_args["root"] == "members"

def test_parse_module_tickets_by_state():
    intent = query_planner.parse("modules in project TEST PMS with tickets grouped by state")
    assert intent.special == "module_tickets_by_state"
    assert intent.special_args["root"] == "project"
    assert any(k.startswith("project.") for k in intent.filters.keys())

def test_parse_module_workitems_by_state():
    intent = query_planner.parse("show modules for project TEST PMS and their work items grouped by state")
    assert intent.special == "module_tickets_by_state"
    assert intent.special_args["root"] == "project"
