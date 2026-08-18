from datetime import datetime, timedelta, timezone

from elenchus.aim import aim, derive_core
from elenchus.assessment.judgment_loop import assess
from elenchus.cli import build_store
from elenchus.content_loader import load_experience, load_library, load_progression, load_rubric
from elenchus.generator import angle_count
from elenchus.model import FakeModel, IntakeClassification, ResponseClassification
from elenchus.orchestration import run_session
from elenchus.persistence import Store
from elenchus.policy import select_next
from elenchus.run_elicitation import load_probe_experience
from elenchus.state import derive_due
from elenchus.surface import format_problem_menu
from elenchus.types import (
    FrameState,
    FrameStrength,
    LearnerState,
    Outcome,
    Proposal,
    Regime,
    Selection,
    Strength,
    TrapState,
    Work,
)

EMBED = "embed_credentials_as_a_list"
P1 = "veldra:embedded_anchor_lock_in"
P2 = "veldra:license_fork_risk"  # continuity_lock_in, EMBED's home
LEAD = "lead_with_what_you_refuse_to_do"
R1 = "veldra:midrollout_contract_boundary"  # license_continuity, LEAD's home (split from license_fork_risk)
R2 = "veldra:concentrated_market_pricing_power"
NOW1 = datetime(2026, 6, 26, tzinfo=timezone.utc)


def _closed(n=4):
    return [
        ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
        for _ in range(n)
    ]


def _steer(experience_id):
    def decide(proposal):
        top_spec, top_receipt = proposal.top
        for spec, receipt in proposal.candidates:
            if spec.experience_id == experience_id:
                outcome = Outcome.accepted if spec is top_spec else Outcome.redirected
                return Selection(
                    proposed_receipt=top_receipt,
                    chosen_spec=spec,
                    chosen_receipt=receipt,
                    outcome=outcome,
                )
        raise AssertionError(f"{experience_id} not in proposal")

    return decide


def _model_for(frames_present, traps, probed_responses):
    intake = IntakeClassification(
        frame_states={
            f: (FrameState.present_reasoned if f in frames_present else FrameState.absent)
            for f in (set(frames_present) | set(probed_responses))
        },
        trap_states={t: TrapState.not_tripped for t in traps},
    )
    return FakeModel(intake, {code: _closed() for code in probed_responses})


def _present(exp):
    return Work(
        opening="reasoning that already holds the move unprompted", respond=lambda push: "mechanism"
    )


def test_continuity_lock_in_clears_the_gate():
    r = load_rubric("continuity_lock_in")
    assert [f.frame_code for f in r.frames] == ["embed_credentials_as_a_list"]
    assert len(r.traps) == 3
    assert angle_count(r) == 8  # 1 frame + 3 traps + 0 binding + 4 dims = floor


def test_session1_credits_embed_unprompted_through_the_real_loop():
    # embed present_reasoned at intake; choose_failure absent (so the loop WILL probe it). If embed were
    # ever probed, it would not be in reasoned_unprompted. This proves the unprompted credit is earned by
    # the real not-probed path, not injected. irreversible_anchor's decision_frame is pinned to
    # choose_the_failure_default_deliberately (living sitting §2d) precisely so the DF probe targets
    # choose_failure and embed KEEPS its unprompted channel here — this test is that channel's teeth.
    exp = load_experience("irreversible_anchor")
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
    model = FakeModel(intake, {"choose_the_failure_default_deliberately": _closed()})
    work = Work(
        opening="reasoning that already holds the anchor move", respond=lambda push: "mechanism"
    )
    a = assess(exp, work, model)
    probed = {p.target_code for p in a.trajectory}
    assert "embed_credentials_as_a_list" in a.reasoned_unprompted
    assert (
        "embed_credentials_as_a_list" not in probed
    )  # never probed -> the read is genuinely unprompted


def test_two_session_run_reaches_strong_through_the_real_path(tmp_path):
    # The DF matrix (living sitting §2d) closed embed's SECOND unprompted home — production
    # continuity_lock_in force-probes embed (the named, accepted cost), so embed can no longer
    # mint strong through two unprompted contexts. The strong arc is therefore pinned on
    # lead_with_what_you_refuse_to_do: the one frame with two non-DF homes on distinct refs
    # (license_continuity -> R1, decision_under_stakes -> R2). Same engine path as before:
    # unprompted at intake on two distinct refs -> strong -> the 30-day savings effect.
    db = tmp_path / "sp3.db"
    store = build_store(db)
    core = derive_core(aim())
    lib, cfg = load_library(), load_progression()

    # --- session 1: license_continuity. lead present_reasoned (unprompted); the DF
    # (commit_under_the_deadline) and protect_the_core_lane absent (probed, closed).
    s1_model = _model_for(
        frames_present=[LEAD],
        traps=["scope_creep_to_please", "erode_core_for_one_customer", "commit_without_a_tripwire"],
        probed_responses={"commit_under_the_deadline", "protect_the_core_lane"},
    )
    state1, _ = run_session(
        store,
        core,
        s1_model,
        NOW1,
        regime=Regime.open_ended,
        present=_present,
        decide=_steer("license_continuity"),
        decide_core=lambda c: [],
    )
    assert state1.frames[LEAD].strength is Strength.forming
    assert state1.frames[LEAD].breadth == {R1}
    assert state1.frames[LEAD].unprompted_breadth == {R1}
    # session-1 learner surface withholds the frame (both sessions credit an unprompted read)
    assert LEAD not in format_problem_menu(Proposal(candidates=select_next(state1, lib, cfg, NOW1)))

    # --- ordering pin at the worst-case forming edge (+7d), derived from the REAL post-S1 state ---
    now2 = NOW1 + timedelta(days=7)
    ranked = select_next(state1, lib, cfg, now2)
    top_spec, top_rcpt = ranked[0]
    assert top_spec.experience_id == "decision_under_stakes"
    assert top_rcpt.frame == LEAD and top_rcpt.drive == "deploy"
    # S1 banks three forming frames the same day, so the two deploy candidates (lead ->
    # decision_under_stakes, protect -> proof_before_promise) TIE on V (1.83) and the policy's
    # deterministic order puts the LEAD deployment first; deploy dominates diagnose at rank 2.
    assert ranked[0][1].scores["V"] == ranked[1][1].scores["V"]
    assert ranked[0][1].scores["V"] > ranked[2][1].scores["V"]
    assert LEAD not in format_problem_menu(
        Proposal(candidates=ranked)
    )  # session-2 surface withholds too

    # --- session 2 at +7d on decision_under_stakes; lead present_reasoned (unprompted) -> strong;
    # the DF (choose_the_failure_default_deliberately) absent (probed, closed).
    s2_model = _model_for(
        frames_present=[LEAD],
        traps=["assumed_the_happy_path", "scope_creep_to_please"],
        probed_responses={"choose_the_failure_default_deliberately"},
    )
    state2, _ = run_session(
        store,
        core,
        s2_model,
        now2,
        regime=Regime.open_ended,
        present=_present,
        decide=_steer("decision_under_stakes"),
        decide_core=lambda c: [],
    )
    assert state2.frames[LEAD].strength is Strength.strong
    assert state2.frames[LEAD].unprompted_breadth == {R1, R2}
    # post-strong savings effect: due interval jumps to 30 days
    fs = Store(db).load_state(now2).frames[LEAD]
    assert derive_due(
        fs.evidence_count, fs.unprompted_breadth, fs.last_seen
    ) == fs.last_seen + timedelta(days=30)


