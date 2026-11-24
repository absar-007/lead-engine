import json
import statistics
from collections import Counter

from sqlalchemy import select

from app.db import LeadRecord, SessionLocal


def compute_metrics() -> dict:
    with SessionLocal() as session:
        rows = session.execute(
            select(
                LeadRecord.result_json,
                LeadRecord.cost_usd,
                LeadRecord.latency_ms,
                LeadRecord.sync_status,
                LeadRecord.status,
            )
        ).all()

    total = len(rows)
    if total == 0:
        return {'total_leads': 0}

    results = [json.loads(r.result_json) for r in rows]
    latencies = sorted(r.latency_ms for r in rows)
    costs = [r.cost_usd for r in rows]

    return {
        'total_leads': total,
        'by_category': dict(Counter(res['category'] for res in results)),
        'needs_human': sum(1 for res in results if res['needs_human']),
        'injection_suspected': sum(1 for res in results if res['injection_suspected']),
        'fallbacks': sum(1 for r in rows if r.status == 'needs_human'),
        'latency_p50_ms': int(statistics.median(latencies)),
        'latency_p95_ms': latencies[int(0.95 * (total - 1))],
        'avg_cost_usd': round(statistics.mean(costs), 6),
        'total_cost_usd': round(sum(costs), 6),
        'airtable_synced': sum(1 for r in rows if r.sync_status == 'synced'),
        'airtable_pending': sum(1 for r in rows if r.sync_status == 'pending'),
    }