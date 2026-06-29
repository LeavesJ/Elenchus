from __future__ import annotations


def region_clears_guard(
    frame_codes: set[str], problems: set[str], *, min_frames: int = 2, min_problems: int = 2
) -> bool:
    """Per-region non-invertibility gate (§4b): a region may render decodable vitality only when it
    draws on enough distinct frames across enough distinct problems that brightness cannot be read
    back to one move. Below threshold the region stays a seed."""
    return len(frame_codes) >= min_frames and len(problems) >= min_problems
