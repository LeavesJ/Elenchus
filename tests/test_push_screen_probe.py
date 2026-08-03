"""Pure logic for probe 1 (the push screen's false-positive rate). No model call anywhere in
this file: `generate_push` is always a scripted double, so every assertion here is provable
offline."""

from __future__ import annotations

from elenchus.push_screen_probe import (
    PushTarget,
    Probe1Result,
    build_cases,
    old_bar_checks,
    push_targets,
    run_push_screen_probe,
    sample_positions,
)
from elenchus.types import Experience, Frame, Mode, Positions, Regime, Rubric, Trap


def _rubric(n_frames=2, n_traps=2):
    frames = [Frame(frame_code=f"frame_{i}", frame_detail=f"detail {i}") for i in range(n_frames)]
    traps = [Trap(trap_code=f"trap_{i}", trap_detail=f"trap detail {i}") for i in range(n_traps)]
    return Rubric(frames=frames, traps=traps, mode=Mode.genuinely_open, decision_frame=None)


def _exp(eid="exp_a", n_frames=2, n_traps=2):
    return Experience(
        experience_id=eid,
        prompt="A decision prompt.",
        rubric=_rubric(n_frames, n_traps),
        ledger_ref=f"veldra:{eid}",
        regime=Regime.open_ended,
    )


# ---------------------------------------------------------------------------
# push_targets / build_cases
# ---------------------------------------------------------------------------


def test_push_targets_gives_each_frame_a_stress_and_a_non_stress_push():
    rubric = _rubric(n_frames=1, n_traps=0)
    targets = push_targets(rubric)
    assert set(targets) == {
        PushTarget("frame", "frame_0", False),
        PushTarget("frame", "frame_0", True),
    }


def test_push_targets_gives_each_trap_only_a_non_stress_push():
    rubric = _rubric(n_frames=0, n_traps=1)
    targets = push_targets(rubric)
    assert targets == [PushTarget("trap", "trap_0", False)]


def test_push_targets_count_matches_two_times_frames_plus_traps():
    rubric = _rubric(n_frames=3, n_traps=2)
    # 3 frames * 2 (stress on/off) + 2 traps * 1 = 8, not e.g. 3+2=5 (proves stress duplication
    # actually happened, not just "one target per code").
    assert len(push_targets(rubric)) == 8


def test_build_cases_doubles_every_target_into_blind_and_positioned():
    exp = _exp(n_frames=1, n_traps=1)
    cases = build_cases([exp])
    # 1 frame -> 2 targets, 1 trap -> 1 target = 3 targets * 2 position modes = 6 cases.
    assert len(cases) == 6
    modes = {c.position_mode for c in cases}
    assert modes == {"blind", "positioned"}


def test_build_cases_covers_every_experience_passed_in():
    cases = build_cases([_exp("exp_a", 1, 0), _exp("exp_b", 1, 0)])
    ids = {c.experience_id for c in cases}
    assert ids == {"exp_a", "exp_b"}


# ---------------------------------------------------------------------------
# sample_positions
# ---------------------------------------------------------------------------


def test_sample_positions_is_empty_positions_on_an_empty_pool():
    assert sample_positions([]) == Positions()


def test_sample_positions_splits_on_angle_then_elsewhere_off_the_front_of_the_pool():
    pool = ["a", "b", "c", "d", "e", "f"]
    got = sample_positions(pool, on_angle_n=2, elsewhere_n=2)
    assert got.on_angle == ("a", "b")
    assert got.elsewhere == ("c", "d")


def test_sample_positions_tolerates_a_pool_smaller_than_requested():
    got = sample_positions(["a", "b"], on_angle_n=3, elsewhere_n=2)
    assert got.on_angle == ("a", "b")
    assert got.elsewhere == ()


# ---------------------------------------------------------------------------
# old_bar_checks -- validate_scene's four checks, run independently (not short-circuited)
# ---------------------------------------------------------------------------

_FW = ["swot", "first principles"]
_SCAFFOLD = ["classic case of", "this is a"]


def test_old_bar_checks_finds_nothing_on_an_ordinary_push():
    checks = old_bar_checks("Where do you draw the boundary here?", _rubric(), _FW, _SCAFFOLD)
    assert checks == {
        "named_framework": None,
        "frame_trap_code_leak": None,
        "type_hint_scaffold": None,
        "cosmetic_wrapper_word": None,
    }


def test_old_bar_checks_catches_a_named_framework():
    checks = old_bar_checks("Have you tried a SWOT here?", _rubric(), _FW, _SCAFFOLD)
    assert checks["named_framework"] == "swot"
    assert checks["frame_trap_code_leak"] is None


def test_old_bar_checks_catches_a_leaked_frame_code():
    rubric = _rubric(n_frames=1, n_traps=0)
    checks = old_bar_checks("You keep circling frame_0 without saying why.", rubric, _FW, _SCAFFOLD)
    assert checks["frame_trap_code_leak"] == "frame_0"
    assert checks["named_framework"] is None


def test_old_bar_checks_catches_a_scaffold_phrase():
    checks = old_bar_checks("This is a classic case of avoidance.", _rubric(), _FW, _SCAFFOLD)
    assert checks["type_hint_scaffold"] is not None


def test_old_bar_checks_catches_a_wrapper_word():
    checks = old_bar_checks("Does the extra time buy you a timer?", _rubric(), _FW, _SCAFFOLD)
    assert checks["cosmetic_wrapper_word"] == "timer"


