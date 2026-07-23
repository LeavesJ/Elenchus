"""Slot resolution — the domain-identity oracle (Spec 2 §4).

Pure: consumes projection components + the persisted registry, returns the resolution.
The ONLY caller is the `_on_done` landing seam; live projections never resolve slots.
L-13: frames/refs are server-side inputs; only the integer slot ever reaches a wire dict.
K exhaustion: log-loud + unslotted (never a bricked landing, L-27 spirit). Extension rule:
K -> K+8 appends bearings; existing bearings never move (spec §3).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

_log = logging.getLogger("retnovation.web")

K_SLOTS = 24


@dataclass(frozen=True)
class Confluence:
    from_slot: int
    to_slot: int


@dataclass
class SlotResolution:
    slot_of_component: dict[int, int | None] = field(default_factory=dict)
    claims: list[dict] = field(default_factory=list)
    confluences: list[Confluence] = field(default_factory=list)
    retire: list[tuple[int, int]] = field(default_factory=list)


def _matches(component: dict, live: list[dict]) -> list[dict]:
    refs = set(component["refs"])
    by_refs = [r for r in live if refs & set(r["member_refs"])]
    if by_refs:
        return by_refs
    frames = set(component["frames"])
    return [r for r in live if frames & set(r["member_frames"])]


def resolve_slots(
    components: list[dict], housed: set[int], registry: list[dict], now_iso: str
) -> SlotResolution:
    res = SlotResolution()
    live = [r for r in registry if r["status"] == "live"]
    ever_assigned = {r["slot"] for r in registry}
    updated: dict[int, dict] = {}

    def _union_into(slot_row: dict, component: dict) -> dict:
        row = updated.get(slot_row["slot"], dict(slot_row))
        row["member_refs"] = sorted(set(row["member_refs"]) | set(component["refs"]))
        row["member_frames"] = sorted(set(row["member_frames"]) | set(component["frames"]))
        updated[row["slot"]] = row
        return row

    for i, component in enumerate(components):
        matched = _matches(component, live)
        if len(matched) >= 2:
            elder = min(matched, key=lambda r: (r["first_touch_at"], r["slot"]))
            res.slot_of_component[i] = elder["slot"]
            row = _union_into(elder, component)
            for young in matched:
                if young["slot"] == elder["slot"]:
                    continue
                row["member_refs"] = sorted(set(row["member_refs"]) | set(young["member_refs"]))
                row["member_frames"] = sorted(
                    set(row["member_frames"]) | set(young["member_frames"])
                )
                res.confluences.append(Confluence(from_slot=young["slot"], to_slot=elder["slot"]))
                res.retire.append((young["slot"], elder["slot"]))
                live = [r for r in live if r["slot"] != young["slot"]]
        elif len(matched) == 1:
            res.slot_of_component[i] = matched[0]["slot"]
            _union_into(matched[0], component)
        elif i in housed:
            free = next((s for s in range(K_SLOTS) if s not in ever_assigned), None)
            if free is None:
                _log.error("slot lattice exhausted (K=%d): component unslotted", K_SLOTS)
                res.slot_of_component[i] = None
                continue
            ever_assigned.add(free)
            row = {
                "slot": free,
                "first_touch_at": now_iso,
                "member_refs": sorted(set(component["refs"])),
                "member_frames": sorted(set(component["frames"])),
                "status": "live",
            }
            live.append(row)
            updated[free] = row
            res.slot_of_component[i] = free
        else:
            res.slot_of_component[i] = None

    res.claims = [updated[s] for s in sorted(updated)]
    return res
