from __future__ import annotations

"""Reusable helpers for Project Management ? Qdrant indexing."""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
import base64
import html as html_lib
import json
import re
import uuid

from bson.binary import Binary
from bson.objectid import ObjectId
from qdrant_client.http import models as qmodels


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class PreparedDocument:
    content_type: str
    mongo_id: str
    title: str
    combined_text: str
    metadata: Dict[str, Any]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


CHUNKING_CONFIG: Dict[str, Dict[str, int]] = {
    "page": {"max_words": 220, "overlap_words": 40, "min_words_to_chunk": 220},
    "work_item": {"max_words": 220, "overlap_words": 40, "min_words_to_chunk": 220},
    "project": {"max_words": 220, "overlap_words": 40, "min_words_to_chunk": 220},
    "cycle": {"max_words": 220, "overlap_words": 40, "min_words_to_chunk": 220},
    "module": {"max_words": 220, "overlap_words": 40, "min_words_to_chunk": 220},
}


PROJECT_COLLECTIONS = {
    "page": "page",
    "workItem": "work_item",
    "project": "project",
    "cycle": "cycle",
    "module": "module",
    "epic": "epic",
}


# ---------------------------------------------------------------------------
# Qdrant collection helpers
# ---------------------------------------------------------------------------


def ensure_collection_with_hybrid(
    client: Any,
    collection_name: str,
    *,
    vector_size: int = 768,
    force_recreate: bool = False,
) -> None:
    """Ensure the collection exists with dense + sparse vector support."""

    try:
        should_create = False
        try:
            existing_names = [c.name for c in client.get_collections().collections]
            should_create = collection_name not in existing_names
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"WARN: could not list collections: {exc}")
            should_create = True

        if force_recreate:
            print(
                f"INFO: recreating Qdrant collection '{collection_name}' "
                "(existing data will be replaced)."
            )
            client.recreate_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": qmodels.VectorParams(
                        size=vector_size, distance=qmodels.Distance.COSINE
                    )
                },
                sparse_vectors_config={
                    "sparse": qmodels.SparseVectorParams(),
                },
            )
            print(f"INFO: collection '{collection_name}' recreated for hybrid search.")
        elif should_create:
            print(
                f"INFO: creating Qdrant collection '{collection_name}' with "
                "dense and sparse vectors."
            )
            client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": qmodels.VectorParams(
                        size=vector_size, distance=qmodels.Distance.COSINE
                    )
                },
                sparse_vectors_config={
                    "sparse": qmodels.SparseVectorParams(),
                },
            )
            print(f"INFO: collection '{collection_name}' created for hybrid search.")
        else:
            print(f"INFO: collection '{collection_name}' already exists; keeping data.")

        try:
            client.update_collection(
                collection_name=collection_name,
                optimizer_config=qmodels.OptimizersConfigDiff(indexing_threshold=1),
            )
            print("INFO: indexing_threshold set to 1 for faster ingestion.")
        except Exception as exc:
            print(f"WARN: failed to update optimizer config: {exc}")

        indexed_fields = [
            ("content_type", qmodels.PayloadSchemaType.KEYWORD),
            ("business_id", qmodels.PayloadSchemaType.KEYWORD),
            ("project_name", qmodels.PayloadSchemaType.KEYWORD),
            ("title", qmodels.PayloadSchemaType.TEXT),
            ("full_text", qmodels.PayloadSchemaType.TEXT),
            ("chunk_index", qmodels.PayloadSchemaType.INTEGER),
            ("parent_id", qmodels.PayloadSchemaType.KEYWORD),
            ("project_id", qmodels.PayloadSchemaType.KEYWORD),
            ("mongo_id", qmodels.PayloadSchemaType.KEYWORD),
        ]

        for field_name, schema in indexed_fields:
            try:
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=schema,
                )
            except Exception as exc:
                if "already exists" not in str(exc):
                    print(f"WARN: failed to ensure index on '{field_name}': {exc}")

    except Exception as exc:  # pragma: no cover - top-level guard
        print(f"ERROR: could not ensure collection '{collection_name}': {exc}")


