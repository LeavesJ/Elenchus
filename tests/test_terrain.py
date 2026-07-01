from datetime import datetime, timezone

from retnovation.terrain import project_terrain, region_clears_guard
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
