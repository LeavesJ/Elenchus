import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from retnovation.web.app import create_app

_ANCHOR_TITLE = "Shipping something you can't take back"  # irreversible_anchor (cto)


def test_menu_carries_persona_theme_and_say_carries_role_theme(tmp_path, make_fake):
    app = create_app(db_path=str(tmp_path / "v.db"), model_factory=make_fake)
    client = TestClient(app)
    menu = client.post("/api/session").json()
    # two-phase: menu has the persona mark but NO role atmosphere yet
    assert menu["theme"]["persona_mark"] == "V"
    assert menu["theme"]["atmosphere_label"] == "neutral"  # role unknown at menu
    assert set(menu["theme"]) == {"persona_mark", "accent", "atmosphere_label"}
    assert "veldra" not in str(menu["theme"]) and "frame" not in str(menu["theme"]).lower()
    # pick the CTO problem -> the opening say carries the role (systems) atmosphere
    idx = menu["problems"].index(_ANCHOR_TITLE)
    r = client.post("/api/session/s/choose", json={"index": idx}).json()
    assert r["kind"] == "say"
    assert r["theme"]["atmosphere_label"] == "systems"
    assert r["theme"]["persona_mark"] == "V"  # constant guide across the phases


def test_index_html_applies_the_theme():
    client = TestClient(create_app(db_path=":memory:", model_factory=None))
    html = client.get("/").text
    assert "persona_mark" in html and "atmosphere_label" in html  # the frontend reads the theme
