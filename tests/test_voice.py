import pytest

from elenchus.model import (
    AnthropicModel,
    FakeModel,
    IntakeClassification,
)
from elenchus.types import (
    ConverseTurn,
    EgressScreen,
    EntryClass,
    EntryClassification,
    Experience,
    Frame,
    Mode,
    Regime,
    Rubric,
    Trap,
)
from elenchus.web import voice


def _fake():
    intake = IntakeClassification(frame_states={}, trap_states={})
    return FakeModel(intake, {})


def _intake():
    return IntakeClassification(frame_states={}, trap_states={})


def _exp():
    rubric = Rubric(
        mode=Mode.genuinely_open,
        binding_constraint=None,
        decision_frame=None,
        frames=[
            Frame(
                frame_code="lead_with_what_you_refuse_to_do",
                frame_detail="State the boundary you will not cross first.",
            )
        ],
        traps=[
            Trap(
                trap_code="scope_creep_to_please", trap_detail="Bend the offer to avoid saying no."
            )
        ],
    )
    return Experience(
        experience_id="e", prompt="p", ledger_ref="r", regime=Regime.open_ended, rubric=rubric
    )


class FakeLeakModel(FakeModel):
    """concierge_turn emits a 'LEAK' string; screen_moves flags any 'LEAK' text as PERFORMING every
    screened move. Drives the egress fallback in both probe and re-invite modes."""

    def concierge_turn(self, problem, push, recent, *, arc=None, voice=""):
        return "LEAK: lead with what you refuse to do"

    def concierge_converse(self, problem, recent, *, stop_reason="converged", voice=""):
        return ConverseTurn(reply="LEAK: lead with what you refuse to do", next_pressure="")

    def screen_moves(self, moves, text):
        hit = list(range(1, len(moves) + 1)) if "LEAK" in text else []
        return EgressScreen(performed=hit, evidence="x")


class _PerMoveModel(FakeModel):
    """screen_moves flags moves per-text (content-addressed) so a test can represent PARTIAL added
    revelation — the engaged turn performs move A, the push performs a DIFFERENT move B — which the
    all-or-nothing LEAK fake cannot. Pins the set-difference heart of the probe gate offline."""

    def __init__(self, intake, flags):
        super().__init__(intake, {})
        self._flags = flags

    def concierge_turn(self, problem, push, recent, *, arc=None, voice=""):
        return "CANDIDATE"

    def screen_moves(self, moves, text):
        return EgressScreen(performed=self._flags.get(text, []), evidence="x")


class FakeDoorModel(FakeModel):
    def __init__(self, intake, entry_class, reply):
        super().__init__(intake, {})
        self._entry = EntryClassification(entry_class=entry_class, reply=reply)

    def classify_entry(self, prompt, opening, recent):
        return self._entry


def test_entry_classification_type():
    ec = EntryClassification(entry_class=EntryClass.greeting, reply="hi there")
    assert ec.entry_class is EntryClass.greeting and ec.reply == "hi there"


def test_fakemodel_entry_is_substantive_passthrough():
    m = _fake()
    ec = m.classify_entry("problem", "any opening", [])
    assert ec.entry_class is EntryClass.substantive and ec.reply == ""


def test_fakemodel_injection_check_is_safe_by_default():
    m = _fake()
    assert m.check_injection_expressed("a move", "some text").expressed is False


def test_fakemodel_concierge_doubles():
    m = _fake()
    assert m.concierge_turn("p", "brief", []) == "brief"  # probe: echoes the brief
    assert m.concierge_turn("p", "", []) == "take a real position"  # reinvite: safe invite
    assert m.concierge_close("p", []) == "[close synthesis]"
    assert m.concierge_open("p") == "[open]"  # opening double
    assert m.concierge_converse("p", []).reply == "[converse winddown]"  # wind-down double
    assert m.concierge_land("p", [], "converged") == "[land:converged]"  # landing double


# --- voice.turn (probe + re-invite) ---------------------------------------------------------------


