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
    health = client.get("/api/health").json()
    assert health["ok"] is True
    assert health.get("build")  # the running build is visible in one glance (durable sittings §2f)


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
    # anchor on the cssText ASSIGNMENT (not the surrounding block): the explanatory comment above it
    # also says "flex:none", so a wider slice would stay green even if the property were removed.
    css_start = html.index("host.style.cssText='")
    css_block = html[css_start : html.index("thread.appendChild(host)", css_start)]
    assert "flex:none" in css_block
    assert "height:460px" in css_block
    # grammatical fallback copy for a single region ("1 area has taken shape.")
    assert "' has':' have'" in html


def test_index_renders_landing_before_end_affordance():
    client = TestClient(create_app(db_path=":memory:", model_factory=None))
    html = client.get("/").text
    # the done branch renders the landing as a Vera bubble...
    assert "bubble('vera', r.landing)" in html
    # ...then reveals the PERSISTENT End control — it lives in the sticky composer row, so it can
    # never be lost in scrollback while the user keeps conversing (dogfood 2026-07-01: the one-shot
    # thread-anchored button drifted six turns up and the user had to hunt for it).
    assert html.index("bubble('vera', r.landing)") < html.index("showEnd(true)")
    assert 'id="end"' in html  # the End control is part of the composer, not the scrolling thread
    assert "endButton" not in html  # the one-shot thread-anchored button is gone


def test_done_payload_carries_next_title(tmp_path, make_fake):
    app = create_app(db_path=str(tmp_path / "nt.db"), model_factory=make_fake)
    client = TestClient(app)
    _, r = _choose_anchor(client)
    r = client.post(
        "/api/session/s/say", json={"text": "reasoning that already holds the move"}
    ).json()
    while r["kind"] == "say":
        r = client.post("/api/session/s/say", json={"text": "mechanism"}).json()
    assert r["kind"] == "done"
    # a next door is offered, as a clean TITLE (never the ref), and it is NOT the just-converged
    # problem (MF-1: sitting dedupe — irreversible_anchor was banked this sitting)
    assert isinstance(r["next_title"], str) and r["next_title"]
    assert "veldra" not in r["next_title"].lower()
    assert r["next_title"] != _ANCHOR_TITLE


def _drive_to_done(client):
    r = client.post(
        "/api/session/s/say", json={"text": "reasoning that already holds the move"}
    ).json()
    while r["kind"] == "say":
        r = client.post("/api/session/s/say", json={"text": "mechanism"}).json()
    assert r["kind"] == "done"
    return r


def test_chained_sitting_continue_end_to_end(tmp_path, make_fake):
    """One tap after the landing starts a NEW clean session in the same thread (opening say);
    End mid-segment closes honestly (MF-5) with the village terrain."""
    app = create_app(db_path=str(tmp_path / "chain.db"), model_factory=make_fake)
    client = TestClient(app)
    _, r = _choose_anchor(client)
    d1 = _drive_to_done(client)
    assert d1["next_title"] and d1["next_title"] != _ANCHOR_TITLE
    r2 = client.post("/api/session/s/continue", json={}).json()
    assert (
        r2["kind"] == "say" and r2["text"]
    )  # the NEW session's opening — the thread just continues
    cl = client.post("/api/session/s/close").json()  # End mid-segment (segment 2 not converged)
    assert cl["kind"] == "close" and isinstance(cl["terrain"], list)
    assert "stepped away mid-problem" in cl["close"]  # MF-5: honest static, not a mirrored close


def test_continue_menu_path_and_double_click_idempotency(tmp_path, make_fake):
    app = create_app(db_path=str(tmp_path / "dc.db"), model_factory=make_fake)
    client = TestClient(app)
    _, r = _choose_anchor(client)
    _drive_to_done(client)
    m = client.post("/api/session/s/continue", json={"menu": True}).json()
    assert m["kind"] == "menu" and m["problems"]  # inline picker path
    # the menu path consumed the continuation; a second continue is refused (MF-6 idempotency)
    again = client.post("/api/session/s/continue", json={}).json()
    assert again["kind"] == "error"


def test_index_has_continue_affordance_following_the_thread():
    client = TestClient(create_app(db_path=":memory:", model_factory=None))
    html = client.get("/").text
    assert "renderContinue(" in html and "other doors" in html
    assert "/continue" in html
    # MF-6: proceed lives IN-THREAD; the sticky composer row never gains a Continue button
    composer = html[html.index('<form id="composer"') : html.index("</form>")]
    assert "Continue" not in composer
    # the affordance re-renders after converse replies (never stranded in scrollback)
    assert "renderContinue(nextTitle)" in html


def test_chained_sitting_builds_two_houses(tmp_path):
    """The hard behavioral gate: a fresh db, two chained convergences, one End — the village terrain
    reflects BOTH sessions' state (more/renderable-r0 vs the single-session baseline). Uses a
    problem-agnostic always-closing fake so ANY auto-picked second problem converges."""
    from retnovation.model import FakeModel

    def factory():
        m = FakeModel(
            IntakeClassification(frame_states={}, trap_states={}),
            {},
        )
        m.classify_intake = lambda exp, opening: IntakeClassification(
            frame_states={f.frame_code: FrameState.absent for f in exp.rubric.frames},
            trap_states={t.trap_code: TrapState.not_tripped for t in exp.rubric.traps},
        )
        m.classify_response = lambda exp, kind, code, push, response, stress=False: (
            ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
        )
        return m

    # BASELINE: one session, one close, separate db
    app1 = create_app(db_path=str(tmp_path / "one.db"), model_factory=factory)
    c1 = TestClient(app1)
    _choose_anchor(c1)
    _drive_to_done(c1)
    t1 = c1.post("/api/session/s/close").json()["terrain"]

    # THE SITTING: two chained convergences, one close
    app = create_app(db_path=str(tmp_path / "houses.db"), model_factory=factory)
    client = TestClient(app)
    _, r = _choose_anchor(client)
    d1 = _drive_to_done(client)
    assert d1["next_title"]
    r2 = client.post("/api/session/s/continue", json={}).json()
    assert r2["kind"] == "say"
    d2 = _drive_to_done(client)  # second convergence in the SAME sitting
    assert d2["landing"]
    cl = client.post("/api/session/s/close").json()
    assert cl["kind"] == "close"
    t2 = cl["terrain"]
    assert isinstance(t2, list) and t2

    # M3 (the hard gate): two banked problems produce STRICTLY more world than one — either a region
    # ignited (a shared frame now spans 2 problems and clears the >=2-frames/>=2-problems guard) or
    # the world simply has more regions than the single-session baseline.
    def rendered(t):
        return sum(1 for row in t if row["render"] == "rendered")

    assert rendered(t2) > rendered(t1) or len(t2) > len(t1), (t1, t2)


