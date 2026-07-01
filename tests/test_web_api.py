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

    assert r["kind"] == "done" and r.get("terminal") is True
    assert "close" not in r  # the engine's 'done' no longer closes — the user owns the exit
    # the felt landing rides the done payload (before the user chooses to end)
    assert isinstance(r.get("landing"), str) and r["landing"]  # authored, non-empty
    seen.append(r["landing"])  # L-13: the landing must not leak a frame_code either (checked below)
    # the user ends the session -> honest close + the (now SURFACED) frozen terrain
    cl = client.post("/api/session/s/close").json()
    assert cl["kind"] == "close" and isinstance(cl["close"], str)
    assert isinstance(cl["terrain"], list)
    seen.append(cl["close"])
    seen.append(str(cl["terrain"]))

    # L-13: no frame_code substring must appear in any dialogue payload (says + close + terrain)
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


def test_index_html_is_a_chat_shell():
    client = TestClient(create_app(db_path=":memory:", model_factory=None))
    html = client.get("/").text
    assert 'id="thread"' in html and 'id="composer"' in html  # chat thread + sticky composer
    assert "your terrain begins" not in html  # the stacked 4-block framing is gone
    assert "veldra" not in html.lower()  # no leak in the static shell
    assert "/converse" in html and "End session" in html  # user-owned closure surface
    assert "Your read is recorded" not in html  # the engine no longer stamps closure


def test_converse_and_close_endpoints(tmp_path, make_fake):
    app = create_app(db_path=str(tmp_path / "ce.db"), model_factory=make_fake)
    client = TestClient(app)
    _, r = _choose_anchor(client)
    r = client.post(
        "/api/session/s/say", json={"text": "reasoning that already holds the move"}
    ).json()
    while r["kind"] == "say":
        r = client.post("/api/session/s/say", json={"text": "mechanism"}).json()
    assert r["kind"] == "done"

    # blank converse is nudged (D1 guard), never reaches the model
    assert client.post("/api/session/s/converse", json={"text": ""}).json()["kind"] == "nudge"
    cv = client.post("/api/session/s/converse", json={"text": "what if I'm wrong?"}).json()
    assert cv["kind"] == "say" and cv["text"]

    cl = client.post("/api/session/s/close").json()
    assert cl["kind"] == "close" and isinstance(cl["close"], str)
    assert isinstance(cl["terrain"], list)
    for row in cl["terrain"]:
        assert set(row) == {
            "region_id",
            "render",
            "vitality",
            "elevation",
        }  # L-13-safe two-axis wire shape
        assert "embed_credentials_as_a_list" not in str(row)


def test_vendor_three_is_served():
    # Three.js + bloom addons are vendored + served locally (no CDN dependency in the product).
    client = TestClient(create_app(db_path=":memory:", model_factory=None))
    r = client.get("/static/vendor/three.min.js")
    assert r.status_code == 200 and b"THREE" in r.content
    assert client.get("/static/vendor/UnrealBloomPass.js").status_code == 200


def test_index_references_3d_terrain_renderer():
    # The close renders the Kindled Valley 3D terrain: the shell loads the vendored engine + the
    # renderer and calls it (no CDN; DOM-circle terrain removed).
    client = TestClient(create_app(db_path=":memory:", model_factory=None))
    html = client.get("/").text
    assert "/static/vendor/three.min.js" in html
    assert "/static/terrain3d.js" in html
    assert "Terrain3D.render" in html


def test_done_payload_carries_a_landing(tmp_path, make_fake):
    app = create_app(db_path=str(tmp_path / "land.db"), model_factory=make_fake)
    client = TestClient(app)
    _, r = _choose_anchor(client)
    r = client.post(
        "/api/session/s/say", json={"text": "reasoning that already holds the move"}
    ).json()
    while r["kind"] == "say":
        r = client.post("/api/session/s/say", json={"text": "mechanism"}).json()
    assert r["kind"] == "done" and r.get("terminal") is True
    # FakeModel.concierge_land echoes the stop reason: "[land:<reason>]" — non-empty, no frame leak.
    assert isinstance(r["landing"], str) and r["landing"].startswith("[land:")
    assert "embed_credentials_as_a_list" not in r["landing"]


class _PlateauModel(FakeModel):
    """Never closes the target -> the diagnostic CANNOT converge (plateau/budget stop). Records what
    stop_reason the converse author is told, to prove the record's reason is threaded (not a default)."""

    told = None

    def classify_response(self, exp, kind, code, push, response, *, stress=False):
        return ResponseClassification(
            outcome="unchanged", mechanism_supplied=False, hard_wrong=False
        )

    def concierge_converse(self, problem, recent, *, stop_reason="converged", voice=""):
        type(self).told = stop_reason
        return "[converse winddown]"


def test_converse_is_told_the_records_stop_reason(tmp_path):
    """Honesty-by-stop-reason end-to-end (dogfood 2026-07-01): after a NON-converged stop, the
    engine-free converse path must tell the author the ACTUAL stop reason from ch.record — a
    wind-down that assumes 'already committed' lies to a user who never committed."""
    _PlateauModel.told = None
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
    app = create_app(
        db_path=str(tmp_path / "sr.db"), model_factory=lambda: _PlateauModel(intake, {})
    )
    client = TestClient(app)
    _, r = _choose_anchor(client)
    r = client.post("/api/session/s/say", json={"text": "an opening without the move"}).json()
    while r["kind"] == "say":
        r = client.post("/api/session/s/say", json={"text": "still no mechanism"}).json()
    assert r["kind"] == "done"
    stop = (
        r["landing"].removeprefix("[land:").removesuffix("]")
    )  # FakeModel.concierge_land echoes it
    assert stop != "converged"  # the scripted flow cannot converge — this test must discriminate
    cv = client.post(
        "/api/session/s/converse", json={"text": "so where does that leave me?"}
    ).json()
    assert cv["kind"] == "say"
    assert _PlateauModel.told == stop  # the author was told the RECORD's stop reason, not a default


def test_terrain_host_cannot_flex_collapse():
    """Dogfood 2026-07-01: #thread is a fixed-height column flex container; the terrain host has
    overflow:hidden, which zeroes its automatic flex minimum size — so without flex:none the host
    absorbs ALL the shrink and collapses to 0px the moment the dialogue overflows the thread, i.e.
    in EVERY real session (sparse harnesses never catch it). Pin the anti-collapse property."""
    client = TestClient(create_app(db_path=":memory:", model_factory=None))
    html = client.get("/").text
    host_block = html[html.index("terrain3d'") : html.index("terrain3d'") + 500]
    assert "flex:none" in host_block
    assert "height:460px" in host_block
    # grammatical fallback copy for a single region ("1 area has taken shape.")
    assert "' has':' have'" in html


def test_index_renders_landing_before_end_affordance():
    client = TestClient(create_app(db_path=":memory:", model_factory=None))
    html = client.get("/").text
    # the done branch renders the landing as a Vera bubble...
    assert "bubble('vera', r.landing)" in html
    # ...before the End affordance is wired for that turn
    assert html.index("bubble('vera', r.landing)") < html.index("endButton()")
