import asyncio
import types
import pytest

import planner
from planner import Planner


class DummyTool:
    def __init__(self, name):
        self.name = name

    async def ainvoke(self, arguments):
        # Just echo back arguments to simulate server
        return [{"echo": arguments}]


class DummyClient:
    def __init__(self):
        self._tools = [DummyTool("aggregate")]

    async def get_tools(self):
        return self._tools


class DummyMongoTools:
    def __init__(self):
        self.client = DummyClient()
        self.tools = []
        self.connected = False

    async def connect(self):
        self.tools = await self.client.get_tools()
        self.connected = True

    async def disconnect(self):
        self.connected = False
        self.tools = []

    async def execute_tool(self, tool_name: str, arguments):
        tool = next((t for t in self.tools if t.name == tool_name), None)
        assert tool, f"Tool {tool_name} not found"
        return await tool.ainvoke(arguments)


@pytest.mark.asyncio
async def test_planner_flow_minimal_echo(monkeypatch):
    # Patch mongodb_tools in planner with our dummy
    dummy = DummyMongoTools()
    monkeypatch.setattr(planner, "mongodb_tools", dummy)

    # Patch LLM parser to return a deterministic intent without calling model
    async def fake_parse(self, query: str):
        return planner.QueryIntent(
            primary_entity="workItem",
            target_entities=[],
            filters={"status": "TODO"},
            aggregations=[],
            group_by=[],
            projections=["title"],
            sort_order=None,
            limit=3,
            wants_details=True,
            wants_count=False,
        )

    monkeypatch.setattr(planner.LLMIntentParser, "parse", fake_parse)

    pl = Planner()
    result = await pl.plan_and_execute("list todo work items")

    assert result["success"] is True
    assert result["intent"]["primary_entity"] == "workItem"
    # The dummy MCP returns the echo of aggregate arguments
    echoed = result["result"][0]["echo"]
    assert echoed["database"] == planner.DATABASE_NAME
    assert echoed["collection"] == "workItem"
    assert isinstance(echoed["pipeline"], list)

