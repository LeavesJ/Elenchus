from elenchus.assessment import judgment_loop
from elenchus.model import FakeModel, IntakeClassification, ResponseClassification
from elenchus.types import (
    Experience,
    Frame,
    FrameState,
    Mode,
    Positions,
    Rubric,
    Regime,
    StopReason,
    Trap,
    TrapState,
    Work,
)


def _exp(mode=Mode.genuinely_open, binding=None):
    rub = Rubric(
        frames=[
            Frame(
                frame_code="lead_with_what_you_refuse_to_do",
                frame_detail="boundary first",
                paired_trap="scope_creep_to_please",
            ),
            Frame(
                frame_code="protect_the_core_lane",
                frame_detail="keep core",
                paired_trap="erode_core_for_one_customer",
            ),
        ],
        traps=[
            Trap(trap_code="scope_creep_to_please", trap_detail="bend to please"),
            Trap(trap_code="erode_core_for_one_customer", trap_detail="special-case"),
        ],
        mode=mode,
        binding_constraint=binding,
    )
    return Experience(
        experience_id="veldra:licensing_continuity",
        prompt="...",
        rubric=rub,
        ledger_ref="veldra:licensing_continuity",
        regime=Regime.open_ended,
    )


def _work():
    return Work(opening="here is my reasoning", respond=lambda push: "reply")


def test_cooperative_student_converges():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )

    def closed():
        return [ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)]

    m = FakeModel(
        intake, {"lead_with_what_you_refuse_to_do": closed(), "protect_the_core_lane": closed()}
    )
    a = judgment_loop.assess(_exp(), _work(), m)
    assert a.stop_reason is StopReason.converged
    assert set(a.frames_closed_under_pressure) == {
        "lead_with_what_you_refuse_to_do",
        "protect_the_core_lane",
    }
    # disband rule: no push text contains a literal frame_code
    assert all("protect_the_core_lane" not in p.text for p in a.trajectory)
    # disband: the loop relays generate_push output verbatim — it never wraps the
    # frame_code into student-facing text. (A regression like
    # f"Think about {code}: {push}" would change p.text and fail this.)
    assert all(p.text == f"[push:{p.kind}]" for p in a.trajectory)
    # the independent grader ran and confirmed both sharper calls (default-agree FakeModel)
    assert len(a.sharper_audit) == 2
    assert all(item.confirmed for item in a.sharper_audit)


def test_bounded_error_violation_stops_immediately():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.tripped,
        },
    )
    m = FakeModel(
        intake,
        {
            "erode_core_for_one_customer": [
                ResponseClassification(
                    outcome="unchanged", mechanism_supplied=False, hard_wrong=True
                )
            ]
        },
    )
    a = judgment_loop.assess(
        _exp(mode=Mode.bounded_error, binding="erode_core_for_one_customer"), _work(), m
    )
    assert a.stop_reason is StopReason.bounded_error_violation
    assert a.hard_wrong_flags == ["erode_core_for_one_customer"]


def test_budget_caps_unproductive_loop():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )
    stuck = [
        ResponseClassification(outcome="unchanged", mechanism_supplied=False, hard_wrong=False)
        for _ in range(judgment_loop.MAX_PUSHES + 2)
    ]
    m = FakeModel(
        intake,
        {"lead_with_what_you_refuse_to_do": list(stuck), "protect_the_core_lane": list(stuck)},
    )
    a = judgment_loop.assess(_exp(), _work(), m)
    assert a.stop_reason in (StopReason.plateau, StopReason.budget)


def test_regression_stops_when_student_backslides():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.present_reasoned,
            "protect_the_core_lane": FrameState.present_asserted,  # unmet; will be targeted
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )
    m = FakeModel(
        intake,
        {
            "protect_the_core_lane": [
                ResponseClassification(
                    outcome="regressed", mechanism_supplied=False, hard_wrong=False
                )
            ]
        },
    )
    a = judgment_loop.assess(_exp(), _work(), m)
    assert a.stop_reason is StopReason.regression
    # backslide recorded: present_asserted -> absent, and not credited as closed
    assert any(
        d.code == "protect_the_core_lane" and d.after is FrameState.absent for d in a.frame_deltas
    )
    assert "protect_the_core_lane" not in a.frames_closed_under_pressure
    # the raw student response is captured on the push
    assert a.trajectory[-1].response == "reply"


