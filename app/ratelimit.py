import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

LIMITS = [(60, 5), (86400, 40)]  # (window in seconds, max requests)
_hits = defaultdict(deque)       # ip -> timestamps of recent requests


def rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else 'unknown'
    now = time.time()
    hits = _hits[ip]
    while hits and now - hits[0] > 86400:
        hits.popleft()
    for window, maximum in LIMITS:
        recent = sum(1 for t in hits if now - t < window)
        if recent >= maximum:
            raise HTTPException(status_code=429, detail='Too many requests. Please slow down.')
    hits.append(now)