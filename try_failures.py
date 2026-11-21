from types import SimpleNamespace
from unittest.mock import patch

import anthropic
import httpx

from app import extractor


def fake_response(text):
    return SimpleNamespace(
        content=[SimpleNamespace(type='text', text=text)],
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
    )


GOOD = '{"name": null, "email": null, "phone": null, "company": null, "category": "other", "priority": 2, "summary": "ok", "suggested_reply": null, "needs_human": false, "injection_suspected": false}'
BAD = '{"category": "banana", "priority": 9, "summary": "x"}'

print('Case 1: bad answer, then a good one')
with patch.object(extractor, 'call_claude', side_effect=[fake_response(BAD), fake_response(GOOD)]):
    out = extractor.extract_lead('hello')
    print(out.status, out.attempts)

print('Case 2: bad answer twice')
with patch.object(extractor, 'call_claude', side_effect=[fake_response(BAD), fake_response(BAD)]):
    out = extractor.extract_lead('hello')
    print(out.status, out.attempts, out.result.needs_human)

print('Case 3: API unreachable')
request = httpx.Request('POST', 'https://api.anthropic.com/v1/messages')
with patch.object(extractor, 'call_claude', side_effect=anthropic.APIConnectionError(request=request)):
    out = extractor.extract_lead('hello')
    print(out.status, out.attempts, out.error)