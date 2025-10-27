from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class PlanNode(BaseModel):
    id: str
    tool: str
    args: Dict[str, Any] = {}
    deps: List[str] = []
    only_if: Optional[str] = None


class Plan(BaseModel):
    nodes: List[PlanNode]
    final_selector: str
    max_parallel: int = 3

