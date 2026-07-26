"""The confirm-before-commit door (Spec-3 §4).

The 2026-07-24 dogfood: the mapper read a go-to-market question as a commitment decision and
forged a scenario; the founder's correction ("no no like how to get my first client") was
absorbed as evasion because voice.gate only asks *is this substantive?*. The sitting then
converged, writing a permanent memory of a decision he never made.

The fix is a gate BEFORE the forge, not an exit inside the loop (L-5: the loop stays sealed —
the gate fires while no scenario exists, so there is no effort to evade yet)."""

from retnovation.web.session_runner import _is_affirmative


def test_plain_agreement_is_affirmative():
    for t in ["yes", "Yes", "yep", "yeah", "correct", "that's it", "right", "ok", "go", "sure"]:
        assert _is_affirmative(t), t


def test_a_correction_is_not_affirmative():
    for t in [
        "no no like how to get my first client",  # the founder's actual words
        "not quite, it's about pricing",
        "no",
        "that's not it",
        "actually I meant the hiring decision",
    ]:
        assert not _is_affirmative(t), t


def test_a_substantive_reply_is_not_affirmative():
    # Anything with real content is a correction or a position, never a bare yes. Erring here
    # costs one re-map; erring the other way forges an unagreed scenario.
    assert not _is_affirmative("yes but the real problem is the co-founder equity split")
    assert not _is_affirmative("I need to decide whether to sign by Friday")


def test_empty_and_whitespace_are_not_affirmative():
    for t in ["", "   ", "\n"]:
        assert not _is_affirmative(t)


import re  # noqa: E402
from pathlib import Path  # noqa: E402

RUNNER = Path("src/retnovation/web/session_runner.py")


def _fn(src: str, name: str) -> str:
    """Extract a def body by indentation — the runner's decide() is nested inside start()."""
    i = src.index("def " + name)
    lines = src[i:].splitlines(True)
    base = len(lines[0]) - len(lines[0].lstrip())
    out = [lines[0]]
    for ln in lines[1:]:
        if ln.strip() and (len(ln) - len(ln.lstrip())) <= base:
            break
        out.append(ln)
    return "".join(out)


def _strip_comments(src: str) -> str:
    """A guard a commented-out fix can still pass is not a guard."""
    return re.sub(r"^\s*#[^\n]*$", "", src, flags=re.M)


def test_confirm_beat_precedes_the_forge():
    # The whole point: no scenario exists until the learner agrees. If the confirm beat ever
    # lands AFTER forge_selection, a false memory can be written again.
    body = _strip_comments(_fn(RUNNER.read_text(), "decide"))
    assert "_CONFIRM_COPY" in body, "decide() must serve the confirm beat"
    confirm_at = body.index("_CONFIRM_COPY")
    forge_at = body.rindex("sel = forge_selection(")
    assert confirm_at < forge_at, "the confirm beat must run BEFORE the forge"


def test_confirm_beat_screens_fit_before_serving_it():
    # L-13: fit is model-authored learner-facing text and rides only after the egress screen.
    body = _strip_comments(_fn(RUNNER.read_text(), "decide"))
    seg = body[body.index("_CONFIRM_COPY") - 900 : body.index("_CONFIRM_COPY") + 400]
    assert "egress_safe_reply" in seg, "the confirm beat must egress-screen fit before serving"


def test_confirm_copy_never_deflects_and_never_grades():
    from retnovation.web.session_runner import _CONFIRM_COPY

    low = _CONFIRM_COPY.lower()
    assert "out of scope" not in low  # founder constraint, structurally unservable
    for banned in ["good", "well done", "correct answer", "score", "you should"]:
        assert banned not in low, banned
    assert "{desc}" in _CONFIRM_COPY, "the beat must name the decision in her own words"


def test_same_world_continue_skips_the_confirm_beat():
    # A queued Continue with a persisted world is a continuation, not a fresh mapping — asking
    # again there is an interrogation. That path returns before the beat.
    body = _strip_comments(_fn(RUNNER.read_text(), "decide"))
    early = body[: body.index("_FRONTDOOR_ASK")]
    assert "return forge_selection(target, world, focus=focus)" in early
    assert "_CONFIRM_COPY" not in early


def test_the_correction_cap_never_forges_silently():
    # THE REVIEW FINDING (Critical). The cap used to `break` straight to forge_selection, so two
    # corrections produced a scenario the user never agreed to — the 2026-07-24 defect deferred by
    # two turns, not fixed. Spec §4b requires falling through to the honest-fit beat, which names
    # the stretch in her own words and keeps the doors answerable.
    body = _strip_comments(_fn(RUNNER.read_text(), "decide"))
    cap = body.index("corrections >= _MAX_CONFIRM_CORRECTIONS")
    forge = body.rindex("sel = forge_selection(")
    between = body[cap:forge]
    assert "honest_fit_beat()" in between, (
        "past the correction cap the composer must serve the honest-fit beat before forging, "
        "never fall straight through to the forge"
    )


def test_the_remap_precedes_the_cap_check():
    # The other review finding: if the cap short-circuits the re-map, the forge builds her LATEST
    # words under a rubric chosen for her PREVIOUS ones — one scenario from two different inputs.
    body = _strip_comments(_fn(RUNNER.read_text(), "decide"))
    seg = body[body.index("corrections += 1") :]
    remap = seg.index("model.map_territories(")
    cap = seg.index("corrections >= _MAX_CONFIRM_CORRECTIONS")
    assert remap < cap, "the re-map must run BEFORE the cap check so eid always matches situation"


def test_honest_fit_beat_is_one_implementation_shared_by_both_callers():
    # L-31: the low-confidence path and the cap path must not drift apart. One definition, two
    # call sites — a second inlined copy is how the two silently diverge.
    body = _strip_comments(_fn(RUNNER.read_text(), "decide"))
    assert body.count("def honest_fit_beat(") == 1
    # count CALL sites only — the def line contains the same substring
    assert len(re.findall(r"(?<!def )honest_fit_beat\(\)", body)) == 2
