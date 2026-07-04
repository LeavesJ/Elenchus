import pytest

from datetime import datetime, timezone
from retnovation.types import (
    Strength,
    Regime,
    Mode,
    FrameState,
    StopReason,
    Frame,
    Trap,
    Rubric,
    Experience,
    Assessment,
    Push,
    FrameDelta,
    LearnerState,
    FrameStrength,
    Work,
)


def test_experience_roundtrips_through_json():
    rub = Rubric(
        frames=[Frame(frame_code="protect_the_core_lane", frame_detail="keep the core promise")],
        traps=[
            Trap(trap_code="erode_core_for_one_customer", trap_detail="special-case one account")
        ],
        mode=Mode.genuinely_open,
    )
    exp = Experience(
        experience_id="veldra:licensing_continuity",
        prompt="...",
        rubric=rub,
        ledger_ref="veldra:licensing_continuity",
        regime=Regime.open_ended,
    )
    again = Experience.model_validate_json(exp.model_dump_json())
    assert again.regime is Regime.open_ended
    assert again.rubric.frames[0].frame_code == "protect_the_core_lane"


def test_learner_state_defaults_are_independent():
    a, b = LearnerState(), LearnerState()
    now = datetime.now(timezone.utc)
    a.frames["x"] = FrameStrength(strength=Strength.weak, last_seen=now, due=now, last_evidence="")
    assert b.frames == {}  # no shared mutable default


def test_assessment_holds_stop_reason_and_work_is_callable():
    asmt = Assessment(
        trajectory=[
            Push(target_code="f", kind="frame", text="t", response_classification="closed")
        ],
        frame_deltas=[
            FrameDelta(code="f", before=FrameState.absent, after=FrameState.present_reasoned)
        ],
        frames_closed_under_pressure=["f"],
        hard_wrong_flags=[],
        stop_reason=StopReason.converged,
    )
    assert asmt.stop_reason is StopReason.converged
    w = Work(opening="hi", respond=lambda push: "ok")
    assert w.respond("anything") == "ok"


def test_gatecode_and_gateresult_and_experience_id():
    from retnovation.types import GateCode, GateResult, Experience, Rubric, Mode, Regime

    assert GateCode.recoverable_label.value == "recoverable_label"
    assert len(list(GateCode)) == 8

    res = GateResult(
        passed=False, rejects=[GateCode.recoverable_label], downgrades=[], angle_count=4
    )
    assert res.passed is False
    assert res.angle_count == 4

    exp = Experience(
        experience_id="x",
        prompt="p",
        rubric=Rubric(frames=[], traps=[], mode=Mode.genuinely_open, binding_constraint=None),
        ledger_ref="veldra:x",
        regime=Regime.open_ended,
    )
    assert exp.experience_id == "x"


def test_checkable_types_build_and_regime_invariant():
    import pytest
    from retnovation.types import (
        CheckType,
        CheckableQuestion,
        CheckableSet,
        ConceptResult,
        CheckableAssessment,
        CheckableGrade,
        Experience,
        Regime,
    )

    q = CheckableQuestion(
        question_id="q1",
        concept="safety_vs_liveness",
        prompt="Which property guarantees nothing bad ever happens?",
        check_type=CheckType.deterministic,
        choices=["safety", "liveness"],
        answer_key=["safety"],
    )
    cs = CheckableSet(questions=[q])
    exp = Experience(
        experience_id="cs1",
        prompt="Answer the following.",
        ledger_ref="veldra:consensus_correctness",
        regime=Regime.cs_technical,
        checkable=cs,
    )
    assert exp.checkable.questions[0].answer_key == ["safety"]
    assert exp.rubric is None

    asmt = CheckableAssessment(
        results=[
            ConceptResult(
                concept="safety_vs_liveness",
                question_id="q1",
                correct=True,
                check_type=CheckType.deterministic,
            )
        ]
    )
    assert asmt.results[0].correct is True
    assert CheckableGrade(correct=False).correct is False

    # invariant: cs_technical with a rubric is rejected
    from retnovation.types import Rubric, Mode

    with pytest.raises(Exception):
        Experience(
            experience_id="bad",
            prompt="p",
            ledger_ref="r",
            regime=Regime.cs_technical,
            rubric=Rubric(frames=[], traps=[], mode=Mode.genuinely_open),
            checkable=cs,
        )
    # invariant: open_ended without a rubric is rejected
    with pytest.raises(Exception):
        Experience(experience_id="bad2", prompt="p", ledger_ref="r", regime=Regime.open_ended)


