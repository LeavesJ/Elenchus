from retnovation.content_loader import load_mush_frames, load_spike_prompt


def test_mush_frames_load_and_validate():
    mush = load_mush_frames()
    assert len(mush) >= 6
    for f in mush:
        assert f["frame_code"] and f["frame_detail"] and f["injection"]
    codes = [f["frame_code"] for f in mush]
    assert len(codes) == len(set(codes))  # unique codes


def test_frame_gen_doctrine_forbids_mush():
    p = load_spike_prompt("frame_gen").lower()
    # the generator must demand non-obvious hidden moves and forbid generic advice (L-6)
    assert "hidden move" in p or "non-obvious" in p
    assert "generic advice" in p or "recognize the type" in p or "homework" in p
