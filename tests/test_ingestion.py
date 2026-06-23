import pytest
import yaml

from retnovation.persistence import Store
from retnovation.types import CorpusEntry, LedgerEntry
from retnovation.veldra_ingest import SeedEntry, ingest, load_seed


def _seed_entries():
    return [
        SeedEntry(
            slug="a_problem",
            domain="cs_technical",
            owned_problem="How to X?",
            why_owned="owned because Y",
            unlabeled="needs working out Z",
            provenance="docs/foo.md",
            corpus_pointers=["docs/foo.md", "docs/bar.md"],
        ),
        SeedEntry(
            slug="b_problem",
            domain="founder_ceo",
            owned_problem="How to W?",
            why_owned="owned because V",
            unlabeled="needs U",
            provenance="docs/baz.md",
            corpus_pointers=["docs/baz.md"],
        ),
    ]


def test_corpus_upsert_load_idempotent(tmp_path):
    s = Store(tmp_path / "t.db")
    e = CorpusEntry(
        ledger_ref="veldra:x",
        domain="cs_technical",
        why_owned="w",
        unlabeled="u",
        provenance="p",
        corpus_pointers=["p1", "p2"],
    )
    s.upsert_corpus(e)
    s.upsert_corpus(e)  # idempotent — no duplicate row
    loaded = s.load_corpus()
    assert len(loaded) == 1
    assert loaded[0].ledger_ref == "veldra:x"
    assert loaded[0].corpus_pointers == ["p1", "p2"]
    assert s.get_corpus("veldra:x").domain == "cs_technical"
    assert s.get_corpus("missing") is None


def test_load_seed_parses_yaml(tmp_path):
    p = tmp_path / "seed.yaml"
    p.write_text(
        yaml.safe_dump(
            [
                {
                    "slug": "a_problem",
                    "domain": "cs_technical",
                    "owned_problem": "How to X?",
                    "why_owned": "Y",
                    "unlabeled": "Z",
                    "provenance": "docs/foo.md",
                    "corpus_pointers": ["docs/foo.md"],
                }
            ]
        )
    )
    seeds = load_seed(p)
    assert len(seeds) == 1
    assert seeds[0].slug == "a_problem"
    assert seeds[0].corpus_pointers == ["docs/foo.md"]


def test_ingest_seeds_ledger_and_corpus_idempotent(tmp_path):
    s = Store(tmp_path / "t.db")
    n = ingest(s, _seed_entries())
    assert n == 2
    led = {e.id: e for e in s.load_ledger()}
    assert "veldra:a_problem" in led
    assert led["veldra:a_problem"].owned_problem == "How to X?"
    assert {c.ledger_ref for c in s.load_corpus()} == {"veldra:a_problem", "veldra:b_problem"}
    # idempotent: re-run leaves counts unchanged AND fields stable
    ingest(s, _seed_entries())
    assert len(s.load_ledger()) == 2
    assert len(s.load_corpus()) == 2
    assert {e.id: e.owned_problem for e in s.load_ledger()}["veldra:a_problem"] == "How to X?"
    assert s.get_corpus("veldra:a_problem").domain == "cs_technical"


def test_reingest_preserves_ledger_links(tmp_path):
    s = Store(tmp_path / "t.db")
    # a downstream link is attached to a ledger entry...
    s.add_ledger_entry(
        LedgerEntry(id="veldra:a_problem", owned_problem="orig", links_to_experiences=["exp1"])
    )
    ingest(s, _seed_entries())  # ...and a re-seed passes links=[]
    led = {e.id: e for e in s.load_ledger()}
    assert led["veldra:a_problem"].links_to_experiences == ["exp1"]  # links preserved
    assert led["veldra:a_problem"].owned_problem == "How to X?"  # owned_problem still updated


def test_load_seed_rejects_non_list(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("")  # yaml.safe_load -> None
    with pytest.raises(ValueError):
        load_seed(p)
