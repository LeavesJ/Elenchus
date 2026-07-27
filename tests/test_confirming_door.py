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
    # A reply that TURNS is a correction or a position, never a yes. Erring here costs one re-map;
    # erring the other way forges an unagreed scenario.
    assert not _is_affirmative("yes but the real problem is the co-founder equity split")
    assert not _is_affirmative("I need to decide whether to sign by Friday")


def test_an_agreement_that_restates_the_question_is_still_agreement():
    # THE 2026-07-27 DOGFOOD, verbatim. The beat had his decision exactly right ("whether to
    # commit to launching the idea with your friend or take one of the internship or full-time
    # offers"). He answered this. The bare-only rule read it as a CORRECTION, so the correction
    # branch overwrote his situation WITH THIS SENTENCE (session_runner.py: `situation = value`,
    # then write_world), re-mapped territories on a string carrying no situation at all, and
    # forged a curated scenario about pricing an analytics tier. His real decision was destroyed
    # by his own agreement. Proven on his live db: web_world for the open sitting reads exactly
    # 'Yes, this is the decision I want to make.'
    assert _is_affirmative("Yes, this is the decision I want to make.")


def test_an_affirmative_lead_is_agreement_even_when_it_carries_words():
    # Leading with agreement cannot forge something unagreed — he said yes. The worst case is that
    # an elaboration is not folded in, which leaves his ORIGINAL situation standing. That is
    # strictly smaller harm than replacing it with a sentence that names no situation.
    for t in [
        "yes this is it",
        "Yeah, that's the one.",
        "correct, that is the decision I'm facing",
        "yep exactly that",
        "Sure, go ahead and build it.",
        "that's right, that's what I'm deciding",
    ]:
        assert _is_affirmative(t), t


def test_a_yes_that_turns_is_still_a_correction():
    # The safety property the bare-only rule existed to protect, kept. A yes followed by a pivot
    # carries new material the forge must map, so it must NOT short-circuit to agreement.
    for t in [
        "yes but the real problem is the co-founder equity split",
        "yeah, actually it's about pricing",
        "yes, although the real decision is whether to hire",
        "sure, except it's really about the co-founder",
        "ok but instead I want to talk about the internship",
        "right, however what I actually face is the funding round",
        "yes, not that one — the other offer",
    ]:
        assert not _is_affirmative(t), t


def test_an_ambiguous_opener_is_not_treated_as_a_lead():
    # The beat asks "say yes, or tell me what it actually is", so a reply that OPENS with a word
    # which is only sometimes agreement is answering the second half. "right now ..." and "go
    # with ..." are situations, not consent, and reading them as yes would forge the PREVIOUS
    # mapping — the very thing this gate exists to prevent. Those words stay valid as a whole
    # bare reply ("right", "go"); they are just not allowed to LEAD a longer sentence.
    for t in [
        "right now I'm deciding between the internship and the startup",
        "go with the internship offer I think",
        "continue building the thing with my friend",
        "proceed to the equity question instead of this one",
    ]:
        assert not _is_affirmative(t), t
    for t in ["right", "go", "continue", "proceed"]:
        assert _is_affirmative(t), t


def test_an_agreement_opener_that_reverses_on_its_last_word_is_a_correction():
    # "you got it wrong" opens with an agreement phrase and negates it at the end. A lead check
    # that only looked at the opener would read this as consent and forge the mapping he was
    # rejecting — a false yes, the one direction this gate must never fail in.
    for t in [
        "you got it wrong",
        "absolutely not",
        "definitely not that one",
        "precisely the opposite",
        "yes, you misunderstood me",
        "sure, nevermind that",
    ]:
        assert not _is_affirmative(t), t


def test_the_other_common_ways_of_saying_yes():
    # Each opener missing from the lead set does not merely cost a re-map — it REPLACES the
    # learner's situation with the sentence they agreed in. These are pinned for that reason.
    for t in [
        "you got it",
        "absolutely, that is the decision",
        "precisely that",
        "that is the one",
        "this is it, exactly",
        "confirmed, build it",
    ]:
        assert _is_affirmative(t), t


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


