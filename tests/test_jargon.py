"""The jargon gate's matcher (spec 2026-07-29-jargon-gate-design §4.3).

Presence is a fact; adequacy is a judgment. Every offline implementation of "is this term
adequately explained" is gameable or noisy — `83(b)` defeats a parenthetical-proximity heuristic
by CONTAINING a parenthetical — so this module answers presence only."""

from pathlib import Path

from elenchus.content_loader import load_jargon_terms
from elenchus.jargon import compact, offending_terms

CONTENT = Path(__file__).resolve().parents[1] / "content"

# Ordinary-English guard (T2 re-review, Finding 2a). The corpus canary below only catches an
# entry that fires on content already living under content/ — `cliff`, `stack`, `grant`, and
# `runway` appear nowhere in that corpus (not even jargon.yaml's own comment, which can never be
# part of its own canary), so the canary structurally cannot catch a bare entry for any of them.
# This is the instrument that can: each sentence uses one of those words, plus a few more
# plausible-but-bad future entries, in its ordinary business sense, and none may ever produce a
# hit against the REAL loaded jargon.yaml.
_CLIFF_SENTENCE = "the negotiation went off a cliff"

ORDINARY_ENGLISH_SENTENCES = [
    _CLIFF_SENTENCE,
    "we stacked three investor calls back to back this morning",
    "the city will grant our permit application by Friday",
    "the drone lifted off from the makeshift runway in the parking lot",
    "our lease renews for another one-year term in the fall",
    "we put a cap on how many pizzas the team orders each month",
    "everyone on the warehouse floor has to wear a safety vest",
    "we left the option open to push the launch a week if QA runs long",
]


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
    # Deliberately absent from the list: it would fire on ordinary English. `_CLIFF_SENTENCE` is
    # also wired into ORDINARY_ENGLISH_SENTENCES (T2 re-review, Finding 2a) so a future bare
    # `cliff` entry fails the suite generally, not just here.
    assert offending_terms(_CLIFF_SENTENCE, load_jargon_terms()) == []
    assert offending_terms("her vesting cliff is in March", load_jargon_terms()) == [
        "vesting cliff"
    ]


def test_ordinary_english_never_fires_on_the_real_jargon_list():
    """The corpus canary (below) can only catch an entry that fires on content already living
    under content/. The words this guards against — cliff, stack, grant, runway, and friends —
    appear nowhere in that corpus, so no in-repo entry could ever exercise the canary for them
    (T2 re-review, Finding 2). Ordinary business-English sentences, checked against the REAL
    loaded jargon.yaml, are the instrument that can: they must never produce a hit."""
    terms = load_jargon_terms()
    hits = {s: found for s in ORDINARY_ENGLISH_SENTENCES if (found := offending_terms(s, terms))}
    assert hits == {}, f"ordinary English fires on jargon.yaml entries: {hits}"


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


# T2 FINAL review, Finding 4: before this, only "83(b)" and "vesting cliff" were exercised
# anywhere in this file — "QSBS", "preferred stack", and "true-up" had zero coverage, so a typo'd
# variant (e.g. "QSBS" -> "QSBBS") or a lost secondary variant silently disabled a term with the
# full suite green throughout.
SEEDED_TERM_SENTENCES = {
    "83(b)": "the 83(b) clock is ticking on those shares",
    "QSBS": "she wants to know if the shares still qualify for QSBS",
    "preferred stack": "the new investor sits above her in the preferred stack",
    "true-up": "the true-up adjustment lands once the audit closes",
    "vesting cliff": "her vesting cliff hits in March",
}


def test_every_seeded_term_fires_on_a_representative_sentence():
    terms = load_jargon_terms()
    # A term added to or dropped from jargon.yaml without a matching sentence added here must
    # fail loud, not silently go untested — so pin the seeded set itself first.
    assert {t for t, _ in terms} == set(SEEDED_TERM_SENTENCES)
    for term, sentence in SEEDED_TERM_SENTENCES.items():
        assert offending_terms(sentence, terms) == [term], term


def test_the_preference_stack_variant_fires():
    # "preferred stack"'s SECOND variant ("preference stack") — previously untested; a
    # truncate-to-first-variant mutation drops it silently.
    terms = load_jargon_terms()
    text = "everyone is watching where they land in the preference stack"
    assert offending_terms(text, terms) == ["preferred stack"]


def test_the_cliff_vesting_variant_fires():
    # "vesting cliff"'s SECOND variant ("cliff vesting") — previously untested for the same
    # reason as above.
    terms = load_jargon_terms()
    text = "the offer uses standard cliff vesting over four years"
    assert offending_terms(text, terms) == ["vesting cliff"]


# Deliberately NOT tested here: "83(b)"'s own secondary variants ("83b", "section 83(b)"). All
# three of that entry's variants compact to strings CONTAINING "83b" — compact("83(b)") ==
# compact("83b") == "83b", and compact("section 83(b)") == "section83b", which itself contains
# "83b" as a substring. A truncate-to-first-variant mutation keeps "83(b)" (variant 0), which
# compacts identically to the ones it would drop, so no sentence can distinguish the truncated
# list from the full one for this entry — inventing a test here would just be
# test_the_83b_family_all_match_one_variant again, unable to ever fail.


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
