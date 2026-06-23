from retnovation.cli import build_store


def test_build_store_seeds_ledger_and_queue(tmp_path):
    store = build_store(tmp_path / "cli.db")
    assert any(e.id == "veldra:licensing_continuity" for e in store.load_ledger())
    assert store.queue_pop() is not None  # an initial experience is queued
