import logging
import os
from datetime import timedelta

import inngest

from app import store

# Local Dev Server mode by default, so the API starts with one command and no keys.
# Production (Inngest Cloud) would set INNGEST_PRODUCTION=1 plus INNGEST_SIGNING_KEY / INNGEST_EVENT_KEY.
inngest_client = inngest.Inngest(
    app_id="report-api",
    is_production=os.environ.get("INNGEST_PRODUCTION") == "1",
)

REPORT_REQUESTED = "report/requested"
SLOW_WORK = timedelta(seconds=8)  # stand-in for real slow work: an AI call, a big export
RETRIES = 2  # 1 attempt + 2 retries = 3 attempts, then the run fails

log = logging.getLogger("report-api")
if not log.handlers:  # print this app's INFO lines (heartbeat summaries, alerts) in the API terminal
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)
    log.propagate = False


@inngest_client.create_function(
    fn_id="say-hello",
    trigger=inngest.TriggerEvent(event="test/hello"),
)
async def say_hello(ctx: inngest.Context) -> str:
    await ctx.step.sleep("wait-a-moment", timedelta(seconds=5))
    return "Hello from the background!"


def build_report(report_id: str, topic: str) -> dict:
    """The work itself: build the result and save it with status done."""
    if topic == "fail":
        raise RuntimeError("The report oven is broken!")
    result = {
        "title": f"Report: {topic}",
        "summary": f"A short report about {topic}, made by a background job.",
        "finished_at": store.now(),
    }
    report = store.REPORTS.setdefault(report_id, {"id": report_id, "topic": topic, "created_at": None})
    report.update(status="done", result=result)
    return result


async def report_failed(ctx: inngest.Context) -> None:
    """Runs once, after the last retry has failed: record the failure and raise an alert."""
    original = ctx.event.data.get("event", {}).get("data", {})
    error = ctx.event.data.get("error", {}).get("message", "unknown error")
    report_id, topic = original.get("id"), original.get("topic")
    if report_id in store.REPORTS:
        store.REPORTS[report_id].update(status="failed", error=error, failed_at=store.now())
    # The alert: in production this line would page someone or post to a channel.
    log.error("ALERT: report %s (topic %r) failed after %d attempts: %s", report_id, topic, RETRIES + 1, error)


@inngest_client.create_function(
    fn_id="make-report",
    trigger=inngest.TriggerEvent(event=REPORT_REQUESTED),
    retries=RETRIES,
    on_failure=report_failed,
)
async def make_report(ctx: inngest.Context) -> dict:
    report_id, topic = ctx.event.data["id"], ctx.event.data["topic"]
    await ctx.step.sleep("do-the-slow-work", SLOW_WORK)
    return await ctx.step.run("build-report", lambda: build_report(report_id, topic))


HEARTBEAT_SCHEDULE = "* * * * *"  # every minute: for testing only; a real one would run daily, e.g. "0 8 * * *"


@inngest_client.create_function(
    fn_id="heartbeat",
    trigger=inngest.TriggerCron(cron=HEARTBEAT_SCHEDULE),
)
async def heartbeat(ctx: inngest.Context) -> str:
    """No request, no event: the clock starts this. Logs one summary line of the reports."""
    counts = store.count_by_status()
    summary = f"heartbeat: {counts['pending']} pending, {counts['done']} done, {counts['failed']} failed"
    log.info(summary)
    return summary


functions = [say_hello, make_report, heartbeat]
