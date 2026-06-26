from retnovation.types import LiftResult, ScenarioVerdict


def _sv(sid, expressed=True, dist=2, pref=1):
    return ScenarioVerdict(
        scenario_id=sid, injection_expressed=expressed, distinguishability=dist, preference=pref
    )


def test_scenario_status_cells():
    assert _sv("s", expressed=False).status(1) == "inconclusive"
    assert _sv("s", dist=0, pref=-1).status(1) == "null"  # below tie-band floor
    assert _sv("s", dist=1, pref=0).status(1) == "neutral"  # tie
    assert _sv("s", dist=2, pref=1).status(1) == "lift"
    assert _sv("s", dist=1, pref=-1).status(1) == "negative"
    assert _sv("s", dist=1, pref=1).status(2) == "null"  # theta_dist=2 -> dist 1 is a wash


def _result(*svs):
    return LiftResult(frame_code="f", scenarios=list(svs), theta_dist=1, min_scenarios=3)


def test_verdict_precedence_is_total():
    assert _result().verdict == "inconclusive"
    assert _result(_sv("a", expressed=False)).verdict == "inconclusive"  # no valid
    assert _result(_sv("a", pref=1), _sv("b", pref=2)).verdict == "lift"  # all lift
    assert _result(_sv("a", pref=1), _sv("b", pref=0)).verdict == "mixed"  # lift + neutral
    assert _result(_sv("a", pref=1), _sv("b", pref=-1)).verdict == "mixed"  # lift + negative
    assert _result(_sv("a", pref=1), _sv("b", dist=0)).verdict == "mixed"  # lift + null
    assert _result(_sv("a", pref=-1), _sv("b", pref=0)).verdict == "negative_lift"  # neg + neutral
    assert _result(_sv("a", pref=-1), _sv("b", dist=0)).verdict == "negative_lift"  # neg + null
    assert _result(_sv("a", pref=0), _sv("b", dist=0)).verdict == "neutral"  # neutral + null
    assert _result(_sv("a", dist=0), _sv("b", dist=0)).verdict == "null"  # all null


def test_screen_action_and_aggregates():
    # auto_kill ONLY on null / negative_lift
    assert _result(_sv("a", dist=0)).screen_action == "auto_kill"  # null
    assert _result(_sv("a", pref=-1)).screen_action == "auto_kill"  # negative_lift
    assert _result(_sv("a", pref=1)).screen_action == "surface"  # lift
    assert _result(_sv("a", pref=1), _sv("b", pref=-1)).screen_action == "surface"  # mixed
    assert _result(_sv("a", pref=0)).screen_action == "surface"  # neutral surfaces
    assert (
        _result(_sv("a", expressed=False)).screen_action == "surface"
    )  # all-inconclusive never kills
    # framed_preferred_count EXCLUDES ties; inconclusive excluded from valid aggregates
    r = _result(_sv("a", pref=2), _sv("b", pref=0), _sv("c", expressed=False))
    assert r.framed_preferred_count == 1  # the tie (b) and inconclusive (c) don't count
    assert r.inconclusive_count == 1
    assert r.mean_preference == 1.0  # (2 + 0) / 2 valid
    assert r.below_floor is True  # 2 valid < min_scenarios 3
