from retnovation.content_loader import load_rubric
from retnovation.generator import angle_count


def test_continuity_lock_in_clears_the_gate():
    r = load_rubric("continuity_lock_in")
    assert [f.frame_code for f in r.frames] == ["embed_credentials_as_a_list"]
    assert len(r.traps) == 3
    assert angle_count(r) == 8  # 1 frame + 3 traps + 0 binding + 4 dims = floor
