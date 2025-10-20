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


def extract_candidate_terms_from_text(text: str, max_terms: int = 12) -> List[str]:
    """Extract lightweight candidate entity terms from free text.

    Heuristics (no LLM):
    - Keep tokens with >= 3 chars
    - Prefer TitleCase, UPPERCASE, tokens with digits, hyphen, slash or underscore
    - Deduplicate while preserving order; cap to max_terms
    """
    if not isinstance(text, str) or not text.strip():
        return []

    # Split on non-word separators, keep simple tokens
    raw_tokens = re.split(r"[^A-Za-z0-9_\-/]+", text)
    seen: set[str] = set()
    terms: List[str] = []

    def looks_like_entity(tok: str) -> bool:
        if len(tok) < 3:
            return False
        if any(ch in tok for ch in "-/_"):
            return True
        if any(ch.isdigit() for ch in tok):
            return True
        # TitleCase or UPPERCASE signals named entity/module/acronym
        return tok.isupper() or (tok[0].isupper() and any(c.islower() for c in tok[1:]))

    for tok in raw_tokens:
        if not tok:
            continue
        if looks_like_entity(tok) and tok not in seen:
            seen.add(tok)
            terms.append(tok)
            if len(terms) >= max_terms:
                break
    return terms


def format_kg_triples_for_prompt(triples: List[Dict[str, Any]], max_lines: int = 16) -> str:
    """Format KG triples as compact bullets for a system prompt.

    Output form: "- subj -(pred)-> obj"
    Deduplicates identical triples and caps the number of lines.
    """
    if not triples:
        return ""
    seen: set[tuple[str, str, str]] = set()
    lines: List[str] = []
    for t in triples:
        subj = str(t.get("subj") or "").strip()
        pred = str(t.get("pred") or "").strip()
        obj = str(t.get("obj") or "").strip()
        if not subj or not pred or not obj:
            continue
        key = (subj, pred, obj)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- {subj} -({pred})-> {obj}")
        if len(lines) >= max_lines:
            break
    return "\n".join(lines)

