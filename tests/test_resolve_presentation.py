import re

from elenchus.content_loader import CONTENT_ROOT, load_experience
from elenchus.web import voice

_GEAR = ["reflect", "re-point", "STOP pressing"]  # markers of the 3 comprehension behaviors


def test_voice_composes_persona_role_craft_for_a_ceo_problem():
    exp = load_experience("decision_under_stakes")  # role=ceo
    v = voice.resolve_presentation("founder_ceo", exp)["voice"]
    assert "You are Vera" in v  # persona
    assert "board" in v.lower()  # CEO role idiom present
    for g in _GEAR:
        assert g.lower() in v.lower(), f"gear behavior missing from composed voice: {g}"


def test_voice_is_graceful_on_unknown_posture_and_no_role():
    v = voice.resolve_presentation("no_such_posture", None)["voice"]
    assert "You are Vera" in v  # falls back to vera + craft, never raises
    for g in _GEAR:
        assert g.lower() in v.lower()


def test_visual_theme_keys_enum_and_frame_free():
    t_ceo = voice.resolve_presentation("founder_ceo", load_experience("decision_under_stakes"))[
        "visual"
    ]
    t_cto = voice.resolve_presentation("founder_ceo", load_experience("irreversible_anchor"))[
        "visual"
    ]
    assert set(t_ceo) == {"persona_mark", "accent", "atmosphere_label"}
    assert t_ceo["persona_mark"] == t_cto["persona_mark"]  # constant guide
    assert t_ceo["atmosphere_label"] in {"boardroom", "systems"}
    assert t_ceo["atmosphere_label"] != t_cto["atmosphere_label"]  # role varies
    for t in (t_ceo, t_cto):
        blob = str(t)
        assert "veldra" not in blob and "frame" not in blob.lower()


def test_no_register_or_persona_word_shares_a_frame_detail_word():
    # belt: the core move-words never appear in a register/persona/craft layer
    forbidden = {"reversible", "rollback", "optionality", "irreversible", "default", "amend"}
    for name in ("vera", "role_ceo", "role_cto", "voice_craft"):
        text = _layer_text(name).lower()
        hits = {w for w in forbidden if re.search(rf"\b{w}\b", text)}
        assert not hits, f"{name} leaks move-words: {hits}"


def test_registers_do_not_reuse_the_live_frame_vocabulary():
    # Spec §9: derive the move-word denylist from the frame_detail/trap_detail vocabulary of EVERY
    # tagged problem (len>=6 content-words = the move-bearing words; short common words excluded),
    # so the guard tracks the corpus and catches register DRIFT, not just a fixed list. The allowlist
    # covers benign long *world* words both legitimately share (not the move itself).
    from elenchus.content_loader import load_library

    # The complete set of benign world/common words the registers and the move-statements share on
    # the current corpus; the distinctive move-words (reversible, optionality, provision, boundary,
    # defaulting, amended) are in the frames but NOT in any register, so a register drifting to one
    # WILL trip this. Re-derive `allow` if a frame edit adds a new benign shared word.
    allow = {"before", "decision", "instead", "naming", "product", "shipped", "single", "without"}
    move_words: set[str] = set()
    for e in load_library():
        if not e.rubric:
            continue
        for d in [f.frame_detail for f in e.rubric.frames] + [
            t.trap_detail for t in e.rubric.traps
        ]:
            move_words |= {w for w in re.findall(r"[a-z]+", d.lower()) if len(w) >= 6}
    move_words -= allow
    for name in ("vera", "role_ceo", "role_cto", "voice_craft"):
        words = set(re.findall(r"[a-z]+", _layer_text(name).lower()))
        hits = words & move_words
        assert not hits, f"{name} reuses live frame-move words: {sorted(hits)}"


def _layer_text(name):
    for sub in ("prompts", "personas", "voice"):
        p = CONTENT_ROOT / sub / f"{name}.md"
        if p.exists():
            return p.read_text()
    raise AssertionError(name)
