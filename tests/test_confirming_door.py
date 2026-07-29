"""The confirm-before-commit door (Spec-3 §4).

The 2026-07-24 dogfood: the mapper read a go-to-market question as a commitment decision and
forged a scenario; the founder's correction ("no no like how to get my first client") was
absorbed as evasion because voice.gate only asks *is this substantive?*. The sitting then
converged, writing a permanent memory of a decision he never made.

The fix is a gate BEFORE the forge, not an exit inside the loop (L-5: the loop stays sealed —
the gate fires while no scenario exists, so there is no effort to evade yet)."""

from elenchus.web.session_runner import _is_affirmative, _is_bare_rejection


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


def test_a_bare_rejection_names_nothing():
    # The beat's own last sentence is "Say yes, or tell me what it actually is", so "no" is the
    # canonical short answer — and it used to be written into web_world AS the learner's
    # situation. Anything here must never replace a world.
    for t in [
        "no",
        "No.",
        "NOPE",
        "nah",
        "not really",
        "not quite",
        "that's not it",
        "thats not it",
        "that is not it",
        "no, not that one",
        "none of these",
        "neither",
        "no it isn't",
        "wrong",
        "that's wrong",
        "stop",
        "cancel",
        "nevermind",
        "no way",
        "not at all",
        "nope, not that",
    ]:
        assert _is_bare_rejection(t), t


def test_a_rejection_that_names_something_is_a_correction():
    # The founder's own live path leads with a rejection and carries a whole situation. Reading
    # it as contentless would throw away the correction the door exists to serve — so the
    # predicate requires that NOTHING substantive survives the rejection words.
    for t in [
        "no no like how to get my first client",
        "not quite, it's about pricing",
        "no, the co-founder equity split",
        "that's not it — I mean the hiring decision",
        "not the money, the timing",
        "no, whether to sign by Friday",
    ]:
        assert not _is_bare_rejection(t), t


def test_a_short_reply_with_no_rejection_word_is_never_bare():
    # A rejection word is REQUIRED. Otherwise a terse correction ("pricing") would be read as
    # contentless and silently discarded — the opposite failure, and just as destructive.
    for t in ["pricing", "the equity split", "", "   ", "yes", "that's it", "one of these"]:
        assert not _is_bare_rejection(t), t


import re  # noqa: E402
from pathlib import Path  # noqa: E402

RUNNER = Path("src/elenchus/web/session_runner.py")


def _fn(src: str, name: str) -> str:
    """Extract a def body by indentation — the runner's decide() is nested inside start().

    The base indent is measured from the START OF THE DEF'S LINE, not from the `def` keyword:
    slicing at the keyword makes every nested def look top-level, so the extraction ran to EOF
    and every guard below silently scanned the whole file. `test_the_remap_precedes_the_cap_check`
    was the one that noticed — it matched a `map_territories(` call 63k characters past the
    function it was guarding."""
    i = src.index("def " + name)
    start = src.rindex("\n", 0, i) + 1
    lines = src[start:].splitlines(True)
    base = i - start
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
    # Scope to the confirm loop itself: an assignment ANYWHERE above the affirmative check erases
    # the world, so the region that must stay clean is the loop head, not "somewhere after".
    loop = body[body.index("corrections = 0") : body.index("sel = forge_selection(")]
    aff = loop.index("_is_affirmative(")
    brk = re.search(r"^\s*break\s*$", loop[aff:], flags=re.M)
    assert brk, "the affirmative check must break out of the confirm loop"
    head = loop[: aff + brk.start()]
    assert not re.search(r"^\s*situation\s*=", head, flags=re.M), (
        "nothing may assign to `situation` before the affirmative check breaks. Agreement that "
        "reaches the correction branch overwrites the learner's stated situation with the "
        "sentence they agreed in, and the forge then builds from a string naming no situation."
    )
    assert "write_world" not in head, (
        "write_world must persist only a real correction, never an agreement — a world overwritten "
        "here is gone from durable state, not merely from this turn"
    )
    assert re.search(r"^\s*situation = value\s*$", loop, flags=re.M), (
        "the correction branch must still re-map on her words"
    )


def test_confirm_beat_precedes_the_forge():
    # The whole point: no scenario exists until the learner agrees. If the confirm beat ever
    # lands AFTER forge_selection, a false memory can be written again.
    body = _strip_comments(_fn(RUNNER.read_text(), "decide"))
    assert "_CONFIRM_COPY" in body, "decide() must serve the confirm beat"
    confirm_at = body.index("_CONFIRM_COPY")
    forge_at = body.rindex("sel = forge_selection(")
    assert confirm_at < forge_at, "the confirm beat must run BEFORE the forge"


