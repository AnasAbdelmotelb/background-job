import time

import inngest
from inngest.experimental import mocked

from app import store
from app.jobs import make_report

mock_client = mocked.Inngest(app_id="report-api-test", is_production=False)


def test_post_returns_202_pending_and_sends_the_event(client, sent_events):
    started = time.perf_counter()
    response = client.post("/reports", json={"topic": "cats"})
    elapsed = time.perf_counter() - started

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending" and len(body["id"]) == 12
    assert elapsed < 1.0  # the endpoint does no slow work
    assert [(e.name, e.data) for e in sent_events] == [("report/requested", {"id": body["id"], "topic": "cats"})]
    assert store.REPORTS[body["id"]]["status"] == "pending"


def test_status_endpoint_shows_pending_then_done(client):
    report_id = client.post("/reports", json={"topic": "cats"}).json()["id"]
    pending = client.get(f"/reports/{report_id}").json()
    assert pending["status"] == "pending" and pending["topic"] == "cats" and "result" not in pending

    result = mocked.trigger(make_report, inngest.Event(name="report/requested", data={"id": report_id, "topic": "cats"}), mock_client)
    assert result.status is mocked.Status.COMPLETED

    done = client.get(f"/reports/{report_id}").json()
    assert done["status"] == "done"
    assert done["result"]["title"] == "Report: cats"
    assert done["result"] == result.output


def test_unknown_report_is_404(client):
    response = client.get("/reports/doesnotexist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Report not found"}


def test_make_report_sleeps_then_builds(client):
    # The mocked runner records each step; the sleep is skipped instead of waiting 8 s.
    report_id = client.post("/reports", json={"topic": "dogs"}).json()["id"]
    started = time.perf_counter()
    result = mocked.trigger(make_report, inngest.Event(name="report/requested", data={"id": report_id, "topic": "dogs"}), mock_client)
    assert time.perf_counter() - started < 2
    assert result.status is mocked.Status.COMPLETED
    assert result.output["summary"] == "A short report about dogs, made by a background job."
