"""The F1 regression harness (user-steered chapters spec §4). The STRUCTURE runs offline (L-22 —
the harness must not rot silently); only the model call is key-gated (@live)."""

import os

import pytest

from elenchus.content_loader import load_steer_fixtures


def test_f1_fixtures_load_and_validate():
    """Structure runs OFFLINE (L-22): fixtures load and the shape is sound."""
    fx = load_steer_fixtures()
    assert isinstance(fx["max_false_nonempty_rate"], float)
    assert 0.0 <= fx["max_false_nonempty_rate"] <= 1.0
    assert fx["context"]["problem"].strip()
    assert fx["context"]["landed_position"].strip()
    assert len(fx["non_steers"]) >= 3
    assert len(fx["genuine"]) >= 2
    assert all(isinstance(t, str) and t.strip() for t in fx["non_steers"] + fx["genuine"])


@pytest.mark.live
@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no key")
def test_live_steer_f1():
    """F1 is the whole ballgame: the false-non-empty rate over re-litigations/chatter stays under
    the recorded baseline. Read the PRINTED turns before treating a red as real (judge noise /
    L-24 529s). Re-run under threshold on ANY concierge_converse.md or model change (spec §4)."""
    from elenchus.model import AnthropicModel

    fx = load_steer_fixtures()
    model = AnthropicModel()
    ctx = fx["context"]
    recent = [("Vera", ctx["problem"]), ("student", ctx["landed_position"])]

    def pressure_for(turn: str) -> str:
        out = model.concierge_converse(
            ctx["problem"], recent + [("student", turn)], stop_reason="converged"
        )
        print(f"turn={turn!r} -> next_pressure={out.next_pressure!r}")
        return out.next_pressure.strip()

    false_nonempty = sum(1 for t in fx["non_steers"] if pressure_for(t))
    rate = false_nonempty / len(fx["non_steers"])
    print(f"false_nonempty_rate={rate:.3f} (baseline {fx['max_false_nonempty_rate']})")
    assert rate <= fx["max_false_nonempty_rate"], (
        f"F1 regressed: {false_nonempty}/{len(fx['non_steers'])} re-litigations distilled a "
        f"pressure (rate {rate:.3f} > {fx['max_false_nonempty_rate']})"
    )
    # recall floor (softer — precision is the gate): the mechanism CAN fire on genuine frames
    genuine_hits = sum(1 for t in fx["genuine"] if pressure_for(t))
    assert genuine_hits >= (len(fx["genuine"]) + 1) // 2, (
        f"F1 never fired: only {genuine_hits}/{len(fx['genuine'])} genuine frames steered"
    )
