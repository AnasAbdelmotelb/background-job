import uuid
from datetime import datetime, timezone

# In-memory store: fast and simple, and empty again after every restart (not a bug, a choice).
REPORTS: dict[str, dict] = {}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_report(topic: str) -> dict:
    report = {"id": uuid.uuid4().hex[:12], "topic": topic, "status": "pending", "created_at": now()}
    REPORTS[report["id"]] = report
    return report


def get_report(report_id: str) -> dict | None:
    return REPORTS.get(report_id)
