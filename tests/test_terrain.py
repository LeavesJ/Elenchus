from datetime import datetime, timezone

from retnovation.terrain import compose_houses, project_terrain, region_clears_guard
from retnovation.types import FrameStrength, LearnerState, RegionRender, Strength, TerrainView

NOW = datetime(2026, 6, 29, tzinfo=timezone.utc)


def _fs(strength, breadth):
    return FrameStrength(
        strength=strength,
        last_seen=NOW,
        due=NOW,
        last_evidence="x",
        evidence_count=len(breadth),
        breadth=set(breadth),
        unprompted_breadth=set(breadth),
    )


def test_guard_refuses_single_frame_region():
    assert region_clears_guard({"embed"}, {"P1", "P2"}) is False  # 1 frame < 2


def test_guard_refuses_single_problem_region():
    assert region_clears_guard({"embed", "choose_failure"}, {"P1"}) is False  # 1 problem < 2


def test_guard_clears_two_by_two():
    assert region_clears_guard({"embed", "choose_failure"}, {"P1", "P2"}) is True


def test_user_zero_single_frame_is_a_seed():
    # embed alone across 2 problems: 1 frame < min_frames -> seed, vitality None, frame_codes hidden in learner_view
    state = LearnerState(frames={"embed": _fs(Strength.strong, ["P1", "P2"])})
    view = project_terrain(state, NOW)
    assert isinstance(view, TerrainView) and len(view.regions) == 1
    assert view.regions[0].render is RegionRender.seed
    assert view.regions[0].vitality is None
    assert "frame_codes" not in view.learner_view()[0]


def test_two_frames_two_problems_renders_a_non_invertible_region():
    # embed + choose_failure sharing problems -> one region, >=2 frames across >=2 problems -> rendered
    state = LearnerState(
        frames={
            "embed": _fs(Strength.strong, ["P1", "P2"]),
            "choose_failure": _fs(Strength.forming, ["P1"]),
        }
    )
    view = project_terrain(state, NOW)
    assert len(view.regions) == 1
    r = view.regions[0]
    assert r.render is RegionRender.rendered
    assert set(r.frame_codes) == {
        "embed",
        "choose_failure",
    }  # vitality draws on >1 frame (non-invertible)
    assert r.vitality is not None and 0.0 <= r.vitality <= 1.0


def test_disjoint_frames_form_separate_regions():
    state = LearnerState(
        frames={
            "a": _fs(Strength.forming, ["P1"]),
            "b": _fs(Strength.forming, ["P9"]),
        }
    )
    view = project_terrain(state, NOW)
    assert len(view.regions) == 2  # no shared problem -> two components, both seeds
    assert all(r.render is RegionRender.seed for r in view.regions)


def test_connected_components_are_transitive():
    # A shares P1 with B; B shares P2 with C; A and C share nothing.
    # Transitively they form ONE component (A-B-C linked through B).
    # 3 frames x 2 problems clears the guard, so the region renders.
    state = LearnerState(
        frames={
            "A": _fs(Strength.forming, ["P1"]),
            "B": _fs(Strength.forming, ["P1", "P2"]),
            "C": _fs(Strength.forming, ["P2"]),
        }
    )
    view = project_terrain(state, NOW)
    assert len(view.regions) == 1
    assert set(view.regions[0].frame_codes) == {"A", "B", "C"}


def test_learner_view_is_non_invertible_under_frame_rename():
    # A frame-code RENAME (strengths + problem structure fixed) must leave learner_view byte-identical:
    # the wire carries no frame identity. (Node COUNT remains an accepted coarse-shape residual, §6.)
    state = LearnerState(
        frames={
            "embed": _fs(Strength.strong, ["P1", "P2"]),
            "choose_failure": _fs(Strength.forming, ["P1"]),
        }
    )
    renamed = LearnerState(
        frames={
            "zzz_other": _fs(Strength.strong, ["P1", "P2"]),
            "aaa_renamed": _fs(Strength.forming, ["P1"]),
        }
    )
    v1 = project_terrain(state, NOW).learner_view()
    v2 = project_terrain(renamed, NOW).learner_view()
    assert v1 == v2  # rename invariant -> non-invertible wire

    row = v1[0]
    assert set(row) == {
        "region_id",
        "render",
        "vitality",
        "elevation",
    }  # exactly the L-13-safe keys
    assert row["region_id"] == "r0"  # positional ordinal, not the old 5-digit frame hash
    assert "frame_codes" not in row
    assert row["vitality"] in (None, 1, 2, 3)  # coarse bucket, not the raw mean
    assert row["elevation"] in (None, 1, 2, 3)  # second axis, same coarse bucketing


