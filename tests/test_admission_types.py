import pytest
from pydantic import ValidationError

from elenchus.types import (
    AdmissionRecord,
    AdmittedAs,
    Gates,
    MinedCandidate,
    Provenance,
    ScreenSummary,
)


def _screen(verdict, action):
    return ScreenSummary(
        verdict=verdict,
        screen_action=action,
        mean_distinguishability=2.0,
        mean_preference=1.0,
        framed_preferred_count=2,
        data_ref="x",
    )


def _all_pass_gates(orthogonality="pass"):
    return Gates(
        surface_independence="pass",
        atomicity="pass",
        orthogonality=orthogonality,
        falsifiable_application="pass",
        trainable_cognition="pass",
    )


def test_mined_candidate_to_candidate_frame():
    mc = MinedCandidate(
        frame_code="build_more_to_own_less",
        frame_detail="d",
        injection="INJ",
        posture="founder_ceo",
        hypothesis="model minimizes scope",
        nearest_sibling="protect_the_core_lane",
        separating_artifact="net-component ledger",
        provenance=Provenance(source_type="owned", pointer="EXECLOG EX-028"),
    )
    cf = mc.to_candidate_frame()
    assert (cf.frame_code, cf.frame_detail, cf.injection) == ("build_more_to_own_less", "d", "INJ")


def test_screen_summary_from_result_and_marginal_lift_is_derived():
    from elenchus.types import LiftResult, ScenarioVerdict

    lr = LiftResult(
        frame_code="f",
        scenarios=[
            ScenarioVerdict(
                scenario_id="s1", injection_expressed=True, distinguishability=2, preference=1
            ),
            ScenarioVerdict(
                scenario_id="s2", injection_expressed=True, distinguishability=2, preference=1
            ),
        ],
        theta_dist=1,
        min_scenarios=2,
    )
    summary = ScreenSummary.from_result(lr, data_ref="data/lift/screen_f.json")
    assert summary.verdict == lr.verdict == "lift"
    assert summary.mean_preference == lr.mean_preference
    assert summary.framed_preferred_count == lr.framed_preferred_count == 2
    assert summary.data_ref == "data/lift/screen_f.json"

    rec = AdmissionRecord(
        frame_code="f",
        posture="founder_ceo",
        provenance=Provenance(source_type="owned", pointer="EXECLOG EX-028"),
        screen=_screen("lift", "surface"),
        gates=_all_pass_gates(),
        nearest_sibling="protect_the_core_lane",
        separating_artifact="artifact",
        decision="admit_provisional",
        rationale="lifts on both",
        admitted_as=AdmittedAs(experience_id="exp", ledger_ref="veldra:slug"),
    )
    assert rec.marginal_lift == "pass"  # derived from screen.verdict, not stored


def test_auto_kill_screen_forces_reject():
    with pytest.raises(ValidationError):
        AdmissionRecord(
            frame_code="f",
            posture="founder_ceo",
            provenance=Provenance(pointer="EXECLOG EX-028"),
            screen=_screen("negative_lift", "auto_kill"),
            gates=_all_pass_gates(),
            decision="admit_provisional",
            rationale="x",
            admitted_as=AdmittedAs(experience_id="exp", ledger_ref="veldra:slug"),
            nearest_sibling="s",
            separating_artifact="a",
        )


def test_reject_requires_rationale():
    with pytest.raises(ValidationError):
        AdmissionRecord(
            frame_code="f",
            posture="founder_ceo",
            provenance=Provenance(pointer="BIZLOG 2026-04-16"),
            screen=_screen("null", "auto_kill"),
            gates=_all_pass_gates(),
            decision="reject",
            rationale="",
        )


def test_admit_requires_separating_artifact_and_admitted_as():
    base = dict(
        frame_code="f",
        posture="founder_ceo",
        provenance=Provenance(pointer="EXECLOG EX-028"),
        screen=_screen("lift", "surface"),
        gates=_all_pass_gates(),
        decision="admit_provisional",
        rationale="lifts",
        nearest_sibling="s",
    )
    with pytest.raises(ValidationError):  # missing separating_artifact + admitted_as
        AdmissionRecord(**base, separating_artifact="", admitted_as=None)


def test_subframe_requires_subframe_orthogonality_and_sibling():
    with pytest.raises(ValidationError):  # orthogonality not "subframe"
        AdmissionRecord(
            frame_code="f",
            posture="founder_ceo",
            provenance=Provenance(pointer="EXECLOG EX-028"),
            screen=_screen("lift", "surface"),
            gates=_all_pass_gates(orthogonality="pass"),
            decision="file_as_subframe",
            rationale="merge",
            nearest_sibling="s",
            separating_artifact="a",
        )
    ok = AdmissionRecord(
        frame_code="f",
        posture="founder_ceo",
        provenance=Provenance(pointer="EXECLOG EX-028"),
        screen=_screen("lift", "surface"),
        gates=_all_pass_gates(orthogonality="subframe"),
        decision="file_as_subframe",
        rationale="merge under sibling",
        nearest_sibling="lead_with_what_you_refuse_to_do",
        separating_artifact="none found",
    )
    assert ok.gates.orthogonality == "subframe"


def test_screen_summary_rounds_means_to_2dp():
    # n=3 means are thirds; the committable audit record should carry clean 2dp, not float noise.
    s = ScreenSummary(
        verdict="lift",
        screen_action="surface",
        mean_distinguishability=2.3333333333333335,
        mean_preference=-0.3333333333333333,
        framed_preferred_count=3,
        data_ref="x",
    )
    assert s.mean_distinguishability == 2.33
    assert s.mean_preference == -0.33


def test_reject_allows_omitted_gates():
    # A screen-reject whose human gates were never walked may omit gates entirely.
    rec = AdmissionRecord(
        frame_code="f",
        posture="founder_ceo",
        provenance=Provenance(pointer="BIZLOG 2026-05-28"),
        screen=_screen("mixed", "surface"),
        gates=None,
        decision="reject",
        rationale="net-dispreferred (1/3); control wins on substance — insufficient necessity",
    )
    assert rec.gates is None and rec.decision == "reject"


def test_admit_requires_gates_present():
    with pytest.raises(ValidationError):
        AdmissionRecord(
            frame_code="f",
            posture="founder_ceo",
            provenance=Provenance(pointer="ADR-001"),
            screen=_screen("lift", "surface"),
            gates=None,
            decision="admit_provisional",
            rationale="lifts",
            nearest_sibling="s",
            separating_artifact="a",
            admitted_as=AdmittedAs(experience_id="e", ledger_ref="veldra:s"),
        )


def test_subframe_requires_gates_present():
    with pytest.raises(ValidationError):
        AdmissionRecord(
            frame_code="f",
            posture="founder_ceo",
            provenance=Provenance(pointer="ADR-001"),
            screen=_screen("lift", "surface"),
            gates=None,
            decision="file_as_subframe",
            rationale="merge",
            nearest_sibling="s",
            separating_artifact="a",
        )
