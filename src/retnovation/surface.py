from __future__ import annotations

from .types import Proposal, SelectionReceipt

_DRIVE_LABEL = {"diagnose": "DIAGNOSE", "consolidate": "CONSOLIDATE", "deploy": "DEPLOY"}


def _label(drive: str) -> str:
    return _DRIVE_LABEL.get(drive, drive.upper())


def format_receipt(receipt: SelectionReceipt) -> str:
    """Author/log-facing: the full frame-level decomposition. NEVER shown to the learner
    pre-experience (it names the frame — §17.1)."""
    head = f"{_label(receipt.drive)} -> {receipt.frame} on {receipt.problem}"
    if receipt.runner_up_drive is not None and receipt.margin > 1e-9:
        head += f" (cross-drive margin {receipt.margin:.2f} over {_label(receipt.runner_up_drive)})"
    else:
        head += " (uncontested / cold start)"
    if receipt.content_gaps:
        head += f" [content gaps: {', '.join(receipt.content_gaps)}]"
    return head


def format_problem_menu(proposal: Proposal) -> str:
    """Learner-facing: owned problems only. Must NOT name a frame or a drive (§17.1) — the move
    the learner has to work out stays withheld; the experience prompt is the only context shown."""
    lines = ["Next up:"]
    for i, (spec, _receipt) in enumerate(proposal.problem_menu(), start=1):
        lines.append(f"  {i}. {spec.ledger_ref}")
    lines.append("Press Enter to start #1, or type a number to switch problem.")
    return "\n".join(lines)
