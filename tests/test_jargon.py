"""The jargon gate's matcher (spec 2026-07-29-jargon-gate-design §4.3).

Presence is a fact; adequacy is a judgment. Every offline implementation of "is this term
adequately explained" is gameable or noisy — `83(b)` defeats a parenthetical-proximity heuristic
by CONTAINING a parenthetical — so this module answers presence only."""

from pathlib import Path

from elenchus.content_loader import load_jargon_terms
from elenchus.jargon import compact, offending_terms

CONTENT = Path(__file__).resolve().parents[1] / "content"


def _canary_corpus():
    """Every file a generated scenario could plausibly echo. Widened past territories/rubrics
    (T2 review, Fix 2) — the original two globs contained none of the five listed terms' actual
    vocabulary, so a bad short entry (e.g. bare `cliff`) sailed through with zero hits to catch
    it. Prompts, personas, and voice files carry the ordinary English the matcher must not fire
    on, which is what makes an overfiring entry show up here at all."""
    return (
        sorted(CONTENT.glob("territories/*.md"))
        + sorted(CONTENT.glob("rubrics/*.yaml"))
        + sorted(CONTENT.glob("prompts/*.md"))
        + sorted(CONTENT.glob("personas/*.md"))
        + sorted(CONTENT.glob("voice/*.md"))
    )


def test_compact_drops_case_and_punctuation():
    assert compact("Section 83(b) election") == "section83belection"
    assert compact("83 (b)") == "83b"
    assert compact("True-Up") == "trueup"
    assert compact("") == ""
    assert compact(None) == ""


def test_the_83b_family_all_match_one_variant():
    terms = load_jargon_terms()
    for phrasing in [
        "the 83(b) clock is ticking",
        "an 83b election is due",
        "file the 83 (b) within 30 days",
        "Section 83(b) matters here",
    ]:
        assert offending_terms(phrasing, terms) == ["83(b)"], phrasing


def test_a_bare_number_does_not_fire():
    # `83` alone is a number, not the election. Compaction must not turn every "83" into a hit.
    assert offending_terms("we are 83 days from the deadline", load_jargon_terms()) == []


def test_bare_cliff_does_not_fire():
    # Deliberately absent from the list: it would fire on ordinary English.
    assert offending_terms("the negotiation went off a cliff", load_jargon_terms()) == []
    assert offending_terms("her vesting cliff is in March", load_jargon_terms()) == [
        "vesting cliff"
    ]


def test_clean_text_returns_empty():
    assert (
        offending_terms("You have to decide what to tell her on Monday.", load_jargon_terms()) == []
    )


def test_two_listed_terms_are_both_reported_in_list_order():
    # T2 review, Fix 3: a scenario naming two listed terms must not cost the single retry twice
    # over — the caller needs to see (and steer against) every offending term at once, not just
    # the first one found.
    text = "Her vesting cliff hits the same week the 83(b) clock runs out."
    terms = load_jargon_terms()
    assert offending_terms(text, terms) == ["83(b)", "vesting cliff"]  # list order, not text order


def test_a_missing_list_makes_the_gate_inert(tmp_path):
    # Fallback is silence: a missing or unreadable list must NEVER block every forge.
    assert load_jargon_terms(root=tmp_path) == []
    assert offending_terms("the 83(b) clock", []) == []


def test_an_unparseable_list_makes_the_gate_inert(tmp_path):
    (tmp_path / "gate").mkdir()
    (tmp_path / "gate" / "jargon.yaml").write_text("this: [is: not: valid: yaml")
    assert load_jargon_terms(root=tmp_path) == []


def test_the_overfire_canary_over_all_existing_content():
    """THE self-policing guard (spec §4.3). The list grows by hand, and an entry that fires on
    content already known good would silently route every learner to a curated fallback. Any such
    entry fails the suite here instead."""
    terms = load_jargon_terms()
    corpus = _canary_corpus()
    assert corpus, "canary needs real content to be meaningful"
    hits = []
    for path in corpus:
        found = offending_terms(path.read_text(), terms)
        if found:
            hits.append(f"{path.name}: {found}")
    assert hits == [], f"jargon.yaml entries fire on known-good content: {hits}"


def test_the_overfire_canary_actually_bites():
    """Proves the guard above is load-bearing, not aspirational (T2 review, Fix 2). Before the
    corpus was widened, the two-glob canary contained none of the five real terms' vocabulary —
    it could not have caught a bad entry if one were added, so its claim in jargon.yaml was
    unverified. A term whose sole variant compacts to the two letters `up` DOES fire on the wider
    corpus (it turns up inside ordinary words like "up" itself), which is exactly the kind of
    short, ambiguous entry the canary exists to reject."""
    corpus = _canary_corpus()
    assert corpus, "canary needs real content to be meaningful"
    bad_terms = [("up", ["up"])]
    hits = [path.name for path in corpus if offending_terms(path.read_text(), bad_terms)]
    assert hits, "a hypothetical overfiring entry must fire on at least one real content file"
