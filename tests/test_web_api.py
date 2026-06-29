import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from retnovation.model import FakeModel, IntakeClassification, ResponseClassification
from retnovation.types import EntryClass, EntryClassification, FrameState, TrapState
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


def test_blank_open_is_nudged_not_bricked(tmp_path, make_fake):
    """D1: a blank/whitespace opening must not reach the model (the live Anthropic 400
    'user messages must have non-empty content') nor brick the session. FakeModel tolerates
    empty input (it never calls the API), so this asserts the GUARD behavior, not the live
    crash: blank input is nudged and the session stays at the opening stage."""
    app = create_app(db_path=str(tmp_path / "w.db"), model_factory=make_fake)
    client = TestClient(app)
    assert client.post("/api/session").json()["kind"] == "menu"
    r = client.post(
        "/api/session/s/choose", json={"ledger_ref": "veldra:embedded_anchor_lock_in"}
    ).json()
    assert r["kind"] == "problem"

    # blank openings are nudged, never forwarded to the engine
    assert client.post("/api/session/s/open", json={"text": ""}).json()["kind"] == "nudge"
    assert client.post("/api/session/s/open", json={"text": "   "}).json()["kind"] == "nudge"

    # the session is still at the opening stage: a real opening now proceeds
    r = client.post(
        "/api/session/s/open", json={"text": "reasoning that already holds the move"}
    ).json()
    assert r["kind"] in ("push", "done")


def test_blank_reply_is_nudged_not_bricked(tmp_path, make_fake):
    """D1: a blank reply mid-loop must not reach the model nor brick the session."""
    app = create_app(db_path=str(tmp_path / "w.db"), model_factory=make_fake)
    client = TestClient(app)
    client.post("/api/session")
    client.post("/api/session/s/choose", json={"ledger_ref": "veldra:embedded_anchor_lock_in"})
    r = client.post(
        "/api/session/s/open", json={"text": "reasoning that already holds the move"}
    ).json()
    assert r["kind"] == "push"

    # a blank reply is nudged; the session is not advanced
    assert client.post("/api/session/s/reply", json={"text": ""}).json()["kind"] == "nudge"

    # a real reply now proceeds
    r = client.post("/api/session/s/reply", json={"text": "mechanism"}).json()
    assert r["kind"] in ("push", "done")


class _DoormanModel(FakeModel):
    """'hi'/'hey'/'hello' -> greeting (door turn); anything else -> substantive (enter engine)."""

    def classify_entry(self, prompt, opening, recent):
        if opening.strip().lower() in {"hi", "hey", "hello"}:
            return EntryClassification(
                entry_class=EntryClass.greeting,
                reply="Welcome — take a position on the problem to begin.",
            )
        return EntryClassification(entry_class=EntryClass.substantive, reply="")


def _doorman_factory():
    intake = IntakeClassification(
        frame_states={
            "embed_credentials_as_a_list": FrameState.present_reasoned,
            "choose_the_failure_default_deliberately": FrameState.absent,
        },
        trap_states={
            "deferred_the_one_time_choice": TrapState.not_tripped,
            "assumed_the_happy_path": TrapState.not_tripped,
        },
    )
    closed = [
        ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
        for _ in range(4)
    ]
    return _DoormanModel(intake, {"choose_the_failure_default_deliberately": closed})


def test_low_signal_opening_gets_a_door_turn_then_real_opening_proceeds(tmp_path):
    app = create_app(db_path=str(tmp_path / "d.db"), model_factory=_doorman_factory)
    client = TestClient(app)
    client.post("/api/session")
    client.post("/api/session/s/choose", json={"ledger_ref": "veldra:embedded_anchor_lock_in"})

    # 'hi' is intercepted by the Doorman — a conversational turn, NOT a probe
    r = client.post("/api/session/s/open", json={"text": "hi"}).json()
    assert r["kind"] == "door"
    assert "embed_credentials_as_a_list" not in r["text"]  # L-13: no frame leak in the door turn

    # a real opening now proceeds into the engine
    r = client.post(
        "/api/session/s/open", json={"text": "reasoning that already holds the move"}
    ).json()
    assert r["kind"] in ("push", "done")