def test_plateau_stops_on_two_distinct_unmoved_targets():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )

    def unchanged():
        return [
            ResponseClassification(outcome="unchanged", mechanism_supplied=False, hard_wrong=False)
        ]

    m = FakeModel(
        intake,
        {"lead_with_what_you_refuse_to_do": unchanged(), "protect_the_core_lane": unchanged()},
    )
    a = judgment_loop.assess(_exp(), _work(), m)
    assert a.stop_reason is StopReason.plateau
    # rotation happened: the two pushes were on DISTINCT targets
    pushed = [p.target_code for p in a.trajectory]
    assert len(pushed) == 2 and pushed[0] != pushed[1]


def test_grader_dispute_demotes_a_sharper_call_in_the_full_loop():
    from elenchus.types import SharperVerdict

    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )

    def closed():
        return [ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)]

    m = FakeModel(
        intake,
        {"lead_with_what_you_refuse_to_do": closed(), "protect_the_core_lane": closed()},
        sharper_verdicts={
            "protect_the_core_lane": [SharperVerdict(sharper=False, reason="assent only")]
        },
    )
    a = judgment_loop.assess(_exp(), _work(), m)
    # instructor closed both; the blind grader disputes protect_the_core_lane -> demoted
    assert "lead_with_what_you_refuse_to_do" in a.frames_closed_under_pressure
    assert "protect_the_core_lane" not in a.frames_closed_under_pressure
    assert any(i.code == "protect_the_core_lane" and not i.confirmed for i in a.sharper_audit)


# ---------------------------------------------------------------------------
# Decision-frame / probe-gated convergence tests (Task 3)
# ---------------------------------------------------------------------------


def _exp_decision():
    rub = Rubric(
        frames=[
            Frame(
                frame_code="lead_with_what_you_refuse_to_do",
                frame_detail="boundary first",
                paired_trap="scope_creep_to_please",
            ),
            Frame(
                frame_code="protect_the_core_lane",
                frame_detail="keep core",
                paired_trap="erode_core_for_one_customer",
            ),
            Frame(
                frame_code="commit_under_the_deadline",
                frame_detail="commit, own the trade, name the reversal",
                paired_trap="commit_without_a_tripwire",
            ),
        ],
        traps=[
            Trap(trap_code="scope_creep_to_please", trap_detail="bend to please"),
            Trap(trap_code="erode_core_for_one_customer", trap_detail="special-case"),
            Trap(trap_code="commit_without_a_tripwire", trap_detail="no reversal line"),
        ],
        mode=Mode.genuinely_open,
        binding_constraint=None,
        decision_frame="commit_under_the_deadline",
    )
    return Experience(
        experience_id="veldra:license_continuity",
        prompt="...",
        rubric=rub,
        ledger_ref="veldra:license_continuity",
        regime=Regime.open_ended,
    )


def _all_reasoned_intake():
    return IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.present_reasoned,
            "protect_the_core_lane": FrameState.present_reasoned,
            "commit_under_the_deadline": FrameState.present_reasoned,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
            "commit_without_a_tripwire": TrapState.not_tripped,
        },
    )


def test_decision_frame_forces_one_stress_probe_before_converging():
    # The dogfood repro: a strong answer rated all-present_reasoned at intake must NOT converge
    # silently — the decision frame is stressed exactly once, then the loop converges.
    m = FakeModel(
        _all_reasoned_intake(),
        {
            "commit_under_the_deadline": [
                ResponseClassification(
                    outcome="unchanged", mechanism_supplied=False, hard_wrong=False
                )
            ]
        },
    )
    a = judgment_loop.assess(_exp_decision(), _work(), m)
    assert a.stop_reason is StopReason.converged
    assert len(a.trajectory) == 1
    assert a.trajectory[0].target_code == "commit_under_the_deadline"