def test_learner_view_orders_by_public_vitality_not_frame_order():
    # Two disjoint rendered regions of different vitality: the brighter sorts first (r0), by PUBLIC
    # vitality — independent of the frame codes' alphabetical order (a_weak* sorts before z_strong*).
    state = LearnerState(
        frames={
            "z_strong_a": _fs(Strength.strong, ["P1", "P2"]),
            "z_strong_b": _fs(Strength.strong, ["P1", "P2"]),  # region: vit 1.0 -> bucket 3
            "a_weak_a": _fs(Strength.weak, ["P8", "P9"]),
            "a_weak_b": _fs(Strength.weak, ["P8", "P9"]),  # region: vit 0.2 -> bucket 1
        }
    )
    rows = project_terrain(state, NOW).learner_view()
    assert [r["region_id"] for r in rows] == ["r0", "r1"]
    assert rows[0]["vitality"] == 3 and rows[1]["vitality"] == 1  # brighter first


def test_learner_view_includes_bucketed_elevation():
    # A rendered region: embed(strong,[P1,P2]) + choose_failure(forming,[P1]) -> problems {P1,P2}
    # -> accretion 2 -> elevation bucket 1.
    state = LearnerState(
        frames={
            "embed": _fs(Strength.strong, ["P1", "P2"]),
            "choose_failure": _fs(Strength.forming, ["P1"]),
        }
    )
    row = project_terrain(state, NOW).learner_view()[0]
    assert set(row) == {"region_id", "render", "vitality", "elevation"}
    assert row["elevation"] == 1
    assert row["vitality"] in (1, 2, 3)


def test_seed_has_no_elevation():
    # 1 frame -> seed -> elevation None (nothing accreted to decode)
    state = LearnerState(frames={"embed": _fs(Strength.strong, ["P1", "P2"])})
    row = project_terrain(state, NOW).learner_view()[0]
    assert row["render"] == "seed"
    assert row["elevation"] is None
    assert row["vitality"] is None


def test_elevation_is_independent_of_vitality_two_axis():
    # TALL-DIM region: 4 weak frames chained across 5 problems -> vitality bucket 1, elevation bucket 3.
    # SHORT-BRIGHT region: 2 strong frames across 2 problems -> vitality bucket 3, elevation bucket 1.
    state = LearnerState(
        frames={
            "t_a": _fs(Strength.weak, ["P1", "P2"]),
            "t_b": _fs(Strength.weak, ["P2", "P3"]),
            "t_c": _fs(Strength.weak, ["P3", "P4"]),
            "t_d": _fs(Strength.weak, ["P4", "P5"]),
            "s_a": _fs(Strength.strong, ["Q1", "Q2"]),
            "s_b": _fs(Strength.strong, ["Q1"]),
        }
    )
    rows = project_terrain(state, NOW).learner_view()
    # regions_to_view orders by descending raw vitality: SHORT-BRIGHT (1.0) first, TALL-DIM (0.2) second.
    short_bright, tall_dim = rows[0], rows[1]
    assert (short_bright["vitality"], short_bright["elevation"]) == (3, 1)
    assert (tall_dim["vitality"], tall_dim["elevation"]) == (1, 3)


# ---- Houses are converged segments (living sitting §2f/M7, plan L5) --------------------------


def _row(eid, ref="P1", at="t", sitting_id="s"):
    return {"sitting_id": sitting_id, "ref": ref, "converged_at": at, "experience_id": eid}


def _two_region_view():
    # Two disjoint regions of distinct PUBLIC vitality: r0 = bright (strong), r1 = dim (weak).
    state = LearnerState(
        frames={
            "z_strong_a": _fs(Strength.strong, ["P1", "P2"]),
            "z_strong_b": _fs(Strength.strong, ["P1", "P2"]),
            "a_weak_a": _fs(Strength.weak, ["P8", "P9"]),
            "a_weak_b": _fs(Strength.weak, ["P8", "P9"]),
        }
    )
    return project_terrain(state, NOW)


