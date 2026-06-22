from __future__ import annotations

from pathlib import Path

from .content_loader import load_map
from .types import Aim, Core

MAX_PROCESS_DIAL = 10


def aim(posture: str = "founder_ceo") -> Aim:
    return Aim(posture=posture, process_dial=MAX_PROCESS_DIAL, content_core=None)


def derive_core(a: Aim, root: Path | None = None) -> Core:
    frames, seed = load_map(a.posture, root=root)
    return Core(process_frames=frames, declarative_seed=seed, content_core=None)