def test_turn_probe_keeps_engaged_text_when_egress_safe():
    # FakeModel.concierge_turn returns the push; screen [] (safe) -> the engaged turn is kept
    m = FakeModel(_intake(), {})
    assert voice.turn(m, _exp(), "the canonical push", [("student", "hi")]) == "the canonical push"


def test_turn_probe_falls_back_to_push_on_added_revelation():
    # concierge_turn returns a LEAK string; screen flags it but not the push -> fallback to push
    m = FakeLeakModel(_intake(), {})
    assert voice.turn(m, _exp(), "the canonical push", [("student", "x")]) == "the canonical push"


def test_turn_reinvite_keeps_safe_engaged_text():
    m = FakeModel(
        _intake(), {}
    )  # concierge_turn("", ...) -> "take a real position"; screen [] safe
    assert voice.turn(m, _exp(), "", [("student", "huh?")]) == "take a real position"


def test_turn_reinvite_uses_flat_gate_and_safe_contract_on_leak():
    m = FakeLeakModel(_intake(), {})  # push="" -> re-invite; leak -> SAFE_CONTRACT
    assert voice.turn(m, _exp(), "", [("student", "what do you want")]) == voice.SAFE_CONTRACT


def test_turn_empty_concierge_output_falls_back():
    class _Empty(FakeModel):
        def concierge_turn(self, problem, push, recent, *, arc=None, voice=""):
            return ""

    m = _Empty(_intake(), {})
    assert voice.turn(m, _exp(), "push", [("student", "x")]) == "push"  # probe -> push
    assert (
        voice.turn(m, _exp(), "", [("student", "x")]) == voice.SAFE_CONTRACT
    )  # reinvite -> contract


def test_turn_keeps_candidate_when_its_moves_are_a_subset_of_the_push():
    # the turn performs only move {2}, which the push ALSO performs -> no ADDED revelation -> keep
    m = _PerMoveModel(_intake(), {"CANDIDATE": [2], "PUSH": [1, 2]})
    assert voice.turn(m, _exp(), "PUSH", [("student", "x")]) == "CANDIDATE"


def test_turn_falls_back_on_partial_added_revelation():
    # the turn performs move {1}; the push performs a DIFFERENT move {2} -> {1}-{2}={1} added -> push
    m = _PerMoveModel(_intake(), {"CANDIDATE": [1], "PUSH": [2]})
    assert voice.turn(m, _exp(), "PUSH", [("student", "x")]) == "PUSH"


# --- egress flat check (re-invite / close baseline) -----------------------------------------------


def test_egress_safe_reply_flags_a_move_naming_string():
    m = FakeLeakModel(_intake(), {})
    assert voice.egress_safe_reply(m, _exp(), "harmless orientation?") is True
    assert voice.egress_safe_reply(m, _exp(), "LEAK here") is False


def test_egress_also_covers_rubric_traps():
    # a learner-facing reply that PERFORMS a trap move ("never name the move", L-5) must be flagged
    # unsafe — the egress screen covers traps, not only frames. _exp()'s trap is the 2nd move, so
    # flagging ONLY it (not the frame) proves the trap path is screened.
    class _TrapLeak(FakeModel):
        def screen_moves(self, moves, text):
            performed = [
                i for i, m in enumerate(moves, 1) if m == "Bend the offer to avoid saying no."
            ]
            return EgressScreen(performed=performed, evidence="x")

    m = _TrapLeak(_intake(), {})
    assert voice.egress_safe_reply(m, _exp(), "anything") is False


# --- voice.close -----------------------------------------------------------------------------------


def test_close_returns_synthesis_when_safe():
    m = FakeModel(_intake(), {})  # concierge_close -> "[close synthesis]"; screen [] -> safe
    assert voice.close(m, _exp(), [("student", "I'd hold.")]) == "[close synthesis]"


def test_close_falls_back_on_leak():
    class _LeakClose(FakeLeakModel):
        def concierge_close(self, problem, recent, *, voice=""):
            return "LEAK the move"

    m = _LeakClose(_intake(), {})
    assert voice.close(m, _exp(), [("student", "x")]) == voice._STATIC_CLOSE


# --- voice.land (felt arrival, honest by stop_reason, egress-backstopped) -------------------------


