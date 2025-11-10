# Qdrant Duplication Issue - Fix Documentation

## Problem

When running `docker-compose up` (especially after `docker-compose build`), the backfill service would run **every time** and send all MongoDB documents to Kafka again. This caused duplicates in Qdrant because:

1. The backfill container restarts with each `docker-compose up`
2. All documents get sent to Kafka again
3. The consumer processes them and upserts to Qdrant
4. Even though `upsert` is used, there could be timing issues or the volume of duplicate data was overwhelming

## Solution

The fix implements **smart duplicate prevention** by:

1. **Checking if Qdrant already has data before running backfill**
   - The backfill now connects to Qdrant before starting
   - Checks if the collection exists and has any points
   - If data exists, skips the entire backfill process
   - This prevents unnecessary re-processing of existing data

2. **Environment variable control**
   - `SKIP_BACKFILL_IF_EXISTS=true` (default) - Skip backfill if Qdrant has data
   - `SKIP_BACKFILL_IF_EXISTS=false` - Force backfill even if data exists

3. **Command-line override**
   - `--force` flag forces backfill even when data exists
   - Useful for re-indexing scenarios

## Usage

### Normal Operation (Prevents Duplicates)

```bash
# First run - will backfill all data
docker-compose up

# Subsequent runs - will skip backfill automatically
docker-compose up
```

### Force Re-indexing (if needed)

If you need to re-index all data (e.g., after schema changes):

```bash
# Option 1: Using environment variable
SKIP_BACKFILL_IF_EXISTS=false docker-compose up

# Option 2: Using command-line flag (when running manually)
docker-compose run --rm backfill python /app/backfill_mongodb.py --force
```

### Clear Qdrant and Re-index

If you need to start fresh:

```bash
# Stop services
docker-compose down

# Remove Qdrant data volume
docker volume rm data-sync_qdrant_data

# Start services (backfill will run since Qdrant is empty)
docker-compose up
```

## How It Works

### Before the Fix

```
docker-compose up
  → Backfill runs
  → Sends ALL documents to Kafka
  → Consumer processes ALL documents
  → Qdrant gets duplicates (timing/volume issues)
```

### After the Fix

```
docker-compose up
  → Backfill starts
  → Checks Qdrant for existing data
  → IF data exists:
      ✅ Skip backfill (log message)
      ✅ No Kafka messages sent
      ✅ No duplicates created
  → IF data doesn't exist:
      → Proceed with normal backfill
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SKIP_BACKFILL_IF_EXISTS` | `true` | Skip backfill if Qdrant has data |
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant connection URL |
| `QDRANT_COLLECTION` | `pms_collection` | Qdrant collection name |

### Docker Compose

The fix is automatically enabled in `docker-compose.yml`:

```yaml
backfill:
  environment:
    - QDRANT_URL=${QDRANT_URL:-http://qdrant:6333}
    - QDRANT_COLLECTION=${QDRANT_COLLECTION:-pms_collection}
    - SKIP_BACKFILL_IF_EXISTS=${SKIP_BACKFILL_IF_EXISTS:-true}
  depends_on:
    qdrant:
      condition: service_started
```

## Logs

### When Skipping (Data Exists)

```
✅ Qdrant already contains data. Skipping backfill to prevent duplicates.
   To force backfill, use --force flag or set SKIP_BACKFILL_IF_EXISTS=false
```

### When Running (No Data)

```
Qdrant collection 'pms_collection' is empty, proceeding with backfill
🔄 Starting backfill for collections: epic, features, cycle, module, members, workItem, userStory, page
✅ Backfill completed. Processed 10000 documents across 8 collections.
```

## Benefits

1. ✅ **No Duplicates**: Backfill only runs once, when Qdrant is empty
2. ✅ **Faster Restarts**: Subsequent `docker-compose up` commands are much faster
3. ✅ **Resource Efficient**: No unnecessary Kafka/Qdrant traffic
4. ✅ **Safe by Default**: Duplicate prevention is enabled by default
5. ✅ **Flexible**: Can force re-indexing when needed

## Testing

To verify the fix works:

```bash
# 1. Start services (first time - will backfill)
docker-compose up -d

# Wait for backfill to complete
docker logs mongodb-backfill

# 2. Restart services (should skip backfill)
docker-compose restart backfill

# Check logs - should see "Skipping backfill"
docker logs mongodb-backfill

# 3. Verify no duplicates in Qdrant
# Check Qdrant UI at http://localhost:6333/dashboard
# or use API to check point count
```

## Troubleshooting

### "Qdrant client not available"

The backfill will proceed normally if it can't check Qdrant (graceful degradation).

**Solution**: Ensure `qdrant-client` is installed in the backfill container.

### "Failed to check Qdrant data"

If the Qdrant check fails, the backfill proceeds anyway (safe default).

**Solution**: Check Qdrant is running and accessible at the configured URL.

### Need to re-index everything

Use one of these methods:
1. `SKIP_BACKFILL_IF_EXISTS=false docker-compose up`
2. `docker-compose run --rm backfill python /app/backfill_mongodb.py --force`
3. Delete Qdrant volume and restart

## Code Changes

### Modified Files

1. **`data-sync/backfill_mongodb.py`**
   - Added Qdrant client import
   - Added `connect_qdrant()` method
   - Added `check_qdrant_has_data()` method
   - Modified `main()` to check Qdrant before backfill
   - Added `--force` command-line flag
   - Added proper logging configuration

2. **`data-sync/docker-compose.yml`**
   - Added `QDRANT_URL` environment variable to backfill service
   - Added `QDRANT_COLLECTION` environment variable to backfill service
   - Added `SKIP_BACKFILL_IF_EXISTS` environment variable to backfill service
   - Added `qdrant` to backfill dependencies

## Related Files

- Consumer logic: `data-sync/consumer/app/main.py`
- Shared indexing functions: `data-sync/qdrant/indexing_shared.py`
- Direct indexing (for manual use): `qdrant/insertdocs.py`

All these files use the same deterministic UUID generation (`point_id_from_seed`) to ensure consistent point IDs across different indexing methods.
