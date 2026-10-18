import inngest.fast_api
from fastapi import FastAPI

from app.jobs import functions, inngest_client

app = FastAPI(title="Report API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# The Inngest Dev Server discovers and calls the functions through this path.
inngest.fast_api.serve(app, inngest_client, functions, serve_path="/api/inngest")