def test_aim_core_content_core_accepts_a_concept_list():
    from retnovation.types import Aim, Core

    a = Aim(posture="cs_systems", process_dial=0, content_core=["safety_vs_liveness"])
    c = Core(
        process_frames=[],
        declarative_seed=["safety_vs_liveness"],
        content_core=["safety_vs_liveness"],
    )
    assert a.content_core == ["safety_vs_liveness"]
    assert c.content_core == ["safety_vs_liveness"]


def test_push_carries_raw_response_with_empty_default():
    from retnovation.types import Push

    p = Push(target_code="f", kind="frame", text="push", response_classification="closed")
    assert p.response == ""
    p2 = Push(
        target_code="f",
        kind="frame",
        text="push",
        response_classification="closed",
        response="my reply",
    )
    assert p2.response == "my reply"


def test_sharper_audit_types_and_assessment_field():
    from retnovation.types import (
        Assessment,
        SharperAuditItem,
        SharperVerdict,
        StopReason,
    )

    assert SharperVerdict(sharper=False, reason="bare assent").sharper is False
    item = SharperAuditItem(
        code="protect_the_core_lane",
        kind="frame",
        instructor_sharper=True,
        grader_sharper=False,
        confirmed=False,
        grader_reason="no mechanism",
    )
    assert item.confirmed is False
    a = Assessment(
        trajectory=[],
        frame_deltas=[],
        frames_closed_under_pressure=[],
        hard_wrong_flags=[],
        stop_reason=StopReason.converged,
    )
    assert a.sharper_audit == []  # default empty
    a2 = Assessment(
        trajectory=[],
        frame_deltas=[],
        frames_closed_under_pressure=[],
        hard_wrong_flags=[],
        stop_reason=StopReason.converged,
        sharper_audit=[item],
    )
    assert a2.sharper_audit[0].code == "protect_the_core_lane"


def test_scene_and_corpus_experience_scene_fields():
    from retnovation.types import (
        CheckableSet,
        CorpusEntry,
        Experience,
        Frame,
        Mode,
        Regime,
        Rubric,
        Scene,
        Trap,
    )

    sc = Scene(
        prompt="A concrete, situated decision.", situation="The world, the actors, the stakes."
    )
    assert sc.prompt and sc.situation

    ce = CorpusEntry(
        ledger_ref="veldra:x",
        domain="founder_ceo",
        why_owned="stakes",
        unlabeled="unlabeled",
        provenance="docs/X",
        corpus_pointers=[],
    )
    assert ce.scene is None  # default
    ce2 = CorpusEntry(
        ledger_ref="veldra:y",
        domain="founder_ceo",
        why_owned="stakes",
        unlabeled="unlabeled",
        provenance="docs/Y",
        corpus_pointers=[],
        scene=sc,
    )
    assert ce2.scene.prompt == "A concrete, situated decision."

    exp = Experience(
        experience_id="e",
        prompt="abstract",
        ledger_ref="veldra:y",
        regime=Regime.open_ended,
        rubric=Rubric(
            frames=[Frame(frame_code="f", frame_detail="d", paired_trap="t")],
            traps=[Trap(trap_code="t", trap_detail="d")],
            mode=Mode.genuinely_open,
        ),
    )
    assert exp.scene is None  # default; runtime-only
    assert (
        exp.model_copy(update={"scene": sc}).scene.situation == "The world, the actors, the stakes."
    )
    # CheckableSet import unused-guard: keep regimes coherent (CS experiences never get a scene)
    assert CheckableSet(questions=[]).questions == []


def _frame(code="commit_under_the_deadline"):
    return Frame(frame_code=code, frame_detail="commit and name the reversal")


def test_decision_frame_defaults_to_none():
    rub = Rubric(frames=[_frame()], traps=[], mode=Mode.genuinely_open)
    assert rub.decision_frame is None


def test_decision_frame_accepts_an_existing_frame_code():
    rub = Rubric(
        frames=[_frame()],
        traps=[],
        mode=Mode.genuinely_open,
        decision_frame="commit_under_the_deadline",
    )
    assert rub.decision_frame == "commit_under_the_deadline"