def test_old_bar_checks_reports_every_check_independently_not_just_the_first_match():
    # Carries BOTH a named framework AND a wrapper word -- validate_scene's real code would
    # raise at the first (`label_leak`) and never evaluate the wrapper bar at all. This proves
    # the probe's four-way split does NOT short-circuit the way validate_scene itself does.
    checks = old_bar_checks(
        "Try a SWOT and see if that buys you a timer.", _rubric(), _FW, _SCAFFOLD
    )
    assert checks["named_framework"] == "swot"
    assert checks["cosmetic_wrapper_word"] == "timer"


# ---------------------------------------------------------------------------
# run_push_screen_probe -- pure orchestration over the Model protocol
# ---------------------------------------------------------------------------


class _ScriptedModel:
    """Returns push texts in the order build_cases enumerates them, and records exactly what
    each call received (proving blind vs positioned actually differ in what reaches the model)."""

    def __init__(self, texts):
        self._texts = list(texts)
        self.calls = []

    def generate_push(self, exp, kind, code, *, stress=False, positions=Positions(), steer=""):
        self.calls.append(
            {"exp": exp.experience_id, "kind": kind, "code": code, "positions": positions}
        )
        return self._texts.pop(0)


def test_run_push_screen_probe_calls_generate_push_once_per_case():
    exp = _exp(n_frames=1, n_traps=1)
    n_cases = len(build_cases([exp]))
    model = _ScriptedModel(["an ordinary push"] * n_cases)
    run_push_screen_probe(
        [exp],
        model,
        positions_pool=["real learner text"],
        framework_denylist=[],
        scaffold_denylist=[],
    )
    assert len(model.calls) == n_cases


def test_run_push_screen_probe_blind_cases_carry_empty_positions_positioned_cases_do_not():
    exp = _exp(n_frames=1, n_traps=0)
    n_cases = len(build_cases([exp]))
    model = _ScriptedModel(["push text"] * n_cases)
    run_push_screen_probe(
        [exp],
        model,
        positions_pool=["real learner text"],
        framework_denylist=[],
        scaffold_denylist=[],
    )
    blind_calls = [
        c for c, case in zip(model.calls, build_cases([exp])) if case.position_mode == "blind"
    ]
    positioned_calls = [
        c for c, case in zip(model.calls, build_cases([exp])) if case.position_mode == "positioned"
    ]
    assert all(c["positions"] == Positions() for c in blind_calls)
    assert all(c["positions"] != Positions() for c in positioned_calls)


def test_run_push_screen_probe_screens_each_returned_push_through_both_bars():
    exp = _exp(n_frames=1, n_traps=0)
    n_cases = len(build_cases([exp]))
    # First returned push leaks the frame code; the rest are ordinary.
    texts = ["You keep circling frame_0."] + ["an ordinary push"] * (n_cases - 1)
    model = _ScriptedModel(texts)
    records = run_push_screen_probe(
        [exp], model, positions_pool=[], framework_denylist=[], scaffold_denylist=[]
    )
    leaking = [r for r in records if r.push_text == "You keep circling frame_0."]
    assert len(leaking) == 1
    assert leaking[0].new_bar_hit == "frame_0"
    assert leaking[0].old_bar_checks["frame_trap_code_leak"] == "frame_0"
    ordinary = [r for r in records if r.push_text == "an ordinary push"]
    assert all(r.new_bar_hit is None for r in ordinary)
    assert all(not r.old_bar_rejected for r in ordinary)


# ---------------------------------------------------------------------------
# Probe1Result.summarize()
# ---------------------------------------------------------------------------


def test_probe1_summary_counts_new_and_old_bar_rejections_independently():
    from elenchus.push_screen_probe import PushScreenRecord

    records = [
        PushScreenRecord(
            experience_id="e",
            kind="frame",
            code="c1",
            stress=False,
            position_mode="blind",
            push_text="clean",
            new_bar_hit=None,
            old_bar_checks={
                "named_framework": None,
                "frame_trap_code_leak": None,
                "type_hint_scaffold": None,
                "cosmetic_wrapper_word": None,
            },
        ),
        PushScreenRecord(
            experience_id="e",
            kind="frame",
            code="c2",
            stress=False,
            position_mode="blind",
            push_text="swot push",
            new_bar_hit="swot",
            old_bar_checks={
                "named_framework": "swot",
                "frame_trap_code_leak": None,
                "type_hint_scaffold": None,
                "cosmetic_wrapper_word": None,
            },
        ),
        PushScreenRecord(
            experience_id="e",
            kind="trap",
            code="t1",
            stress=False,
            position_mode="positioned",
            push_text="wrapper push",
            new_bar_hit=None,  # new bar clears it, old bar does not
            old_bar_checks={
                "named_framework": None,
                "frame_trap_code_leak": None,
                "type_hint_scaffold": None,
                "cosmetic_wrapper_word": "timer",
            },
        ),
    ]
    result = Probe1Result(
        model_id="claude-opus-5",
        corpus_source="empty_fallback",
        positions_pool_size=0,
        framework_denylist=[],
        scaffold_denylist=[],
        records=records,
    )
    summary = result.summarize()
    assert summary.total == 3
    assert summary.new_bar_rejected == 1
    assert summary.new_bar_rejected_phrases == {"swot": 1}
    assert summary.old_bar_rejected == 2
    assert summary.old_bar_rejected_by_check == {"named_framework": 1, "cosmetic_wrapper_word": 1}
