from __future__ import annotations

from datetime import datetime

from .types import LearnerState, Region, RegionRender, Strength, TerrainView, _vitality_bucket

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


def compose_houses(
    regions: list[Region],
    rows: list[dict],
    territory_frames: dict[str, tuple[list[str], str | None]],
) -> list[dict]:
    """Houses are converged segments (living sitting §2f/M7/D2): one house per `web_converged`
    row, cumulative across sittings (the village accumulates exactly as the terrain's own engine
    state does), in the rows' converged_at order — a public time signal; ORDER carries time, no
    timestamps ride the wire.

    Wire shape per house: ``{"region": <ordinal into the ORDERED regions — the same positional
    ids the learner_view wire assigns>, "bucket": <that region's existing public vitality
    bucket>}`` — no refs, no codes (L-13: houses are positional).

    Region membership: the row's territory (`experience_id`) -> its rubric's frame codes (from
    `territory_frames`) -> the region containing them. A territory whose frames span regions
    resolves to the region holding its decision_frame; absent a DF among the holders, the lowest
    ordinal wins (deterministic). Rows without a territory (pre-living-sitting curated
    convergences, experience_id='') fall back to the region whose `problems` hold the row's ref;
    a row nothing matches lands in region 0 — never dropped, never a crash.

    Honest residual (review D11): per-region converged COUNTS and problem-to-region grouping
    become public — justified as user-known (she lived each convergence; the close narrates
    them) and as the intended reward. Codes stay protected: membership is computed from frame
    SETS, so a consistent content rename leaves the payload byte-identical; tied-region order
    remains the accepted coarse-shape residual (§6)."""
    houses: list[dict] = []
    for row in rows:
        idx = _house_region(regions, row, territory_frames)
        bucket = _vitality_bucket(regions[idx].vitality) if regions else None
        houses.append({"region": idx, "bucket": bucket})
    return houses


def _house_height_bucket(stories: int) -> int:
    """A saga-height bucket (1 story / a few / many). DIFFERS from `_elevation_bucket` (which buckets
    region breadth-count with `<=2 -> 1`): a saga's FIRST growth (1 -> 2 stories) must cross a tier so
    the "watch my saga grow" payoff registers, so 1 story is its OWN floor tier. Coarse 3-tier only —
    the raw count stays server-side (L-13); only this bucket rides the wire."""
    if stories <= 1:
        return 1
    if stories <= 4:
        return 2
    return 3


def _house_region(
    regions: list[Region], row: dict, territory_frames: dict[str, tuple[list[str], str | None]]
) -> int:
    eid = row.get("experience_id", "")
    if eid and eid in territory_frames:
        codes, df = territory_frames[eid]
        wanted = set(codes)
        holders = [i for i, r in enumerate(regions) if wanted & set(r.frame_codes)]
        if holders:
            if df is not None:
                for i in holders:
                    if df in regions[i].frame_codes:
                        return i
            return holders[0]
    ref = row.get("ref", "")
    if ref:
        for i, r in enumerate(regions):
            if ref in r.problems:
                return i
    return 0


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
