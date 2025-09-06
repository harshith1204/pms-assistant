from typing import List
from planning_schema import Plan, PlanNode
from tool_registry import ToolSpec


def build_naive_plan(query: str, shortlisted_specs: List[ToolSpec]) -> Plan:
    # Minimal single-step plan using the top-ranked tool
    if not shortlisted_specs:
        return Plan(nodes=[], final_selector="", max_parallel=1)
    top = shortlisted_specs[0]
    node = PlanNode(id="step_1", tool=top.name, args={}, deps=[])
    return Plan(nodes=[node], final_selector=node.id, max_parallel=1)