def test_agreement_never_rewrites_the_world():
    """The 2026-07-27 failure was not the predicate alone — it was what the correction branch does.

    `situation = value` followed by `write_world` REPLACES the learner's stated situation with
    whatever they just typed. That is right for a real correction and catastrophic for a
    misread agreement: on his live db, `web_world` for the open sitting ended up holding the
    literal string 'Yes, this is the decision I want to make.', his actual decision gone, and the
    forge then built a curated pricing scenario off a sentence naming no situation at all.

    So the ordering is load-bearing: the affirmative check must `break` BEFORE anything assigns to
    `situation`. Nothing downstream can recover a world that has already been overwritten.
    """
    body = _strip_comments(_fn(RUNNER.read_text(), "decide"))
    i = body.index("_is_affirmative(")
    assign = re.search(r"^\s*situation = value\s*$", body[i:], flags=re.M)
    assert assign, "the correction branch must still be readable as `situation = value`"
    between = body[i : i + assign.start()]
    assert re.search(r"^\s*break\s*$", between, flags=re.M), (
        "the affirmative check must break out of the confirm loop BEFORE `situation = value`. "
        "Agreement that falls through to the correction branch overwrites the learner's stated "
        "situation with the sentence they agreed in, and the forge then builds from nothing."
    )
    world_at = body.find("write_world", i)
    assert world_at > i + assign.start(), (
        "write_world must persist only a real correction, never an agreement"
    )


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


# ---- T4: the content-gap ledger --------------------------------------------------------------
# The door becomes an instrument as well as a surface. When a correction still cannot be served
# honestly, that is a CONTENT gap (five territories), not a user failure — and the mining pipeline
# should be told mechanically rather than left to infer it from dogfood memory.


def test_content_gap_is_recorded_with_her_words(tmp_path):
    import sqlite3
    from datetime import datetime, timezone

    from retnovation.web.sitting_store import SittingStore

    db = tmp_path / "g.db"
    s = SittingStore(str(db))
    s.log_content_gap(
        situation="how do I find my first client",
        mapped_eid="proof_before_promise",
        confidence="low",
        verdict="topic",
        corrected=True,
        now=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )
    c = sqlite3.connect(str(db))
    rows = c.execute(
        "SELECT situation, mapped_eid, confidence, verdict, corrected FROM web_content_gap"
    ).fetchall()
    c.close()
    assert rows == [("how do I find my first client", "proof_before_promise", "low", "topic", 1)]


def test_content_gap_is_inert_on_a_memory_store():
    # :memory: stores are inert by design; a gap write must not raise.
    from datetime import datetime, timezone

    from retnovation.web.sitting_store import SittingStore

    SittingStore(":memory:").log_content_gap(
        situation="x",
        mapped_eid="y",
        confidence="low",
        verdict="topic",
        corrected=False,
        now=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )


def test_gap_is_logged_only_when_the_correction_still_does_not_fit():
    # A correction that lands cleanly is NOT a gap — the mapper just needed her second phrasing.
    # Logging every correction would drown the content axis's signal in noise.
    body = _strip_comments(_fn(RUNNER.read_text(), "decide"))
    assert "log_content_gap" in body, "the no-branch must record the miss"
    seg = body[body.index("log_content_gap") - 900 : body.index("log_content_gap") + 400]
    assert "corrections" in seg, "a gap is only meaningful after a correction"
    assert "verdict" in seg and "confidence" in seg, (
        "only log when the re-map still does not fit honestly"
    )


def test_gap_is_recorded_before_the_forge_not_after():
    # The gap is about what the door COULD NOT serve. Recording it after the forge would describe
    # a scenario that was built anyway, which is a different (and misleading) fact.
    body = _strip_comments(_fn(RUNNER.read_text(), "decide"))
    assert body.index("log_content_gap") < body.rindex("sel = forge_selection(")


# ---- T6: the teeth ---------------------------------------------------------------------------


def test_every_front_door_forge_path_is_consented():
    # THE regression that matters. From the front door there must be exactly two ways to reach a
    # forge: a DOOR CLICK (she picked the problem herself — its own consent), or falling out of
    # the confirm loop. A third path is the 2026-07-24 defect returning.
    body = _strip_comments(_fn(RUNNER.read_text(), "decide"))
    after_ask = body[body.index("_FRONTDOOR_ASK") :]
    calls = re.findall(r"forge_selection\([^)]*\)", after_ask)
    assert calls, "expected forge paths to exist"
    for call in calls:
        consented = "clicked=True" in call or call == "forge_selection(eid, situation)"
        assert consented, f"unreviewed forge path from the front door: {call}"


def test_confirm_beat_carries_no_identifier_to_the_client():
    # L-13: the confirm beat is a NEW learner-facing surface, so it gets the same sweep as every
    # other one. `fit` is her own words; a ref/eid/frame code must never ride with it.
    from retnovation.web.app import _emit

    data = {"text": "Before I build it — here's the decision I'd put to you: the price you set."}
    out = _emit(object(), "say", data)
    blob = repr(out)
    for forbidden in ["gen:", "veldra:", "experience_id", "ledger_ref", "sitting_id", "frame_code"]:
        assert forbidden not in blob, forbidden
