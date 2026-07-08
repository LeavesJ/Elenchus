import os

import pytest

from retnovation.aim import aim, derive_core
from retnovation.experience import select_experience
from retnovation.model import AnthropicModel, IntakeClassification
from retnovation.types import FrameState, Regime, TrapState

_HAS_KEY = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


@pytest.mark.live
@pytest.mark.skipif(not _HAS_KEY, reason="no Anthropic credential in env")
def test_live_intake_on_selected_experience(tmp_path):
    """Smoke: a real Opus 4.8 call classifies every rubric code on a REAL selected experience.
    Setup mirrors test_voice_live._first_open_exp — the production selection path (store → propose →
    select), NOT a hand-built shortcut: the old spec=None 'fixed experience' call rotted silently
    when select_experience gained `corpus`, because this key-gated test never runs offline (L-22)."""
    from datetime import datetime, timezone

    from retnovation.cli import build_store
    from retnovation.content_loader import load_library, load_progression
    from retnovation.scheduler import propose_open_ended

    store = build_store(str(tmp_path / "live_intake.db"))
    try:
        core = derive_core(aim())
        now = datetime.now(timezone.utc)
        state, ledger, corpus = store.load_state(now), store.load_ledger(), store.load_corpus()
        exps = [e for e in load_library() if e.regime is Regime.open_ended]
        spec, _ = propose_open_ended(state, exps, load_progression(), now).problem_menu()[0]
        exp = select_experience(core, state, ledger, corpus, spec)
    finally:
        store.close()
    result = AnthropicModel().classify_intake(
        exp, "I would hold the original commitment because reversing it later costs more."
    )
    assert isinstance(result, IntakeClassification)
    assert set(result.frame_states) == {f.frame_code for f in exp.rubric.frames}
    assert set(result.trap_states) == {t.trap_code for t in exp.rubric.traps}
    assert all(isinstance(v, FrameState) for v in result.frame_states.values())
    assert all(isinstance(v, TrapState) for v in result.trap_states.values())


@pytest.mark.live
def test_live_grade_answer_smoke():
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("no ANTHROPIC_API_KEY")
    from retnovation.model import AnthropicModel
    from retnovation.types import CheckableQuestion, CheckType, Experience, CheckableSet

    q = CheckableQuestion(
        question_id="q1",
        concept="idempotency_under_retry",
        prompt="One word: a handler safe to apply twice is ____.",
        check_type=CheckType.model_graded,
        answer_key=["idempotent"],
        criteria="correct iff the answer means idempotent",
    )
    exp = Experience(
        experience_id="live",
        prompt="p",
        ledger_ref="veldra:x",
        regime=Regime.cs_technical,
        checkable=CheckableSet(questions=[q]),
    )
    grade = AnthropicModel().grade_answer(exp, q, "idempotent")
    assert isinstance(grade.correct, bool)


@pytest.mark.live
@pytest.mark.skipif(not _HAS_KEY, reason="no Anthropic credential in env")
def test_live_grade_sharper_smoke():
    from retnovation.model import AnthropicModel
    from retnovation.types import (
        Experience,
        Frame,
        Mode,
        Regime,
        Rubric,
        Trap,
    )

    exp = Experience(
        experience_id="live",
        prompt="p",
        ledger_ref="veldra:x",
        regime=Regime.open_ended,
        rubric=Rubric(
            frames=[
                Frame(
                    frame_code="protect_the_core_lane",
                    frame_detail="Keep the promise the core product makes to everyone.",
                    paired_trap="t",
                )
            ],
            traps=[Trap(trap_code="t", trap_detail="d")],
            mode=Mode.genuinely_open,
        ),
    )
    v = AnthropicModel().grade_sharper(
        exp,
        "frame",
        "protect_the_core_lane",
        "What do you give up by holding that line?",
        "you're right",
    )
    assert isinstance(v.sharper, bool)


# --- M2 novelty-gate honest 3-way: the §5.1 labeled bracket (fixtures ≠ Task-1 prompt exemplars) ---