def test_land_returns_authored_text_when_safe():
    m = FakeModel(_intake(), {})  # concierge_land -> "[land:converged]"; screen [] safe
    assert voice.land(m, _exp(), [("student", "I'd hold.")], "converged") == "[land:converged]"


def test_land_threads_the_stop_reason_through():
    m = FakeModel(_intake(), {})  # the fake echoes the stop reason it was handed
    assert voice.land(m, _exp(), [("student", "x")], "budget") == "[land:budget]"


def test_land_falls_back_to_static_on_leak():
    class _LeakLand(FakeLeakModel):
        def concierge_land(self, problem, recent, stop_reason, *, steer="", voice=""):
            return "LEAK the move"

    m = _LeakLand(_intake(), {})
    assert voice.land(m, _exp(), [("student", "x")], "converged") == voice._STATIC_LAND


def test_land_falls_back_to_static_on_empty():
    class _EmptyLand(FakeModel):
        def concierge_land(self, problem, recent, stop_reason, *, steer="", voice=""):
            return ""

    m = _EmptyLand(_intake(), {})
    assert voice.land(m, _exp(), [("student", "x")], "converged") == voice._STATIC_LAND


class _PerTextLandModel(FakeModel):
    """Content-addressed screen + scripted landings: pins the student-baseline gate offline.
    screen_moves flags by exact text; concierge_land pops scripted outputs (records steers)."""

    def __init__(self, intake, flags, landings):
        super().__init__(intake, {})
        self._flags = flags
        self._landings = list(landings)
        self.steers = []

    def concierge_land(self, problem, recent, stop_reason, *, steer="", voice=""):
        self.steers.append(steer)
        return self._landings.pop(0)

    def screen_moves(self, moves, text):
        return EgressScreen(performed=self._flags.get(text, []), evidence="x")


def test_land_keeps_a_mirror_of_the_students_own_move():
    # The landing performs move {1} — but the STUDENT's own dialogue already performed {1}:
    # no ADDED revelation (you can't hand someone what they already hold) -> the landing SHIPS.
    m = _PerTextLandModel(
        _intake(),
        {"MIRROR": [1], "I refuse to cross that line.": [1]},
        ["MIRROR"],
    )
    out = voice.land(m, _exp(), [("student", "I refuse to cross that line.")], "converged")
    assert out == "MIRROR"


def test_land_retry_recovers_with_steer():
    # Attempt 1 adds move {2} beyond the student's {1} -> flagged; the RETRY (with the no-mechanism
    # steer) comes back clean -> the retry ships. Exactly one retry, steer only on the second call.
    m = _PerTextLandModel(
        _intake(),
        {"TOO-PLAIN": [1, 2], "CLEAN": [], "I refuse to cross that line.": [1]},
        ["TOO-PLAIN", "CLEAN"],
    )
    out = voice.land(m, _exp(), [("student", "I refuse to cross that line.")], "converged")
    assert out == "CLEAN"
    assert m.steers == ["", voice._RETRY_STEER]  # steer fires ONLY on the retry


def test_land_static_after_retry_still_adds_a_move():
    m = _PerTextLandModel(
        _intake(),
        {"BAD1": [2], "BAD2": [2]},
        ["BAD1", "BAD2"],
    )
    out = voice.land(m, _exp(), [("student", "no moves here")], "converged")
    assert out == voice._STATIC_LAND
    assert m.steers == ["", voice._RETRY_STEER]  # exactly one retry, then the honest static


# --- voice.converse (post-convergence, engine-free) -----------------------------------------------


def test_converse_winds_down_via_concierge_converse_not_reinvite():
    # THE REGRESSION: converse must route to concierge_converse (wind-down), NEVER concierge_turn(push="")
    # (the RE-INVITE path that re-demanded a committed answer — DEVLOG 2026-07-01).
    class _Probe(FakeModel):
        def __init__(self, intake):
            super().__init__(intake, {})
            self.called = None

        def concierge_converse(self, problem, recent, *, stop_reason="converged", voice=""):
            self.called = "converse"
            return ConverseTurn(reply="we're done here — that's a good place to be")

        def concierge_turn(self, problem, push, recent, *, arc=None, voice=""):
            self.called = "turn"
            return "take a real position"  # the OLD re-invite path — must NOT be reached

    m = _Probe(_intake())
    out, _ = voice.converse(m, _exp(), [("student", "I'd hold.")], "makes sense")
    assert m.called == "converse"  # wound down; did not re-invite
    assert out == "we're done here — that's a good place to be"


