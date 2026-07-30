from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

from banhelper.app.paths import AppPaths
from banhelper.domain.models import BanEvent
from banhelper.infrastructure.database import Database
from banhelper.infrastructure.repositories import BanRepository


def event(index: int, received_at: float) -> BanEvent:
    return BanEvent.from_payload(
        {
            "protocol_version": 2, "event_id": f"benchmark-{index:06d}",
            "event_type": "ban", "player": f"Bench_{index}", "moderator": "Benchmark",
            "reason": "5.5", "server_mode": "RW" if index % 2 else "FT",
        }, received_at=received_at,
    )


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))]


def run(count: int = 100) -> dict:
    with tempfile.TemporaryDirectory(prefix="banhelper-benchmark-") as root:
        paths = AppPaths.temporary(root)
        connection = Database(paths.database).connect()
        repo = BanRepository(connection)
        received = time.time()
        batch = tuple(event(index, received) for index in range(count))
        started = time.perf_counter()
        accepted, duplicates, current, queue, latencies = repo.process_events(batch)
        database_ms = (time.perf_counter() - started) * 1000
        duplicate_started = time.perf_counter()
        accepted_again, duplicates_again, _current, _queue, duplicate_latencies = repo.process_events(batch)
        duplicate_ms = (time.perf_counter() - duplicate_started) * 1000
        stored = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        connection.close()
    return {
        "events": count,
        "minimum_ms": round(min(latencies), 3),
        "median_ms": round(statistics.median(latencies), 3),
        "p95_ms": round(percentile(latencies, 0.95), 3),
        "maximum_ms": round(max(latencies), 3),
        "lost": count - accepted,
        "duplicates_created": stored - count,
        "duplicates_rejected": duplicates_again,
        "database_batch_ms": round(database_ms, 3),
        "duplicate_batch_ms": round(duplicate_ms, 3),
        "queue_items": len(queue) + (1 if current else 0),
        "second_delivery_accepted": accepted_again,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(run(args.count), ensure_ascii=False, indent=2))