def test_license_continuity_is_never_shadowed_by_continuity_lock_in():
    """THE SHADOW WAS THE BUG, AND THIS TEST USED TO ASSERT IT AS A FEATURE.

    Its earlier form was `test_shadow_on_license_continuity_self_resolves`, and it asserted that
    ONE `ledger_ref` (`P2`) resolved to `continuity_lock_in` on a fresh state and to
    `license_continuity` once `embed` went strong -- describing that as a cascade that "self
    resolves". It only ever did that because the two experiences SHARED
    `veldra:license_fork_risk` and `Proposal.problem_menu()` dedupes by ref, keeping one candidate
    per owned problem. The "shadow" was `license_continuity` being silently unreachable from the
    menu, which is one of the three live defects the ref split fixed. A docstring explaining why a
    defect is desirable is the most expensive kind of wrong comment, because it stops the next
    reader from looking.

    They are two owned problems, so neither shadows the other and both are offerable from any
    state. `commit_under_the_deadline` is `license_continuity`'s only home, and it no longer has
    to wait for another problem's frame to mature before it can be reached."""
    lib, cfg = load_library(), load_progression()

    def menu_ids(state):
        menu = Proposal(candidates=select_next(state, lib, cfg, NOW1)).problem_menu()
        return {s.experience_id for s, _ in menu}

    fresh = menu_ids(LearnerState())
    assert {"continuity_lock_in", "license_continuity"} <= fresh, (
        f"one problem is shadowing the other on a fresh state: {sorted(fresh)}"
    )

    strong = LearnerState(
        frames={
            EMBED: FrameStrength(
                strength=Strength.strong,
                last_seen=NOW1,
                due=NOW1,
                last_evidence="x",
                evidence_count=2,
                breadth={P1, P2},
                unprompted_breadth={P1, P2},
            )
        }
    )
    assert {"continuity_lock_in", "license_continuity"} <= menu_ids(strong)

    # and they occupy distinct menu slots, which is the property the shared ref destroyed
    menu = Proposal(candidates=select_next(LearnerState(), lib, cfg, NOW1)).problem_menu()
    refs = [s.ledger_ref for s, _ in menu]
    assert len(refs) == len(set(refs)), "problem_menu emitted two candidates for one owned problem"


def test_loop_guardian_embed_unprompted_on_continuity_lock_in():
    # Loop-side equivalence guardian (P2 analogue of test_session1_...): embed present_reasoned at
    # intake on the isolate; one trap tripped so the loop ACTUALLY runs a probe on another target;
    # embed must still land in reasoned_unprompted and never be probed. A judgment-loop edit that
    # lets a present-at-intake frame be probed/lowered turns this red — the enforcement the
    # rubric-shaped guard (assert_intake_equivalence) structurally cannot provide. Runs on the
    # DF-free variant (living sitting §2d): production continuity_lock_in force-probes embed by
    # design now, and the equivalence instrument lives on content/elicitation/'s variants.
    exp = load_probe_experience("continuity_lock_in")
    intake = IntakeClassification(
        frame_states={"embed_credentials_as_a_list": FrameState.present_reasoned},
        trap_states={
            "shipped_the_one_shot_term": TrapState.tripped,
            "over_built_the_escape_hatch": TrapState.not_tripped,
            "treated_the_shipped_choice_as_amendable": TrapState.not_tripped,
        },
    )
    model = FakeModel(intake, {"shipped_the_one_shot_term": _closed()})
    work = Work(opening="reasoning that already holds the move", respond=lambda push: "mechanism")
    a = assess(exp, work, model)
    probed = {p.target_code for p in a.trajectory}
    assert "embed_credentials_as_a_list" in a.reasoned_unprompted
    assert "embed_credentials_as_a_list" not in probed
    assert (
        "shipped_the_one_shot_term" in probed
    )  # the loop did run a probe — guardian is non-trivial