def test_converse_threads_stop_reason_to_the_author():
    # Honesty-by-stop-reason (dogfood 2026-07-01): on a NON-converged stop the wind-down author must
    # not be told the user "already committed". voice.converse threads the record's stop reason through.
    class _Rec(FakeModel):
        def __init__(self, intake):
            super().__init__(intake, {})
            self.told = None

        def concierge_converse(self, problem, recent, *, stop_reason="converged", voice=""):
            self.told = stop_reason
            return ConverseTurn(reply="[converse winddown]")

    m = _Rec(_intake())
    voice.converse(m, _exp(), [("student", "x")], "so how did that go?", None, "budget")
    assert m.told == "budget"
    m2 = _Rec(_intake())
    voice.converse(m2, _exp(), [("student", "x")], "ok")  # default stays the safe converged premise
    assert m2.told == "converged"


def test_converse_returns_winddown_when_egress_safe():
    m = FakeModel(_intake(), {})  # concierge_converse -> "[converse winddown]"; screen [] safe
    out, _ = voice.converse(m, _exp(), [("student", "I'd hold.")], "but what about the long run?")
    assert out == "[converse winddown]"


def test_converse_falls_back_to_honest_static_on_leak():
    # A leaked wind-down takes the HONEST static (spec §2c) — never SAFE_CONTRACT's "I'll push"
    # lie on a dead engine; no sequel here (has_sequel default) -> the fresh static.
    m = FakeLeakModel(_intake(), {})
    out, _ = voice.converse(m, _exp(), [("student", "x")], "tell me the trick")
    assert out == voice._CONVERSE_DONE_FRESH
    assert out != voice.SAFE_CONTRACT and "push" not in out.lower()


# --- voice.opening (concrete turn 0) --------------------------------------------------------------


def test_opening_returns_authored_text_when_safe():
    class _Open(FakeModel):
        def concierge_open(self, problem, *, voice=""):
            return "Picture the contract on your desk, unsigned. What do you do, and why?"

    m = _Open(_intake(), {})
    assert voice.opening(m, _exp()).startswith("Picture the contract")


def test_opening_falls_back_to_problem_plus_invite_on_leak():
    class _LeakOpen(FakeLeakModel):
        def concierge_open(self, problem, *, voice=""):
            return "LEAK the move in the opening"

    m = _LeakOpen(_intake(), {})
    assert voice.opening(m, _exp()) == _exp().prompt + "\n\n" + voice._INVITE


def test_opening_falls_back_on_empty():
    class _EmptyOpen(FakeModel):
        def concierge_open(self, problem, *, voice=""):
            return ""

    m = _EmptyOpen(_intake(), {})
    assert voice.opening(m, _exp()) == _exp().prompt + "\n\n" + voice._INVITE


def test_concierge_open_is_frame_blind_and_returns_text():
    stub = _StubClient(text="The board wants an answer by Friday. What do you commit to, and why?")
    m = AnthropicModel(client=stub)
    out = m.concierge_open("The pricing problem text.")
    assert out.startswith("The board wants an answer")
    blob = str(stub.last)
    assert "frame_detail" not in blob and "Rubric" not in blob
    assert "The pricing problem text." in blob  # the problem IS the only input


# --- voice.gate ------------------------------------------------------------------------------------


def test_gate_returns_entry_class():
    m = FakeDoorModel(_intake(), EntryClass.greeting, "")
    assert voice.gate(m, _exp(), "hi", []) is EntryClass.greeting


def test_gate_substantive_enters_engine():
    m = FakeDoorModel(_intake(), EntryClass.substantive, "")
    assert voice.gate(m, _exp(), "I'd hold the line because...", []) is EntryClass.substantive


