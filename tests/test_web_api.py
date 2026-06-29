import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from retnovation.web.app import create_app


def test_health_ok():
    client = TestClient(create_app(db_path=":memory:", model_factory=None))
    assert client.get("/api/health").json() == {"ok": True}
