from __future__ import annotations

from datetime import datetime

from .types import LearnerState, Region, RegionRender, Strength, TerrainView

_VITALITY = {Strength.weak: 0.2, Strength.forming: 0.6, Strength.strong: 1.0}


def region_clears_guard(
    frame_codes: set[str], problems: set[str], *, min_frames: int = 2, min_problems: int = 2
) -> bool:
    """Per-region non-invertibility gate (§4b): a region may render decodable vitality only when it
    draws on enough distinct frames across enough distinct problems that brightness cannot be read
    back to one move. Below threshold the region stays a seed."""
    return len(frame_codes) >= min_frames and len(problems) >= min_problems


def _components(frames: dict) -> list[list[str]]:
    """Connected components of frames linked by a shared problem (ledger_ref in breadth)."""
    codes = sorted(frames)
    seen: set[str] = set()
    comps: list[list[str]] = []
    for start in codes:
        if start in seen:
            continue
        stack, comp = [start], []
        while stack:
            c = stack.pop()
            if c in seen:
                continue
            seen.add(c)
            comp.append(c)
            for other in codes:
                if other not in seen and frames[c].breadth & frames[other].breadth:
                    stack.append(other)
        comps.append(sorted(comp))
    return comps


def project_terrain(
    state: LearnerState,
    now: datetime,  # reserved: decay/savings time-axis (§4d), inert in the MVP
    *,
    min_frames: int = 2,
    min_problems: int = 2,
) -> TerrainView:
    regions: list[Region] = []
    for comp in _components(state.frames):
        problems: set[str] = set()
        for c in comp:
            problems |= state.frames[c].breadth
        clears = region_clears_guard(
            set(comp), problems, min_frames=min_frames, min_problems=min_problems
        )
        vitality = (
            sum(_VITALITY[state.frames[c].strength] for c in comp) / len(comp) if clears else None
        )
        # accretion (height axis, §4): breadth COUNT only — rename-invariant, gated by the same guard.
        accretion = float(len(problems)) if clears else None
        regions.append(
            Region(
                region_id="",  # assigned positionally in regions_to_view (L-13: never frame-derived)
                frame_codes=comp,
                problems=sorted(problems),
                vitality=vitality,
                accretion=accretion,
                render=RegionRender.rendered if clears else RegionRender.seed,
            )
        )
    return regions_to_view(regions)


def regions_to_view(regions: list[Region]) -> TerrainView:
    # L-13 wire ordering: order by PUBLIC signal only — rendered before seed, then vitality
    # descending — so a node's POSITION carries no frame information (a frame-code rename leaves the
    # learner_view payload identical). region_id is then a positional ordinal, never a hash of the
    # frame set. Tied/seed order and the node COUNT remain an accepted coarse-shape residual (§6).
    ordered = sorted(
        regions, key=lambda r: (r.render is not RegionRender.rendered, -(r.vitality or 0.0))
    )
    return TerrainView(
        regions=[r.model_copy(update={"region_id": f"r{i}"}) for i, r in enumerate(ordered)]
    )
