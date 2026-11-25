import json
import os
import time
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import LeadRecord, SessionLocal
from app.extractor import MODEL, extract_lead
from app.fingerprint import make_fingerprint
from app.prompts import PROMPT_VERSION

# Haiku 5.5 prices in USD per million tokens. Verify on Anthropic's pricing page.
PRICES_PER_M = {
    'claude-haiku-5-5': (0.10, 0.50),    # (input, output) USD per million tokens
    'claude-sonnet-5-5': (2.00, 10.00),
}
INPUT_PRICE_PER_M, OUTPUT_PRICE_PER_M = PRICES_PER_M[MODEL]

DAILY_CAP_USD = float(os.getenv('DAILY_CAP_USD', '0.25'))


class DailyCapReached(Exception):
    """Raised when today's spending has hit the daily cap."""


def spent_today(session) -> float:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    total = session.scalar(
        select(func.sum(LeadRecord.cost_usd)).where(LeadRecord.created_at >= start)
    )
    return total or 0.0
def calc_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * INPUT_PRICE_PER_M + output_tokens * OUTPUT_PRICE_PER_M) / 1_000_000


def to_response(record: LeadRecord, duplicate: bool) -> dict:
    return {
        'id': record.id,
        'duplicate': duplicate,
        'saved': True,
        'status': record.status,
        'result': json.loads(record.result_json),
        'cost_usd': record.cost_usd,
        'latency_ms': record.latency_ms,
    }


def find_by_fingerprint(session, fingerprint: str):
    return session.scalar(select(LeadRecord).where(LeadRecord.fingerprint == fingerprint))


def process_lead(message: str, source: str | None = None) -> dict:
    fingerprint = make_fingerprint(message, source)

    with SessionLocal() as session:
        existing = find_by_fingerprint(session, fingerprint)
        if existing:
            return to_response(existing, duplicate=True)
        if spent_today(session) >= DAILY_CAP_USD:
            raise DailyCapReached()

        start = time.perf_counter()
        out = extract_lead(message)
        latency_ms = int((time.perf_counter() - start) * 1000)

        # Temporary API failures are not saved, so a retry can succeed later
        if out.status == 'needs_human' and (out.error or '').startswith('API error'):
            return {
                'id': None,
                'duplicate': False,
                'saved': False,
                'status': out.status,
                'result': out.result.model_dump(mode='json'),
                'cost_usd': 0.0,
                'latency_ms': latency_ms,
            }

        record = LeadRecord(
            fingerprint=fingerprint,
            raw_input=message,
            source=source,
            status=out.status,
            result_json=out.result.model_dump_json(),
            prompt_version=PROMPT_VERSION,
            model=MODEL,
            attempts=out.attempts,
            input_tokens=out.input_tokens,
            output_tokens=out.output_tokens,
            cost_usd=calc_cost(out.input_tokens, out.output_tokens),
            latency_ms=latency_ms,
            error=out.error,
        )
        session.add(record)
        try:
            session.commit()
        except IntegrityError:
            # Another request saved the same lead a moment ago
            session.rollback()
            existing = find_by_fingerprint(session, fingerprint)
            return to_response(existing, duplicate=True)

        return to_response(record, duplicate=False)