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


def saga_order(rows: list[dict]) -> list[str]:
    """Distinct `sitting_id`s in FIRST-ARRIVAL order over converged rows (rows arrive
    `converged_at`-ordered from `converged_log`). The SINGLE index->saga source: `compose_houses`
    derives its grouping FROM this function, so `houses[i]` is the saga `saga_order(rows)[i]` by
    construction — the correspondence cannot drift (L-31: one seam, every caller). Server-side
    only; sitting ids never ride the wire (L-13) — the client clicks an INDEX. Because
    `web_converged` is append-only (L-3), an index is stable for all time: a saga only grows or
    gains successors, so the index a FROZEN homebase render shipped keeps resolving to the same
    saga at click time."""
    order: dict[str, None] = {}
    for row in rows:
        order.setdefault(row["sitting_id"], None)
    return list(order)


def compose_houses(
    regions: list[Region],
    rows: list[dict],
    territory_frames: dict[str, tuple[list[str], str | None]],
) -> list[dict]:
    """Houses are SAGAS (a saga = one sitting's forged world). One house per distinct `sitting_id`,
    in FIRST-ARRIVAL order (rows arrive `converged_at`-ordered from `converged_log`), so a saga's
    position is stable as it grows. A saga's HEIGHT = its convergence count; its REGION = its
    MOST-RECENTLY-converged row's region (the last row in arrival order).

    Wire shape per house: ``{"region": <ordinal into the ORDERED regions>, "bucket": <that region's
    public vitality bucket>, "height_bucket": <coarse 1|2|3 saga-height tier>}`` — no refs, no codes,
    no sitting_id, no raw count (L-13: houses are positional; the raw height stays server-side and is
    used here only to derive the bucket). Grouping is by `sitting_id` ALONE — a sitting is one saga
    regardless of what mix of curated/`gen:` refs its rows carry.

    height_bucket is FLOORED to 1 on a seed region (`bucket is None`) — the same non-invertibility
    gate the region vitality/elevation axes clear (`region_clears_guard`).

    Region membership per representative row: the row's territory (`experience_id`) -> its rubric's
    frame codes (from `territory_frames`) -> the region containing them; a territory spanning regions
    resolves to its decision_frame's region, else the lowest ordinal. Rows without a territory
    (curated `experience_id=''`) fall back to the region whose `problems` hold the row's ref; a row
    nothing matches lands in region 0 — never dropped, never a crash."""
    groups: dict[str, list[dict]] = {s: [] for s in saga_order(rows)}
    for row in rows:
        groups[row["sitting_id"]].append(row)
    houses: list[dict] = []
    for (
        saga_rows
    ) in groups.values():  # insertion order == first-arrival order (rows are time-ordered)
        idx = _house_region(
            regions, saga_rows[-1], territory_frames
        )  # the most-recent row's region
        bucket = _vitality_bucket(regions[idx].vitality) if regions else None
        height_bucket = _house_height_bucket(len(saga_rows)) if bucket is not None else 1
        houses.append({"region": idx, "bucket": bucket, "height_bucket": height_bucket})
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
