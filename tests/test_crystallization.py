from datetime import datetime, timedelta, timezone

from retnovation.crystallization import crystallization_candidates
from retnovation.types import (
    Core,
    CoreKind,
    Experience,
    Frame,
    FrameStrength,
    LearnerState,
    LedgerEntry,
    Mode,
    Regime,
    Rubric,
    Strength,
)

NOW = datetime(2026, 6, 25, tzinfo=timezone.utc)
CFG = {"theta_ledger_refs": 2}


def _exp(eid, ref, frames):
    return Experience(
        experience_id=eid,
        prompt="p",
        ledger_ref=ref,
        regime=Regime.open_ended,
        rubric=Rubric(
            frames=[Frame(frame_code=c, frame_detail="d") for c in frames],
            traps=[],
            mode=Mode.genuinely_open,
        ),
    )


def _core(frames):
    return Core(process_frames=frames, declarative_seed=[], content_core=None)


def test_demote_orphan_core_frame():
    # 'ghost' is a core frame, zero evidence, in NO active-problem experience -> demote
    ledger = [LedgerEntry(id="veldra:p1", owned_problem="x")]
    exps = [_exp("e1", "veldra:p1", ["lead"])]
    cands = crystallization_candidates(
        core=_core(["lead", "ghost"]),
        state=LearnerState(),
        ledger=ledger,
        experiences=exps,
        now=NOW,
        config=CFG,
    )
    demotes = [c for c in cands if c.kind is CoreKind.demote]
    assert [c.target for c in demotes] == ["ghost"]  # 'lead' is referenced -> not demoted


def test_no_demote_when_frame_referenced_even_if_unseen():
    ledger = [LedgerEntry(id="veldra:p1", owned_problem="x")]
    exps = [_exp("e1", "veldra:p1", ["lead"])]  # 'lead' referenced by an active problem
    cands = crystallization_candidates(
        core=_core(["lead"]),
        state=LearnerState(),
        ledger=ledger,
        experiences=exps,
        now=NOW,
        config=CFG,
    )
    assert not [c for c in cands if c.kind is CoreKind.demote]


def test_promote_decayed_frame_referenced_across_problems():
    st = LearnerState()
    # forming (interval 7d), last seen 10d ago -> retention_due > 0 (decayed)
    st.frames["lead"] = FrameStrength(
        strength=Strength.forming,
        last_seen=NOW - timedelta(days=10),
        due=NOW,
        last_evidence="x",
        evidence_count=1,
        breadth={"veldra:p1"},
        unprompted_breadth=set(),
    )
    ledger = [
        LedgerEntry(id="veldra:p1", owned_problem="x"),
        LedgerEntry(id="veldra:p2", owned_problem="y"),
    ]
    exps = [_exp("e1", "veldra:p1", ["lead"]), _exp("e2", "veldra:p2", ["lead"])]  # 2 problems
    cands = crystallization_candidates(
        core=_core(["lead"]), state=st, ledger=ledger, experiences=exps, now=NOW, config=CFG
    )
    promotes = [c for c in cands if c.kind is CoreKind.promote]
    assert [c.target for c in promotes] == ["lead"]


def test_no_promote_when_not_decayed():
    st = LearnerState()
    st.frames["lead"] = FrameStrength(
        strength=Strength.forming,
        last_seen=NOW,
        due=NOW,
        last_evidence="x",
        evidence_count=1,
        breadth={"veldra:p1"},
        unprompted_breadth=set(),
    )
    ledger = [
        LedgerEntry(id="veldra:p1", owned_problem="x"),
        LedgerEntry(id="veldra:p2", owned_problem="y"),
    ]
    exps = [_exp("e1", "veldra:p1", ["lead"]), _exp("e2", "veldra:p2", ["lead"])]
    cands = crystallization_candidates(
        core=_core(["lead"]), state=st, ledger=ledger, experiences=exps, now=NOW, config=CFG
    )
    assert not [c for c in cands if c.kind is CoreKind.promote]


def test_empty_when_nothing_qualifies():
    cands = crystallization_candidates(
        core=_core([]), state=LearnerState(), ledger=[], experiences=[], now=NOW, config=CFG
    )
    assert cands == []