# ---------------------------------------------------------------------------
# Mongo ? text helpers
# ---------------------------------------------------------------------------


def normalize_mongo_id(mongo_id: Any) -> str:
    if mongo_id is None:
        return ""
    if isinstance(mongo_id, ObjectId):
        return str(mongo_id)
    if isinstance(mongo_id, Binary) and mongo_id.subtype == 3:
        return str(uuid.UUID(bytes=mongo_id))
    if isinstance(mongo_id, dict):
        for key in ("$oid", "oid", "$uuid", "uuid", "value"):
            if key in mongo_id and mongo_id[key] is not None:
                try:
                    return str(mongo_id[key])
                except Exception:
                    continue
        # Extended JSON binary shape {"$binary": {"base64": "...", "subType": "03"}}
        binary = mongo_id.get("$binary") if "$binary" in mongo_id else None
        if isinstance(binary, dict):
            base64_value = binary.get("base64")
            subtype = binary.get("subType") or binary.get("subtype")
            if base64_value and str(subtype) == "03":
                try:
                    data = base64.b64decode(base64_value)
                    return str(uuid.UUID(bytes=data))
                except Exception:
                    pass
        return json.dumps(mongo_id, sort_keys=True)
    return str(mongo_id)


def html_to_text(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<(br|BR)\s*/?>", "\n", html)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_editorjs_blocks(content_str: str) -> Tuple[List[Dict[str, Any]], str]:
    if not content_str or not content_str.strip():
        return [], ""
    try:
        content_json = json.loads(content_str)
        blocks = content_json.get("blocks", [])
    except Exception as exc:
        print(f"WARN: failed to parse EditorJS content: {exc}")
        return [], ""

    extracted: List[str] = []
    for block in blocks:
        btype = (block or {}).get("type") or ""
        data = (block or {}).get("data") or {}

        if btype in {"paragraph", "header", "quote"}:
            text = html_to_text(data.get("text", ""))
            caption = html_to_text(data.get("caption", "")) if btype == "quote" else ""
            line = text if not caption else f"{text} - {caption}"
            if line:
                extracted.append(line)
        elif btype == "list":
            items = data.get("items") or []
            style = (data.get("style") or "").lower()
            lines: List[str] = []
            for idx, item in enumerate(items, 1):
                item_text = html_to_text(item if isinstance(item, str) else str(item))
                if not item_text:
                    continue
                prefix = f"{idx}. " if style == "ordered" else "- "
                lines.append(prefix + item_text)
            if lines:
                extracted.append("\n".join(lines))
        elif btype == "checklist":
            items = data.get("items") or []
            lines: List[str] = []
            for item in items:
                text = html_to_text((item or {}).get("text", ""))
                if not text:
                    continue
                checked = bool((item or {}).get("checked", False))
                prefix = "[x] " if checked else "[ ] "
                lines.append(prefix + text)
            if lines:
                extracted.append("\n".join(lines))
        elif btype == "table":
            table = data.get("content") or []
            rows: List[str] = []
            for row in table:
                cells = [html_to_text(cell) for cell in (row or [])]
                rows.append(" | ".join(cells).strip())
            if rows:
                extracted.append("\n".join(rows))
        elif btype == "code":
            code = data.get("code", "").strip()
            if code:
                extracted.append(code)
        elif btype in {"image", "embed", "linkTool", "raw", "delimiter"}:
            parts: List[str] = []
            if data.get("caption"):
                parts.append(html_to_text(data.get("caption", "")))
            if btype == "linkTool":
                link = (data.get("link") or "").strip()
                meta = data.get("meta") or {}
                title = html_to_text(meta.get("title", "")) if isinstance(meta, dict) else ""
                description = (
                    html_to_text(meta.get("description", ""))
                    if isinstance(meta, dict)
                    else ""
                )
                parts.extend([p for p in [title, description, link] if p])
            text = " - ".join([p for p in parts if p])
            if text:
                extracted.append(text)
        else:
            text = html_to_text(data.get("text", ""))
            if text:
                extracted.append(text)

    combined_text = "\n\n".join([t for t in extracted if t]).strip()
    return blocks, combined_text


def point_id_from_seed(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def chunk_text(
    text: str,
    *,
    max_words: int,
    overlap_words: int,
    min_words_to_chunk: Optional[int] = None,
) -> List[str]:
    if not text:
        return []

    words = text.split()
    threshold = min_words_to_chunk if min_words_to_chunk is not None else max_words

    if len(words) <= threshold:
        return [text]

    chunks: List[str] = []
    step = max(1, max_words - overlap_words)
    for start in range(0, len(words), step):
        end = min(start + max_words, len(words))
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end == len(words):
            break
    return chunks


def get_chunks_for_content(text: str, content_type: str) -> List[str]:
    config = CHUNKING_CONFIG.get(content_type, CHUNKING_CONFIG["work_item"])
    return chunk_text(
        text,
        max_words=config["max_words"],
        overlap_words=config["overlap_words"],
        min_words_to_chunk=config.get("min_words_to_chunk", config["max_words"]),
    )


# ---------------------------------------------------------------------------
# Document preparation / chunking / point generation
# ---------------------------------------------------------------------------


def prepare_document(collection_name: str, doc: Dict[str, Any]) -> Tuple[Optional[PreparedDocument], List[str]]:
    """Convert a Mongo document into a normalized representation."""

    if not doc:
        return None, ["WARN: received empty document"]

    content_type = PROJECT_COLLECTIONS.get(collection_name)
    if not content_type:
        return None, [f"INFO: skipping unsupported collection '{collection_name}'"]

    try:
        if content_type == "page":
            return _prepare_page(doc)
        if content_type == "work_item":
            return _prepare_work_item(doc)
        if content_type == "project":
            return _prepare_project(doc)
        if content_type == "cycle":
            return _prepare_cycle(doc)
        if content_type == "module":
            return _prepare_module(doc)
        if content_type == "epic":
            return _prepare_epic(doc)
    except SkipDocument as exc:
        return None, [str(exc)]
    except Exception as exc:  # pragma: no cover - defensive logging
        return None, [f"ERROR: failed to prepare document from '{collection_name}': {exc}"]

    return None, [f"INFO: no handler for collection '{collection_name}'"]


def chunk_prepared_document(prepared: PreparedDocument) -> List[str]:
    if not prepared.combined_text:
        return []
    chunks = get_chunks_for_content(prepared.combined_text, prepared.content_type)
    return chunks or [prepared.combined_text]


def generate_points(
    prepared: PreparedDocument,
    chunks: Iterable[str],
    embedder: Any,
    splade_encoder: Any,
) -> List[qmodels.PointStruct]:
    chunk_list = list(chunks)
    if not chunk_list:
        return []

    vectors = embedder.encode(chunk_list)
    if hasattr(vectors, "tolist"):
        vectors = vectors.tolist()

    if len(vectors) != len(chunk_list):
        raise ValueError("embedding dimension mismatch with chunk count")

    points: List[qmodels.PointStruct] = []
    for idx, chunk in enumerate(chunk_list):
        vector = vectors[idx]
        if hasattr(vector, "tolist"):
            vector = vector.tolist()
        if not isinstance(vector, list):
            vector = [float(x) for x in vector]

        full_text = f"{prepared.title} {chunk}".strip()

        payload: Dict[str, Any] = {
            "mongo_id": prepared.mongo_id,
            "parent_id": prepared.mongo_id,
            "chunk_index": idx,
            "chunk_count": len(chunk_list),
            "title": prepared.title,
            "content": chunk,
            "full_text": full_text,
            "content_type": prepared.content_type,
        }
        payload.update({k: v for k, v in prepared.metadata.items() if v is not None})

        vector_map: Dict[str, Any] = {"dense": [float(x) for x in vector]}

        if splade_encoder is not None:
            splade_vec = splade_encoder.encode_text(full_text)
            if splade_vec.get("indices"):
                vector_map["sparse"] = qmodels.SparseVector(
                    indices=splade_vec["indices"], values=splade_vec["values"]
                )

        point_id = point_id_from_seed(f"{prepared.mongo_id}/{prepared.content_type}/{idx}")
        points.append(
            qmodels.PointStruct(
                id=point_id,
                vector=vector_map,
                payload=payload,
            )
        )

    return points


# ---------------------------------------------------------------------------
# Internal helpers per content type
# ---------------------------------------------------------------------------


class SkipDocument(RuntimeError):
    pass


def _prepare_page(doc: Dict[str, Any]) -> Tuple[PreparedDocument, List[str]]:
    mongo_id = normalize_mongo_id(doc.get("_id"))
    title = doc.get("title", "")
    _, combined_text = parse_editorjs_blocks(doc.get("content", ""))

    warnings: List[str] = []

    if combined_text:
        for field_name, field_value in doc.items():
            if field_name in {
                "_id",
                "title",
                "content",
                "visibility",
                "isFavourite",
                "createdAt",
                "updatedAt",
                "createdTimeStamp",
                "updatedTimeStamp",
                "project",
                "createdBy",
                "business",
            }:
                continue
            if isinstance(field_value, str) and len(field_value.strip()) > 20:
                combined_text += " " + field_value.strip()

    if not combined_text and title:
        combined_text = title
        warnings.append(
            f"WARN: page '{title}' ({mongo_id}) lacked content; title used as fallback"
        )

    if not combined_text:
        raise SkipDocument(f"WARN: skipping page {mongo_id} - empty title/content")

    metadata: Dict[str, Any] = {
        "visibility": doc.get("visibility"),
        "isFavourite": doc.get("isFavourite", False),
        "createdAt": doc.get("createdAt") or doc.get("createdTimeStamp"),
        "updatedAt": doc.get("updatedAt") or doc.get("updatedTimeStamp"),
    }

    project = doc.get("project")
    if isinstance(project, dict):
        metadata["project_name"] = project.get("name")
        if project.get("_id") is not None:
            metadata["project_id"] = normalize_mongo_id(project.get("_id"))

    business = doc.get("business")
    if isinstance(business, dict):
        metadata["business_name"] = business.get("name")
        if business.get("_id") is not None:
            metadata["business_id"] = normalize_mongo_id(business.get("_id"))

    created_by = doc.get("createdBy")
    if isinstance(created_by, dict):
        metadata["created_by_name"] = created_by.get("name")

    prepared = PreparedDocument(
        content_type="page",
        mongo_id=mongo_id,
        title=title,
        combined_text=combined_text,
        metadata=metadata,
    )

    return prepared, warnings


def _prepare_work_item(doc: Dict[str, Any]) -> Tuple[PreparedDocument, List[str]]:
    mongo_id = normalize_mongo_id(doc.get("_id"))
    title_clean = html_to_text(doc.get("title", ""))
    desc_clean = html_to_text(doc.get("description", ""))

    worklogs_descriptions: List[str] = []
    worklogs = doc.get("workLogs")
    if isinstance(worklogs, list):
        for log in worklogs:
            if isinstance(log, dict) and log.get("description"):
                worklogs_descriptions.append(html_to_text(log.get("description", "")))

    combined_text = " ".join(
        filter(None, [title_clean, desc_clean, " ".join(worklogs_descriptions)])
    ).strip()

    if not combined_text:
        raise SkipDocument(
            f"WARN: skipping work item {mongo_id} - no substantial text content"
        )

    metadata: Dict[str, Any] = {
        "displayBugNo": doc.get("displayBugNo"),
        "priority": doc.get("priority"),
        "status": doc.get("status"),
        "createdAt": doc.get("createdAt") or doc.get("createdTimeStamp"),
        "updatedAt": doc.get("updatedAt") or doc.get("updatedTimeStamp"),
    }

    state = doc.get("state")
    if isinstance(state, dict):
        metadata["state_name"] = state.get("name")

    project = doc.get("project")
    if isinstance(project, dict):
        metadata["project_name"] = project.get("name")
        if project.get("_id") is not None:
            metadata["project_id"] = normalize_mongo_id(project.get("_id"))

    cycle = doc.get("cycle")
    if isinstance(cycle, dict):
        metadata["cycle_name"] = cycle.get("name")

    modules = doc.get("modules")
    if isinstance(modules, dict):
        metadata["module_name"] = modules.get("name")

    business = doc.get("business")
    if isinstance(business, dict):
        metadata["business_name"] = business.get("name")
        if business.get("_id") is not None:
            metadata["business_id"] = normalize_mongo_id(business.get("_id"))

    assignee = doc.get("assignee")
    if isinstance(assignee, list) and assignee and isinstance(assignee[0], dict):
        metadata["assignee_name"] = assignee[0].get("name")
    elif isinstance(assignee, dict):
        metadata["assignee_name"] = assignee.get("name")

    created_by = doc.get("createdBy")
    if isinstance(created_by, dict):
        metadata["created_by_name"] = created_by.get("name")

    prepared = PreparedDocument(
        content_type="work_item",
        mongo_id=mongo_id,
        title=doc.get("title", ""),
        combined_text=combined_text,
        metadata=metadata,
    )

    return prepared, []


def _prepare_project(doc: Dict[str, Any]) -> Tuple[PreparedDocument, List[str]]:
    mongo_id = normalize_mongo_id(doc.get("_id"))
    name = doc.get("name", "")
    description = (doc.get("description") or "").strip()

    text_parts: List[str] = []
    if name:
        text_parts.append(name)
    if description and len(description) > 10:
        text_parts.append(description)

    excluded = {
        "_id",
        "name",
        "description",
        "createdAt",
        "updatedAt",
        "createdTimeStamp",
        "updatedTimeStamp",
        "business",
    }
    text_parts.extend(_aggregate_text_parts(doc, excluded_fields=excluded))

    combined_text = " ".join(text_parts).strip()
    if not combined_text:
        raise SkipDocument(
            f"WARN: skipping project {mongo_id} - no substantial text content"
        )

    metadata = _build_metadata_with_business(doc)

    prepared = PreparedDocument(
        content_type="project",
        mongo_id=mongo_id,
        title=name,
        combined_text=combined_text,
        metadata=metadata,
    )

    return prepared, []


def _prepare_cycle(doc: Dict[str, Any]) -> Tuple[PreparedDocument, List[str]]:
    mongo_id = normalize_mongo_id(doc.get("_id"))
    name = doc.get("name") or doc.get("title") or ""
    description = (doc.get("description") or "").strip()

    text_parts: List[str] = []
    if name:
        text_parts.append(name)
    if description and len(description) > 10:
        text_parts.append(description)

    excluded = {
        "_id",
        "name",
        "title",
        "description",
        "createdAt",
        "updatedAt",
        "createdTimeStamp",
        "updatedTimeStamp",
        "business",
    }
    text_parts.extend(_aggregate_text_parts(doc, excluded_fields=excluded))

    combined_text = " ".join(text_parts).strip()
    if not combined_text:
        raise SkipDocument(
            f"WARN: skipping cycle {mongo_id} - no substantial text content"
        )

    metadata = _build_metadata_with_business(doc)

    prepared = PreparedDocument(
        content_type="cycle",
        mongo_id=mongo_id,
        title=name,
        combined_text=combined_text,
        metadata=metadata,
    )

    return prepared, []


def _prepare_module(doc: Dict[str, Any]) -> Tuple[PreparedDocument, List[str]]:
    mongo_id = normalize_mongo_id(doc.get("_id"))
    name = doc.get("name") or doc.get("title") or ""
    description = (doc.get("description") or "").strip()

    text_parts: List[str] = []
    if name:
        text_parts.append(name)
    if description and len(description) > 10:
        text_parts.append(description)

    excluded = {
        "_id",
        "name",
        "title",
        "description",
        "createdAt",
        "updatedAt",
        "createdTimeStamp",
        "updatedTimeStamp",
        "business",
    }
    text_parts.extend(_aggregate_text_parts(doc, excluded_fields=excluded))

    combined_text = " ".join(text_parts).strip()
    if not combined_text:
        raise SkipDocument(
            f"WARN: skipping module {mongo_id} - no substantial text content"
        )

    metadata = _build_metadata_with_business(doc)

    prepared = PreparedDocument(
        content_type="module",
        mongo_id=mongo_id,
        title=name,
        combined_text=combined_text,
        metadata=metadata,
    )

    return prepared, []


def _prepare_epic(doc: Dict[str, Any]) -> Tuple[PreparedDocument, List[str]]:
    mongo_id = normalize_mongo_id(doc.get("_id"))
    title_clean = html_to_text(doc.get("title", ""))
    desc_clean = html_to_text(doc.get("description", ""))
    combined_text = " ".join(filter(None, [title_clean, desc_clean])).strip()

    if not combined_text:
        raise SkipDocument(f"WARN: skipping epic {mongo_id} - no substantial text content")

    metadata: Dict[str, Any] = {
        "bugNo": doc.get("bugNo"),
        "priority": doc.get("priority"),
        "createdAt": doc.get("createdAt") or doc.get("createdTimeStamp"),
        "updatedAt": doc.get("updatedAt") or doc.get("updatedTimeStamp"),
    }

    state = doc.get("state")
    if isinstance(state, dict):
        metadata["state_name"] = state.get("name")

    state_master = doc.get("stateMaster")
    if isinstance(state_master, dict):
        metadata["stateMaster_name"] = state_master.get("name")

    project = doc.get("project")
    if isinstance(project, dict):
        metadata["project_name"] = project.get("name")
        if project.get("_id") is not None:
            metadata["project_id"] = normalize_mongo_id(project.get("_id"))

    business = doc.get("business")
    if isinstance(business, dict):
        metadata["business_name"] = business.get("name")
        if business.get("_id") is not None:
            metadata["business_id"] = normalize_mongo_id(business.get("_id"))

    assignee = doc.get("assignee")
    if isinstance(assignee, list) and assignee and isinstance(assignee[0], dict):
        metadata["assignee_name"] = assignee[0].get("name")
    elif isinstance(assignee, dict):
        metadata["assignee_name"] = assignee.get("name")

    created_by = doc.get("createdBy")
    if isinstance(created_by, dict):
        metadata["created_by_name"] = created_by.get("name")

    prepared = PreparedDocument(
        content_type="epic",
        mongo_id=mongo_id,
        title=doc.get("title", ""),
        combined_text=combined_text,
        metadata=metadata,
    )

    return prepared, []


def _aggregate_text_parts(doc: Dict[str, Any], *, excluded_fields: set[str]) -> List[str]:
    text_parts: List[str] = []
    for field_name, field_value in doc.items():
        if field_name in excluded_fields:
            continue
        if isinstance(field_value, str) and len(field_value.strip()) > 20:
            text_parts.append(field_value.strip())
    return text_parts


def _build_metadata_with_business(doc: Dict[str, Any]) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    business = doc.get("business")
    if isinstance(business, dict):
        metadata["business_name"] = business.get("name")
        if business.get("_id") is not None:
            metadata["business_id"] = normalize_mongo_id(business.get("_id"))
    return metadata

