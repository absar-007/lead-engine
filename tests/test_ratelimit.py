from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import ratelimit


@pytest.fixture(autouse=True)
def clean_hits():
    ratelimit._hits.clear()
    yield
    ratelimit._hits.clear()


def fake_request(ip):
    return SimpleNamespace(client=SimpleNamespace(host=ip))


def test_first_five_requests_pass():
    for _ in range(5):
        ratelimit.rate_limit(fake_request('1.1.1.1'))


def test_sixth_request_is_blocked():
    for _ in range(5):
        ratelimit.rate_limit(fake_request('1.1.1.1'))
    with pytest.raises(HTTPException) as err:
        ratelimit.rate_limit(fake_request('1.1.1.1'))
    assert err.value.status_code == 429


def test_other_visitors_are_not_affected():
    for _ in range(5):
        ratelimit.rate_limit(fake_request('1.1.1.1'))
    ratelimit.rate_limit(fake_request('2.2.2.2'))  # must not raise