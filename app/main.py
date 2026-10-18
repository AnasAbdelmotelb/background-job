from fastapi import FastAPI

app = FastAPI(title="Report API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
