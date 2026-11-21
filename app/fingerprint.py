import hashlib


def make_fingerprint(message: str, source: str | None = None) -> str:
    normalized = ' '.join(message.lower().split())
    key = f'{source or ""}|{normalized}'
    return hashlib.sha256(key.encode('utf-8')).hexdigest()