"""
Simple TTL-based garbage collection for data/uploads/.

Uploaded datasets are persisted to disk (parquet + manifest) so they survive
a restart, but nothing ever deleted them — left alone, data/uploads/ grows
unbounded. This runs a sweep at startup and then periodically via an asyncio
background task; it's intentionally not a full scheduler/cron system, just
enough for a single-instance deployment.
"""
import asyncio
import os
import time

from schema import UPLOAD_DIR

UPLOAD_TTL_SECONDS = int(os.environ.get("UPLOAD_TTL_SECONDS", str(24 * 60 * 60)))
CLEANUP_INTERVAL_SECONDS = int(os.environ.get("CLEANUP_INTERVAL_SECONDS", str(60 * 60)))


def sweep_expired_uploads() -> int:
    """Delete manifest/parquet pairs older than UPLOAD_TTL_SECONDS. Returns
    the number of datasets removed."""
    now = time.time()
    removed = 0
    for manifest_path in UPLOAD_DIR.glob("*.json"):
        try:
            age = now - manifest_path.stat().st_mtime
        except OSError:
            continue
        if age <= UPLOAD_TTL_SECONDS:
            continue
        dataset_id = manifest_path.stem
        parquet_path = UPLOAD_DIR / f"{dataset_id}.parquet"
        for path in (manifest_path, parquet_path):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        removed += 1
    return removed


async def periodic_cleanup_task() -> None:
    """Background task: sweep expired uploads on an interval for the lifetime
    of the process. Started once at app startup via FastAPI's lifespan."""
    while True:
        try:
            sweep_expired_uploads()
        except Exception:
            pass
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
