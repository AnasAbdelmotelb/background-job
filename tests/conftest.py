import pytest
from fastapi.testclient import TestClient

from app import store
from app.jobs import inngest_client
from app.main import app


@pytest.fixture(autouse=True)
def instant_write(monkeypatch):
    """The write-report step really waits 3 s; tests don't need to."""
    monkeypatch.setattr("app.jobs.WRITE_SECONDS", 0)


@pytest.fixture(autouse=True)
def empty_store():
    store.REPORTS.clear()
    yield
    store.REPORTS.clear()


@pytest.fixture
def sent_events(monkeypatch):
    """Captures events instead of sending them, so API tests need no Dev Server."""
    events = []

    async def fake_send(event, **kwargs):
        events.extend(event if isinstance(event, list) else [event])
        return ["test-event-id"]

    monkeypatch.setattr(inngest_client, "send", fake_send)
    return events


@pytest.fixture
def client(sent_events):
    return TestClient(app)