# --- AnthropicModel request shape (frame-blind) ---------------------------------------------------


class _Resp:
    def __init__(self, parsed=None, content=None, stop_reason="end_turn"):
        self.parsed_output = parsed
        self.content = content or []
        self.stop_reason = stop_reason


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _StubClient:
    """Captures the last request kwargs and returns canned responses."""

    def __init__(self, parsed=None, text=None):
        self._parsed, self._text = parsed, text
        self.last = {}
        self.messages = self

    def parse(self, **kw):
        self.last = kw
        return _Resp(parsed=self._parsed)

    def create(self, **kw):
        self.last = kw
        return _Resp(content=[_Block(self._text)])


class _RefusingClient(_StubClient):
    def create(self, **kw):
        self.last = kw
        return _Resp(content=[], stop_reason="refusal")


def test_classify_entry_is_frame_blind_and_parses():
    parsed = EntryClassification(entry_class=EntryClass.greeting, reply="Welcome.")
    stub = _StubClient(parsed=parsed)
    m = AnthropicModel(client=stub)
    out = m.classify_entry("The pricing problem text.", "hi", [("student", "hi")])
    assert out.entry_class is EntryClass.greeting
    # frame-blind: neither rubric codes nor details may appear anywhere in the request
    blob = str(stub.last)
    assert "lead_with_what_you_refuse_to_do" not in blob
    assert "frame_detail" not in blob and "Rubric" not in blob
    # the problem prompt IS available to the classifier
    assert "The pricing problem text." in blob


def test_concierge_turn_is_frame_blind_and_returns_text():
    stub = _StubClient(
        text="You said data settles it — but whose audit do they trust when it is your number?"
    )
    m = AnthropicModel(client=stub)
    out = m.concierge_turn(
        "The pricing problem text.",
        "Which mistake here can you actually walk back?",
        [("student", "Verifiable audits and data are what's essential.")],
    )
    assert out.startswith("You said data settles it")
    blob = str(stub.last)
    assert (
        "lead_with_what_you_refuse_to_do" not in blob
        and "frame_detail" not in blob
        and "Rubric" not in blob
    )
    # the safe push (brief) and the problem ARE inputs
    assert (
        "Which mistake here can you actually walk back?" in blob
        and "The pricing problem text." in blob
    )


def test_concierge_turn_reinvite_mode_has_no_brief():
    stub = _StubClient(text="That is a fair worry — but what would you actually do, and why?")
    m = AnthropicModel(client=stub)
    out = m.concierge_turn("Problem P.", "", [("student", "what do you want from me")])
    assert out.startswith("That is a fair worry")
    assert "what do you want from me" in str(stub.last)


def test_concierge_close_is_frame_blind_and_returns_text():
    stub = _StubClient(
        text="You committed to holding the line and bet on data; you are exposed if the audit is contested."
    )
    m = AnthropicModel(client=stub)
    out = m.concierge_close("Problem P.", [("student", "I'd hold and rely on audits.")])
    assert out.startswith("You committed to holding the line")
    blob = str(stub.last)
    assert "frame_detail" not in blob and "Rubric" not in blob


def test_concierge_turn_refusal_returns_empty():
    m = AnthropicModel(client=_RefusingClient())
    assert m.concierge_turn("P", "brief", [("student", "x")]) == ""


def test_concierge_land_is_frame_blind_and_carries_stop_reason():
    stub = _StubClient(
        text="You reckoned with what it costs; there's no clean answer, and now you know why."
    )
    m = AnthropicModel(client=stub)
    out = m.concierge_land("Problem P.", [("student", "I'd hold and eat the churn.")], "converged")
    assert out.startswith("You reckoned with")
    blob = str(stub.last)
    assert "frame_detail" not in blob and "Rubric" not in blob  # frame-blind
    assert "converged" in blob  # the stop reason IS available to the author


def test_concierge_land_refusal_returns_empty():
    m = AnthropicModel(client=_RefusingClient())
    assert m.concierge_land("P", [("student", "x")], "converged") == ""


