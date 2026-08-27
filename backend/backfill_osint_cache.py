#!/usr/bin/env python3
"""
backfill_osint_cache.py — Populate the osint_cache table from all previous
completed jobs in the DB. Run once after the OsintCache table is created.
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import AsyncSessionLocal, Job, OsintCache, init_db
from pipeline.osint_engine import _cache_key
from sqlalchemy import select


async def backfill():
    print("Initialising DB / creating osint_cache table...")
    await init_db()

    async with AsyncSessionLocal() as sess:
        # Load all completed jobs that have result_json and source_url
        result = await sess.execute(
            select(Job).where(
                Job.result_json.isnot(None),
                Job.source_url.isnot(None),
                Job.status == "complete",
            )
        )
        jobs = result.scalars().all()
        print(f"Found {len(jobs)} completed jobs to scan.")

        populated = 0
        for job in jobs:
            try:
                data = json.loads(job.result_json)
                matches_raw = data.get("osint", {}).get("matches", [])
                if not matches_raw:
                    continue

                source_url = job.source_url.strip()
                url_hash = _cache_key(source_url)

                # Check if already cached
                existing = await sess.get(OsintCache, url_hash)
                if existing:
                    continue

                entry = OsintCache(
                    url_hash=url_hash,
                    source_url=source_url[:1000],
                    result_json=json.dumps(matches_raw),
                )
                sess.add(entry)
                populated += 1
                print(f"  Cached {len(matches_raw)} OSINT matches for: {source_url[:70]}")

            except Exception as exc:
                print(f"  Skipping job {job.id}: {exc}")

        await sess.commit()
        print(f"\nDone. Populated {populated} new cache entries.")


if __name__ == "__main__":
    asyncio.run(backfill())
