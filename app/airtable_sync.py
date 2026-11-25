import json
import logging
import os

import httpx
from dotenv import load_dotenv
from sqlalchemy import select

from app.db import LeadRecord, SessionLocal

load_dotenv()
logger = logging.getLogger(__name__)

TOKEN = os.getenv('AIRTABLE_TOKEN')
BASE_ID = os.getenv('AIRTABLE_BASE_ID')
TABLE = os.getenv('AIRTABLE_TABLE', 'Leads')
URL = f'https://api.airtable.com/v0/{BASE_ID}/{TABLE}'


def upsert_lead(fingerprint: str, fields: dict) -> None:
    """Create the row, or update it if this fingerprint already exists."""
    body = {
        'performUpsert': {'fieldsToMergeOn': ['fingerprint']},
        'records': [{'fields': {'fingerprint': fingerprint, **fields}}],
    }
    response = httpx.patch(
        URL,
        json=body,
        headers={'Authorization': f'Bearer {TOKEN}'},
        timeout=10,
    )
    response.raise_for_status()


def sync_lead(lead_id: int) -> None:
    """Send one saved lead to Airtable. Never raises: a failure leaves it pending."""
    with SessionLocal() as session:
        record = session.get(LeadRecord, lead_id)
        if record is None:
            return
        data = json.loads(record.result_json)
        fields = {
            'name': data.get('name'),
            'email': data.get('email'),
            'phone': data.get('phone'),
            'company': data.get('company'),
            'category': data.get('category'),
            'priority': data.get('priority'),
            'summary': data.get('summary'),
            'suggested_reply': data.get('suggested_reply'),
            'needs_human': data.get('needs_human'),
            'injection_suspected': data.get('injection_suspected'),
            'source': record.source,
        }
        fields = {k: v for k, v in fields.items() if v is not None}
        try:
            upsert_lead(record.fingerprint, fields)
            record.sync_status = 'synced'
        except httpx.HTTPError as e:
            logger.warning('Airtable sync failed for lead %s: %s', lead_id, e)
            record.sync_status = 'pending'
        session.commit()
def sync_all_pending() -> dict:
    """Retry every lead that has not reached Airtable yet."""
    with SessionLocal() as session:
        ids = list(session.scalars(
            select(LeadRecord.id).where(LeadRecord.sync_status == 'pending')
        ))
    for lead_id in ids:
        sync_lead(lead_id)
    with SessionLocal() as session:
        still_pending = len(session.scalars(
            select(LeadRecord.id).where(LeadRecord.sync_status == 'pending')
        ).all())
    return {'attempted': len(ids), 'still_pending': still_pending}