def test_concierge_converse_is_frame_blind_and_carries_stop_reason():
    stub = _StubClient(
        parsed=ConverseTurn(reply="We're done here — and that's a good place to be.")
    )
    m = AnthropicModel(client=stub)
    out = m.concierge_converse("Problem P.", [("student", "ok")], stop_reason="plateau")
    assert out.reply.startswith("We're done")
    blob = str(stub.last)
    assert "frame_detail" not in blob and "Rubric" not in blob  # frame-blind
    assert "plateau" in blob  # the stop reason IS available to the wind-down author


def test_require_names_truncation_distinctly():
    # A thinking-eats-the-budget truncation must not masquerade as a refusal: the founder-dogfood
    # brick (2026-07-01) surfaced as the generic message and cost a live diagnosis to attribute.
    from elenchus.model import ModelError, _require

    import pytest as _pytest

    with _pytest.raises(ModelError, match="max_tokens"):
        _require(_Resp(parsed=None, stop_reason="max_tokens"))


def test_graded_classifier_budgets_have_thinking_headroom():
    """L-17 (third strike, founder dogfood 2026-07-01): classify_intake measured 1052-1828 output
    tokens on a real founder opening against a 2048 cap — one longer adaptive-thinking excursion
    crosses it, parsed_output=None, and the session BRICKS terminally. Intake + response get the
    same 4096 headroom as the egress screen; entry stays 2048 (measured ~19 tokens)."""
    from elenchus.model import _IntakeWire, ResponseClassification

    stub = _StubClient(parsed=_IntakeWire(frames=[], traps=[]))
    m = AnthropicModel(client=stub)
    m.classify_intake(_exp(), "a long reasoned opening")
    assert stub.last["max_tokens"] == 4096

    stub2 = _StubClient(
        parsed=ResponseClassification(
            outcome="unchanged", mechanism_supplied=False, hard_wrong=False
        )
    )
    m2 = AnthropicModel(client=stub2)
    m2.classify_response(_exp(), "frame", "lead_with_what_you_refuse_to_do", "push?", "my reply")
    assert stub2.last["max_tokens"] == 4096


def test_display_titles_have_no_veldra_and_cover_open_ended():
    titles = voice.display_titles()
    assert titles, "expected at least one open-ended experience title"
    for ref, title in titles.items():
        assert ref.startswith("veldra:")  # keyed by the internal ref (server-side only)
        assert "veldra" not in title.lower()  # the VALUE never leaks the source
        assert title and title[0].isupper()


# --- arc threading (woven stance modulation) ------------------------------------------------------


def test_turn_threads_arc_to_the_author():
    class _Rec(FakeModel):
        def __init__(self, intake):
            super().__init__(intake, {})
            self.arc = "unset"

        def concierge_turn(self, problem, push, recent, *, arc=None, voice=""):
            self.arc = arc
            return push or "take a real position"

    m = _Rec(_intake())
    voice.turn(m, _exp(), "the push", [("student", "x")], None, (3, 8))
    assert m.arc == (3, 8)
    m2 = _Rec(_intake())
    voice.turn(m2, _exp(), "the push", [("student", "x")])  # default: no arc
    assert m2.arc is None


def test_concierge_turn_brief_carries_arc_line_only_on_probe():
    stub = _StubClient(text="A sharp probe?")
    m = AnthropicModel(client=stub)
    m.concierge_turn("P", "the angle", [("student", "x")], arc=(3, 8))
    blob = str(stub.last)
    assert "Arc: this is push 3" in blob and "8 pushes" in blob
    stub2 = _StubClient(text="A sharp probe?")
    m2 = AnthropicModel(client=stub2)
    m2.concierge_turn("P", "the angle", [("student", "x")])  # no arc -> no line
    # (the doctrine text itself mentions "Arc:" in the system prompt — assert on the BRIEF line)
    assert "Arc: this is push" not in str(stub2.last)
    stub3 = _StubClient(text="An invite.")
    m3 = AnthropicModel(client=stub3)
    m3.concierge_turn("P", "", [("student", "x")], arc=(3, 8))  # re-invite NEVER carries an arc
    assert "Arc: this is push" not in str(stub3.last)


