from datetime import datetime, timezone

from retnovation.surface import format_problem_menu, format_receipt
from retnovation.types import NextExperienceSpec, Proposal, Regime, SelectionReceipt

NOW = datetime(2026, 6, 25, tzinfo=timezone.utc)


def _rc(frame, ref, eid, drive, ru, margin, gaps=None):
    return SelectionReceipt(
        frame=frame,
        problem=ref,
        experience_id=eid,
        drive=drive,
        scores={"V": 0.7},
        runner_up_drive=ru,
        margin=margin,
        content_gaps=gaps or [],
        created_at=NOW,
    )


def test_format_receipt_names_drive_runner_up_and_margin():
    s = format_receipt(_rc("lead", "veldra:lic", "e1", "deploy", "consolidate", 0.12))
    assert "DEPLOY" in s and "lead" in s and "veldra:lic" in s
    assert "0.12" in s and "CONSOLIDATE" in s


def test_format_receipt_reads_sensibly_with_no_runner_up():
    s = format_receipt(_rc("a", "veldra:p1", "e1", "diagnose", None, 0.0))
    assert "DEPLOY" not in s and "over" not in s  # no false "decisive over X"
    assert "DIAGNOSE" in s


def test_format_receipt_lists_content_gaps():
    s = format_receipt(_rc("a", "veldra:p1", "e1", "diagnose", None, 0.0, gaps=["a", "b"]))
    assert "a" in s and "b" in s and "gap" in s.lower()


def test_problem_menu_never_names_a_frame():
    def mk(frame, ref, eid):
        spec = NextExperienceSpec(
            target_frames=[frame], ledger_ref=ref, regime=Regime.open_ended, experience_id=eid
        )
        return (spec, _rc(frame, ref, eid, "deploy", "diagnose", 0.2))

    p = Proposal(
        candidates=[
            mk("lead_with_what_you_refuse_to_do", "veldra:lic", "e1"),
            mk("protect_the_core_lane", "veldra:price", "e2"),
        ]
    )
    menu = format_problem_menu(p)
    assert "veldra:lic" in menu and "veldra:price" in menu
    # the gating guard: no frame_code, no drive, leaks to the learner
    for leak in (
        "lead_with_what_you_refuse_to_do",
        "protect_the_core_lane",
        "deploy",
        "diagnose",
        "DEPLOY",
    ):
        assert leak not in menu
