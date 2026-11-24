from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


def test_rejects_missing_key(monkeypatch):
    monkeypatch.setattr(main, 'ADMIN_KEY', 'secret123')
    assert client.post('/admin/sync-pending').status_code == 403


def test_rejects_wrong_key(monkeypatch):
    monkeypatch.setattr(main, 'ADMIN_KEY', 'secret123')
    response = client.post('/admin/sync-pending', headers={'x-admin-key': 'nope'})
    assert response.status_code == 403


def test_locked_when_no_key_is_configured(monkeypatch):
    monkeypatch.setattr(main, 'ADMIN_KEY', None)
    response = client.post('/admin/sync-pending', headers={'x-admin-key': 'anything'})
    assert response.status_code == 403


def test_accepts_correct_key(monkeypatch):
    monkeypatch.setattr(main, 'ADMIN_KEY', 'secret123')
    monkeypatch.setattr(main, 'sync_all_pending', lambda: {'attempted': 0, 'still_pending': 0})
    response = client.post('/admin/sync-pending', headers={'x-admin-key': 'secret123'})
    assert response.status_code == 200