def test_arc_doctrine_lives_only_in_the_probe_prompt():
    """MF-2: voice_craft rides into EVERY author — the press/arc stance must live in concierge.md
    (probe-only). Sentinel: the section header. land/converse must never see it."""
    from elenchus.content_loader import load_prompt

    assert "The arc of the press" in load_prompt("concierge")
    assert "The arc of the press" not in load_prompt("voice_craft")
    v = voice.resolve_presentation(None, None)["voice"]
    stub = _StubClient(text="landing text")
    m = AnthropicModel(client=stub)
    m.concierge_land("P", [("student", "x")], "converged", voice=v)
    assert "The arc of the press" not in str(stub.last)
    stub2 = _StubClient(parsed=ConverseTurn(reply="wind-down"))
    m2 = AnthropicModel(client=stub2)
    m2.concierge_converse("P", [("student", "x")], voice=v)
    assert "The arc of the press" not in str(stub2.last)
    stub3 = _StubClient(text="a probe?")
    m3 = AnthropicModel(client=stub3)
    m3.concierge_turn("P", "angle", [("student", "x")], voice=v)
    assert "The arc of the press" in str(stub3.last)  # and the probe author DOES see it


# --- _render_turns windowing --------------------------------------------------------------------


def test_render_turns_default_window_is_six():
    from elenchus.model import _render_turns

    turns = [("student", f"t{i}") for i in range(10)]
    out = _render_turns(turns)
    assert "t9" in out and "t4" in out  # last 6: t4..t9
    assert "t3" not in out  # older than the 6-turn tail is dropped


def test_render_turns_wider_window_keeps_more():
    from elenchus.model import _render_turns

    turns = [("student", f"t{i}") for i in range(25)]
    out = _render_turns(turns, limit=20)
    assert "t24" in out and "t5" in out  # last 20: t5..t24
    assert "t4" not in out


def test_render_turns_empty_is_blank():
    from elenchus.model import _render_turns

    assert _render_turns([]) == ""
    assert _render_turns([], limit=20) == ""


# --- _render_turns: no learner byte at column 0, bounded on what is actually rendered -----------

# Private-use methodology (Task 1, tests/test_prompt_text.py): a character from U+E000+ never
# appears in this module's own template text ("Recent exchange:", the role names, or
# LEARNER_INDENT), so any payload character surviving as a line's leading non-blank character is
# unambiguous proof of a leak, not a coincidence of overlapping alphabets. The separator matrix
# itself (the full width of str.splitlines()) is already exhaustively parametrized against
# _indent_after_first in test_prompt_text.py; these only prove _render_turns' own wiring -- the
# role prefix, the per-turn cap -- doesn't reopen the hole that discipline closes.
_TURN_PAYLOAD_FIRST = chr(0xE000)
_TURN_PAYLOAD_SECOND = chr(0xE001)


def _leading_nonspace_chars(rendered):
    return [line[0] for line in rendered.split("\n") if line and not line[0].isspace()]


@pytest.mark.parametrize("sep", ["\n", "\r\n"])
def test_render_turns_no_payload_byte_reaches_column_0(sep):
    from elenchus.model import _render_turns

    turn = f"{_TURN_PAYLOAD_FIRST}{sep}{_TURN_PAYLOAD_SECOND}"
    out = _render_turns([("student", turn)])
    leaders = _leading_nonspace_chars(out)
    assert _TURN_PAYLOAD_SECOND not in leaders  # the continuation byte is indented past column 0


