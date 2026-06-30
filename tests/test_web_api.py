import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from retnovation.model import FakeModel, IntakeClassification, ResponseClassification
from retnovation.types import EntryClass, EntryClassification, FrameState, TrapState
from retnovation.web.app import create_app

# irreversible_anchor's display title — the menu shows titles, never the veldra: ref, so the tests
# pick by index resolved from the (stable, content-authored) title.
_ANCHOR_TITLE = "Shipping something you can't take back"


def _choose_anchor(client):
    menu = client.post("/api/session").json()
    assert menu["kind"] == "menu"
    idx = menu["problems"].index(_ANCHOR_TITLE)
    return menu, client.post("/api/session/s/choose", json={"index": idx}).json()


def test_health_ok():
    client = TestClient(create_app(db_path=":memory:", model_factory=None))
    assert client.get("/api/health").json() == {"ok": True}


def test_full_session_and_l13_surface(tmp_path, make_fake):
    """The picker never leaks the veldra: ref; no frame_code leaks into any Concierge turn or the
    close; the session ends in a conversational 'done' with a close (terrain deferred for the MVP)."""
    app = create_app(db_path=str(tmp_path / "w.db"), model_factory=make_fake)
    client = TestClient(app)
    seen = []

    menu, r = _choose_anchor(client)
    assert all(
        "veldra:" not in p for p in menu["problems"]
    )  # clean labels, no confidentiality leak
    seen.append(str(menu["problems"]))
    assert r["kind"] == "say"  # scenario + invite
    seen.append(r["text"])

    r = client.post(
        "/api/session/s/say", json={"text": "reasoning that already holds the move"}
    ).json()
    while r["kind"] == "say":  # each probe is a display-only say
        seen.append(r["text"])
        r = client.post("/api/session/s/say", json={"text": "mechanism"}).json()

    assert r["kind"] == "done"
    assert "close" in r and isinstance(r["close"], str)
    assert "terrain" not in r  # deferred for the MVP
    seen.append(r["close"])

    # L-13: no frame_code substring must appear in any dialogue payload (says + close)
    for blob in seen:
        assert "embed_credentials_as_a_list" not in blob
        assert "choose_the_failure_default_deliberately" not in blob


def test_blank_say_is_nudged_not_bricked(tmp_path, make_fake):
    """D1: a blank/whitespace turn must not reach the model (live Anthropic 400 'non-empty content')
    nor brick the session — at the opening AND mid-loop. FakeModel never calls the API, so this
    asserts the GUARD behavior: blank input is nudged and the session does not advance."""
    app = create_app(db_path=str(tmp_path / "w.db"), model_factory=make_fake)
    client = TestClient(app)
    _, r = _choose_anchor(client)
    assert r["kind"] == "say"  # scenario

    # blank openings are nudged, never forwarded to the engine
    assert client.post("/api/session/s/say", json={"text": ""}).json()["kind"] == "nudge"
    assert client.post("/api/session/s/say", json={"text": "   "}).json()["kind"] == "nudge"

    # a real opening now proceeds
    r = client.post(
        "/api/session/s/say", json={"text": "reasoning that already holds the move"}
    ).json()
    assert r["kind"] in ("say", "done")

    # a blank reply mid-loop is also nudged; a real reply proceeds
    if r["kind"] == "say":
        assert client.post("/api/session/s/say", json={"text": ""}).json()["kind"] == "nudge"
        r2 = client.post("/api/session/s/say", json={"text": "mechanism"}).json()
        assert r2["kind"] in ("say", "done")


class _DoormanModel(FakeModel):
    """'hi'/'hey'/'hello' -> greeting (re-invite); anything else -> substantive (enter engine)."""

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


def test_low_signal_opening_gets_a_reinvite_then_real_opening_proceeds(tmp_path):
    app = create_app(db_path=str(tmp_path / "d.db"), model_factory=_doorman_factory)
    client = TestClient(app)
    _, r = _choose_anchor(client)
    assert r["kind"] == "say"  # scenario

    # 'hi' is intercepted as non-substantive — a re-invite turn, NOT a probe into the engine
    r = client.post("/api/session/s/say", json={"text": "hi"}).json()
    assert r["kind"] == "say"
    assert "embed_credentials_as_a_list" not in r["text"]  # L-13: no frame leak in the re-invite

    # a real opening now proceeds into the engine
    r = client.post(
        "/api/session/s/say", json={"text": "reasoning that already holds the move"}
    ).json()
    assert r["kind"] in ("say", "done")
