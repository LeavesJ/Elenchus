"""A ceiling on what one process can spend, because nothing else bounds it.

Every route on the web surface is unauthenticated and the hostname is the only credential, so
anyone who is forwarded or guesses an invitee link can loop POSTs. One learner turn is roughly
five or six Opus calls at ~$0.89/sitting, 83% of it output tokens, and `MAX_PUSHES = 8` bounds a
single segment while nothing bounds the number of segments. Auth belongs in front of the tunnel
and is not this module's job; this is the blast-radius bound that holds even when auth is absent
or misconfigured, which is the state the beta is in right now.

Counted at `_TimedMessages._timed` because that is the ONE seam every paid call passes through --
verified by the emission audit: all eight `messages.create` sites and all three `messages.parse`
sites go through `_get_client()`, there is no streaming, no token counting, and no batch use.
"""

import pytest

from elenchus import spend
from elenchus.model import ModelError, _TimedMessages


class _FakeMessages:
    def create(self, **kwargs):
        return "created"

    def parse(self, **kwargs):
        return "parsed"


class _FakeClient:
    def __init__(self):
        self.messages = _FakeMessages()


def test_calls_under_the_ceiling_pass_straight_through():
    budget = spend.Budget(max_calls=3)
    client = _TimedMessages(_FakeClient(), budget=budget)

    assert client.create(model="m") == "created"
    assert client.parse(model="m") == "parsed"
    assert budget.spent == 2


def test_the_call_that_would_exceed_the_ceiling_is_refused_before_it_is_billed():
    """Refused BEFORE dispatch, not after: a check that runs afterwards has already paid for the
    call it was meant to prevent."""
    budget = spend.Budget(max_calls=1)
    client = _TimedMessages(_FakeClient(), budget=budget)
    client.create(model="m")

    with pytest.raises(ModelError, match="budget"):
        client.create(model="m")

    assert budget.spent == 1, "the refused call must not be counted as spent"


def test_the_refusal_names_the_ceiling_and_that_it_is_per_process():
    budget = spend.Budget(max_calls=1)
    client = _TimedMessages(_FakeClient(), budget=budget)
    client.create(model="m")

    with pytest.raises(ModelError) as exc:
        client.parse(model="m")

    msg = str(exc.value)
    assert "1" in msg and "process" in msg.lower()


def test_no_budget_means_no_ceiling_so_every_existing_caller_is_unchanged():
    """The suite, the probes and the CLI construct models without a budget. Absent must mean
    'unbounded', never 'zero' -- a default that silently refused every call would take the whole
    product down rather than bound it."""
    client = _TimedMessages(_FakeClient())

    for _ in range(50):
        assert client.create(model="m") == "created"


def test_a_call_that_raises_still_counts_against_the_ceiling():
    """It was billed, or it was an attempt that cost latency and a retry slot. Either way an
    attacker must not get unlimited attempts by making each one fail."""

    class _Boom:
        class messages:
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("upstream")

    budget = spend.Budget(max_calls=2)
    client = _TimedMessages(_Boom(), budget=budget)

    with pytest.raises(RuntimeError):
        client.create(model="m")

    assert budget.spent == 1


def test_the_real_model_path_enforces_the_ceiling_not_just_the_shim(monkeypatch):
    """L-9: the shim tests above prove the counter works. They do NOT prove a call made the way
    the product makes one ever reaches it. This drives a real `AnthropicModel` through
    `_get_client()` -- the path every one of the eleven call sites uses -- with a fake SDK client
    so no money moves."""
    from elenchus.model import AnthropicModel

    model = AnthropicModel(api_key="x", client=_FakeClient(), budget=spend.Budget(max_calls=2))

    assert model._get_client().messages.create(model="m") == "created"
    assert model._get_client().messages.parse(model="m") == "parsed"
    with pytest.raises(ModelError, match="spend budget"):
        model._get_client().messages.create(model="m")


def test_the_budget_survives_across_get_client_calls():
    """`_get_client()` builds a NEW wrapper every time it is called (model.py:708), so a counter
    owned by the wrapper would reset on every single call and bound nothing at all. The budget has
    to live on the model."""
    from elenchus.model import AnthropicModel

    model = AnthropicModel(api_key="x", client=_FakeClient(), budget=spend.Budget(max_calls=1))
    model._get_client().messages.create(model="m")

    with pytest.raises(ModelError, match="spend budget"):
        model._get_client().messages.create(model="m")


