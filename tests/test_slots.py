"""Pure slot-resolution rules (Spec 2 §4): first-touch claiming, inheritance, confluence,
earned existence (P4), retirement permanence, exhaustion. No store, no engine — pure."""

from elenchus.web.slots import K_SLOTS, Confluence, resolve_slots

T0 = "2026-07-22T00:00:00+00:00"
T1 = "2026-07-23T00:00:00+00:00"


def comp(frames, refs):
    return {"frames": list(frames), "refs": list(refs)}


def row(slot, at, refs, frames, status="live"):
    return {
        "slot": slot,
        "first_touch_at": at,
        "member_refs": refs,
        "member_frames": frames,
        "status": status,
    }


def test_housed_component_claims_lowest_virgin_slot():
    r = resolve_slots([comp(["a1", "a2"], ["prob:A1"])], housed={0}, registry=[], now_iso=T0)
    assert r.slot_of_component == {0: 0}
    assert r.claims[0]["slot"] == 0 and r.claims[0]["status"] == "live"
    assert r.confluences == [] and r.retire == []


def test_houseless_singleton_claims_nothing_P4():
    # A pushed-but-deflected frame: empty-breadth singleton, no house -> invisible, no claim.
    r = resolve_slots([comp(["f3"], [])], housed=set(), registry=[], now_iso=T0)
    assert r.slot_of_component == {0: None}
    assert r.claims == []


def test_component_inherits_its_slot_on_ref_overlap():
    reg = [row(0, T0, ["prob:A1"], ["a1", "a2"])]
    r = resolve_slots(
        [comp(["a1", "a2", "a3"], ["prob:A1", "prob:A9"])], housed={0}, registry=reg, now_iso=T1
    )
    assert r.slot_of_component == {0: 0}
    assert r.claims[0]["slot"] == 0  # updated row (unioned members), same slot
    assert "prob:A9" in r.claims[0]["member_refs"]
    assert r.confluences == []


def test_absorbing_a_houseless_singleton_is_inheritance_not_confluence():
    # f3 (never slotted) joins A's component via a new shared problem: ONE live slot matches.
    reg = [row(0, T0, ["prob:A1"], ["a1", "a2"])]
    r = resolve_slots(
        [comp(["a1", "a2", "f3"], ["prob:A1", "prob:X"])], housed={0}, registry=reg, now_iso=T1
    )
    assert r.slot_of_component == {0: 0}
    assert r.confluences == [] and r.retire == []


def test_two_slotted_domains_merging_is_a_confluence_elder_inherits():
    reg = [row(0, T0, ["prob:A1"], ["a1"]), row(1, T1, ["prob:B1"], ["b1"])]
    merged = comp(["a1", "b1"], ["prob:A1", "prob:B1", "prob:CROSS"])
    r = resolve_slots([merged], housed={0}, registry=reg, now_iso=T1)
    assert r.slot_of_component == {0: 0}  # elder (earliest first_touch_at)
    assert r.confluences == [Confluence(from_slot=1, to_slot=0)]
    assert r.retire == [(1, 0)]
    elder_row = [c for c in r.claims if c["slot"] == 0][0]
    assert set(elder_row["member_refs"]) >= {"prob:A1", "prob:B1", "prob:CROSS"}


def test_retired_slots_never_match_and_are_never_reclaimed():
    reg = [
        row(0, T0, ["prob:A1"], ["a1"]),
        row(1, T1, ["prob:B1"], ["b1"], status="confluent-into:0"),
    ]
    # A brand-new domain sharing nothing: must claim slot 2, never retired slot 1.
    r = resolve_slots([comp(["c1"], ["prob:C1"])], housed={0}, registry=reg, now_iso=T1)
    assert r.slot_of_component == {0: 2}
    # And a component overlapping the RETIRED row's refs does not resurrect it:
    r2 = resolve_slots([comp(["b9"], ["prob:B1"])], housed={0}, registry=reg, now_iso=T1)
    assert r2.slot_of_component == {0: 2}


def test_bulk_first_assignment_orders_by_component_index():
    comps = [comp(["a1"], ["prob:A"]), comp(["b1"], ["prob:B"]), comp(["c1"], ["prob:C"])]
    r = resolve_slots(comps, housed={0, 1, 2}, registry=[], now_iso=T0)
    assert r.slot_of_component == {0: 0, 1: 1, 2: 2}


def test_frame_fallback_fires_only_with_zero_ref_overlap():
    # Whole-component ref set changed (e.g. re-ingest renamed problems) but frames survive:
    reg = [row(0, T0, ["prob:OLD"], ["a1", "a2"])]
    r = resolve_slots([comp(["a1", "a2"], ["prob:NEW"])], housed={0}, registry=reg, now_iso=T1)
    assert r.slot_of_component == {0: 0}  # frame-secondary match, no new claim


def test_exhaustion_logs_and_leaves_component_unslotted(caplog):
    reg = [row(s, T0, [f"prob:{s}"], [f"f{s}"]) for s in range(K_SLOTS)]
    r = resolve_slots([comp(["zz"], ["prob:ZZ"])], housed={0}, registry=reg, now_iso=T1)
    assert r.slot_of_component == {0: None}
    assert any("exhausted" in m for m in caplog.messages)
