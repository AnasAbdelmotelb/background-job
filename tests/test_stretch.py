import asyncio

import inngest
from inngest.experimental import mocked

from app import jobs, store
from app.jobs import MAX_REPORTS_AT_ONCE, build_report, make_report

mock_client = mocked.Inngest(app_id="report-api-test", is_production=False)


def test_the_same_event_twice_builds_the_report_once(client, monkeypatch):
    report_id = client.post("/reports", json={"topic": "cats"}).json()["id"]
    event = inngest.Event(name="report/requested", data={"id": report_id, "topic": "cats"})

    builds = []
    original_now = store.now
    monkeypatch.setattr(jobs.store, "now", lambda: builds.append(1) or original_now())

    first = mocked.trigger(make_report, event, mock_client)
    second = mocked.trigger(make_report, event, mock_client)

    assert first.status is second.status is mocked.Status.COMPLETED
    assert second.output == first.output  # same result, not a new one
    assert len(builds) == 1  # the result was built (timestamped) only once
    assert client.get(f"/reports/{report_id}").json()["status"] == "done"


def test_a_done_report_is_returned_without_building(caplog):
    store.REPORTS["r1"] = {
        "id": "r1", "topic": "cats", "status": "done", "built_by_run": "run-1",
        "result": {"title": "Report: cats", "summary": "first build", "finished_at": "t1"},
    }
    with caplog.at_level("INFO", logger="report-api"):
        result = build_report("r1", "cats", "run-2")
    assert result["summary"] == "first build"
    assert store.REPORTS["r1"]["built_by_run"] == "run-1"
    assert "report r1 is already done (built by run run-1); skipping the build" in caplog.text


def test_build_records_which_run_built_it(client):
    report_id = client.post("/reports", json={"topic": "dogs"}).json()["id"]
    build_report(report_id, "dogs", "run-abc")
    assert client.get(f"/reports/{report_id}").json()["built_by_run"] == "run-abc"


def test_make_report_runs_at_most_two_at_once():
    assert MAX_REPORTS_AT_ONCE == 2
    config = make_report.get_config("http://localhost:8000/api/inngest").main
    assert [(c.limit, c.key) for c in config.concurrency] == [(2, None)]


def test_make_report_writes_then_builds(client):
    report_id = client.post("/reports", json={"topic": "owls"}).json()["id"]
    result = mocked.trigger(make_report, inngest.Event(name="report/requested", data={"id": report_id, "topic": "owls"}), mock_client)
    assert result.status is mocked.Status.COMPLETED
    assert result.output["body"] == "Owls: three key points, written by the make-report job."
    assert client.get(f"/reports/{report_id}").json()["result"]["body"] == result.output["body"]


def test_write_report_waits_and_skips_when_done(monkeypatch):
    monkeypatch.setattr(jobs, "WRITE_SECONDS", 0.05)
    waited = []
    real_sleep = asyncio.sleep

    async def spy_sleep(seconds):
        waited.append(seconds)
        await real_sleep(0)

    monkeypatch.setattr(jobs.asyncio, "sleep", spy_sleep)
    assert asyncio.run(jobs.write_report("new", "cats"))["body"].startswith("Cats:")
    assert waited == [0.05]

    store.REPORTS["d"] = {"id": "d", "status": "done", "result": {"body": "old text"}}
    assert asyncio.run(jobs.write_report("d", "cats")) == {"body": "old text"}
    assert waited == [0.05]  # no second wait for a report that is already done