def test_from_env_is_absent_by_default_and_reads_the_override():
    assert spend.from_env({}) is None
    assert spend.from_env({"ELENCHUS_MAX_CALLS": ""}) is None
    assert spend.from_env({"ELENCHUS_MAX_CALLS": "42"}).max_calls == 42


def test_the_web_factory_reads_the_ceiling_from_the_environment_once(monkeypatch):
    """The served process picks the ceiling up from the environment without anybody passing it.
    Offline callers -- the CLI, the probes, the suite -- keep getting None. (This replaces a test
    that called the old per-call `_default_model()`, which was the defect.)"""
    from elenchus.web import app as web_app

    monkeypatch.setenv("ELENCHUS_MAX_CALLS", "7")
    model = web_app.model_factory_for_this_process()()
    assert model._budget is not None and model._budget.max_calls == 7

    monkeypatch.delenv("ELENCHUS_MAX_CALLS", raising=False)
    assert web_app.model_factory_for_this_process()()._budget is None


def test_the_ceiling_says_so_server_side_when_it_fires(caplog):
    """Invariant 10, and an operations question: the wire is deliberately generic ("that door hit
    an error"), so if the ceiling is silent server-side too then hitting it is indistinguishable
    from a 401, a timeout, or a bug. The operator needs to tell "we bounded this" from "this
    broke", and the whole point of the ceiling is that it fires under abuse -- exactly when
    somebody will be reading the log to find out what happened."""
    import logging

    budget = spend.Budget(max_calls=1)
    client = _TimedMessages(_FakeClient(), budget=budget)
    client.create(model="m")

    with caplog.at_level(logging.WARNING, logger="elenchus.model"):
        with pytest.raises(ModelError):
            client.create(model="m")

    assert any("spend budget" in r.getMessage() for r in caplog.records), (
        "the ceiling fired and the server log says nothing about it"
    )


def test_the_ceiling_is_per_PROCESS_which_means_one_budget_across_every_segment(monkeypatch):
    """THE DEFECT THE PRE-MERGE REVIEW FOUND (2026-09-02), confirmed by an independent verifier.

    `_default_model()` minted a fresh Budget on every call, and SessionRegistry invokes the model
    factory once per worker start -- on every `start()`, including the one `continue_session`
    makes. So the counter reset on every Continue, the scope was per SEGMENT, and since
    MAX_PUSHES = 8 bounds a segment to far fewer than 500 calls, the shipped ceiling could never
    fire at all. Two commit messages and the module docstring said "per process". They were wrong.

    The reviewer made 49 paid calls under a ceiling of 20 by clicking Continue three times. The
    docstring itself named the hole it was meant to close -- "nothing bounds the number of
    segments" -- and the code left it open. This test is the one line that would have caught it.
    """
    from elenchus.web import app as web_app

    monkeypatch.setenv("ELENCHUS_MAX_CALLS", "7")
    factory = web_app.model_factory_for_this_process()

    a = factory()
    b = factory()
    assert a._budget is b._budget, (
        "two segments got two budgets: the ceiling resets on Continue and bounds nothing"
    )
    assert a._budget.max_calls == 7


def test_a_malformed_ceiling_fails_at_boot_not_at_the_first_learners_click():
    """`ELENCHUS_MAX_CALLS=abc`, `=0`, `=-1` all used to build a factory that raised or refused
    inside the segment worker -- AFTER /api/health had returned {"ok": true}, so the process looked
    healthy while every door died on the first click. That is L-18's shape exactly, with a new
    cause. A value that cannot be a ceiling must refuse to start the process."""
    for bad in ("abc", "0", "-1", "1.5", ""):
        env = {"ELENCHUS_MAX_CALLS": bad}
        if bad == "":
            assert spend.from_env(env) is None  # unset stays unbounded
            continue
        with pytest.raises(ValueError, match="ELENCHUS_MAX_CALLS"):
            spend.from_env(env)
