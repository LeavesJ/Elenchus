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