def test_decision_frame_stress_probe_can_be_credited_sharper():
    m = FakeModel(
        _all_reasoned_intake(),
        {
            "commit_under_the_deadline": [
                ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
            ]
        },
    )
    a = judgment_loop.assess(_exp_decision(), _work(), m)
    assert a.stop_reason is StopReason.converged
    assert "commit_under_the_deadline" in a.frames_closed_under_pressure
    assert len(a.trajectory) == 1


def test_decision_frame_absent_is_targeted_first():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
            "commit_under_the_deadline": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
            "commit_without_a_tripwire": TrapState.not_tripped,
        },
    )

    def closed():
        return [ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)]

    m = FakeModel(
        intake,
        {
            "commit_under_the_deadline": closed(),
            "lead_with_what_you_refuse_to_do": closed(),
            "protect_the_core_lane": closed(),
        },
    )
    a = judgment_loop.assess(_exp_decision(), _work(), m)
    # without the force, rubric order would target lead_with_what_you_refuse_to_do first
    assert a.trajectory[0].target_code == "commit_under_the_deadline"


def test_no_decision_frame_all_reasoned_still_converges_at_intake():
    # Byte-stability lock: a rubric with no decision_frame keeps today's behavior —
    # an all-present_reasoned opening converges immediately with an empty trajectory.
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.present_reasoned,
            "protect_the_core_lane": FrameState.present_reasoned,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )
    a = judgment_loop.assess(_exp(), _work(), FakeModel(intake, {}))
    assert a.stop_reason is StopReason.converged
    assert a.trajectory == []


def test_assess_reports_reasoned_unprompted_for_held_intake_frames():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.present_reasoned,  # reasoned unprompted, never pushed
            "protect_the_core_lane": FrameState.present_reasoned,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )
    a = judgment_loop.assess(_exp(), _work(), FakeModel(intake, {}))
    assert a.stop_reason is StopReason.converged
    assert set(a.reasoned_unprompted) == {
        "lead_with_what_you_refuse_to_do",
        "protect_the_core_lane",
    }


def test_stress_probed_frame_excluded_from_reasoned_unprompted():
    # A decision_frame that is present_reasoned at intake gets force-stress-probed.
    # If the student supplies a mechanism (outcome="closed"), it lands in
    # frames_closed_under_pressure — but must NOT also appear in reasoned_unprompted,
    # because it was pushed (not genuinely unprompted).  The two non-probed intake-
    # reasoned frames MUST still appear in reasoned_unprompted.
    m = FakeModel(
        _all_reasoned_intake(),
        {
            "commit_under_the_deadline": [
                ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
            ]
        },
    )
    a = judgment_loop.assess(_exp_decision(), _work(), m)
    assert a.stop_reason is StopReason.converged
    # The probed frame must NOT appear in reasoned_unprompted.
    assert "commit_under_the_deadline" not in a.reasoned_unprompted
    # The two non-probed intake-reasoned frames MUST appear.
    assert "lead_with_what_you_refuse_to_do" in a.reasoned_unprompted
    assert "protect_the_core_lane" in a.reasoned_unprompted


def test_regressed_under_stress_probe_excluded_from_reasoned_unprompted():
    # A decision_frame that is present_reasoned at intake then regresses under the
    # stress probe is excluded from reasoned_unprompted because its final state is
    # no longer present_reasoned (the existing final-state guard covers this; lock it).
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.present_reasoned,
            "protect_the_core_lane": FrameState.present_reasoned,
            "commit_under_the_deadline": FrameState.present_reasoned,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
            "commit_without_a_tripwire": TrapState.not_tripped,
        },
    )
    m = FakeModel(
        intake,
        {
            "commit_under_the_deadline": [
                ResponseClassification(
                    outcome="regressed", mechanism_supplied=False, hard_wrong=False
                )
            ]
        },
    )
    a = judgment_loop.assess(_exp_decision(), _work(), m)
    assert a.stop_reason is StopReason.regression
    # Regressed frame dropped from final state — excluded by the final-state guard.
    assert "commit_under_the_deadline" not in a.reasoned_unprompted


