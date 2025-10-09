from typing import List, Dict, Any

from mongo.constants import uuid_str_to_mongo_binary


def _project_id_match_stage(collection: str, project_ids_bin: List[Any]) -> List[Dict[str, Any]]:
    """Build a simple $match stage restricting to a set of project IDs.

    This is used when explicit allowed project IDs are provided in user context.
    """
    if collection == "project":
        return [{"$match": {"_id": {"$in": project_ids_bin}}}]
    if collection in {"workItem", "cycle", "module", "page", "members"}:
        return [{"$match": {"project._id": {"$in": project_ids_bin}}}]
    if collection == "projectState":
        return [{"$match": {"projectId": {"$in": project_ids_bin}}}]
    return []


def _member_lookup_auth_stages(collection: str, member_id_bin: Any) -> List[Dict[str, Any]]:
    """Return $lookup-based auth stages that allow a document only if the
    authenticated user (by memberId) is a member of the document's project.

    Works across collections by checking the appropriate project reference field.
    """
    # Map each collection to its local project reference field
    project_field_by_collection = {
        "project": "$_id",
        "workItem": "$project._id",
        "cycle": "$project._id",
        "module": "$project._id",
        "page": "$project._id",
        "projectState": "$projectId",
        "members": "$project._id",
    }

    local_project_expr = project_field_by_collection.get(collection)
    if not local_project_expr:
        return []

    # $lookup to members to assert that the current doc's project has a
    # membership document for the authenticated memberId
    lookup_stage = {
        "$lookup": {
            "from": "members",
            "let": {"local_project_id": local_project_expr},
            "pipeline": [
                {
                    "$match": {
                        "$expr": {
                            "$and": [
                                {"$eq": ["$project._id", "$$local_project_id"]},
                                {"$eq": ["$memberId", member_id_bin]},
                            ]
                        }
                    }
                }
            ],
            "as": "__auth_members__",
        }
    }

    # Keep documents where there is at least one matching membership
    has_membership_match = {
        "$match": {"$expr": {"$gt": [{"$size": "$__auth_members__"}, 0]}}
    }

    cleanup_stage = {"$unset": "__auth_members__"}

    return [lookup_stage, has_membership_match, cleanup_stage]


def apply_authorization_filter(collection: str, user_context: dict) -> List[Dict[str, Any]]:
    """
    Build authorization filter stages for a given collection based on user context.

    - Admin role: no restrictions
    - Otherwise: restrict to projects the user is a member of, by memberId
      (using a $lookup to the members collection). Optionally, if
      `allowed_project_ids` are provided in the user_context (canonical UUID
      strings), we match directly against those project IDs.
    """
    # Role-based bypass removed: enforce membership or explicit allowed project IDs

    # If explicit allowed project UUIDs are provided, use them directly
    allowed_project_ids = (user_context or {}).get("allowed_project_ids") or []
    project_ids_bin: List[Any] = []
    for pid in allowed_project_ids:
        try:
            project_ids_bin.append(uuid_str_to_mongo_binary(pid))
        except Exception:
            continue
    if project_ids_bin:
        return _project_id_match_stage(collection, project_ids_bin)

    # Otherwise, use the authenticated member's ID to assert membership per document
    member_uuid = (user_context or {}).get("member_id")
    member_id_bin = None
    if member_uuid:
        try:
            member_id_bin = uuid_str_to_mongo_binary(member_uuid)
        except Exception:
            member_id_bin = None

    if member_id_bin is not None:
        return _member_lookup_auth_stages(collection, member_id_bin)

    # If we cannot determine identity or allowed projects, do not inject filters
    # Returning empty list means no additional auth restrictions
    return []