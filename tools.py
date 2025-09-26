from langchain_core.tools import tool
from typing import Optional, Dict, List, Any, Union
import mongo.constants
import os
import json
import re
from glob import glob
from datetime import datetime

# Qdrant and RAG dependencies
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
    from sentence_transformers import SentenceTransformer
    import numpy as np
except ImportError:
    QdrantClient = None
    SentenceTransformer = None
    np = None

mongodb_tools = mongo.constants.mongodb_tools
DATABASE_NAME = mongo.constants.DATABASE_NAME
try:
    from planner import plan_and_execute_query
except ImportError:
    plan_and_execute_query = None


def normalize_mongodb_types(obj: Any) -> Any:
    """Convert MongoDB extended JSON types to regular Python types."""
    if obj is None:
        return None

    if isinstance(obj, dict):
        # Handle MongoDB-specific types
        if '$binary' in obj:
            # Convert binary to string representation (we'll filter it out anyway)
            return f"<binary:{obj['$binary']['base64'][:8]}...>"
        elif '$date' in obj:
            # Convert MongoDB date to string representation
            return obj['$date']
        elif '$oid' in obj:
            # Convert ObjectId to string
            return obj['$oid']
        else:
            # Recursively process nested objects
            return {key: normalize_mongodb_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        # Process lists recursively
        return [normalize_mongodb_types(item) for item in obj]
    else:
        # Return primitive types as-is
        return obj


def filter_meaningful_content(data: Any) -> Any:
    """Filter MongoDB documents to keep only meaningful content fields.

    Removes unnecessary fields like _id, timestamps, and other metadata
    while preserving actual content like text, names, descriptions, etc.

    Args:
        data: Raw MongoDB document(s) - can be dict, list, or other types

    Returns:
        Filtered data with only meaningful content fields
    """
    # First, normalize MongoDB extended JSON to regular Python types
    normalized_data = normalize_mongodb_types(data)

    # Handle edge cases
    if normalized_data is None:
        return None

    # Define fields that contain meaningful content (not metadata)
    CONTENT_FIELDS = {
        # Text content
        'title', 'description', 'name', 'content', 'email', 'role',
        'priority', 'status', 'state', 'displayBugNo', 'projectDisplayId',
        # Business logic fields
        'label', 'type', 'access', 'visibility', 'icon', 'imageUrl',
        'business', 'staff', 'createdBy', 'assignee', 'project', 'cycle', 'module',
        'members', 'pages', 'projectStates', 'subStates', 'linkedCycle', 'linkedModule',
        # Date fields (but not timestamps)
        'startDate', 'endDate', 'joiningDate', 'createdAt', 'updatedAt',
        # Count/aggregation results
        'total', 'count', 'group', 'items'
    }

    # Fields to always exclude (metadata)
    EXCLUDE_FIELDS = {
        '_id', 'createdTimeStamp', 'updatedTimeStamp',
        '_priorityRank'  # Helper field added by pipeline
    }

    def is_meaningful_field(key: str, value: Any) -> bool:
        """Check if a field contains meaningful content."""
        # Always exclude metadata fields
        if key in EXCLUDE_FIELDS:
            return False

        # Keep content fields
        if key in CONTENT_FIELDS:
            return True

        # For unknown fields, check if they have meaningful values
        if isinstance(value, str) and value.strip():
            # Non-empty strings are meaningful
            return True
        elif isinstance(value, (int, float)) and not key.endswith(('Id', '_id')):
            # Numbers that aren't IDs are meaningful
            return True
        elif isinstance(value, bool):
            # Boolean values are meaningful
            return True
        elif isinstance(value, dict):
            # Recursively check nested objects
            return any(is_meaningful_field(k, v) for k, v in value.items())
        elif isinstance(value, list) and value:
            # Check if list contains meaningful content
            return any(isinstance(item, (str, int, float, bool)) and
                      (isinstance(item, str) and item.strip() or True)
                      for item in value if isinstance(item, (str, int, float, bool, dict)))

        return False

    def clean_document(doc: Any) -> Any:
        """Clean a single document or value."""
        if isinstance(doc, dict):
            # Filter dictionary
            cleaned = {}
            for key, value in doc.items():
                if is_meaningful_field(key, value):
                    if isinstance(value, (dict, list)):
                        cleaned_value = clean_document(value)
                        if cleaned_value:  # Only add if there's meaningful content
                            cleaned[key] = cleaned_value
                    else:
                        cleaned[key] = value
            return cleaned if cleaned else {}
        elif isinstance(doc, list):
            # Filter list of documents
            cleaned = []
            for item in doc:
                cleaned_item = clean_document(item)
                if cleaned_item:  # Only add if there's meaningful content
                    cleaned.append(cleaned_item)
            return cleaned
        else:
            # Return primitive values as-is
            return doc

    return clean_document(normalized_data)


@tool
async def mongo_query(query: str, show_all: bool = False) -> str:
    """Plan-first Mongo query executor for structured, factual questions.

    Use this ONLY when the user asks for authoritative data that must come from
    MongoDB (counts, lists, filters, group-by, state/assignee/project details)
    across collections: `project`, `workItem`, `cycle`, `module`, `members`,
    `page`, `projectState`.

    Do NOT use this for:
    - Free-form content questions (use `rag_answer_question` or `rag_content_search`).
    - Pure summarization or opinion without data retrieval.
    - When you already have the exact answer in prior tool results.

    Behavior:
    - Follows a planner to generate a safe aggregation pipeline; avoids
      hallucinated fields.
    - Return concise summaries by default; pass `show_all=True` only when the
      user explicitly requests full records.

    Args:
        query: Natural language, structured data request about PM entities.
        show_all: If True, output full details instead of a summary. Use sparingly.

    Returns: A compact result suitable for direct user display.
    """
    if not plan_and_execute_query:
        return "❌ Intelligent query planner not available. Please ensure query_planner.py is properly configured."

    try:
        result = await plan_and_execute_query(query)

        if result["success"]:
            response = f"🎯 INTELLIGENT QUERY RESULT:\n"
            response += f"Query: '{query}'\n\n"

            # Show parsed intent
            intent = result["intent"]
            response += f"📋 UNDERSTOOD INTENT:\n"
            if result.get("planner"):
                response += f"• Planner: {result['planner']}\n"
            response += f"• Primary Entity: {intent['primary_entity']}\n"
            if intent['target_entities']:
                response += f"• Related Entities: {', '.join(intent['target_entities'])}\n"
            if intent['filters']:
                response += f"• Filters: {intent['filters']}\n"
            if intent['aggregations']:
                response += f"• Aggregations: {', '.join(intent['aggregations'])}\n"
            response += "\n"

            # Show the generated pipeline (first few stages)
            pipeline = result["pipeline"]
            if pipeline:
                response += f"🔧 GENERATED PIPELINE:\n"
                for i, stage in enumerate(pipeline):
                    stage_name = list(stage.keys())[0]
                    # Format the stage content nicely
                    stage_content = json.dumps(stage[stage_name], indent=2)
                    # Truncate very long content for readability but show complete structure
                    if len(stage_content) > 200:
                        stage_content = stage_content + "..."
                    response += f"• {stage_name}: {stage_content}\n"
                response += "\n"

            # Show results (compact preview)
            rows = result.get("result")
            try:
                # Attempt to parse stringified JSON results
                if isinstance(rows, str):
                    parsed = json.loads(rows)
                else:
                    parsed = rows
            except Exception:
                parsed = rows

            # Handle the specific MongoDB response format
            if isinstance(parsed, list) and len(parsed) > 0:
                # Check if first element is a string (like "Found X documents...")
                if isinstance(parsed[0], str) and parsed[0].startswith("Found"):
                    # This is the MongoDB response format: [message, doc1_json, doc2_json, ...]
                    # Parse the JSON strings and filter them
                    documents = []
                    for item in parsed[1:]:  # Skip the first message
                        if isinstance(item, str):
                            try:
                                doc = json.loads(item)
                                filtered_doc = filter_meaningful_content(doc)
                                if filtered_doc:  # Only add if there's meaningful content
                                    documents.append(filtered_doc)
                            except Exception:
                                # Skip invalid JSON
                                continue
                        else:
                            # Already parsed, filter directly
                            filtered_doc = filter_meaningful_content(item)
                            if filtered_doc:
                                documents.append(filtered_doc)

                    filtered = documents
                else:
                    # Regular list, filter as before
                    filtered = filter_meaningful_content(parsed)
            else:
                # Not a list, filter as before
                filtered = filter_meaningful_content(parsed)


            def format_llm_friendly(data, max_items=20):
                """Format data in a more LLM-friendly way to avoid hallucinations."""
                if isinstance(data, list):
                    # Handle count-only results
                    if len(data) == 1 and isinstance(data[0], dict) and "total" in data[0]:
                        return f"📊 RESULTS:\nTotal: {data[0]['total']}"

                    # Handle grouped/aggregated results
                    if len(data) > 0 and isinstance(data[0], dict) and "count" in data[0]:
                        response = "📊 RESULTS SUMMARY:\n"
                        total_items = sum(item.get('count', 0) for item in data)

                        # Determine what type of grouping this is
                        first_item = data[0]
                        group_keys = [k for k in first_item.keys() if k not in ['count', 'items']]

                        if group_keys:
                            response += f"Found {total_items} items grouped by {', '.join(group_keys)}:\n\n"

                            # Sort by count (highest first) and show more groups
                            sorted_data = sorted(data, key=lambda x: x.get('count', 0), reverse=True)

                            # Show all groups if max_items is None, otherwise limit
                            display_limit = len(sorted_data) if max_items is None else 15
                            for item in sorted_data[:display_limit]:
                                group_values = [f"{k}: {item[k]}" for k in group_keys if k in item]
                                group_label = ', '.join(group_values)
                                count = item.get('count', 0)
                                response += f"• {group_label}: {count} items\n"

                            if max_items is not None and len(data) > 15:
                                remaining = sum(item.get('count', 0) for item in sorted_data[15:])
                                response += f"• ... and {len(data) - 15} other categories: {remaining} items\n"
                            elif max_items is None and len(data) > display_limit:
                                remaining = sum(item.get('count', 0) for item in sorted_data[display_limit:])
                                response += f"• ... and {len(data) - display_limit} other categories: {remaining} items\n"
                        else:
                            response += f"Found {total_items} items\n"
                        print(response)
                        return response

                    # Handle list of documents - show summary instead of raw JSON
                    if max_items is not None and len(data) > max_items:
                        response = f"📊 RESULTS SUMMARY:\n"
                        response += f"Found {len(data)} items. Showing key details for first {max_items}:\n\n"

                        # Group by priority if available
                        priority_counts = {}
                        for item in data[:max_items]:
                            if isinstance(item, dict) and 'priority' in item:
                                priority = item['priority']
                                priority_counts[priority] = priority_counts.get(priority, 0) + 1

                        if priority_counts:
                            response += "Priority breakdown:\n"
                            for priority, count in sorted(priority_counts.items()):
                                response += f"• {priority}: {count} items\n"
                            response += "\n"

                        # Show sample items in a readable format
                        response += "Sample items:\n"
                        for i, item in enumerate(data[:5], 1):  # Show 5 samples instead of 3
                            if isinstance(item, dict):
                                title = item.get('title', 'No title')[:50] + "..." if len(item.get('title', '')) > 50 else item.get('title', 'No title')
                                priority = item.get('priority', 'No priority')
                                display_no = item.get('displayBugNo', f'Item {i}')
                                response += f"• {display_no}: {title} ({priority})\n"

                        if len(data) > 5:
                            response += f"• ... and {len(data) - 5} more items\n"
                        print(response)
                        return response
                    else:
                        # Show all items or small list - show in formatted way
                        response = "📊 RESULTS:\n"
                        for i, item in enumerate(data, 1):
                            if isinstance(item, dict):
                                title = item.get('title', 'No title')[:30] + "..." if len(item.get('title', '')) > 30 else item.get('title', 'No title')
                                priority = item.get('priority', 'No priority')
                                display_no = item.get('displayBugNo', f'Item {i}')
                                response += f"• {display_no}: {title} ({priority})\n"
                        print(response)
                        return response

                # Single document or other data
                if isinstance(data, dict):
                    # Format single document in a readable way
                    response = "📊 RESULT:\n"
                    for key, value in data.items():
                        if isinstance(value, (str, int, float, bool)):
                            response += f"• {key}: {value}\n"
                        elif isinstance(value, dict):
                            response += f"• {key}:\n"
                            for sub_key, sub_value in value.items():
                                response += f"  - {sub_key}: {sub_value}\n"
                        elif isinstance(value, list) and len(value) <= 3:
                            response += f"• {key}: {value}\n"
                        else:
                            response += f"• {key}: [{len(value)} items]\n"
                    print(response)
                    return response
                else:
                    # Fallback to JSON for other data types
                    return f"📊 RESULTS:\n{json.dumps(data, indent=2)}"

            # Format in LLM-friendly way
            max_items = None if show_all else 20
            formatted_result = format_llm_friendly(filtered, max_items=max_items)
            response += formatted_result
            print(response)
            return response
        else:
            return f"❌ QUERY FAILED:\nQuery: '{query}'\nError: {result['error']}"

    except Exception as e:
        return f"❌ INTELLIGENT QUERY ERROR:\nQuery: '{query}'\nError: {str(e)}"

# RAG Tool for page and work item content
class RAGTool:
    """RAG tool for querying page and work item content from Qdrant"""

    def __init__(self):
        self.qdrant_client = None
        self.embedding_model = None
        self.connected = False

    async def connect(self):
        """Initialize connection to Qdrant and embedding model"""
        if self.connected:
            return

        if not QdrantClient or not SentenceTransformer:
            raise ImportError("Qdrant client or sentence transformer not available. Please install qdrant-client and sentence-transformers.")

        try:
            self.qdrant_client = QdrantClient(url=mongo.constants.QDRANT_URL,api_key=mongo.constants.QDRANT_API_KEY)

            self.embedding_model = SentenceTransformer(mongo.constants.EMBEDDING_MODEL)
            self.connected = True
            print(f"Connected to Qdrant at {mongo.constants.QDRANT_URL}")
        except Exception as e:
            print(f"Failed to connect to Qdrant: {e}")
            raise

    async def search_content(self, query: str, content_type: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant content in Qdrant based on the query"""
        if not self.connected:
            await self.connect()

        try:
            # Generate embedding for the query
            query_embedding = self.embedding_model.encode(query).tolist()
            # h
            print("Query embedding generated")
            # Build filter if content_type is specified
            search_filter = None
            if content_type:
                search_filter = Filter(
                    must=[
                        FieldCondition(
                            key="content_type",
                            match=MatchValue(value=content_type)
                        )
                    ]
                )

            # Primary vector search in Qdrant (fetch extra for post-filtering)
            fetch_k = max(limit * 3, 10)
            search_results = self.qdrant_client.search(
                collection_name=mongo.constants.QDRANT_COLLECTION_NAME,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=fetch_k,
                with_payload=True
            )

            # Format + post-filter results
            raw_results = []
            for result in search_results:
                payload = result.payload or {}
                title = (payload.get("title") or "").strip()
                content = (payload.get("content") or "").strip()
                content_len = len(content)
                # Skip extremely short/noisy chunks
                if content_len < 30 and title == "":
                    continue
                raw_results.append({
                    "id": result.id,
                    "score": float(result.score or 0.0),
                    "title": title if title else "Untitled",
                    "content": content,
                    "content_type": payload.get("content_type", "unknown"),
                    "mongo_id": payload.get("mongo_id"),
                    "parent_id": payload.get("parent_id"),
                    "chunk_index": payload.get("chunk_index"),
                    "chunk_count": payload.get("chunk_count"),
                    "full_text": (payload.get("full_text") or "").strip(),
                })

            if not raw_results:
                return []

            # Apply a minimum score cutoff to reduce junk. Qdrant cosine scores are similarity; tuneable threshold.
            min_score = 0.2
            filtered_by_score = [r for r in raw_results if r["score"] >= min_score]
            if not filtered_by_score:
                filtered_by_score = raw_results[:5]

            # Simple lexical reranking using query term overlap on title/full_text
            query_terms = [t.lower() for t in query.split() if t]
            def lexical_score(r: Dict[str, Any]) -> float:
                hay = f"{r.get('title','')} {r.get('full_text','')}".lower()
                if not hay:
                    hay = r.get('content','').lower()
                matches = sum(1 for t in query_terms if t in hay)
                return matches / max(1, len(set(query_terms)))

            for r in filtered_by_score:
                r["lexical"] = lexical_score(r)

            # Combine vector score and lexical score (weighted)
            def combined_score(r: Dict[str, Any]) -> float:
                return 0.7 * r["score"] + 0.3 * r.get("lexical", 0.0)

            filtered_by_score.sort(key=combined_score, reverse=True)

            # Deduplicate by mongo_id, prefer earlier (higher combined score)
            seen_ids = set()
            deduped: List[Dict[str, Any]] = []
            for r in filtered_by_score:
                key = r.get("mongo_id") or r.get("id")
                if key and key not in seen_ids:
                    seen_ids.add(key)
                    deduped.append(r)

            results = deduped[:limit]

            return results

        except Exception as e:
            print(f"Error searching Qdrant: {e}")
            return []

    async def get_content_context(self, query: str, content_types: List[str] = None) -> str:
        """Get relevant context for answering questions about page and work item content"""
        if not content_types:
            content_types = ["page", "work_item", "project", "cycle", "module"]

        all_results = []
        for content_type in content_types:
            results = await self.search_content(query, content_type=content_type, limit=4)
            all_results.extend(results)

        # Sort by combined heuristic if available; fallback to score
        def sort_key(r):
            return (0.7 * float(r.get("score", 0.0))) + (0.3 * float(r.get("lexical", 0.0)))
        all_results.sort(key=sort_key, reverse=True)

        # Format context
        context_parts = []
        # print(all_results)
        for i, result in enumerate(all_results[:5], 1):  # Limit to top 5 results
            chunk_info = ""
            if result.get("chunk_index") is not None and result.get("chunk_count"):
                chunk_info = f" (chunk {int(result['chunk_index'])+1}/{int(result['chunk_count'])})"
            context_parts.append(
                f"[{i}] {result['content_type'].upper()}: {result['title']}{chunk_info}\n"
                f"Content: {result['content'][:500]}{'...' if len(result['content']) > 500 else ''}\n"
                f"Score: {float(result['score']):.3f}  Lexical: {float(result.get('lexical', 0.0)):.3f}\n"
            )

        return "\n".join(context_parts) if context_parts else "No relevant content found."


@tool
async def rag_content_search(query: str, content_type: str = None, limit: int = 5) -> str:
    """Retrieve relevant content snippets for inspection (not final answers).

    Use to locate semantically relevant `page` or `work_item` snippets via RAG
    when the user asks to "search/find/show examples" or when you need context
    BEFORE answering. Prefer `rag_answer_question` when the user asks a direct
    question that needs synthesized context.

    Do NOT use this for:
    - Structured database facts (use `mongo_query`).
    - Producing the final answer. This returns excerpts to read, not conclusions.
    - Large limits by default; keep `limit` small (<= 5) unless the user asks.

    Args:
        query: Search phrase to find related content.
        content_type: 'page' | 'work_item' | None (both).
        limit: How many snippets to show (default 5).

    Returns: Snippets with scores to inform subsequent reasoning.
    """
    try:
        rag_tool = RAGTool()
        results = await rag_tool.search_content(query, content_type=content_type, limit=limit)

        if not results:
            return f"❌ No relevant content found for query: '{query}'"

        # Format response
        response = f"🔍 RAG SEARCH RESULTS for '{query}':\n\n"
        response += f"Found {len(results)} relevant content pieces:\n\n"

        for i, result in enumerate(results, 1):
            response += f"[{i}] {result['content_type'].upper()}: {result['title']}\n"
            response += f"Relevance Score: {result['score']:.3f}\n"
            response += f"Content Preview: {result['content'][:300]}{'...' if len(result['content']) > 300 else ''}\n"

            # if result['metadata']:
            #     response += f"Metadata: {json.dumps(result['metadata'], indent=2)}\n"

            response += "\n" + "="*50 + "\n"

        return response

    except ImportError:
        return "❌ RAG functionality not available. Please install qdrant-client and sentence-transformers."
    except Exception as e:
        return f"❌ RAG SEARCH ERROR:\nQuery: '{query}'\nError: {str(e)}"


@tool
async def rag_answer_question(question: str, content_types: List[str] = None) -> str:
    """Assemble compact context to answer a content question (RAG-first).

    Use when the user asks a direct question about content in `page`/`work_item`
    data and you need short, high-signal context to support your answer.

    Do NOT use this for:
    - Structured facts like counts/groupings (use `mongo_query`).
    - Broad content discovery (use `rag_content_search`).

    Behavior:
    - Gathers a few high-relevance snippets and returns them as context to read.
    - Keep the final answer in the agent message; this tool returns only context.

    Args:
        question: The specific content question to answer.
        content_types: Optional list of ['page','work_item']; defaults to both.

    Returns: Concise context snippets for the agent to read and then answer.
    """
    try:
        rag_tool = RAGTool()
        context = await rag_tool.get_content_context(question, content_types)

        if not context or "No relevant content found" in context:
            return f"❌ No relevant context found for question: '{question}'"

        response = f"📖 CONTEXT FOR QUESTION: '{question}'\n\n"
        response += "Relevant content found:\n\n"
        response += context
        response += "\n" + "="*50 + "\n"
        response += "Use this context to answer the question about page and work item content."

        return response

    except ImportError:
        return "❌ RAG functionality not available. Please install qdrant-client and sentence-transformers."
    except Exception as e:
        return f"❌ RAG QUESTION ERROR:\nQuestion: '{question}'\nError: {str(e)}"


@tool
async def rag_to_mongo_workitems(query: str, limit: int = 20) -> str:
    """Bridge free-text to canonical work item records (RAG → Mongo).

    Use when the user describes issues in prose and wants real work items with
    authoritative fields (e.g., `state.name`, `assignee`, `project.name`). This
    first vector-matches likely items, then fetches official records from Mongo.

    Do NOT use this for:
    - Pure semantic browsing without mapping to Mongo (use `rag_content_search`).
    - Arbitrary entities other than work items.

    Args:
        query: Free-text description to match work items.
        limit: Maximum records to return (keep modest; default 20).

    Returns: Brief lines summarizing matched items with canonical fields.
    """
    try:
        # Step 1: RAG search for work items only
        rag_tool = RAGTool()
        rag_results = await rag_tool.search_content(query, content_type="work_item", limit=max(limit, 5))

        # Extract unique Mongo IDs and titles from RAG results (point id is mongo_id)
        all_ids: List[str] = []
        titles: List[str] = []
        seen_ids: set[str] = set()
        for r in rag_results:
            mongo_id = str(r.get("mongo_id") or r.get("id") or "").strip()
            title = str(r.get("title") or "").strip()
            if mongo_id and mongo_id not in seen_ids:
                seen_ids.add(mongo_id)
                all_ids.append(mongo_id)
            if title:
                titles.append(title)

        # Partition IDs: keep only 24-hex strings for ObjectId conversion; ignore UUIDs here
        object_id_strings = [s for s in all_ids if len(s) == 24 and all(c in '0123456789abcdefABCDEF' for c in s)]
        object_id_strings = object_id_strings[: max(0, limit)]
        # Deduplicate and cap titles
        seen_titles: set[str] = set()
        title_patterns: List[str] = []
        for t in titles:
            if t and t not in seen_titles:
                seen_titles.add(t)
                title_patterns.append(t)
            if len(title_patterns) >= max(0, limit):
                break

        # Helper builders
        def build_match_from_ids_and_titles(ids: List[str], title_list: List[str]) -> Dict[str, Any]:
            or_clauses_local: List[Dict[str, Any]] = []
            if ids:
                id_array_expr = {
                    "$map": {
                        "input": ids,
                        "as": "id",
                        "in": {"$toObjectId": "$$id"}
                    }
                }
                or_clauses_local.append({"$expr": {"$in": ["$_id", id_array_expr]}})
            if title_list:
                # Use escaped regex to avoid pathological patterns
                title_or = [{"title": {"$regex": re.escape(t), "$options": "i"}} for t in title_list if t]
                if title_or:
                    or_clauses_local.append({"$or": title_or})
            if not or_clauses_local:
                return {"$match": {"_id": {"$exists": True}}}  # no-op match
            if len(or_clauses_local) == 1:
                return {"$match": or_clauses_local[0]}
            return {"$match": {"$or": or_clauses_local}}

        def project_stage() -> Dict[str, Any]:
            return {
                "$project": {
                    "_id": 1,
                    "displayBugNo": 1,
                    "title": 1,
                    "state.name": 1,
                    "assignee.name": 1,
                    "project.name": 1,
                    "createdTimeStamp": 1,
                }
            }

        def parse_mcp_rows(rows_any: Any) -> List[Dict[str, Any]]:
            try:
                parsed_local = json.loads(rows_any) if isinstance(rows_any, str) else rows_any
            except Exception:
                parsed_local = rows_any
            docs_local: List[Dict[str, Any]] = []
            if isinstance(parsed_local, list) and parsed_local:
                if isinstance(parsed_local[0], str) and parsed_local[0].startswith("Found"):
                    for item in parsed_local[1:]:
                        if isinstance(item, str):
                            try:
                                doc = json.loads(item)
                                if isinstance(doc, dict):
                                    docs_local.append(doc)
                            except Exception:
                                continue
                        elif isinstance(item, dict):
                            docs_local.append(item)
                else:
                    # Filter only dicts
                    docs_local = [d for d in parsed_local if isinstance(d, dict)]
            elif isinstance(parsed_local, dict):
                docs_local = [parsed_local]
            else:
                docs_local = []
            return docs_local

        # Step 2: First attempt — match by RAG object IDs and RAG titles
        primary_match = build_match_from_ids_and_titles(object_id_strings, title_patterns)
        pipeline = [
            primary_match,
            project_stage(),
            {"$limit": limit}
        ]

        args = {
            "database": DATABASE_NAME,
            "collection": "workItem",
            "pipeline": pipeline,
        }

        rows = await mongodb_tools.execute_tool("aggregate", args)

        # Normalize and produce a compact summary
        docs = parse_mcp_rows(rows)

        # Fallback 1: If nothing matched via IDs/titles, try Mongo text search
        if not docs:
            text_pipeline = [
                {"$match": {"$text": {"$search": query}}},
                project_stage(),
                {"$limit": limit}
            ]
            rows_text = await mongodb_tools.execute_tool("aggregate", {
                "database": DATABASE_NAME,
                "collection": "workItem",
                "pipeline": text_pipeline,
            })
            docs = parse_mcp_rows(rows_text)

        # Fallback 2: Regex across common fields and tokens
        if not docs:
            tokens = [w for w in re.findall(r"[A-Za-z0-9_]+", query) if w]
            field_list = ["title", "description", "state.name", "project.name", "cycle.name", "modules.name"]
            and_conditions: List[Dict[str, Any]] = []
            for tok in tokens:
                or_fields = [{fld: {"$regex": re.escape(tok), "$options": "i"}} for fld in field_list]
                and_conditions.append({"$or": or_fields})
            regex_match = {"$match": {"$and": and_conditions}} if and_conditions else {"$match": {"_id": {"$exists": True}}}
            regex_pipeline = [
                regex_match,
                project_stage(),
                {"$limit": limit}
            ]
            rows_regex = await mongodb_tools.execute_tool("aggregate", {
                "database": DATABASE_NAME,
                "collection": "workItem",
                "pipeline": regex_pipeline,
            })
            docs = parse_mcp_rows(rows_regex)

        if not docs:
            return f"❌ No MongoDB records found for the RAG matches or fallbacks of '{query}'"

        # Keep content meaningful
        cleaned = filter_meaningful_content(docs)

        # Render
        lines = [f"🔗 Matches for '{query}':"]
        for d in cleaned[:limit]:
            if not isinstance(d, dict):
                continue
            bug = d.get("displayBugNo") or d.get("_id")
            title = d.get("title", "(no title)")
            state = (d.get("state") or {}).get("name") if isinstance(d.get("state"), dict) else d.get("state")
            # assignee may be array or object depending on schema; try best-effort
            assignee_val = d.get("assignee")
            if isinstance(assignee_val, dict):
                assignee = assignee_val.get("name")
            elif isinstance(assignee_val, list) and assignee_val and isinstance(assignee_val[0], dict):
                assignee = assignee_val[0].get("name")
            else:
                assignee = None
            lines.append(f"• {bug}: {title} — state={state or 'N/A'}, assignee={assignee or 'N/A'}")

        return "\n".join(lines)

    except ImportError:
        return "❌ RAG functionality not available. Please install qdrant-client and sentence-transformers."
    except Exception as e:
        return f"❌ RAG→Mongo ERROR:\nQuery: '{query}'\nError: {str(e)}"


# Define the tools list (no schema tool)
tools = [
    mongo_query,
    rag_content_search,
    rag_answer_question,
    rag_to_mongo_workitems,
]

# import asyncio

# if __name__ == "__main__":
#     async def main():
#         # Test the tools    
#         while True:
#             question = input("Enter your question: ")
#             if question.lower() in ['exit', 'quit']:
#                 break

#             print("\n🎯 Testing intelligent_query...")

#             print("🔍 Testing rag_content_search...")
#             result1 = await rag_content_search.ainvoke({
#                 "query": question,   # rag_content_search expects `query`
#             })
#             print(result1)

#             print("\n📖 Testing rag_answer_question...")
#             result2 = await rag_answer_question.ainvoke({
#                 "question": question,   # rag_answer_question expects `question`
#             })
#             print(result2)

#     asyncio.run(main())