def test_houses_founder_regression_two_convergences_one_saga_two_stories():
    # The 2026-07-02 dogfood collapse is mended by HEIGHT now: two convergences in one sitting =
    # ONE saga = one house whose height is 2 stories (not two separate houses).
    state = LearnerState(
        frames={
            "embed": _fs(Strength.strong, ["P1", "P2"]),
            "choose_failure": _fs(Strength.forming, ["P1", "P2"]),
        }
    )
    view = project_terrain(state, NOW)
    membership = {
        "anchor": (["embed", "choose_failure"], "choose_failure"),
        "stakes": (["choose_failure"], "choose_failure"),
    }
    rows = [
        _row("anchor", ref="P1", at="t1"),
        _row("stakes", ref="P2", at="t2"),
    ]  # same sitting "s"
    houses = compose_houses(view.regions, rows, membership)
    assert len(houses) == 1  # one saga -> one house
    assert houses[0]["region"] == 0
    assert houses[0]["bucket"] == view.learner_view()[0]["vitality"]  # region's public vitality
    assert houses[0]["height_bucket"] == 2  # two stories (region rendered, so the gate is open)


def test_house_order_follows_converged_arrival_not_region_order():
    # Arrival order carries time: a saga in the DIMMER region (r1) that converged first stays first.
    # DISTINCT sittings -> two sagas -> two houses (one convergence each).
    view = _two_region_view()
    membership = {"dim_t": (["a_weak_a"], None), "bright_t": (["z_strong_a"], None)}
    rows = [
        _row("dim_t", ref="P8", at="t1", sitting_id="s1"),
        _row("bright_t", ref="P1", at="t2", sitting_id="s2"),
    ]
    houses = compose_houses(view.regions, rows, membership)
    assert [h["region"] for h in houses] == [1, 0]
    assert houses[0]["bucket"] == 1 and houses[1]["bucket"] == 3
    assert houses[0]["height_bucket"] == 1 and houses[1]["height_bucket"] == 1  # one story each


def test_spanning_territory_resolves_to_its_decision_frame_region():
    # A territory whose frames span regions maps to the region holding its DF frame
    # (deterministic); with no DF among the holders, the lowest ordinal wins.
    view = _two_region_view()
    rows = [_row("span_t")]
    spanning = (["z_strong_a", "a_weak_a"], "a_weak_a")  # DF lives in the dim region (r1)
    assert compose_houses(view.regions, rows, {"span_t": spanning})[0]["region"] == 1
    no_df = (["z_strong_a", "a_weak_a"], None)
    assert compose_houses(view.regions, rows, {"span_t": no_df})[0]["region"] == 0


def test_curated_and_unknown_rows_fall_back_to_ref_then_region_zero():
    # Pre-living-sitting rows (experience_id='') match their REF against Region.problems; an
    # unmatched ref lands in region 0 — never dropped. DISTINCT sittings keep them three sagas.
    view = _two_region_view()
    rows = [
        _row("", ref="P8", at="t1", sitting_id="s1"),  # curated: ref matches the dim region
        _row("", ref="GONE", at="t2", sitting_id="s2"),  # unmatched -> region 0
        _row("unknown_t", ref="P9", at="t3", sitting_id="s3"),  # unknown eid -> ref -> dim region
    ]
    assert [h["region"] for h in compose_houses(view.regions, rows, {})] == [1, 0, 1]


def test_first_convergence_house_sits_in_a_seed_region_with_no_bucket():
    # One forged convergence in a still-seed region: the house renders anyway, carrying the seed's
    # public bucket (None) and a floored height_bucket (1 — the gate is closed on a seed).
    state = LearnerState(
        frames={
            "embed": _fs(Strength.forming, ["G1"]),
            "choose_failure": _fs(Strength.forming, ["G1"]),
        }
    )
    view = project_terrain(state, NOW)
    assert view.regions[0].render is RegionRender.seed
    rows = [_row("anchor", ref="G1")]
    houses = compose_houses(view.regions, rows, {"anchor": (["embed", "choose_failure"], None)})
    assert houses == [{"region": 0, "bucket": None, "height_bucket": 1}]


def test_houses_with_no_regions_default_safely():
    # A converged row over an empty projection: region 0, bucket None, height 1 — never crashes.
    assert compose_houses([], [_row("", ref="veldra:x")], {}) == [
        {"region": 0, "bucket": None, "height_bucket": 1}
    ]


