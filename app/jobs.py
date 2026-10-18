import os
from datetime import timedelta

import inngest

# Local Dev Server mode by default, so the API starts with one command and no keys.
# Production (Inngest Cloud) would set INNGEST_PRODUCTION=1 plus INNGEST_SIGNING_KEY / INNGEST_EVENT_KEY.
inngest_client = inngest.Inngest(
    app_id="report-api",
    is_production=os.environ.get("INNGEST_PRODUCTION") == "1",
)


@inngest_client.create_function(
    fn_id="say-hello",
    trigger=inngest.TriggerEvent(event="test/hello"),
)
async def say_hello(ctx: inngest.Context) -> str:
    await ctx.step.sleep("wait-a-moment", timedelta(seconds=5))
    return "Hello from the background!"


functions = [say_hello]