def test_the_served_fit_is_screened_at_one_seam_and_read_in_one_place():
    # L-13: fit is model-authored learner-facing text and rides only after the egress screen. The
    # screen lives in `screened_desc` now — one model call per MAP rather than one per serve
    # (residual 3, 2026-07-28) — so the pin follows it. Both beats that carry `desc` take it from
    # that seam; an inlined second copy is how the screen silently drops off one of them.
    body = _strip_comments(_fn(RUNNER.read_text(), "decide"))
    assert body.count("def screened_desc(") == 1
    # The read and the screen are the same two lines, so "screened before it rides" is structural
    # rather than a claim about ordering: there is nowhere else that reads the mapper's fit.
    assert body.count("fit_text = tmap.fit.strip()") == 1
    assert body.count("if fit_text and voice.egress_safe_reply(model, base, fit_text):") == 1
    assert len(re.findall(r"tmap\.fit", body)) == 1, "the mapper's fit is read at the seam only"
    assert body.count("desc = screened_desc()") == 2  # the confirm beat and the honest-fit beat
    assert "_CONFIRM_COPY.format(desc=desc)" in body and "fit_copy.format(desc=desc)" in body


def test_confirm_copy_never_deflects_and_never_grades():
    from elenchus.web.session_runner import _CONFIRM_COPY

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
    remap = seg.index("remap(")
    cap = seg.index("corrections >= _MAX_CONFIRM_CORRECTIONS")
    assert remap < cap, "the re-map must run BEFORE the cap check so eid always matches situation"


def test_every_front_door_mapping_goes_through_one_seam():
    # Three sites map her words now — the intake loop, the confirm beat's correction, and a
    # correction that turns out to be a topic. The hallucination-proof ranking fallback and the
    # `mapped_rank` bank must fire at ALL of them: a site that maps without banking leaves the
    # doors answering for the territory of a PREVIOUS mapping. One seam is how that stays true.
    body = _strip_comments(_fn(RUNNER.read_text(), "decide"))
    door = body[body.index("_FRONTDOOR_ASK") : body.rindex("sel = forge_selection(")]
    assert door.count("def remap(") == 1
    assert len(re.findall(r"model\.map_territories\(", door)) == 1, (
        "every front-door mapping must go through the one remap seam"
    )
    assert len(re.findall(r"(?<!def )remap\(", door)) == 3  # intake, correction, topic-correction


def test_conversion_beat_is_one_implementation_shared_by_both_callers():
    # L-31 again, on the OTHER learner-facing beat. The intake loop and the confirm loop both
    # serve the conversion; a second inlined copy is how the egress screen (or the forbidden
    # "out of scope" filter) silently drifts on one of the two surfaces but not the other.
    body = _strip_comments(_fn(RUNNER.read_text(), "decide"))
    assert body.count("def conversion_beat(") == 1
    assert len(re.findall(r"(?<!def )conversion_beat\(\)", body)) == 2


def test_a_topic_correction_asks_instead_of_asserting():
    # The 2026-07-26 residual. Inside the confirm loop the conversion beat must come AFTER the
    # affirmative break (an agreement can never trigger it) and AFTER the cap check (the cap
    # bounds the loop; converting past it would extend an interrogation the cap exists to end).
    body = _strip_comments(_fn(RUNNER.read_text(), "decide"))
    loop = body[body.index("corrections = 0") : body.index("sel = forge_selection(")]
    conv = loop.index("conversion_beat()")
    assert loop.index("_is_affirmative(") < conv, "an agreement must never reach the conversion"
    assert loop.index("corrections >= _MAX_CONFIRM_CORRECTIONS") < conv, (
        "the cap check must precede the topic conversion — past the cap the loop ends"
    )
    assert "not converted" in loop, (
        "the confirm loop must spend the SAME one-per-pass conversion budget as the intake loop"
    )


def test_honest_fit_beat_is_one_implementation_shared_by_all_callers():
    # L-31: the paths that hedge must not drift apart. Three now — the low-confidence path, the
    # correction cap, and the agreement at the confirm loop's conversion park (residuals 2+3,
    # 2026-07-28: that one used to re-assert `_CONFIRM_COPY` byte-identically on a topic/low map).
    # One definition, three call sites — a second inlined copy is how they silently diverge, and
    # this beat is the only one carrying the doors escape.
    body = _strip_comments(_fn(RUNNER.read_text(), "decide"))
    assert body.count("def honest_fit_beat(") == 1
    # count CALL sites only — the def line contains the same substring
    assert len(re.findall(r"(?<!def )honest_fit_beat\(\)", body)) == 3


# ---- T4: the content-gap ledger --------------------------------------------------------------
# The door becomes an instrument as well as a surface. When a correction still cannot be served
# honestly, that is a CONTENT gap (five territories), not a user failure — and the mining pipeline
# should be told mechanically rather than left to infer it from dogfood memory.


def test_content_gap_is_recorded_with_her_words(tmp_path):
    import sqlite3
    from datetime import datetime, timezone

    from elenchus.web.sitting_store import SittingStore

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

    from elenchus.web.sitting_store import SittingStore

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
    from elenchus.web.app import _emit

    data = {"text": "Before I build it — here's the decision I'd put to you: the price you set."}
    out = _emit(object(), "say", data)
    blob = repr(out)
    for forbidden in ["gen:", "veldra:", "experience_id", "ledger_ref", "sitting_id", "frame_code"]:
        assert forbidden not in blob, forbidden
