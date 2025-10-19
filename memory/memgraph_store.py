from __future__ import annotations

from typing import Any, Dict, List, Optional
import os

from neo4j import GraphDatabase


class MemgraphStore:
    """Thin wrapper to write triples into Memgraph (Neo4j protocol).

    Expected env vars:
      - MEMGRAPH_URI (e.g., bolt://localhost:7687)
      - MEMGRAPH_USER
      - MEMGRAPH_PASSWORD
    """

    def __init__(self) -> None:
        uri = os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")
        user = os.getenv("MEMGRAPH_USER", "neo4j")
        pwd = os.getenv("MEMGRAPH_PASSWORD", "password")
        self._driver = GraphDatabase.driver(uri, auth=(user, pwd))

    def close(self) -> None:
        try:
            self._driver.close()
        except Exception:
            pass

    def upsert_triples(self, conversation_id: str, triples: List[Dict[str, Any]]) -> None:
        if not triples:
            return
        cypher = (
            "UNWIND $rows AS row "
            "MERGE (s:Entity {name: row.subj}) "
            "MERGE (o:Entity {name: row.obj}) "
            "MERGE (s)-[r:REL {pred: row.pred}]->(o) "
            "SET r.conversationId = $conv, r.kind = row.kind, r.ts = timestamp()"
        )
        rows = [
            {"subj": t.get("subj"), "pred": t.get("pred"), "obj": t.get("obj"), "kind": t.get("kind", "text")}
            for t in triples
            if t.get("subj") and t.get("pred") and t.get("obj")
        ]
        if not rows:
            return
        with self._driver.session() as session:
            session.run(cypher, rows=rows, conv=conversation_id)


# Singleton accessor
_memgraph_singleton: Optional[MemgraphStore] = None


def get_memgraph_store() -> MemgraphStore:
    global _memgraph_singleton
    if _memgraph_singleton is None:
        _memgraph_singleton = MemgraphStore()
    return _memgraph_singleton

