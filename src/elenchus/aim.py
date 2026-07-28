from __future__ import annotations

from pathlib import Path

from .content_loader import load_content_map, load_map, load_path_type
from .types import Aim, Core

MAX_PROCESS_DIAL = 10
MIN_PROCESS_DIAL = 0


def aim(posture: str = "founder_ceo", root: Path | None = None) -> Aim:
    path_type = load_path_type(posture, root=root)
    dial = MAX_PROCESS_DIAL if path_type == "posture" else MIN_PROCESS_DIAL
    return Aim(posture=posture, process_dial=dial, content_core=None)


def derive_core(a: Aim, root: Path | None = None) -> Core:
    if load_path_type(a.posture, root=root) == "domain":
        concepts = load_content_map(a.posture, root=root)
        return Core(process_frames=[], declarative_seed=concepts, content_core=concepts)
    frames, seed = load_map(a.posture, root=root)
    return Core(process_frames=frames, declarative_seed=seed, content_core=None)
