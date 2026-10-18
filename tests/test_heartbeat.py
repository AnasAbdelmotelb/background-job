import logging

import inngest
from inngest.experimental import mocked

from app import store
from app.jobs import HEARTBEAT_SCHEDULE, heartbeat

mock_client = mocked.Inngest(app_id="report-api-test", is_production=False)


def test_heartbeat_is_a_cron_function_every_minute():
    assert HEARTBEAT_SCHEDULE == "* * * * *"
    config = heartbeat.get_config("http://localhost:8000/api/inngest").main
    assert [t.cron for t in config.triggers] == ["* * * * *"]


def test_counts_by_status():
    store.REPORTS.update(
        {
            "a": {"status": "pending"},
            "b": {"status": "done"},
            "c": {"status": "done"},
            "d": {"status": "failed"},
        }
    )
    assert store.count_by_status() == {"pending": 1, "done": 2, "failed": 1}


def test_heartbeat_logs_and_returns_one_summary_line(caplog):
    store.REPORTS.update({"a": {"status": "pending"}, "b": {"status": "done"}, "c": {"status": "failed"}})
    with caplog.at_level(logging.INFO, logger="report-api"):
        result = mocked.trigger(heartbeat, inngest.Event(name="inngest/scheduled.timer"), mock_client)
    assert result.status is mocked.Status.COMPLETED
    assert result.output == "heartbeat: 1 pending, 1 done, 1 failed"
    assert [r.getMessage() for r in caplog.records] == ["heartbeat: 1 pending, 1 done, 1 failed"]


def test_heartbeat_with_no_reports():
    result = mocked.trigger(heartbeat, inngest.Event(name="inngest/scheduled.timer"), mock_client)
    assert result.output == "heartbeat: 0 pending, 0 done, 0 failed"
