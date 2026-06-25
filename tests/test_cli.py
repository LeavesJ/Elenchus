from datetime import datetime, timezone

from retnovation.cli import build_store

_NOW = datetime(2026, 6, 24, tzinfo=timezone.utc)


def test_build_store_seeds_ledger_but_not_queue(tmp_path):
    store = build_store(tmp_path / "cli.db")
    assert any(e.id == "veldra:license_fork_risk" for e in store.load_ledger())
    assert store.queue_len() == 0  # open_ended proposes from live state; no queue seed


def test_build_store_produces_a_runnable_gated_db(tmp_path):
    """Fresh DB must seed every authored ref so select_experience gates clean (no GateError)."""
    from retnovation.aim import aim, derive_core
    from retnovation.experience import select_experience

    store = build_store(tmp_path / "fresh.db")
    exp = select_experience(
        derive_core(aim()), store.load_state(_NOW), store.load_ledger(), store.load_corpus()
    )
    assert exp.experience_id  # gated selection succeeds on a fresh DB with no queued spec
