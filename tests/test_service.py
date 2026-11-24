from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app import service
from app.db import Base, LeadRecord
from app.schemas import LeadResult


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """A throwaway database file, used instead of leads.db."""
    engine = create_engine(f'sqlite:///{tmp_path}/test.db')
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, 'SessionLocal', session_factory)
    return session_factory


@pytest.fixture
def fake_claude(monkeypatch):
    """Replace the real Claude call with a fake one that counts how often it is used."""
    calls = []

    def fake_extract(message):
        calls.append(message)
        result = LeadResult(
            name='Test Person', email='t@example.com', phone=None, company=None,
            category='sales_inquiry', priority=3, summary='A test lead.',
            suggested_reply='Thanks!', needs_human=False, injection_suspected=False,
        )
        return SimpleNamespace(
            result=result, status='ok', attempts=1,
            input_tokens=100, output_tokens=50, error=None,
        )

    monkeypatch.setattr(service, 'extract_lead', fake_extract)
    return calls


def count_leads(session_factory):
    with session_factory() as session:
        return session.scalar(select(func.count()).select_from(LeadRecord))


def test_new_lead_is_saved(test_db, fake_claude):
    result = service.process_lead('Hello, I need a quote', 'web')
    assert result['saved'] is True
    assert result['duplicate'] is False
    assert count_leads(test_db) == 1


def test_same_message_twice_is_duplicate_and_claude_called_once(test_db, fake_claude):
    first = service.process_lead('Hello, I need a quote', 'web')
    second = service.process_lead('hello,   I NEED a quote', 'web')
    assert second['duplicate'] is True
    assert second['id'] == first['id']
    assert len(fake_claude) == 1
    assert count_leads(test_db) == 1


def test_daily_cap_blocks_new_leads(test_db, fake_claude, monkeypatch):
    monkeypatch.setattr(service, 'DAILY_CAP_USD', 0.0)
    with pytest.raises(service.DailyCapReached):
        service.process_lead('Brand new message', 'web')
    assert len(fake_claude) == 0


def test_duplicates_still_work_when_cap_is_reached(test_db, fake_claude, monkeypatch):
    service.process_lead('Hello, I need a quote', 'web')
    monkeypatch.setattr(service, 'DAILY_CAP_USD', 0.0)
    again = service.process_lead('Hello, I need a quote', 'web')
    assert again['duplicate'] is True


def test_api_outage_is_not_saved(test_db, monkeypatch):
    def failing_extract(message):
        result = LeadResult(
            name=None, email=None, phone=None, company=None,
            category='other', priority=1, summary='Could not process.',
            suggested_reply=None, needs_human=True, injection_suspected=False,
        )
        return SimpleNamespace(
            result=result, status='needs_human', attempts=3,
            input_tokens=0, output_tokens=0, error='API error: connection failed',
        )

    monkeypatch.setattr(service, 'extract_lead', failing_extract)
    result = service.process_lead('Hello, I need a quote', 'web')
    assert result['saved'] is False
    assert count_leads(test_db) == 0