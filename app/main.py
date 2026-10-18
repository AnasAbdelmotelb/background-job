import inngest
import inngest.fast_api
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app import store
from app.jobs import REPORT_REQUESTED, functions, inngest_client

app = FastAPI(title="Report API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/reports", status_code=202)
async def request_report(request: Request) -> JSONResponse:
    """The fast door: save the order, hand the work to a background job, answer 202 at once."""
    body = await request.json()
    report = store.create_report(body["topic"])
    await inngest_client.send(inngest.Event(name=REPORT_REQUESTED, data={"id": report["id"], "topic": report["topic"]}))
    return JSONResponse({"id": report["id"], "status": report["status"]}, status_code=202)


@app.get("/reports/{report_id}")
def read_report(report_id: str) -> dict:
    """The status endpoint: pending first, done with the result later."""
    report = store.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


# The Inngest Dev Server discovers and calls the functions through this path.
inngest.fast_api.serve(app, inngest_client, functions, serve_path="/api/inngest")