def test_positions_are_grouped_on_the_FULL_target_key():
    """Spec §4.2. A target is (kind, code) everywhere else in the system. Frame and trap codes
    do not collide today (5 frame, 8 trap, zero overlap) and NOTHING enforces that, while the
    rubric bank is designed to grow by hand. A trap position landing in on_angle would tell the
    stress author it was the reasoned engagement with the angle being pressed."""
    from elenchus.assessment.judgment_loop import _group_positions
    from elenchus.types import Push

    traj = [
        Push(
            target_code="shared",
            kind="frame",
            text="p",
            response_classification="closed",
            response="FRAME POSITION",
        ),
        Push(
            target_code="shared",
            kind="trap",
            text="p",
            response_classification="closed",
            response="TRAP POSITION",
        ),
    ]
    grouped = _group_positions(traj, "frame", "shared")
    assert grouped.on_angle == ("FRAME POSITION",)
    assert grouped.elsewhere == ("TRAP POSITION",)


def test_no_classification_value_reaches_the_groups():
    """Spec §6. Tested with SENTINELS, not the real vocabulary: `closed` / `unchanged` /
    `regressed` are ordinary English and asserting their absence would false-positive the moment
    a learner writes 'I closed the round'."""
    from elenchus.assessment.judgment_loop import _group_positions
    from elenchus.types import Push

    traj = [
        Push(
            target_code="c",
            kind="frame",
            text="p",
            response_classification="ZZSENTINELVERDICTZZ",
            response="my words",
        ),
    ]
    grouped = _group_positions(traj, "frame", "c")
    assert "ZZSENTINELVERDICTZZ" not in "".join(grouped.on_angle + grouped.elsewhere)


def test_positions_are_capped_at_a_sentence_boundary_with_the_elision_marked():
    """Spec §4.2. A mid-clause cut hands the author a position that appears to end where the
    learner stopped talking; the author then presses a trailing thought that is an artifact of
    our cap."""
    from elenchus.assessment.judgment_loop import _POSITION_CAP, _cap

    marker = "…[trimmed]"
    long = ("First sentence here. " * 200).strip()
    out = _cap(long)

    # The exact boundary, derived from the fixture's own structure: 21 characters per sentence,
    # so the last one ending under the cap ends at index 1195. Never from calling _cap.
    assert out == "First sentence here. " * 56 + "First sentence here." + marker
    assert len(out) <= _POSITION_CAP + len(marker)
    assert out.endswith(marker)
    assert out[: -len(marker)].endswith(".")
    assert long.startswith(out[: -len(marker)])  # a prefix of the input, not a rewrite


def test_a_short_position_is_returned_untouched():
    from elenchus.assessment.judgment_loop import _cap

    assert _cap("Short answer.") == "Short answer."


# ---------------------------------------------------------------------------
# Opus review fixes on Task 3 (positions=_group_positions(...) wiring + edges)
# ---------------------------------------------------------------------------


class _RecordingPushModel(FakeModel):
    """FakeModel that also records the Positions passed to each generate_push call, in call
    order. Named for reuse: a later task needs a model that both records positions and returns
    scripted push text, and can subclass this instead of duplicating the FakeModel wiring."""

    def __init__(self, intake, responses, grades=None, sharper_verdicts=None):
        super().__init__(intake, responses, grades, sharper_verdicts)
        self.recorded_positions: list[Positions] = []

    def generate_push(self, exp, kind, code, *, stress=False, positions=Positions()):
        self.recorded_positions.append(positions)
        return super().generate_push(exp, kind, code, stress=stress, positions=positions)


