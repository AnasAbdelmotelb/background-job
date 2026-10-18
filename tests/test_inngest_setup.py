from fastapi.testclient import TestClient

from app.jobs import functions, inngest_client
from app.main import app

client = TestClient(app)


def test_inngest_endpoint_is_served_in_dev_mode():
    response = client.get("/api/inngest")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "dev"
    assert body["function_count"] == len(functions) == 1


def test_client_and_function_ids_match_the_brief():
    assert inngest_client.app_id == "report-api"
    assert [fn.local_id for fn in functions] == ["say-hello"]
    assert [fn.id for fn in functions] == ["report-api-say-hello"]  # Inngest prefixes the app id