def test_decision_frame_naming_a_missing_frame_raises():
    with pytest.raises(ValueError):
        Rubric(
            frames=[_frame()],
            traps=[],
            mode=Mode.genuinely_open,
            decision_frame="not_a_frame",
        )


def test_frame_strength_storage_fields_default_empty():
    from datetime import datetime, timezone
    from retnovation.types import FrameStrength, Strength

    now = datetime(2026, 6, 24, tzinfo=timezone.utc)
    fs = FrameStrength(strength=Strength.weak, last_seen=now, due=now, last_evidence="")
    assert fs.evidence_count == 0
    assert fs.breadth == set()
    assert fs.unprompted_breadth == set()
    fs2 = FrameStrength(
        strength=Strength.strong,
        last_seen=now,
        due=now,
        last_evidence="x",
        evidence_count=3,
        breadth={"veldra:a", "veldra:b"},
        unprompted_breadth={"veldra:a", "veldra:b"},
    )
    assert fs2.evidence_count == 3 and fs2.breadth == {"veldra:a", "veldra:b"}
    assert fs2.unprompted_breadth == {"veldra:a", "veldra:b"}


def test_next_experience_spec_carries_experience_id_default_none():
    from retnovation.types import NextExperienceSpec, Regime

    s = NextExperienceSpec(target_frames=["f"], ledger_ref="veldra:x", regime=Regime.open_ended)
    assert s.experience_id is None
    s2 = NextExperienceSpec(
        target_frames=["f"],
        ledger_ref="veldra:x",
        regime=Regime.open_ended,
        experience_id="license_continuity",
    )
    assert s2.experience_id == "license_continuity"


def test_selection_receipt_shape():
    from datetime import datetime, timezone
    from retnovation.types import SelectionReceipt

    r = SelectionReceipt(
        frame="lead_with_what_you_refuse_to_do",
        problem="veldra:license_fork_risk",
        experience_id="license_continuity",
        drive="diagnose",
        scores={"uncertainty": 1.0, "retention": 0.0, "transfer": 0.0, "penalty": 1.0, "V": 0.5},
        runner_up_drive=None,
        margin=0.5,
        content_gaps=["commit_under_the_deadline"],
        created_at=datetime(2026, 6, 24, tzinfo=timezone.utc),
    )
    assert (
        r.drive == "diagnose"
        and r.scores["V"] == 0.5
        and r.content_gaps == ["commit_under_the_deadline"]
    )


def test_proposal_top_and_problem_menu_dedup():
    from retnovation.types import NextExperienceSpec, Proposal, Regime, SelectionReceipt
    from datetime import datetime, timezone

    now = datetime(2026, 6, 25, tzinfo=timezone.utc)

    def mk(frame, ref, eid):
        spec = NextExperienceSpec(
            target_frames=[frame], ledger_ref=ref, regime=Regime.open_ended, experience_id=eid
        )
        rc = SelectionReceipt(
            frame=frame,
            problem=ref,
            experience_id=eid,
            drive="diagnose",
            scores={"V": 0.5},
            runner_up_drive=None,
            margin=0.0,
            content_gaps=[],
            created_at=now,
        )
        return (spec, rc)

    p = Proposal(
        candidates=[
            mk("a", "veldra:p1", "e1"),
            mk("b", "veldra:p1", "e2"),
            mk("c", "veldra:p2", "e3"),
        ]
    )
    assert p.top[0].experience_id == "e1"
    menu = p.problem_menu()
    assert [s.ledger_ref for s, _ in menu] == ["veldra:p1", "veldra:p2"]  # deduped, rank order
    assert menu[0][0].experience_id == "e1"  # best candidate per problem kept


def test_core_candidate_and_verdict_roundtrip():
    from retnovation.types import CoreCandidate, CoreKind, CoreVerdict

    c = CoreCandidate(
        kind=CoreKind.demote, target="orphan_frame", rationale="no evidence, unreferenced"
    )
    v = CoreVerdict(candidate=c, outcome="rejected")
    assert v.candidate.kind is CoreKind.demote and v.outcome == "rejected"


def test_territory_map_defaults_are_decision_and_empty_conversion():
    """Additive wire fields (front-door conversion spec §2a): every existing fake and caller
    stays valid — verdict defaults to decision, conversion to empty."""
    from retnovation.types import TerritoryMap

    tm = TerritoryMap(ranked=["a"], confidence="high", reflection="r")
    assert tm.verdict == "decision"
    assert tm.conversion == ""
