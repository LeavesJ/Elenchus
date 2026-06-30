from retnovation.content_loader import load_experience


def test_role_loads_ceo_and_cto():
    assert load_experience("decision_under_stakes").role == "ceo"
    assert load_experience("continuity_lock_in").role == "ceo"
    assert load_experience("license_continuity").role == "ceo"
    assert load_experience("irreversible_anchor").role == "cto"
    assert load_experience("proof_before_promise").role == "cto"
