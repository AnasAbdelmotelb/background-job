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


@inngest_client.create_function(
    fn_id="say-hello",
    trigger=inngest.TriggerEvent(event="test/hello"),
)
async def say_hello(ctx: inngest.Context) -> str:
    await ctx.step.sleep("wait-a-moment", timedelta(seconds=5))
    return "Hello from the background!"


def build_report(report_id: str, topic: str) -> dict:
    """The work itself: build the result and save it with status done."""
    result = {
        "title": f"Report: {topic}",
        "summary": f"A short report about {topic}, made by a background job.",
        "finished_at": store.now(),
    }
    report = store.REPORTS.setdefault(report_id, {"id": report_id, "topic": topic, "created_at": None})
    report.update(status="done", result=result)
    return result


@inngest_client.create_function(
    fn_id="make-report",
    trigger=inngest.TriggerEvent(event=REPORT_REQUESTED),
)
async def make_report(ctx: inngest.Context) -> dict:
    report_id, topic = ctx.event.data["id"], ctx.event.data["topic"]
    await ctx.step.sleep("do-the-slow-work", SLOW_WORK)
    return await ctx.step.run("build-report", lambda: build_report(report_id, topic))


functions = [say_hello, make_report]
