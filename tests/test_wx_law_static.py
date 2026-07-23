"""Static source guards over the pure placement law (Spec-2 §5): wx_law.js is the determinism
boundary — no Math.random, no THREE, no DOM; mulberry32 is the only randomness; the lattice and
law constants exist with their pinned values. (Behavioral determinism — double-run identity — is
the Phase-C browser smoke's tooth, per the spec's §13 split.)"""
import re
from pathlib import Path

SRC = Path("src/retnovation/web/static/wx_law.js")


def _src() -> str:
    return SRC.read_text()


def test_wx_law_exists_and_is_pure():
    s = _src()
    assert "Math.random" not in s  # the ban has no exceptions in THIS file
    assert "THREE" not in s and "document." not in s and "window.addEventListener" not in s


def test_wx_law_declares_the_pinned_constants():
    s = _src()
    for token in ["K = 24", "R_ORBIT = 46", "R_ROCK = 13", "R_DOME_MAX = 10", "QUAY_W = 3",
                  "137.50776", "R0 = 1.5", "STACK_DR = 0.55", "STACK_DH = 1.1"]:
        assert token in s, token


def test_wx_law_has_mulberry32_and_layout():
    s = _src()
    assert "function mulberry32" in s and "function layout" in s and "function bearing" in s


def test_wx_law_carries_no_banned_copy_tokens():
    # the law file ships no learner-facing strings at all — belt-and-suspenders
    s = _src().lower()
    for tok in ["solved", "mastered", "correct", "streak", "interleave", "innovation"]:
        assert tok not in s, tok
