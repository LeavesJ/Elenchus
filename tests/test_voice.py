from retnovation.model import (
    AnthropicModel,
    FakeModel,
    IntakeClassification,
)
from retnovation.types import (
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
from retnovation.web import voice


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

    def concierge_turn(self, problem, push, recent):
        return "LEAK: lead with what you refuse to do"

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

    def concierge_turn(self, problem, push, recent):
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
        def concierge_turn(self, problem, push, recent):
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
        def concierge_close(self, problem, recent):
            return "LEAK the move"

    m = _LeakClose(_intake(), {})
    assert voice.close(m, _exp(), [("student", "x")]) == voice._STATIC_CLOSE


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


def test_display_titles_have_no_veldra_and_cover_open_ended():
    titles = voice.display_titles()
    assert titles, "expected at least one open-ended experience title"
    for ref, title in titles.items():
        assert ref.startswith("veldra:")  # keyed by the internal ref (server-side only)
        assert "veldra" not in title.lower()  # the VALUE never leaks the source
        assert title and title[0].isupper()