def test_generate_push_receives_a_prior_pushes_own_words_through_assess():
    """Finding 1 (Opus review): `positions=_group_positions(trajectory, kind, code)` at the push
    site had no assertion that goes through `assess` — deleting it silently reverts every push to
    a default Positions() and the offline suite stayed green. Drives `assess` (never calls
    `_group_positions` directly) and pins that a LATER push's `positions` argument carries an
    EARLIER push's raw response text.

    Under `_select_target`'s exhausted/probed bookkeeping, a (kind, code) target is pushed at
    most once per `assess` run (closed -> present_reasoned skips it; anything else -> exhausted
    skips it; regressed/hard_wrong stop the loop outright), so the real target sequence never
    revisits a target. The reachable case is `elsewhere` (a later push on a DIFFERENT target
    carries the earlier push's response) — this is that case, asserted against the literal
    scripted response string, never against a value obtained by calling `_group_positions`.
    """
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )
    scripted_responses = iter(
        ["first take: the boundary is non-negotiable", "second take: locked in"]
    )
    work = Work(opening="here is my reasoning", respond=lambda push: next(scripted_responses))
    m = _RecordingPushModel(
        intake,
        {
            "lead_with_what_you_refuse_to_do": [
                ResponseClassification(
                    outcome="unchanged", mechanism_supplied=False, hard_wrong=False
                )
            ],
            "protect_the_core_lane": [
                ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
            ],
        },
    )
    a = judgment_loop.assess(_exp(), work, m)

    # the real target sequence this rubric+intake produces: two distinct frame targets
    assert [p.target_code for p in a.trajectory] == [
        "lead_with_what_you_refuse_to_do",
        "protect_the_core_lane",
    ]
    assert len(m.recorded_positions) == 2
    # push 1: nothing has been said yet in this sitting
    assert m.recorded_positions[0] == Positions()
    # push 2 targets a DIFFERENT (kind, code) than push 1 -> push 1's response lands in
    # `elsewhere`, never `on_angle`
    assert m.recorded_positions[1].on_angle == ()
    assert m.recorded_positions[1].elsewhere == ("first take: the boundary is non-negotiable",)


def test_cap_no_terminator_falls_back_to_rstripped_head():
    """Finding 2: 1200+ characters with no '.', '?', or '!' anywhere in the first _POSITION_CAP
    characters gives stop == -1, the head.rstrip() + marker branch. Pins that the head is
    right-stripped before the marker is appended, not left with trailing whitespace."""
    from elenchus.assessment.judgment_loop import _POSITION_CAP, _cap

    head_no_terminator = "a" * (_POSITION_CAP - 5) + " " * 5  # exactly _POSITION_CAP chars
    text = head_no_terminator + "b" * 50
    assert _cap(text) == "a" * (_POSITION_CAP - 5) + "…[trimmed]"


def test_cap_lone_leading_terminator_does_not_truncate_to_one_character():
    """Finding 2 / repo doctrine: a '.' at head[0] and nowhere else in the first _POSITION_CAP
    characters gives stop == 0. `stop > 0` (not `stop >= 0`) is deliberate: truncating to that
    lone leading terminator would hand back a one-character position, worse than a mid-clause
    cut. Pins the `> 0` boundary against a `>= 0` mutation."""
    from elenchus.assessment.judgment_loop import _POSITION_CAP, _cap

    text = "." + "a" * (_POSITION_CAP - 1) + "b" * 50  # exactly _POSITION_CAP chars in head
    assert _cap(text) == "." + "a" * (_POSITION_CAP - 1) + "…[trimmed]"


def test_cap_exact_boundary_length_is_returned_untouched():
    """Finding 3: a text of exactly _POSITION_CAP characters must be returned untouched. The
    only existing short-input test uses a 13-character string, which does not distinguish `<=`
    from `<` at the boundary."""
    from elenchus.assessment.judgment_loop import _POSITION_CAP, _cap

    text = "x" * _POSITION_CAP
    assert _cap(text) == text


def test_group_positions_on_an_empty_trajectory():
    """Finding 4: an empty trajectory is the state of the very first push in every real
    session -- the most-executed input this function has. Pins Positions((), ())."""
    from elenchus.assessment.judgment_loop import _group_positions

    assert _group_positions([], "frame", "any_code") == Positions()