_DISTINCT = {  # TIGHT END — clearly distinct from the 5 -> expect confident-novel
    "compete_on_a_metric_they_cant_copy": (
        "A price level is trivially matched; a pricing AXIS is not. Charge on a unit where an "
        "incumbent copying you must re-price their entire installed base and eat the cannibalization."
    ),
    "liquidity_is_local_not_global": (
        "Liquidity is felt inside a narrow slice (one category, one city, one size-band), not across "
        "the whole platform. A dense, matchable pocket beats subsidy sprayed thin over both sides."
    ),
    "separate_the_call_from_who_owns_the_call": (
        "Two decisions are stacked: the right staffing move, and whether you are the one who gets to "
        "make the call. Overruling spends authority capital far scarcer than one account's near-term "
        "risk."
    ),
}

_RESTATEMENTS = [  # OVER-ADMIT GUARD — topic-specialization restatements -> must NEVER be confident-novel
    "You're unsure whether to fire an underperforming VP now or give them another quarter. Name "
    "which way it fails if you're wrong, and default to the choice you can walk back.",
    "Before you negotiate the term sheet, state the governance and control provisions you will not "
    "sign under any valuation, up front.",
]


def _is_confident_novel(c):
    return c.restates_nearest is False and c.confidence == "high"


@pytest.mark.live
@pytest.mark.skipif(not _HAS_KEY, reason="no Anthropic credential in env")
def test_live_novelty_confident_novel_is_reachable():
    """Reachability + strangling test (spec §5.1 tight end): >=2/3 clear-distinct frames must reach
    confident-novel. 0/3 => the necessity bar is STRANGLING (loosen the prompt, §3A(b)), NOT the
    model failing symmetric confidence. This is the L-9 anti-synthetic-lie teeth — offline can't
    prove the confident-novel cell is reachable at all."""
    from retnovation.frame_gen_spike import _curated_frames

    m, curated = AnthropicModel(), _curated_frames()
    hits, seen = 0, []
    for code, detail in _DISTINCT.items():
        c = m.frame_convergence(detail, curated)
        seen.append(f"{code}: restates={c.restates_nearest} conf={c.confidence} near={c.nearest}")
        if _is_confident_novel(c):
            hits += 1
    assert hits >= 2, (
        "calibration collapse / necessity bar strangling: only "
        f"{hits}/3 clear-distinct frames reached confident-novel.\n" + "\n".join(seen)
    )


@pytest.mark.live
@pytest.mark.skipif(not _HAS_KEY, reason="no Anthropic credential in env")
def test_live_novelty_over_admit_guard():
    """Honesty guard (spec §5.1): a genuine restatement re-skinned onto a new subject must NEVER be
    confident-novel — that is the over-admit failure the reachability change re-arms."""
    from retnovation.frame_gen_spike import _curated_frames

    m, curated = AnthropicModel(), _curated_frames()
    for detail in _RESTATEMENTS:
        c = m.frame_convergence(detail, curated)
        assert not _is_confident_novel(c), (
            "over-admit re-armed: a topic-specialization restatement returned confident-novel "
            f"(nearest={c.nearest}, rationale={c.rationale})"
        )


@pytest.mark.live
@pytest.mark.skipif(not _HAS_KEY, reason="no Anthropic credential in env")
def test_live_novelty_convergent_and_boundary():
    """CONVERGENT: a verbatim paraphrase of a curated move restates it (true & high). BOUNDARY:
    design_for_the_teardown half-restates embed_credentials -> expect confidence=low (recorded)."""
    from retnovation.frame_gen_spike import _curated_frames

    m, curated = AnthropicModel(), _curated_frames()
    paraphrase = (
        "When a choice can't be amended after it ships, buy the cheap optionality now — the option "
        "to add it later won't exist."  # a paraphrase of embed_credentials_as_a_list
    )
    c = m.frame_convergence(paraphrase, curated)
    assert c.restates_nearest is True and c.confidence == "high", (
        f"verbatim paraphrase not caught as convergent: {c}"
    )
    assert c.nearest == "embed_credentials_as_a_list"

    boundary = (
        "Build the feature so it degrades gracefully when the rules tighten, rather than requiring a "
        "full unwind that strands customers."  # design_for_the_teardown
    )
    b = m.frame_convergence(boundary, curated)
    print(f"[boundary] restates={b.restates_nearest} conf={b.confidence} rationale={b.rationale}")
    assert not _is_confident_novel(b), (
        "the boundary frame (half-restates embed_credentials) came back confident-novel — inspect "
        f"whether the bar is too loose: {b}"
    )
