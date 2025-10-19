from __future__ import annotations

from typing import Any, Dict, List, Optional
import re

# Minimal KG extraction utilities using heuristics over your existing shapes
# Future: could be replaced by an LLM-based IE prompt if needed.

TRIPLE_KEYS = [
    # Common cross-entity fields
    ("projectName", "belongs_to_project", "string"),
    ("businessName", "belongs_to_business", "string"),
    ("moduleName", "in_module", "string"),
    ("stateName", "has_state", "string"),
    ("leadName", "has_lead", "string"),
    # Work item specifics
    ("priority", "has_priority", "string"),
    ("assignees", "assigned_to", "array_string"),
    ("assignee", "assigned_to", "array_string_or_single"),
    ("cycleName", "in_cycle", "string"),
    ("createdByName", "created_by", "string"),
    # Page specifics
    ("visibility", "has_visibility", "string"),
    ("linkedCycleNames", "links_cycle", "array_string"),
    ("linkedModuleNames", "links_module", "array_string"),
]


def extract_triples_from_doc(doc: Dict[str, Any], subject_hint: Optional[str] = None) -> List[Dict[str, Any]]:
    """Extract simple triples from a flattened entity document.
    Subject is inferred from `title`/`name` or provided via subject_hint.
    """
    triples: List[Dict[str, Any]] = []
    subj = subject_hint or doc.get("title") or doc.get("name")
    if not isinstance(subj, str) or not subj.strip():
        return triples
    def _emit(value: Any, pred: str, kind: str) -> None:
        if isinstance(value, str) and value.strip():
            triples.append({"subj": subj, "pred": pred, "obj": value.strip(), "kind": kind})
        elif isinstance(value, list) and value:
            for v in value:
                if isinstance(v, str) and v.strip():
                    triples.append({"subj": subj, "pred": pred, "obj": v.strip(), "kind": kind})

    for key, pred, kind in TRIPLE_KEYS:
        val = doc.get(key)
        if val is None:
            continue
        if kind in ("array_string", "array_string_or_single") and isinstance(val, dict):
            # sometimes arrays come as dicts with names
            val = [val.get("name") or val.get("title")] if val else []
        _emit(val, pred, kind)
    return triples


def extract_triples_from_text(text: str) -> List[Dict[str, Any]]:
    """Very light rule-based extraction: patterns like 'X -> Y: Z'.
    Avoids LLM passes as requested.
    """
    triples: List[Dict[str, Any]] = []
    if not text:
        return triples
    # Example pattern: Decision -> next_step: Cut login scope
    for line in text.splitlines():
        m = re.search(r"^\s*([^:>]+)\s*[-=]>\s*([^:]+):\s*(.+)$", line.strip())
        if m:
            subj, pred, obj = m.groups()
            subj, pred, obj = subj.strip(), pred.strip(), obj.strip()
            if subj and pred and obj:
                triples.append({"subj": subj, "pred": pred, "obj": obj, "kind": "text"})
    return triples

