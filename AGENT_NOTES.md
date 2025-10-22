Member-level RBAC at Mongo layer

Environment variables:
- ENFORCE_MEMBER_FILTER=true|false (default: false unless MEMBER_ID/STAFF_ID present)
- MEMBER_ID=<uuid> (legacy UUID string of staff/member)
- or STAFF_ID=<uuid> (alias if you use staff id)

Behavior:
- All Mongo aggregations via mongo.client.DirectMongoClient inject a membership filter.
- Allowed docs: those whose `project._id` (or `projectId` for `projectState`) has at least one matching entry in `members` where `staff._id == MEMBER_ID`.
- For `members` collection, results are restricted to records with `staff._id == MEMBER_ID`.

Business filter coexists:
- Existing business scoping stays in place (ENFORCE_BUSINESS_FILTER + BUSINESS_ID via websocket env).
- Both filters apply when enabled.

Indexes added:
- members.staff._id
- members.(project._id, staff._id)

How to run:
- export ENFORCE_MEMBER_FILTER=true
- export MEMBER_ID=<uuid>
- start backend; all queries will be scoped to this member.
