import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from retnovation.web.app import create_app


def test_health_ok():
    client = TestClient(create_app(db_path=":memory:", model_factory=None))
    assert client.get("/api/health").json() == {"ok": True}


def test_full_session_and_l13_surface(tmp_path, make_fake):
    """L-13 surface: no frame_code or terrain leaks into menu/problem/push; terrain only in done."""
    app = create_app(db_path=str(tmp_path / "w.db"), model_factory=make_fake)
    client = TestClient(app)
    seen_texts = []

    # Start session — expect menu
    r = client.post("/api/session").json()
    assert r["kind"] == "menu"
    seen_texts.append(str(r["problems"]))

    # Choose by ledger_ref
    r = client.post(
        "/api/session/s/choose",
        json={"ledger_ref": "veldra:embedded_anchor_lock_in"},
    ).json()
    assert r["kind"] == "problem"
    seen_texts.append(r["prompt"])

    # Open: send reasoning
    r = client.post(
        "/api/session/s/open",
        json={"text": "reasoning that already holds the move"},
    ).json()

    # Drive reply loop until done
    while r["kind"] == "push":
        seen_texts.append(r["text"])
        r = client.post("/api/session/s/reply", json={"text": "mechanism"}).json()

    assert r["kind"] == "done"
    assert "terrain" in r and isinstance(r["terrain"], list)

    # L-13: no frame_code substring must appear in any dialogue payload
    for blob in seen_texts:
        assert "embed_credentials_as_a_list" not in blob
        assert "choose_the_failure_default_deliberately" not in blob

    # terrain must be non-empty so the loop below cannot pass vacuously
    assert r["terrain"]

    # terrain entries are learner_view (no frame_codes key)
    for region in r["terrain"]:
        assert "frame_codes" not in region