def test_houses_payload_is_rename_invariant():
    # Renaming a frame consistently leaves the houses byte-identical — the wire carries region
    # ordinals + public buckets only, never frame identity. (height_bucket is a count, rename-invariant.)
    state = LearnerState(
        frames={
            "embed": _fs(Strength.strong, ["P1", "P2"]),
            "choose_failure": _fs(Strength.forming, ["P1"]),
        }
    )
    renamed = LearnerState(
        frames={
            "zzz_other": _fs(Strength.strong, ["P1", "P2"]),
            "aaa_renamed": _fs(Strength.forming, ["P1"]),
        }
    )
    rows = [_row("anchor", ref="P1", at="t1"), _row("anchor", ref="P2", at="t2")]  # one sitting
    h1 = compose_houses(
        project_terrain(state, NOW).regions,
        rows,
        {"anchor": (["embed", "choose_failure"], "choose_failure")},
    )
    h2 = compose_houses(
        project_terrain(renamed, NOW).regions,
        rows,
        {"anchor": (["zzz_other", "aaa_renamed"], "aaa_renamed")},
    )
    assert h1 == h2  # rename invariant -> non-invertible wire
    assert len(h1) == 1  # one sitting -> one saga -> one house (two stories)
    for h in h1:
        assert set(h) == {"region", "bucket", "height_bucket"}  # exactly the L-13-safe keys
        assert isinstance(h["region"], int)
        assert h["bucket"] in (None, 1, 2, 3)
        assert h["height_bucket"] in (1, 2, 3)


def test_cross_sitting_convergences_are_distinct_sagas_not_one_pile():
    # THE "6 houses for 3 convergences" REGRESSION: six convergences across three sittings (2+2+2)
    # must render as THREE houses (three sagas), each two stories — not six houses. This is the
    # dogfood bug, fixed by construction. (L-25: earlier tests never crossed sittings.)
    view = _two_region_view()
    membership = {"dim_t": (["a_weak_a"], None)}
    rows = []
    for s in ("s1", "s2", "s3"):
        rows.append(_row("dim_t", ref="P8", at=f"{s}a", sitting_id=s))
        rows.append(_row("dim_t", ref="P8", at=f"{s}b", sitting_id=s))
    houses = compose_houses(view.regions, rows, membership)
    assert len(houses) == 3  # three sagas, NOT six houses
    assert all(h["region"] == 1 for h in houses)
    assert all(h["height_bucket"] == 2 for h in houses)  # each saga is two stories


def test_saga_region_follows_its_most_recent_convergence():
    # A saga spanning territories/regions across chapters takes the region of its MOST-RECENT
    # converged row (the last in arrival order), deterministically.
    view = _two_region_view()
    membership = {"dim_t": (["a_weak_a"], None), "bright_t": (["z_strong_a"], None)}
    rows = [  # same sitting: chapter 1 in the dim region, chapter 2 (latest) in the bright region
        _row("dim_t", ref="P8", at="t1", sitting_id="s1"),
        _row("bright_t", ref="P1", at="t2", sitting_id="s1"),
    ]
    houses = compose_houses(view.regions, rows, membership)
    assert len(houses) == 1
    assert houses[0]["region"] == 0  # the bright region (r0) — the most-recent chapter's region
    assert houses[0]["height_bucket"] == 2


def test_elevation_is_rename_invariant():
    # Extends the rename-invariance guarantee to the elevation channel.
    state = LearnerState(
        frames={
            "embed": _fs(Strength.strong, ["P1", "P2"]),
            "choose_failure": _fs(Strength.forming, ["P1"]),
        }
    )
    renamed = LearnerState(
        frames={
            "zzz_other": _fs(Strength.strong, ["P1", "P2"]),
            "aaa_renamed": _fs(Strength.forming, ["P1"]),
        }
    )
    assert (
        project_terrain(state, NOW).learner_view() == project_terrain(renamed, NOW).learner_view()
    )


def test_house_height_bucket_puts_one_story_on_its_own_floor_tier():
    from retnovation.terrain import _house_height_bucket

    # 1 story = tier 1; "a few" (2-4) = tier 2; "many" (5+) = tier 3. The 1->2 growth MUST cross a
    # tier (unlike _elevation_bucket's <=2 -> 1) so the "watch my saga grow" payoff registers.
    assert _house_height_bucket(1) == 1
    assert _house_height_bucket(2) == 2
    assert _house_height_bucket(4) == 2
    assert _house_height_bucket(5) == 3
    assert _house_height_bucket(20) == 3
