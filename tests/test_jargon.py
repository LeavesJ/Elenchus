"""The jargon gate's matcher (spec 2026-07-29-jargon-gate-design §4.3).

Presence is a fact; adequacy is a judgment. Every offline implementation of "is this term
adequately explained" is gameable or noisy — `83(b)` defeats a parenthetical-proximity heuristic
by CONTAINING a parenthetical — so this module answers presence only."""

from pathlib import Path

from elenchus.content_loader import load_jargon_terms
from elenchus.jargon import compact, offending_term

CONTENT = Path(__file__).resolve().parents[1] / "content"


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
        assert offending_term(phrasing, terms) == "83(b)", phrasing


def test_a_bare_number_does_not_fire():
    # `83` alone is a number, not the election. Compaction must not turn every "83" into a hit.
    assert offending_term("we are 83 days from the deadline", load_jargon_terms()) is None


def test_bare_cliff_does_not_fire():
    # Deliberately absent from the list: it would fire on ordinary English.
    assert offending_term("the negotiation went off a cliff", load_jargon_terms()) is None
    assert offending_term("her vesting cliff is in March", load_jargon_terms()) == "vesting cliff"


def test_clean_text_returns_none():
    assert (
        offending_term("You have to decide what to tell her on Monday.", load_jargon_terms())
        is None
    )


def test_a_missing_list_makes_the_gate_inert(tmp_path):
    # Fallback is silence: a missing or unreadable list must NEVER block every forge.
    assert load_jargon_terms(root=tmp_path) == []
    assert offending_term("the 83(b) clock", []) is None


def test_an_unparseable_list_makes_the_gate_inert(tmp_path):
    (tmp_path / "gate").mkdir()
    (tmp_path / "gate" / "jargon.yaml").write_text("this: [is: not: valid: yaml")
    assert load_jargon_terms(root=tmp_path) == []


def test_the_overfire_canary_over_all_existing_content():
    """THE self-policing guard (spec §4.3). The list grows by hand, and an entry that fires on
    content already known good would silently route every learner to a curated fallback. Any such
    entry fails the suite here instead."""
    terms = load_jargon_terms()
    corpus = sorted(CONTENT.glob("territories/*.md")) + sorted(CONTENT.glob("rubrics/*.yaml"))
    assert corpus, "canary needs real content to be meaningful"
    hits = []
    for path in corpus:
        term = offending_term(path.read_text(), terms)
        if term is not None:
            hits.append(f"{path.name}: {term}")
    assert hits == [], f"jargon.yaml entries fire on known-good content: {hits}"