def test_choose_marker_and_seam_ride_the_endpoints(tmp_path, make_fake):
    """Durable sittings §2b at the HTTP layer: choosing a door persists what the user did;
    the continue response carries the seam text the shell renders."""
    from retnovation.web.sitting_store import SittingStore

    db = str(tmp_path / "wt-api.db")
    app = create_app(db_path=db, model_factory=make_fake)
    client = TestClient(app)
    _choose_anchor(client)
    _drive_to_done(client)
    r2 = client.post("/api/session/s/continue", json={}).json()
    assert r2["kind"] == "say"
    assert r2.get("seam") == "Same sitting — next door."

    store = SittingStore(db)
    sit = store.live_sitting()
    turns = store.turns(sit["id"])
    kinds = [t["kind"] for t in turns]
    assert kinds[0] == "muted" and turns[0]["payload"]["text"] == "door chosen"
    assert kinds[1] == "you" and turns[1]["payload"]["text"] == _ANCHOR_TITLE
    assert "seam" in kinds
    import json as _json

    assert "veldra:" not in _json.dumps([t["payload"] for t in turns])


def test_shell_handles_resume_seam_and_empty_pick_doors():
    """Served-shell assertions (durable sittings §2c/§2d/§2e): resume rendering via a fragment,
    seam rendering on says, and the doors link surviving an empty pick."""
    client = TestClient(create_app(db_path=":memory:", model_factory=None))
    html = client.get("/").text
    assert "renderResume(" in html and "kind==='resume'" in html
    assert "DocumentFragment" in html or "createDocumentFragment" in html
    assert "r.seam" in html  # the say-borne seam renders as a muted line
    # the doors link renders even when next_title is empty (a fully-worked window must not hide
    # both continue affordances)
    assert "other doors" in html
    assert "menuNonce" in html  # choose echoes the menu nonce


def test_shell_is_served_no_store_and_build_stamp_rides_health_and_session(tmp_path, make_fake):
    """§2f: the stale-shell class dies structurally; the running build is visible in one glance."""
    app = create_app(db_path=str(tmp_path / "b.db"), model_factory=make_fake)
    client = TestClient(app)
    resp = client.get("/")
    assert resp.headers.get("cache-control") == "no-store"
    health = client.get("/api/health").json()
    assert health["ok"] is True and health.get("build")
    cold = client.post("/api/session").json()
    assert cold["kind"] == "menu" and cold.get("build")
    assert cold.get("nonce")  # the stale-menu guard rides the cold menu too


def test_resume_over_http_carries_the_room(tmp_path, make_fake):
    """The founder's incident, exercised end-to-end over HTTP: converge, 'restart' (new app over
    the same db), and the front door returns the WHOLE room — transcript, End, Continue, mode."""
    db = str(tmp_path / "resume-api.db")
    app1 = create_app(db_path=db, model_factory=make_fake)
    c1 = TestClient(app1)
    _choose_anchor(c1)
    d1 = _drive_to_done(c1)
    assert d1["landing"]

    app2 = create_app(db_path=db, model_factory=make_fake)  # the restart
    c2 = TestClient(app2)
    r = c2.post("/api/session").json()
    assert r["kind"] == "resume"
    assert r["mode"] == "converse" and r["end_visible"] is True
    assert any(t["kind"] == "landing" and t["text"] == d1["landing"] for t in r["turns"])
    assert r["next_title"] and "veldra:" not in str(r)
    # converse works over the rebuilt record; End still closes with the village
    cv = c2.post("/api/session/s/converse", json={"text": "one more thought"}).json()
    assert cv["kind"] == "say" and cv["text"]
    cl = c2.post("/api/session/s/close").json()
    assert cl["kind"] == "close" and isinstance(cl["terrain"], list)


def test_menu_suffix_marks_just_worked_doors(tmp_path, make_fake):
    """§2e: a converged-within-24h door is a visible, informed choice on the next cold menu —
    ' · just worked', title-layer only, refs still server-side."""
    db = str(tmp_path / "suffix.db")
    app1 = create_app(db_path=db, model_factory=make_fake)
    c1 = TestClient(app1)
    _choose_anchor(c1)
    _drive_to_done(c1)
    c1.post("/api/session/s/close")  # the sitting ends; the converged log survives

    app2 = create_app(db_path=db, model_factory=make_fake)
    menu = TestClient(app2).post("/api/session").json()
    assert menu["kind"] == "menu"
    marked = [p for p in menu["problems"] if p.endswith(" · just worked")]
    assert _ANCHOR_TITLE + " · just worked" in menu["problems"]
    assert len(marked) < len(menu["problems"])  # unworked doors stay clean
    assert all("veldra:" not in p for p in menu["problems"])