@pytest.mark.parametrize("sep", ["\n", "\r\n", chr(0x2028)])
def test_render_turns_indents_every_splitlines_recognised_break(sep):
    """U+2028 (LINE SEPARATOR) is not `"\\n"`, so a bare `.split("\\n")` check (the test above)
    cannot see it -- it never opens a `"\\n"`-delimited line either before or after the fix, so an
    absence-from-column-0 check alone passes vacuously for it in both cases. This asserts on the
    PRESENCE of the indented continuation line instead, which only exists once `_render_turns`
    recognises the separator (splitlines() width) AND indents past it -- both halves of the fix,
    for every separator splitlines() recognises, not just the two that also happen to be `"\\n"`
    literals."""
    from elenchus.model import _render_turns

    turn = f"{_TURN_PAYLOAD_FIRST}{sep}{_TURN_PAYLOAD_SECOND}"
    out = _render_turns([("student", turn)])
    lines = out.split("\n")
    assert lines[1] == f"student: {_TURN_PAYLOAD_FIRST}"
    assert f"    {_TURN_PAYLOAD_SECOND}" in lines


def test_render_turns_role_prefix_stays_legible_at_column_0():
    """The role name IS meant to open its line -- that's the only way a reader tells `student`
    from `Vera` apart. Only the learner's OWN continuation bytes must be pushed off column 0."""
    from elenchus.model import _render_turns

    out = _render_turns([("student", "one\ntwo"), ("Vera", "three\nfour")])
    lines = out.split("\n")
    assert "student: one" in lines
    assert "Vera: three" in lines


def test_render_turns_single_line_turn_is_byte_identical_to_the_old_form():
    """R2 byte-stability, asserted against a literal: the pre-fix rendering
    (`f"{role}: {text}"`) for the common, single-line case, which is almost all real input."""
    from elenchus.model import _render_turns

    out = _render_turns([("student", "Verifiable audits and data are what's essential.")])
    assert out == "Recent exchange:\nstudent: Verifiable audits and data are what's essential.\n\n"


def test_render_turns_multiple_single_line_turns_are_byte_identical_to_the_old_form():
    from elenchus.model import _render_turns

    out = _render_turns([("student", "hi"), ("Vera", "hello there")])
    assert out == "Recent exchange:\nstudent: hi\nVera: hello there\n\n"


def test_render_turns_bounds_a_pathological_turn_on_the_rendered_output():
    """Pinned on the RENDERED string, not the input. `judgment_loop._POSITION_CAP`'s own comment
    records that a cap measured before render does not bound what comes out: a newline-heavy
    input renders to several times its own length once every continuation line gets an indent.
    50,000 raw characters (25x the render cap) must not reach the model as 50,000 characters."""
    from elenchus.model import _TURN_RENDER_CAP, _render_turns

    pathological = "\n" * 50_000
    out = _render_turns([("student", pathological)])
    assert len(out) < _TURN_RENDER_CAP + 100  # bounded far under the raw input's size


def test_concierge_converse_prompt_defers_a_fresh_pressure_to_the_next_chapter():
    from elenchus.content_loader import load_prompt

    p = load_prompt("concierge_converse")
    assert "next chapter" in p.lower()


def test_concierge_converse_empty_by_default_contract():
    """User-steered chapters F1: the structured next_pressure field leans EMPTY by default; a
    re-argument of the landed call is not a fresh pressure."""
    from elenchus.content_loader import load_prompt

    low = load_prompt("concierge_converse").lower()
    assert "next_pressure" in low
    assert "empty" in low and "default" in low
    assert "re-argument" in low or "re-litigat" in low


def test_converse_fallback_is_honest_and_branches_on_sequel():
    """Spec §2c / review pt 4: the fallback never promises a push; it promises a next chapter
    ONLY when a sequel exists."""

    class _RefuseModel(FakeModel):
        def concierge_converse(self, problem, recent, *, stop_reason="converged", voice=""):
            return ConverseTurn(reply="", next_pressure="")  # refused -> fallback

    m = _RefuseModel(_intake(), {})
    exp = _exp()
    story, _ = voice.converse(m, exp, [], "some text", None, "converged", has_sequel=True)
    fresh, _ = voice.converse(m, exp, [], "some text", None, "converged", has_sequel=False)
    assert "push" not in story.lower() and "push" not in fresh.lower()  # no lie
    assert story == voice._CONVERSE_DONE_STORY and "chapter" in story.lower()
    assert fresh == voice._CONVERSE_DONE_FRESH and "chapter" not in fresh.lower()
    assert voice.SAFE_CONTRACT not in (story, fresh)
