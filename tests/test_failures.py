import asyncio
import logging
from types import SimpleNamespace

import inngest
import pytest
from inngest.experimental import mocked

from app import store
from app.jobs import RETRIES, make_report, report_failed

mock_client = mocked.Inngest(app_id="report-api-test", is_production=False)


def test_make_report_is_configured_for_two_retries_and_an_alert():
    assert RETRIES == 2
    assert make_report._opts.retries == 2
    assert make_report.on_failure_fn_id == "report-api-make-report-failure"


def test_fail_topic_makes_the_job_fail(client):
    report_id = client.post("/reports", json={"topic": "fail"}).json()["id"]
    result = mocked.trigger(make_report, inngest.Event(name="report/requested", data={"id": report_id, "topic": "fail"}), mock_client)
    assert result.status is mocked.Status.FAILED
    assert "The report oven is broken!" in str(result.error)
    assert store.REPORTS[report_id]["status"] == "pending"  # still pending until the failure handler runs


def test_failure_handler_marks_the_report_failed_and_alerts(client, caplog):
    report_id = client.post("/reports", json={"topic": "fail"}).json()["id"]
    failed_event = SimpleNamespace(
        data={
            "event": {"name": "report/requested", "data": {"id": report_id, "topic": "fail"}},
            "error": {"name": "RuntimeError", "message": "The report oven is broken!"},
        }
    )
    with caplog.at_level(logging.ERROR, logger="report-api"):
        asyncio.run(report_failed(SimpleNamespace(event=failed_event)))

    report = client.get(f"/reports/{report_id}").json()
    assert report["status"] == "failed"
    assert report["error"] == "The report oven is broken!"
    assert f"ALERT: report {report_id} (topic 'fail') failed after 3 attempts: The report oven is broken!" in caplog.text


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({}, "topic is required and must be a non-empty string"),
        ({"topic": ""}, "topic is required and must be a non-empty string"),
        ({"topic": "   "}, "topic is required and must be a non-empty string"),
        ({"topic": 42}, "topic is required and must be a non-empty string"),
        ({"subject": "cats"}, "topic is required and must be a non-empty string"),
        (["cats"], "topic is required and must be a non-empty string"),
        ({"topic": "x" * 201}, "topic must be at most 200 characters"),
    ],
)
def test_bad_input_is_rejected_with_400_and_no_job(client, sent_events, body, detail):
    response = client.post("/reports", json=body)
    assert response.status_code == 400
    assert response.json() == {"detail": detail}
    assert sent_events == [] and store.REPORTS == {}


def test_body_that_is_not_json_is_400(client, sent_events):
    response = client.post("/reports", content=b"topic=cats", headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert sent_events == [] and store.REPORTS == {}


def test_topic_is_trimmed(client, sent_events):
    client.post("/reports", json={"topic": "  cats  "})
    assert sent_events[0].data["topic"] == "cats"
