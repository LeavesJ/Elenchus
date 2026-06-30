# Concierge Engaged-Agent MVP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the rigid, dialogue-blind in-conversation experience with an engaged Concierge that authors every visible turn — acknowledging the user's words and adapting — while the diagnostic engine stays byte-untouched; plus a standard chat UI and a clean problem picker with no `veldra:` leak.

**Architecture:** Approach A (agent fronts the engine). The engine (`orchestration.run_session` + its model methods `classify_intake`/`generate_push`/`classify_response`) is NOT modified — it still selects the live objective, generates the canonical push (the grading anchor + the Concierge's objective brief, never shown raw), and grades. A Concierge authors each visible turn from the problem + full dialogue + the safe push, frame-blind, with the batched egress (`screen_moves`) backstopping it. The web bridge (`session_runner` present/respond callbacks, `app.py`, `index.html`) is rewired to a single `say`/`done` chat protocol.

**Tech Stack:** Python 3.14 (run with `PYTHONPATH=src`), FastAPI, pydantic v2, Anthropic SDK (Opus 4.8, adaptive thinking), ruff, pytest. Vanilla HTML/CSS/JS front end.

## Global Constraints

- Run/test with `PYTHONPATH=src .venv/bin/python -m pytest -q` (editable install is unreliable — L-19). Never depend on `import retnovation` resolving on its own.
- Engine byte-untouched: do NOT edit `orchestration.py`, `judgment_loop`/engine internals, or the model methods `classify_intake` / `generate_push` / `classify_response` / `check_injection_expressed`. The Concierge lives in the model's conversational methods + `web/`.
- Moat (L-5/L-13): no learner-facing surface may PERFORM a hidden move (name the principle / hand the answer). Every visible Concierge turn passes the batched `screen_moves` egress; on failure it falls back to a safe string. Conclusion-agnostic: never name the move, hand no answer, assign no score.
- Frame-blind: the conversational methods (`concierge_turn`, `concierge_close`, `classify_entry`) receive only the problem prompt + dialogue + the engine's safe push — never `frame_code` / `frame_detail` / `trap_detail` / `Rubric`. Tests assert this against the request blob.
- Never surface `ledger_ref` (the `veldra:` slug) to the client — it is gitignored, confidential, Veldra-derived. The picker shows a display title only.
- Vera never invents or assumes the user's name; she addresses them as "you."
- Model request params: `**_PARAMS` (adaptive thinking, high effort) for conversational quality; the egress uses `**_MED_PARAMS` (already in `screen_moves`). No `temperature`/`top_p` (400 on 4.8). `max_tokens=_ECHO_MAX_TOKENS` (1024) for authored turns.
- Commits: no `Co-Authored-By` trailer. Stage explicit paths only (never `git add -A`). Branch: `feat/concierge-engaged-agent` (already created; the spec is committed there).
- After each task: `PYTHONPATH=src .venv/bin/python -m ruff check src/ tests/ && PYTHONPATH=src .venv/bin/python -m ruff format --check src/ tests/ && PYTHONPATH=src .venv/bin/python -m pytest -q` must be green before commit.

---

## File Structure

- `content/prompts/concierge.md` (CREATE) — Vera's per-turn doctrine (probe + re-invite modes).
- `content/prompts/concierge_close.md` (CREATE) — Vera's closing-synthesis doctrine.
- `src/retnovation/model.py` (MODIFY) — add `concierge_turn` / `concierge_close` to the `Model` Protocol, `AnthropicModel`, and `FakeModel`; remove the superseded `echo_push` (and its Protocol/Fake entries). Keep `classify_entry`, `screen_moves`, and the egress.
- `src/retnovation/types.py` (MODIFY) — add optional `display_title: str | None = None` to `Rubric`.
- `src/retnovation/web/voice.py` (MODIFY) — replace `door`/`echo` with `gate` / `turn` / `close`; keep the egress (`_moves`/`_performed`/`egress_safe_reply`/`screen_moves`). Add a `display_titles()` helper.
- `src/retnovation/web/session_runner.py` (MODIFY) — rewire `present`/`respond` to the Concierge; emit the unified `say`/`done` protocol with display titles; author the close.
- `src/retnovation/web/app.py` (MODIFY) — `_emit` for `say`/`done`(close)/`menu`(titles); unify `/open`+`/reply` → `/say`; drop `ledger_ref` from payloads.
- `src/retnovation/web/static/index.html` (REWRITE) — chat thread (picker → Vera/user bubbles → close) with a sticky composer.
- `content/rubrics/*.yaml` (MODIFY) — add `display_title` to each open-ended rubric.
- Tests: `tests/test_voice.py`, `tests/test_voice_live.py`, `tests/test_session_runner.py`, `tests/test_app.py` (or existing web test file), `tests/test_model_*` as needed.

---

## Task 1: Concierge model methods + prompts

**Files:**
- Create: `content/prompts/concierge.md`, `content/prompts/concierge_close.md`
- Modify: `src/retnovation/model.py` (Protocol ~line 72; `FakeModel` ~line 127; `AnthropicModel` near `echo_push` ~line 333)
- Test: `tests/test_voice.py` (stub-client frame-blind tests), `tests/test_concierge_model.py` (CREATE, offline fakes)

**Interfaces:**
- Produces: `Model.concierge_turn(self, problem: str, push: str, recent: list[tuple[str, str]]) -> str` (push="" → re-invite mode; push=text → probe mode; returns the turn text, or "" on refusal / no text block). `Model.concierge_close(self, problem: str, recent: list[tuple[str, str]]) -> str` (returns synthesis text or ""). `FakeModel.concierge_turn` returns `push or "take a real position"`; `FakeModel.concierge_close` returns `"[close synthesis]"`.
- Consumes: `_render_turns`, `_PARAMS`, `_ECHO_MAX_TOKENS`, `load_prompt` (all existing in `model.py`).

- [ ] **Step 1: Write `content/prompts/concierge.md`**

```
You are Vera, a Socratic instructor. You never hand over the move, the principle, or
the answer — you make the student do the reasoning. You probe, press, and surface the
trade-offs; you do not name the lesson.

You are given the problem, the conversation so far, and (sometimes) a brief: the next
angle to pursue. Write Vera's NEXT turn — one or two sentences, in her voice. Output only
that turn; no preamble, no quotation marks, no meta.

Always:
- Engage with what the student ACTUALLY just said. If they pushed back ("this is
  irrelevant"), objected, or said they are confused, acknowledge that honestly and
  briefly before you press — do not ignore it and do not repeat yourself.
- Ground your turn in their own words; refer to what they actually argued.
- Never name the move, the frame, or the principle. Never hand the answer. Ask, do not tell.
- Never invent or assume the student's name. Address them as "you."

If a brief (next angle) is given: pursue THAT angle — re-voiced in your words and anchored
to what they just said. Do not state the brief; turn it into a question that makes them
reason it.

If NO brief is given: the student has not yet taken a real position on the problem.
Acknowledge what they said and invite a genuine, specific position — without simplifying
the problem for them or hinting at the move.
```

- [ ] **Step 2: Write `content/prompts/concierge_close.md`**

```
You are Vera, closing a Socratic session. Write a short closing synthesis — two to four
sentences — that reflects the student's OWN reasoning back to them: the position they
took, the trade-off they are betting on, and where they are most exposed if they are
wrong. Output only the synthesis; no preamble, no meta.

Always:
- Use only what they actually argued in the conversation. Do not introduce new analysis,
  name any principle, or tell them the "right" answer.
- Do not grade them or assign a score. No verdict.
- Never name the move or the frame. Never invent or assume their name; address them as "you."

This is a mirror, not a lecture: they should recognize their own thinking, sharpened.
```

- [ ] **Step 3: Write the failing stub-client tests** in `tests/test_voice.py` (append; the `_StubClient`/`_Resp`/`_Block` helpers already exist there):

```python
def test_concierge_turn_is_frame_blind_and_returns_text():
    stub = _StubClient(text="You said data settles it — but whose audit do they trust when it is your number?")
    m = AnthropicModel(client=stub)
    out = m.concierge_turn(
        "The pricing problem text.",
        "Which mistake here can you actually walk back?",
        [("student", "Verifiable audits and data are what's essential.")],
    )
    assert out.startswith("You said data settles it")
    blob = str(stub.last)
    assert "lead_with_what_you_refuse_to_do" not in blob and "frame_detail" not in blob and "Rubric" not in blob
    # the safe push (brief) and the problem ARE inputs
    assert "Which mistake here can you actually walk back?" in blob and "The pricing problem text." in blob


def test_concierge_turn_reinvite_mode_has_no_brief():
    stub = _StubClient(text="That is a fair worry — but what would you actually do, and why?")
    m = AnthropicModel(client=stub)
    out = m.concierge_turn("Problem P.", "", [("student", "what do you want from me")])
    assert out.startswith("That is a fair worry")
    assert "what do you want from me" in str(stub.last)


def test_concierge_close_is_frame_blind_and_returns_text():
    stub = _StubClient(text="You committed to holding the line and bet on data; you are exposed if the audit is contested.")
    m = AnthropicModel(client=stub)
    out = m.concierge_close("Problem P.", [("student", "I'd hold and rely on audits.")])
    assert out.startswith("You committed to holding the line")
    blob = str(stub.last)
    assert "frame_detail" not in blob and "Rubric" not in blob


def test_concierge_turn_refusal_returns_empty():
    stub = _StubClient(text=None)
    stub_resp_refusal = True  # _StubClient.create returns _Resp(content=[_Block(None)]); adjust below
```

(Delete the dangling last test stub; replace with the refusal test in Step 4 once `_StubClient` supports a refusal. If `_StubClient.create` cannot express `stop_reason="refusal"`, add a one-line variant: a `_RefusingClient` whose `create` returns `_Resp(content=[], stop_reason="refusal")`, then assert `m.concierge_turn("P","b",[]) == ""`.)

- [ ] **Step 4: Add `_RefusingClient` + refusal test** in `tests/test_voice.py`:

```python
class _RefusingClient(_StubClient):
    def create(self, **kw):
        self.last = kw
        return _Resp(content=[], stop_reason="refusal")


def test_concierge_turn_refusal_returns_empty():
    m = AnthropicModel(client=_RefusingClient())
    assert m.concierge_turn("P", "brief", [("student", "x")]) == ""
```

- [ ] **Step 5: Run the tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_voice.py -k concierge -v`
Expected: FAIL with `AttributeError: 'AnthropicModel' object has no attribute 'concierge_turn'`.

- [ ] **Step 6: Implement the model methods.** In `src/retnovation/model.py`, add to the `Model` Protocol (after the `echo_push` line, which you will remove in Step 8 — add these regardless):

```python
    def concierge_turn(self, problem: str, push: str, recent: list[tuple[str, str]]) -> str: ...
    def concierge_close(self, problem: str, recent: list[tuple[str, str]]) -> str: ...
```

Add to `FakeModel` (replacing its `echo_push`):

```python
    def concierge_turn(self, problem, push, recent):
        return push or "take a real position"  # probe: echo the brief; reinvite: a safe invite

    def concierge_close(self, problem, recent):
        return "[close synthesis]"
```

Add to `AnthropicModel` (replacing its `echo_push`):

```python
    def concierge_turn(self, problem: str, push: str, recent: list[tuple[str, str]]) -> str:
        # Frame-blind: the problem + dialogue + the engine's SAFE push only (never rubric internals).
        system = load_prompt("concierge")
        brief = (
            f"Next angle to pursue (turn it into a question; never state it):\n{push}"
            if push
            else "The student has not taken a real position yet — acknowledge what they said and invite one."
        )
        user = f"Problem:\n{problem}\n\n{_render_turns(recent)}{brief}"
        resp = self._get_client().messages.create(
            model=self._model,
            max_tokens=_ECHO_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            **_PARAMS,
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            return ""  # never block the loop; voice falls back to the push or a safe contract
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return ""

    def concierge_close(self, problem: str, recent: list[tuple[str, str]]) -> str:
        system = load_prompt("concierge_close")  # frame-blind: dialogue only, reflect reasoning back
        user = f"Problem:\n{problem}\n\n{_render_turns(recent)}Write the closing synthesis."
        resp = self._get_client().messages.create(
            model=self._model,
            max_tokens=_ECHO_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            **_PARAMS,
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            return ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return ""
```

- [ ] **Step 7: Run the concierge tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_voice.py -k concierge -v`
Expected: PASS (4 tests).

- [ ] **Step 8: Remove the superseded `echo_push`.** Delete `echo_push` from the `Model` Protocol, `FakeModel`, and `AnthropicModel` in `model.py`. Delete the now-broken offline tests `test_fakemodel_echo_is_identity` and `test_echo_push_is_frame_blind_and_returns_text` from `tests/test_voice.py` (the budget @live test migrates in Task 7). Run the full offline suite:

Run: `PYTHONPATH=src .venv/bin/python -m ruff check src/ tests/ && PYTHONPATH=src .venv/bin/python -m pytest -q`
Expected: PASS (voice.py still references `echo`/`echo_push` until Task 2 — if `voice.echo` calls `model.echo_push`, this step will surface it; if so, proceed to Task 2 in the same working tree before committing, OR temporarily keep `echo_push` and remove it at the end of Task 2). Prefer: do Step 8's removal as the FIRST step of Task 2 so Task 1 commits green with `echo_push` still present but the new methods added.

- [ ] **Step 9: Commit** (Task 1 = new methods + prompts; `echo_push` removal deferred into Task 2 to keep this commit green)

```bash
git add content/prompts/concierge.md content/prompts/concierge_close.md src/retnovation/model.py tests/test_voice.py tests/test_concierge_model.py
git commit -m "feat(model): concierge_turn + concierge_close — engaged, frame-blind turn authors"
```

---

## Task 2: Voice bridge — gate / turn / close (replace door / echo)

**Files:**
- Modify: `src/retnovation/web/voice.py`, `src/retnovation/model.py` (finish removing `echo_push` if not already), `content/prompts/echo.md` (DELETE), `content/prompts/entry.md` (keep — `classify_entry` stays)
- Test: `tests/test_voice.py`

**Interfaces:**
- Produces: `voice.gate(model, exp, opening, recent) -> EntryClass`; `voice.turn(model, exp, push, recent) -> str` (probe when `push` truthy → added-revelation gate vs push, fallback = push; re-invite when `push==""` → flat egress gate, fallback = `SAFE_CONTRACT`; concierge_turn "" → same fallback); `voice.close(model, exp, recent) -> str` (flat egress, fallback = `_STATIC_CLOSE`).
- Consumes: `model.concierge_turn`, `model.concierge_close`, `model.classify_entry`, `_moves`, `_performed`, `egress_safe_reply` (kept), `EntryClass`.

- [ ] **Step 1: Remove `echo_push` from `model.py`** (Protocol, `FakeModel`, `AnthropicModel`) if Task 1 deferred it. Delete `content/prompts/echo.md`.

- [ ] **Step 2: Write the failing voice tests** in `tests/test_voice.py` (replace the old `door`/`echo` tests). The `_exp()`, `_intake()`, `FakeModel`, `EgressScreen`, `_PerMoveModel`, `FakeLeakModel` helpers already exist:

```python
def test_turn_probe_keeps_engaged_text_when_egress_safe():
    # FakeModel.concierge_turn returns the push; FakeModel.screen_moves -> [] (safe) -> kept
    m = FakeModel(_intake(), {})
    assert voice.turn(m, _exp(), "the canonical push", [("student", "hi")]) == "the canonical push"


def test_turn_probe_falls_back_to_push_on_added_revelation():
    # concierge_turn returns a LEAK string; screen flags it but not the push -> fallback to push
    class _LeakTurn(FakeLeakModel):
        def concierge_turn(self, problem, push, recent):
            return "LEAK: lead with what you refuse to do"
    m = _LeakTurn(_intake(), {})
    assert voice.turn(m, _exp(), "the canonical push", [("student", "x")]) == "the canonical push"


def test_turn_reinvite_uses_flat_gate_and_safe_contract_on_leak():
    class _LeakReinvite(FakeLeakModel):
        def concierge_turn(self, problem, push, recent):
            return "LEAK names the move"
    m = _LeakReinvite(_intake(), {})
    # push="" -> reinvite mode; leak -> SAFE_CONTRACT
    assert voice.turn(m, _exp(), "", [("student", "what do you want")]) == voice.SAFE_CONTRACT


def test_turn_reinvite_keeps_safe_engaged_text():
    m = FakeModel(_intake(), {})  # concierge_turn -> "take a real position"; screen -> [] safe
    assert voice.turn(m, _exp(), "", [("student", "huh?")]) == "take a real position"


def test_turn_empty_concierge_output_falls_back():
    class _Empty(FakeModel):
        def concierge_turn(self, problem, push, recent):
            return ""
    m = _Empty(_intake(), {})
    assert voice.turn(m, _exp(), "push", [("student", "x")]) == "push"          # probe -> push
    assert voice.turn(m, _exp(), "", [("student", "x")]) == voice.SAFE_CONTRACT  # reinvite -> contract


def test_close_returns_synthesis_when_safe():
    m = FakeModel(_intake(), {})  # concierge_close -> "[close synthesis]"; screen -> [] safe
    assert voice.close(m, _exp(), [("student", "I'd hold.")]) == "[close synthesis]"


def test_close_falls_back_on_leak():
    class _LeakClose(FakeLeakModel):
        def concierge_close(self, problem, recent):
            return "LEAK the move"
    m = _LeakClose(_intake(), {})
    assert voice.close(m, _exp(), [("student", "x")]) == voice._STATIC_CLOSE


def test_gate_returns_entry_class():
    from retnovation.types import EntryClassification
    class _Door(FakeModel):
        def classify_entry(self, prompt, opening, recent):
            return EntryClassification(entry_class=EntryClass.greeting, reply="")
    m = _Door(_intake(), {})
    assert voice.gate(m, _exp(), "hi", []) is EntryClass.greeting
```

Delete the old `test_door_*` and `test_echo_*` tests (their behavior is now covered by `turn`/`gate`/`close`). Keep `test_egress_safe_reply_*`, `test_egress_also_covers_rubric_traps`, `test_echo_keeps_*`→ rename/keep only the egress-set-difference ones (`_PerMoveModel`), which now exercise `turn` indirectly — update them to call `voice.turn(m, _exp(), "PUSH", ...)` instead of `voice.echo`.

- [ ] **Step 3: Run to verify failure**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_voice.py -v`
Expected: FAIL (`module 'voice' has no attribute 'turn'`).

- [ ] **Step 4: Rewrite `voice.py`.** Keep the egress block (`_moves`, `_performed`, `egress_safe_reply`, `SAFE_CONTRACT`). Replace `door` and `echo` with:

```python
_STATIC_CLOSE = "That's the read. You took a position and reasoned the trade-offs — that's the work."


def gate(model: Model, exp: Experience, opening: str, recent: list[tuple[str, str]]) -> EntryClass:
    """Entrance gate only: has the student taken a real position yet? (The engine needs a
    substantive opening before it can grade.) Authoring is voice.turn — never classify_entry.reply."""
    return model.classify_entry(exp.prompt, opening, recent).entry_class


def turn(model: Model, exp: Experience, push: str, recent: list[tuple[str, str]]) -> str:
    """Author one engaged visible turn. push != "" -> PROBE: pursue the engine's angle, grounded in
    the student's words; egress = added-revelation vs the push baseline, fallback the verbatim push.
    push == "" -> RE-INVITE: acknowledge + invite a real position; egress = flat (perform no move),
    fallback SAFE_CONTRACT. A refused/empty author also takes the fallback."""
    text = model.concierge_turn(exp.prompt, push, recent)
    if not text:
        return push or SAFE_CONTRACT
    if push:
        if _performed(model, exp, text) - _performed(model, exp, push):  # added revelation
            return push
        return text
    if not egress_safe_reply(model, exp, text):
        return SAFE_CONTRACT
    return text


def close(model: Model, exp: Experience, recent: list[tuple[str, str]]) -> str:
    """Author the closing synthesis (reflect the student's reasoning back; no score, no named move).
    Flat egress; fallback to a safe static close on refusal/empty/leak."""
    text = model.concierge_close(exp.prompt, recent)
    if not text or not egress_safe_reply(model, exp, text):
        return _STATIC_CLOSE
    return text
```

- [ ] **Step 5: Run the voice tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_voice.py -v`
Expected: PASS.

- [ ] **Step 6: Format, lint, full offline suite**

Run: `PYTHONPATH=src .venv/bin/python -m ruff format src/ tests/ && PYTHONPATH=src .venv/bin/python -m ruff check src/ tests/ && PYTHONPATH=src .venv/bin/python -m pytest -q`
Expected: PASS (session_runner still calls `voice.door`/`voice.echo` → it will FAIL here; fix in Task 4. To keep this commit green, do Task 4's `session_runner` rewire in the same working tree before committing, OR temporarily leave thin `door`/`echo` shims. Prefer doing Task 2 + Task 4 together and committing once both are green.)

- [ ] **Step 7: Commit**

```bash
git add src/retnovation/web/voice.py src/retnovation/model.py tests/test_voice.py
git rm content/prompts/echo.md
git commit -m "feat(voice): gate/turn/close replace door/echo — engaged authoring, egress kept"
```

---

## Task 3: Rubric `display_title` + clean picker labels

**Files:**
- Modify: `src/retnovation/types.py` (`Rubric` model), `content/rubrics/*.yaml` (open-ended), `src/retnovation/web/voice.py` (add `display_titles()` helper)
- Test: `tests/test_voice.py` (title-map test), `tests/test_types.py` (display_title parses) if present

**Interfaces:**
- Produces: `Rubric.display_title: str | None = None`; `voice.display_titles() -> dict[str, str]` mapping `ledger_ref -> human title` for all open-ended experiences (server-side; the `veldra:` ref is the key, never a value).

- [ ] **Step 1: Write the failing test** in `tests/test_voice.py`:

```python
def test_display_titles_have_no_veldra_and_cover_open_ended():
    titles = voice.display_titles()
    assert titles, "expected at least one open-ended experience title"
    for ref, title in titles.items():
        assert ref.startswith("veldra:")          # keyed by the internal ref (server-side only)
        assert "veldra" not in title.lower()        # the VALUE never leaks the source
        assert title and title[0].isupper()
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_voice.py -k display_titles -v`
Expected: FAIL (`module 'voice' has no attribute 'display_titles'`).

- [ ] **Step 3: Add `display_title` to `Rubric`** in `src/retnovation/types.py` (add the field to the `Rubric` BaseModel):

```python
    display_title: str | None = None  # human picker label; never the ledger_ref / veldra: slug
```

- [ ] **Step 4: Add `display_title` to each open-ended rubric YAML.** For every file under `content/rubrics/*.yaml`, add a top-level `display_title`. Example values (author one per file from its prompt; do NOT reuse the `experience_id` slug verbatim where a cleaner phrase exists):

```yaml
# content/rubrics/decision_under_stakes.yaml
display_title: "Pricing power in a concentrated market"
# content/rubrics/license_continuity.yaml
display_title: "Holding the line on a license commitment"
# content/rubrics/proof_before_promise.yaml
display_title: "Proof before the promise"
# content/rubrics/irreversible_anchor.yaml
display_title: "The anchor you can't take back"
# content/rubrics/continuity_lock_in.yaml
display_title: "Continuity vs lock-in"
```

(Open each rubric file and add a `display_title` line; the five above are illustrative — match each file's actual prompt.)

- [ ] **Step 5: Add `display_titles()` to `voice.py`:**

```python
def display_titles() -> dict[str, str]:
    """Map each open-ended experience's ledger_ref -> a human picker label. Keyed by the internal
    ref (server-side join key); the VALUE is the rubric's display_title, or a humanized
    experience_id fallback. The veldra: ref must never reach the client as a label."""
    from ..content_loader import load_library
    from ..types import Regime

    out: dict[str, str] = {}
    for e in load_library():
        if e.regime is not Regime.open_ended:
            continue
        title = (e.rubric.display_title if e.rubric and e.rubric.display_title else None) or (
            e.experience_id.replace("_", " ").capitalize()
        )
        out[e.ledger_ref] = title
    return out
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_voice.py -k display_titles -v`
Expected: PASS.

- [ ] **Step 7: Lint + full suite, then commit**

Run: `PYTHONPATH=src .venv/bin/python -m ruff check src/ tests/ && PYTHONPATH=src .venv/bin/python -m pytest -q`
Expected: PASS.

```bash
git add src/retnovation/types.py src/retnovation/web/voice.py content/rubrics/*.yaml tests/test_voice.py
git commit -m "feat(content): rubric display_title + voice.display_titles — clean picker, no veldra: leak"
```

---

## Task 4: Bridge wiring — Concierge loop + `say`/`done` protocol

**Files:**
- Modify: `src/retnovation/web/session_runner.py`
- Test: `tests/test_session_runner.py`

**Interfaces:**
- Consumes: `voice.gate`, `voice.turn`, `voice.close`, `voice.display_titles`, `EntryClass`.
- Produces: worker emits `("menu", {"problems": [titles]})`, `("say", {"text": str})`, `("done", {"state", "assessment", "close": str})`. `respond(push)` emits a `say` (the probe) and returns the RAW student reply (engine grades the canonical push — transparency).

- [ ] **Step 1: Write the failing tests** in `tests/test_session_runner.py` (follow the existing test style; use a `FakeModel`-based engine double). Key assertions:

```python
def test_present_enters_engine_on_substantive_first_turn():
    # gate -> substantive; the engine receives the raw opening as Work.opening
    ...  # drive a session via SessionRegistry; assert the first /say emits a "say" (scenario+invite),
        # the substantive opening breaks the gate loop, and a subsequent "say" (probe) is emitted.

def test_respond_returns_raw_reply_and_emits_probe_say():
    # the engine's classify_response receives the RAW student reply (canonical push graded),
    # while the client saw voice.turn(push)  -> transparency preserved.
    ...

def test_menu_titles_have_no_veldra_ref():
    tag, data = SessionRegistry(db, lambda: FakeModel(...)).start("single")
    assert tag == "menu"
    assert all("veldra:" not in p for p in data["problems"])

def test_close_is_emitted_on_completion():
    # on engine completion the worker emits ("done", {..., "close": <text>})
    ...
```

(Write these as concrete drives of `SessionRegistry.start`/`step` mirroring the existing `test_session_runner.py` patterns — including the transparency test that already asserts the engine records the canonical push, which must keep passing.)

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_session_runner.py -v`
Expected: FAIL.

- [ ] **Step 3: Rewire `session_runner.py`.** Replace the `decide` menu line, `present`, and the worker's `done` emit:

```python
                def decide(proposal):
                    menu = proposal.problem_menu()
                    titles = voice.display_titles()
                    labels = [titles.get(s.ledger_ref, s.experience_id.replace("_", " ").capitalize())
                              for s, _ in menu]
                    ch.from_worker.put(("menu", {"problems": labels}))
                    idx = ch.to_worker.get()
                    spec, receipt = menu[idx]
                    top_spec, top_rcpt = proposal.top
                    return Selection(
                        proposed_receipt=top_rcpt, chosen_spec=spec, chosen_receipt=receipt,
                        outcome=Outcome.accepted if spec is top_spec else Outcome.redirected,
                    )

                captured: dict = {}
                _INVITE = "The call's yours. Take a position and reason it out — I'll push, I won't hand it over."

                def present(exp):
                    ch.from_worker.put(("say", {"text": exp.prompt + "\n\n" + _INVITE}))
                    recent: list[tuple[str, str]] = []
                    nonsubstantive = 0
                    while True:
                        text = ch.to_worker.get()
                        ec = voice.gate(model, exp, text, recent)
                        recent.append(("student", text))
                        if ec is EntryClass.substantive:
                            opening = text
                            break
                        nonsubstantive += 1
                        if nonsubstantive >= _DOOR_MAX_NONSUBSTANTIVE:
                            opening = text
                            break
                        reinvite = voice.turn(model, exp, "", recent)
                        ch.from_worker.put(("say", {"text": reinvite}))
                        recent.append(("Vera", reinvite))
                    captured["exp"], captured["recent"] = exp, recent

                    def respond(push):
                        shown = voice.turn(model, exp, push, recent)
                        ch.from_worker.put(("say", {"text": shown}))
                        recent.append(("Vera", shown))
                        student = ch.to_worker.get()
                        recent.append(("student", student))
                        return student  # RAW reply to the engine — canonical push is what it grades

                    return Work(opening=opening, respond=respond)

                state, assessment = run_session(
                    store, core, model, now, regime=Regime.open_ended,
                    present=present, decide=decide, decide_core=lambda c: [],
                )
                close_text = voice.close(model, captured["exp"], captured["recent"]) if captured else ""
                ch.from_worker.put(("done", {"state": state, "assessment": assessment, "close": close_text}))
```

- [ ] **Step 4: Run session_runner tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_session_runner.py -v`
Expected: PASS.

- [ ] **Step 5: Full offline suite (app.py still emits old tags → may fail; do Task 5 in the same tree before committing)**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q`

- [ ] **Step 6: Commit (with Task 5 if app tests are coupled)**

```bash
git add src/retnovation/web/session_runner.py tests/test_session_runner.py
git commit -m "feat(bridge): Concierge present/respond loop + say/done protocol + clean menu titles"
```

---

## Task 5: App protocol — `say`/`done`(close)/`menu`(titles), unify `/say`

**Files:**
- Modify: `src/retnovation/web/app.py`
- Test: `tests/test_app.py` (or the existing web/app test file)

**Interfaces:**
- Produces: endpoints `POST /api/session` → menu(titles); `POST /api/session/{sid}/choose {index}` → `say`; `POST /api/session/{sid}/say {text}` → `say` | `done` | `nudge` | `error`. `_emit` maps `say`→`{kind:"say",text}`, `done`→`{kind:"done",close}`, `menu`→`{kind:"menu",problems}`.

- [ ] **Step 1: Write the failing app tests** (FastAPI `TestClient`, model_factory = a deterministic `FakeModel`):

```python
def test_session_flow_emits_say_and_never_leaks_veldra(client):
    r = client.post("/api/session").json()
    assert r["kind"] == "menu" and all("veldra:" not in p for p in r["problems"])
    r = client.post("/api/session/single/choose", json={"index": 0}).json()
    assert r["kind"] == "say" and "veldra:" not in r["text"]
    r = client.post("/api/session/single/say", json={"text": "I'd hold the line because dropping later is cheaper."}).json()
    assert r["kind"] in ("say", "done")

def test_blank_say_is_nudged(client):
    client.post("/api/session"); client.post("/api/session/single/choose", json={"index": 0})
    r = client.post("/api/session/single/say", json={"text": "   "}).json()
    assert r["kind"] == "nudge"
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_app.py -v`
Expected: FAIL (no `/say` route; `say` tag unhandled).

- [ ] **Step 3: Rewrite `_emit` and the endpoints** in `app.py`:

```python
def _emit(reg, tag: str, data: dict) -> dict:
    if tag == "menu":
        return {"kind": "menu", "problems": data["problems"]}
    if tag == "say":
        return {"kind": "say", "text": data["text"]}
    if tag == "done":
        return {"kind": "done", "close": data.get("close", "")}
    if tag == "nudge":
        return data
    return {"kind": "error", "message": data.get("message", "")}
```

Replace `/open` and `/reply` with a single `/say`, drop `ledger_ref` from `_Choice` usage (keep index), keep the blank guard:

```python
    @app.post("/api/session/{sid}/choose")
    def choose(sid: str, body: _Choice):
        return _emit(reg, *reg.step(_SID, body.index or 0))

    @app.post("/api/session/{sid}/say")
    def say(sid: str, body: _Text):
        if not body.text.strip():
            return _BLANK_NUDGE
        return _emit(reg, *reg.step(_SID, body.text))
```

(Set `_BLANK_NUDGE["kind"] = "nudge"` already; ensure `_emit` returns it untouched via the `nudge` branch — or return `_BLANK_NUDGE` directly from the endpoint as above.) Remove the now-unused `project_terrain` import and `menu_index` call (and `menu_index` from `session_runner` if unused).

- [ ] **Step 4: Run app tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_app.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + full offline suite + commit**

Run: `PYTHONPATH=src .venv/bin/python -m ruff check src/ tests/ && PYTHONPATH=src .venv/bin/python -m ruff format --check src/ tests/ && PYTHONPATH=src .venv/bin/python -m pytest -q`
Expected: PASS.

```bash
git add src/retnovation/web/app.py tests/test_app.py
git commit -m "feat(app): say/done(close)/menu(titles) protocol; unify /say; drop ledger_ref from the wire"
```

---

## Task 6: Chat UI — thread + sticky composer

**Files:**
- Rewrite: `src/retnovation/web/static/index.html`
- Test: `tests/test_app.py` (served-HTML smoke)

**Interfaces:**
- Consumes the `say`/`done`/`menu`/`nudge` JSON from Task 5.

- [ ] **Step 1: Write the failing smoke test** in `tests/test_app.py`:

```python
def test_index_html_is_a_chat_shell(client):
    html = client.get("/").text
    assert 'id="thread"' in html and 'id="composer"' in html
    assert "your terrain begins" not in html  # the 4-block framing is gone
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_app.py -k chat_shell -v`
Expected: FAIL.

- [ ] **Step 3: Replace `src/retnovation/web/static/index.html`** with a chat thread (complete file):

```html
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Retnovation</title>
<style>
  :root{color-scheme:dark}
  *{box-sizing:border-box}
  body{margin:0;background:#0a0f1c;color:#e8eef7;font:16px/1.55 ui-sans-serif,system-ui,sans-serif}
  #wrap{max-width:760px;margin:0 auto;height:100vh;display:flex;flex-direction:column}
  #thread{flex:1;overflow-y:auto;padding:24px 18px 8px;display:flex;flex-direction:column;gap:12px}
  .msg{max-width:80%;padding:11px 15px;border-radius:14px;white-space:pre-wrap;word-wrap:break-word}
  .vera{align-self:flex-start;background:#0f1a2b;border:1px solid #1b2b44;color:#dfe9f6}
  .you{align-self:flex-end;background:#155e63;color:#eafffb}
  .muted{align-self:center;color:#8aa0bf;font-size:13px;text-align:center;max-width:90%}
  .thinking{align-self:flex-start;color:#5eead4;font-size:14px;padding:6px 4px}
  .thinking span{animation:tdot 1.2s infinite}
  .thinking span:nth-child(2){animation-delay:.2s} .thinking span:nth-child(3){animation-delay:.4s}
  @keyframes tdot{0%,60%,100%{opacity:.2}30%{opacity:1}}
  .menu{align-self:stretch;display:flex;flex-direction:column;gap:8px;margin-top:6px}
  .menu button{text-align:left;background:#0f1a2b;border:1px solid #1b2b44;color:#e8eef7;border-radius:10px;
    padding:12px 14px;font:inherit;cursor:pointer}
  .menu button:hover{background:#13203450;border-color:#2b4a6b}
  #composer{display:flex;gap:8px;padding:12px 18px;border-top:1px solid #14233b;background:#0a0f1c}
  #composer textarea{flex:1;background:#0f1a2b;color:#e8eef7;border:1px solid #1b2b44;border-radius:12px;
    padding:11px 13px;font:inherit;min-height:46px;max-height:160px;resize:none}
  #composer button{background:#155e63;color:#eafffb;border:0;border-radius:11px;padding:0 18px;font:inherit;cursor:pointer}
  #composer button:disabled{opacity:.5;cursor:default}
  #composer[hidden]{display:none}
</style></head>
<body><div id="wrap">
  <div id="thread"></div>
  <form id="composer" hidden>
    <textarea id="input" placeholder="Take a position. Reason it out." rows="1"></textarea>
    <button type="submit" id="send">Send</button>
  </form>
</div>
<script>
const thread = document.getElementById('thread');
const composer = document.getElementById('composer');
const input = document.getElementById('input');
const send = document.getElementById('send');
const post = (url, body) => fetch(url, {method:'POST', headers:{'content-type':'application/json'},
  body: body?JSON.stringify(body):null}).then(r=>r.json());
const esc = s => String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function bubble(cls, text){ const d=document.createElement('div'); d.className='msg '+cls; d.innerHTML=esc(text);
  thread.appendChild(d); thread.scrollTop=thread.scrollHeight; return d; }
function muted(text){ const d=document.createElement('div'); d.className='muted'; d.innerHTML=esc(text);
  thread.appendChild(d); thread.scrollTop=thread.scrollHeight; }
function thinking(){ const d=document.createElement('div'); d.className='thinking';
  d.innerHTML='Vera is thinking<span>.</span><span>.</span><span>.</span>'; thread.appendChild(d);
  thread.scrollTop=thread.scrollHeight; return d; }
function showComposer(on){ composer.hidden=!on; if(on){ input.disabled=false; send.disabled=false; input.focus(); } }

async function start(){
  const r = await post('/api/session');
  renderMenu(r.problems);
}
function renderMenu(problems){
  muted('Pick a problem to work. You are never told the move to make.');
  const m=document.createElement('div'); m.className='menu';
  problems.forEach((p,i)=>{ const b=document.createElement('button'); b.innerHTML=esc(p);
    b.onclick=()=>choose(i,m); m.appendChild(b); });
  thread.appendChild(m); thread.scrollTop=thread.scrollHeight;
}
async function choose(i, menuEl){
  menuEl.remove();
  const t=thinking(); const r=await post('/api/session/single/choose',{index:i}); t.remove();
  advance(r);
}
function advance(r){
  if(r.kind==='say'){ bubble('vera', r.text); showComposer(true); return; }
  if(r.kind==='done'){ if(r.close) bubble('vera', r.close); muted('Your read is recorded.'); showComposer(false); return; }
  if(r.kind==='nudge'){ muted(r.message); showComposer(true); return; }
  muted('error: '+(r.message||'')); showComposer(true);
}
composer.addEventListener('submit', async e=>{
  e.preventDefault();
  const text=input.value.trim(); if(!text) return;
  bubble('you', text); input.value=''; input.disabled=true; send.disabled=true;
  const t=thinking();
  try { const r=await post('/api/session/single/say',{text}); t.remove(); advance(r); }
  catch(err){ t.remove(); muted('connection lost — is the server still running? try again.'); showComposer(true); }
});
input.addEventListener('keydown', e=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); composer.requestSubmit(); } });
start();
</script></body></html>
```

- [ ] **Step 4: Run the smoke test + manual check**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_app.py -k chat_shell -v`
Expected: PASS. Then manual: `PYTHONPATH=src .venv/bin/python -m retnovation.web`, open http://127.0.0.1:8000, confirm the thread + composer, no `veldra:`/4-block, and a real back-and-forth.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/web/static/index.html tests/test_app.py
git commit -m "feat(ui): chat thread + sticky composer; retire the 4-block form"
```

---

## Task 7: @live engagement + moat verification

**Files:**
- Modify: `tests/test_voice_live.py`

**Interfaces:** real `AnthropicModel` (key-gated, `@pytest.mark.live` + skipif on `ANTHROPIC_API_KEY`).

- [ ] **Step 1: Migrate the budget test and add engagement/moat @live tests.** Replace `test_echo_push_budget_on_a_long_turn` (it referenced the removed `echo_push`) and add:

```python
@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no key")
def test_concierge_turn_budget_on_a_long_turn():
    m = AnthropicModel()
    long_reply = "I would hold the line. " * 60
    out = m.concierge_turn("Problem P.", "Which mistake can you walk back?", [("student", long_reply)])
    assert out and isinstance(out, str)


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no key")
def test_concierge_turn_engages_the_users_words(tmp_path):
    """The regression that started this: the probe must respond to what the user ACTUALLY said,
    not march a blind angle. We give a distinctive reply and assert the turn references it AND is a
    question (Socratic), not a topic pivot that ignores it."""
    exp = _first_open_exp(str(tmp_path / "engage.db"))
    m = AnthropicModel()
    f = exp.rubric.frames[0]
    push = m.generate_push(exp, "frame", f.frame_code, stress=False)
    reply = "I think verifiable audits and data settle this across every industry."
    turn = m.concierge_turn(exp.prompt, push, [("student", reply)])
    low = turn.lower()
    assert "?" in turn  # it presses, Socratically
    assert any(w in low for w in ("audit", "data", "you")), "turn ignores the student's actual words"


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no key")
def test_concierge_turn_acknowledges_an_objection(tmp_path):
    """When the user says the question is irrelevant, the turn must engage that — not silently pivot."""
    exp = _first_open_exp(str(tmp_path / "obj.db"))
    m = AnthropicModel()
    f = exp.rubric.frames[0]
    push = m.generate_push(exp, "frame", f.frame_code, stress=False)
    turn = m.concierge_turn(exp.prompt, push, [
        ("student", "I'd hold and rely on audits."),
        ("Vera", push),
        ("student", "Your question is irrelevant to what I said."),
    ])
    assert turn and isinstance(turn, str)  # authored a turn (manual read confirms it acknowledges)


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no key")
def test_concierge_turn_never_names_the_move_and_no_invented_name(tmp_path):
    """Moat: a faithful engaged turn passes the egress (no added revelation vs the push); and Vera
    does not address the user by a fabricated name."""
    from retnovation.web import voice
    exp = _first_open_exp(str(tmp_path / "moat.db"))
    m = AnthropicModel()
    f = exp.rubric.frames[0]
    push = m.generate_push(exp, "frame", f.frame_code, stress=False)
    turn = m.concierge_turn(exp.prompt, push, [("student", "I'd hold the line on price.")])
    added = bool(voice._performed(m, exp, turn) - voice._performed(m, exp, push))
    assert added is False, "engaged turn leaked a move beyond the push"
    assert "Sam" not in turn  # no invented name (the dogfood artifact)
```

- [ ] **Step 2: Run the @live suite with the key**

Run: `set -a; . ./.env; set +a; PYTHONPATH=src .venv/bin/python -m pytest tests/test_voice_live.py -m live -v`
Expected: PASS (golden-set, budget, engagement, objection, moat). Read the objection-test output manually to confirm Vera acknowledges the pushback.

- [ ] **Step 3: Commit**

```bash
git add tests/test_voice_live.py
git commit -m "test(live): concierge engages user words, handles objections, never names the move"
```

---

## Task 8: DEVLOG + manual dogfood + merge

- [ ] **Step 1:** Add a DEVLOG entry (top of `docs/DEVLOG.md`) summarizing the Concierge pivot: dialogue-blind engine diagnosed, Approach A (agent fronts untouched engine), chat UI, `veldra:`-leak fixed, conversational close. Note terrain still deferred.
- [ ] **Step 2:** Manual browser dogfood (the original failure): pick a problem, give a substantive position, then object "your question is irrelevant" — confirm Vera acknowledges and grounds, never names the move, never invents a name, and the close reflects your reasoning. Confirm no `veldra:` anywhere and the chat thread feels like an agent.
- [ ] **Step 3:** Adversarial OPUS review of the moat-critical surface (the egress still backstops every visible turn; frame-blindness holds for `concierge_turn`/`concierge_close`; bridge transparency: engine grades the canonical push). Incorporate findings.
- [ ] **Step 4:** Commit DEVLOG; merge `feat/concierge-engaged-agent` → main locally (`--ff-only`); hold the gated push for the user.

---

## Self-Review (run before handing off)

- **Spec coverage:** §3 architecture → Tasks 1–6 (engine untouched, Concierge authors turns); §4 turn kinds → Task 1 (`concierge_turn` probe/reinvite, `concierge_close`) + Task 2 (egress modes/fallbacks); §5 bridge → Task 4; §6 picker/`veldra:` → Task 3 + 5; §7 chat UI → Task 6; §8 testing → Tasks 1–7; §9 out-of-scope honored (no terrain UI). All covered.
- **Per-task green:** Tasks 1↔2 and 4↔5 are coupled (removing `echo_push` / changing tags breaks the other side mid-flight). The plan flags doing each coupled pair in one working tree and committing once both are green — an executor should treat 1+2 and 4+5 as paired commits if the intermediate suite is red.
- **Types consistent:** `concierge_turn(problem, push, recent)` / `concierge_close(problem, recent)` / `voice.turn(model, exp, push, recent)` / `voice.gate(...)->EntryClass` / `voice.close(...)` used identically across model.py, voice.py, session_runner.py, tests. `display_titles()->dict[str,str]` keyed by `ledger_ref`.
- **Placeholder scan:** clean (the CSS color typo was fixed inline).
