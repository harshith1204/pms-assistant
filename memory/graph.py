from __future__ import annotations

from typing import Any, Dict, List, Optional
import re

# Minimal KG extraction utilities using heuristics over your existing shapes
# Future: could be replaced by an LLM-based IE prompt if needed.

TRIPLE_KEYS = [
    ("projectName", "has_project", "string"),
    ("stateName", "has_state", "string"),
    ("moduleName", "has_module", "string"),
    ("businessName", "has_business", "string"),
    ("leadName", "has_lead", "string"),
]


def extract_triples_from_doc(doc: Dict[str, Any], subject_hint: Optional[str] = None) -> List[Dict[str, Any]]:
    """Extract simple triples from a flattened entity document.
    Subject is inferred from `title`/`name` or provided via subject_hint.
    """
    triples: List[Dict[str, Any]] = []
    subj = subject_hint or doc.get("title") or doc.get("name")
    if not isinstance(subj, str) or not subj.strip():
        return triples
    for key, pred, kind in TRIPLE_KEYS:
        val = doc.get(key)
        if isinstance(val, str) and val.strip():
            triples.append({"subj": subj, "pred": pred, "obj": val.strip(), "kind": kind})
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
