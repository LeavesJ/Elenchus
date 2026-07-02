# Chained Sittings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bounded engine sessions inside one continuous user thread — after each landing, one tap starts the next clean session; End persists from the first convergence; the village reveals at the true exit.

**Architecture:** The worker computes the next-top proposal (pure policy, exception-safe) at `done`; the registry owns sitting state (`_last_record`, converged-refs dedupe, guarded auto-pick, `continue_session`, poison-pill reap of parked workers); the UI adds a Continue affordance that follows the thread. Engine byte-untouched.

**Tech Stack:** Python 3.14 (`PYTHONPATH=src .venv/bin/...`), FastAPI/TestClient, pytest, ruff.

## Global Constraints

- **Engine byte-untouched:** `orchestration.py`, `assessment/` — empty diff. The next-top proposal reuses `propose_open_ended` (pure, zero model calls).
- **L-13:** only `display_title`s reach the client; ranked refs stay server-side (`last_menu_refs` discipline). No new model-authored surface.
- **Spec must-fixes are binding:** MF-1 sitting-dedupe of the auto-pick (converged refs only); MF-2 next-top inside `try`, before `finally`, own `try/except` (empty menu RAISES: `select_next` ValueError / `Proposal.top` IndexError) → `next_title=""`, never `kind:"error"`; MF-3 absent-ref → inline MENU (never silent door-0); MF-4 sentinel reap (`_ABANDON`/`_Abandoned`) so an orphaned worker's `finally: store.close()` runs; MF-5 mid-segment End → `_STATIC_SITTING_CLOSE` + last-converged terrain (no mirrored close); MF-6 Continue follows the thread, disables on click, per-record `continued` idempotency.
- Per commit: ruff format+check, `PYTHONPATH=src .venv/bin/pytest -q` green **with real exit codes (L-23)**; confidential-docs guard; explicit paths. Baseline: 331 passed / 25 skipped. Repo `~/Documents/Retnovation`, branch `main`, hold push.

---

### Task S1: Worker computes the guarded next door; `_emit` passes it

**Files:**
- Modify: `src/retnovation/web/session_runner.py` (imports; `_Channel`; the worker after the landing block; the `done` tag handling in `start`/`step`)
- Modify: `src/retnovation/web/app.py` (`_emit` done branch)
- Test: `tests/test_session_runner.py`, `tests/test_web_api.py`

**Interfaces:**
- Produces: `_Channel.next_menu: list[tuple[str, str]]` (ref, title — server-side only); registry `self._last_record: dict[str, dict]`, `self._sitting_done: dict[str, set[str]]`, `self._next_pick: dict[str, str | None]`; the `done` payload dict gains `"next_title": str`; `_emit` done → `{"kind":"done","terminal":True,"landing":...,"next_title":...}`.

- [ ] **Step 1: Failing tests.** Add to `tests/test_web_api.py`:

```python
def test_done_payload_carries_next_title(tmp_path, make_fake):
    app = create_app(db_path=str(tmp_path / "nt.db"), model_factory=make_fake)
    client = TestClient(app)
    _, r = _choose_anchor(client)
    r = client.post("/api/session/s/say", json={"text": "reasoning that already holds the move"}).json()
    while r["kind"] == "say":
        r = client.post("/api/session/s/say", json={"text": "mechanism"}).json()
    assert r["kind"] == "done"
    # a next door is offered, as a clean TITLE (never the ref), and it is NOT the just-converged
    # problem (MF-1: sitting dedupe — irreversible_anchor was banked this sitting)
    assert isinstance(r["next_title"], str) and r["next_title"]
    assert "veldra" not in r["next_title"].lower()
    assert r["next_title"] != _ANCHOR_TITLE
```

- [ ] **Step 2: Verify fail** — KeyError `next_title`.

- [ ] **Step 3: Implement.** `session_runner.py`:

(a) imports: add `load_library, load_progression` via `from ..content_loader import load_library, load_progression` and `from ..scheduler import propose_open_ended`.

(b) `_Channel.__init__` gains `self.next_menu: list[tuple[str, str]] = []`.

(c) `SessionRegistry.__init__` gains:
```python
        self._last_record: dict[str, dict] = {}
        self._sitting_done: dict[str, set[str]] = {}
        self._next_pick: dict[str, str | None] = {}
```

(d) in the worker, AFTER the `if captured:` landing/record block and BEFORE the `done` put (still inside `try` — MF-2; needs no store):
```python
                # The next door (chained sittings): the PURE policy over the post-session state.
                # "Empty menu" is an EXCEPTION path here (select_next raises ValueError on no
                # candidates; Proposal.top raises IndexError) — any failure means "no door offered",
                # never an error emission (MF-2). Refs stay server-side (L-13).
                try:
                    exps = [e for e in load_library() if e.regime is Regime.open_ended]
                    menu2 = propose_open_ended(state, exps, load_progression(), now).problem_menu()
                    titles2 = voice.display_titles()
                    ch.next_menu = [
                        (sp.ledger_ref, titles2.get(sp.ledger_ref, "Untitled problem"))
                        for sp, _ in menu2
                    ]
                except Exception:
                    ch.next_menu = []
```

(e) the `done` tag handling in BOTH `start()` and `step()` (extract a helper on the registry):
```python
    def _on_done(self, session_id: str, ch: _Channel, data: dict) -> None:
        # Sitting bookkeeping (MF-1): bank the converged ref; the offered next door is the
        # highest-ranked proposal NOT already converged this sitting; if all repeat -> no door.
        if ch.record is not None:
            self._last_record[session_id] = ch.record
            self._sitting_done.setdefault(session_id, set()).add(ch.record["exp"].ledger_ref)
        done_refs = self._sitting_done.get(session_id, set())
        pick = next(((r, t) for r, t in ch.next_menu if r not in done_refs), None)
        self._next_pick[session_id] = pick[0] if pick else None
        data["next_title"] = pick[1] if pick else ""
```
and in `start`/`step` replace `if tag in ("done", "error"): ch.terminal = True` handling with:
```python
        if tag == "done":
            self._on_done(session_id, ch, data)
        if tag in ("done", "error"):
            ch.terminal = True
```

(f) `app.py` `_emit` done branch:
```python
    if tag == "done":  # the engine converged — the SESSION does not end; the user owns closure. The
        # felt landing rides the payload; the guarded next door (chained sittings) rides with it.
        return {
            "kind": "done",
            "terminal": True,
            "landing": data.get("landing", ""),
            "next_title": data.get("next_title", ""),
        }
```

- [ ] **Step 4: Gate** (real exit codes) — suite expect **332 passed / 25 skipped**; bridge-transparency untouched (the done payload gains an additive key only).

- [ ] **Step 5: Commit** — `feat(web): guarded next-door proposal on the done payload (sitting dedupe, exception-safe, refs server-side)`.

---

### Task S2: `continue_session` + reap + honest mid-segment exit

**Files:**
- Modify: `src/retnovation/web/session_runner.py` (module sentinel; `present`/`respond`/`decide` checks; worker except; `continue_session`; `converse`/`close` migration)
- Modify: `src/retnovation/web/app.py` (`POST /api/session/{sid}/continue`)
- Test: `tests/test_session_runner.py`, `tests/test_web_api.py`

**Interfaces:**
- Produces: `SessionRegistry.continue_session(session_id, menu: bool = False) -> tuple[str, dict]`; module-level `_ABANDON = object()`, `class _Abandoned(Exception)`, `_STATIC_SITTING_CLOSE: str`; `_Channel.thread` (the worker thread, for the reap test); HTTP `POST /api/session/{sid}/continue` with body `{"menu": bool}`.

- [ ] **Step 1: Failing tests.** Add to `tests/test_web_api.py`:

```python
def _drive_to_done(client):
    r = client.post("/api/session/s/say", json={"text": "reasoning that already holds the move"}).json()
    while r["kind"] == "say":
        r = client.post("/api/session/s/say", json={"text": "mechanism"}).json()
    assert r["kind"] == "done"
    return r


def test_chained_sitting_continue_end_to_end(tmp_path, make_fake):
    """One tap after the landing starts a NEW clean session in the same thread (opening say);
    End after the chain closes with terrain; the second segment's problem differs (MF-1)."""
    app = create_app(db_path=str(tmp_path / "chain.db"), model_factory=make_fake)
    client = TestClient(app)
    _, r = _choose_anchor(client)
    d1 = _drive_to_done(client)
    assert d1["next_title"] and d1["next_title"] != _ANCHOR_TITLE
    r2 = client.post("/api/session/s/continue", json={}).json()
    assert r2["kind"] == "say" and r2["text"]  # the NEW session's opening — the thread just continues
    cl = client.post("/api/session/s/close").json()  # End mid-segment (segment 2 not converged)
    assert cl["kind"] == "close" and isinstance(cl["terrain"], list)
    assert "stepped away mid-problem" in cl["close"]  # MF-5: honest static, not a mirrored close


def test_continue_menu_path_and_double_click_idempotency(tmp_path, make_fake):
    app = create_app(db_path=str(tmp_path / "dc.db"), model_factory=make_fake)
    client = TestClient(app)
    _, r = _choose_anchor(client)
    _drive_to_done(client)
    m = client.post("/api/session/s/continue", json={"menu": True}).json()
    assert m["kind"] == "menu" and m["problems"]  # inline picker path
    # the menu path consumed the continuation; a second continue is refused (MF-6 idempotency)
    again = client.post("/api/session/s/continue", json={}).json()
    assert again["kind"] == "error"
```

Add to `tests/test_session_runner.py`:

```python
def test_continue_reaps_the_parked_worker_and_restarts_arc(tmp_path, make_fake):
    """MF-4: continuing over a live mid-segment worker unblocks it (finally closes its store,
    thread exits). Also: the arc counter restarts at push 1 in the new segment (spy across both)."""
    arcs = []

    def factory():
        m = make_fake()
        orig = m.concierge_turn

        def rec(problem, push, recent, *, arc=None, voice=""):
            if push:
                arcs.append(arc)
            return orig(problem, push, recent, arc=arc, voice=voice)

        m.concierge_turn = rec
        return m

    reg = SessionRegistry(str(tmp_path / "reap.db"), model_factory=factory)
    tag, _ = reg.start("s1", now=NOW)
    tag, _ = reg.step("s1", reg.menu_index("s1", _ANCHOR))
    tag, data = reg.step("s1", "reasoning that already holds the move")
    while tag == "say":
        tag, data = reg.step("s1", "mechanism")
    assert tag == "done"
    n_first = len(arcs)
    tag, data = reg.continue_session("s1")
    assert tag == "say"  # the new opening
    old_thread = None  # the first segment's worker already exited via done
    # drive one probe into segment 2 to observe the arc restart
    tag, data = reg.step("s1", "an opening without the move")
    if tag == "say":
        assert arcs[n_first][0] == 1  # fresh segment: push 1 again
    # now continue over the LIVE mid-segment worker: it must be reaped (thread exits)
    ch2 = reg._ch["s1"]
    # the second continue must first be allowed: fake a converged record for idempotency bookkeeping
    tag2, _ = reg.close("s1")  # mid-segment close also reaps (MF-4/MF-5 path)
    assert tag2 == "close"
    ch2.thread.join(timeout=5)
    assert not ch2.thread.is_alive()  # finally ran -> store closed, thread gone
```

- [ ] **Step 2: Verify fail** — `continue_session` missing / 404 on the endpoint / `thread` attr missing.

- [ ] **Step 3: Implement.** `session_runner.py`:

(a) module level, after `_DOOR_MAX_NONSUBSTANTIVE`:
```python
# Chained sittings: a poison-pill put on an ORPHANED segment's to_worker queue (continue/close over
# a live channel). The worker raises _Abandoned at its next collect, swallows it, and exits through
# finally so its store CLOSES (MF-4 — otherwise the parked worker leaks an open connection forever).
_ABANDON = object()

_STATIC_SITTING_CLOSE = (
    "You stepped away mid-problem — that one stays unbuilt. Here's the village you built."
)


class _Abandoned(Exception):
    pass
```

(b) `_Channel.__init__` gains `self.thread: threading.Thread | None = None`; in `start()` after creating the thread: keep a reference —
```python
        t = threading.Thread(target=worker, daemon=True)
        ch.thread = t
        t.start()
```

(c) sentinel checks at EVERY worker collect point:
- `decide()`: after `idx = ch.to_worker.get()` add `if idx is _ABANDON: raise _Abandoned()`.
- door loop: after `text = ch.to_worker.get()` add `if text is _ABANDON: raise _Abandoned()`.
- `respond()`: after `student = ch.to_worker.get()` add `if student is _ABANDON: raise _Abandoned()`.

(d) worker except chain: BEFORE `except Exception as e:` add
```python
            except _Abandoned:
                pass  # orphaned segment (user continued/closed past it); store closes in finally
```

(e) `continue_session`:
```python
    def continue_session(self, session_id: str, menu: bool = False) -> tuple[str, dict]:
        """Chained sittings: start the NEXT bounded session in the same thread. One-click path
        auto-picks the door the button NAMED (the guarded next pick); menu=True returns the inline
        picker instead. Idempotent per converged segment (MF-6); reaps a live prior worker (MF-4);
        absent pick -> the MENU, never a silent door-0 (MF-3)."""
        rec = self._last_record.get(session_id)
        if rec is None:
            return ("error", {"message": "nothing to continue from"})
        if rec.get("continued"):
            return ("error", {"message": "continuation already in flight"})
        rec["continued"] = True
        old = self._ch.get(session_id)
        if old is not None and not old.terminal:
            old.to_worker.put(_ABANDON)  # reap the parked mid-segment worker
        pick = self._next_pick.get(session_id)
        tag, data = self.start(session_id)
        if tag != "menu":
            return (tag, data)
        if menu or pick is None:
            return (tag, data)
        try:
            idx = self.menu_index(session_id, pick)
        except ValueError:
            return (tag, data)  # the offered door vanished: show the doors honestly (MF-3)
        return self.step(session_id, idx)
```

(f) `converse()` and `close()` migrate to the sitting record + MF-5:
```python
    def converse(self, session_id: str, value) -> tuple[str, dict]:
        rec = self._last_record.get(session_id)
        if rec is None:
            return ("error", {"message": "session has not converged"})
        reply = voice.converse(
            rec["model"], rec["exp"], rec["recent"], value, rec["posture"],
            rec.get("stop_reason", "converged"),
        )
        rec["recent"].append(("student", value))
        rec["recent"].append(("Vera", reply))
        return ("say", {"text": reply})

    def close(self, session_id: str) -> tuple[str, dict]:
        rec = self._last_record.get(session_id)
        if rec is None:
            return ("error", {"message": "session has not converged"})
        ch = self._ch.get(session_id)
        if ch is not None and not ch.terminal and ch.record is None:
            # An in-flight segment past the last convergence: authoring a mirrored close would
            # reflect the PREVIOUS problem while the current turns vanish (MF-5). Honest static
            # sign-off + the village; reap the parked worker (MF-4).
            ch.to_worker.put(_ABANDON)
            return ("close", {"close": _STATIC_SITTING_CLOSE, "terrain": rec["terrain"]})
        close_text = voice.close(rec["model"], rec["exp"], rec["recent"], rec["posture"])
        return ("close", {"close": close_text, "terrain": rec["terrain"]})
```
(The old `ch.record`-reading bodies are removed; `_last_record[sid]` IS the same dict object the worker built, so post-done behavior is unchanged.)

(g) `app.py`:
```python
class _Cont(BaseModel):
    menu: bool = False
```
```python
    @app.post("/api/session/{sid}/continue")
    def continue_(sid: str, body: _Cont):
        return _emit(reg, *reg.continue_session(_SID, body.menu))
```

- [ ] **Step 4: Gate** (real exit codes) — expect **335 passed / 25 skipped**; the full existing converse/close tests stay green (post-done identity of `_last_record` and `ch.record`).

- [ ] **Step 5: Commit** — `feat(web): chained sittings server core — continue_session, poison-pill reap, honest mid-segment exit`.

---

### Task S3: The UI seam

**Files:**
- Modify: `src/retnovation/web/static/index.html`
- Test: `tests/test_web_api.py`

- [ ] **Step 1: Failing test.**

```python
def test_index_has_continue_affordance_following_the_thread():
    client = TestClient(create_app(db_path=":memory:", model_factory=None))
    html = client.get("/").text
    assert "renderContinue(" in html and "other doors" in html
    assert "/continue" in html
    # MF-6/minor: proceed lives IN-THREAD; the sticky composer row never gains a Continue button
    composer = html[html.index('<form id="composer"') : html.index("</form>")]
    assert "Continue" not in composer
    # the affordance re-renders after converse replies (never stranded in scrollback)
    assert html.index("renderContinue(nextTitle)") != -1
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement** in `index.html`:

(a) state + renderer (after `showEnd`):
```javascript
let nextTitle='';
let contBox=null;
function renderContinue(title){
  if(contBox){ contBox.remove(); contBox=null; }
  if(!title) return;
  contBox=document.createElement('div');
  contBox.style.cssText='align-self:center;display:flex;gap:12px;align-items:center;margin:6px 0';
  const b=document.createElement('button'); b.type='button';
  b.style.cssText='background:#155e63;color:#eafffb;border:0;border-radius:11px;padding:9px 16px;font:inherit;cursor:pointer';
  b.textContent='Continue → '+title;
  b.onclick=()=>goContinue(b,{});
  const o=document.createElement('button'); o.type='button';
  o.style.cssText='background:none;border:0;color:#8aa0bf;font:inherit;cursor:pointer;text-decoration:underline';
  o.textContent='other doors…';
  o.onclick=()=>goContinue(o,{menu:true});
  contBox.append(b,o); thread.appendChild(contBox); thread.scrollTop=thread.scrollHeight;
}
async function goContinue(btn,body){
  btn.disabled=true; input.disabled=true; send.disabled=true; const t=thinking();
  try{ const r=await post('/api/session/single/continue',body); t.remove();
    if(contBox){ contBox.remove(); contBox=null; } nextTitle=''; mode='engine'; advance(r); }
  catch(_){ t.remove(); btn.disabled=false; input.disabled=false; send.disabled=false;
    muted('connection lost — try again.'); }
}
```

(b) `advance()` changes:
- `done` branch becomes: `if(r.kind==='done'){ mode='converse'; if(r.landing) bubble('vera', r.landing); showComposer(true); showEnd(true); nextTitle=r.next_title||''; renderContinue(nextTitle); return; }`
- `say` branch: after `bubble('vera', r.text); showComposer(true);` add `if(mode==='converse') renderContinue(nextTitle);` (the affordance follows converse replies — MF-6). (`mode` is still `'converse'` for converse replies; continue's own `say` arrives with `mode` already `'engine'`, so no affordance renders there.)
- add a `menu` branch: `if(r.kind==='menu'){ renderMenu(r.problems); return; }` (the inline `other doors…` picker; `choose()` posts `/choose`, which steps the NEW channel).
- End persistence: nothing to change — `showEnd(true)` is never undone during the sitting, and continue does not call `showEnd(false)`.

- [ ] **Step 4: Gate** — served-shell tests + `node --check` the inline script + full suite (real exit codes), expect **336 passed / 25 skipped**.

- [ ] **Step 5: Commit** — `feat(web): the sitting seam — in-thread Continue that follows the conversation, inline other-doors picker`.

---

### Task S4: Chain smoke + DEVLOG + batch review

- [ ] Health smoke: documented launch boots; a FakeModel chained sitting (converge → continue → converge → End) through the HTTP API shows two houses' worth of terrain (fresh db) — add as an offline test if not already covered by S2's chain test plus a terrain-length assertion.
- [ ] DEVLOG entry (vision, the review's empirical grind finding, the six MF folds, verification).
- [ ] 2-lens OPUS batch review over the S1..S4 commits; fold findings; ledger/memory/handoff updates.
- [ ] Founder gates: felt dogfood of a chained sitting; push.

## Self-Review (planner)

**Spec coverage:** §3a → S3 (affordances, lifecycle, layer split, menu branch); §3b → S1 (next-top, MF-1/MF-2, `_emit`) + S2 (`continue_session` MF-3/MF-6, `_last_record`, MF-4 reap, MF-5 static close); §3c signal purity → structural (fresh worker `recent`, unchanged) + S2 chain tests; §3d End semantics → S3 (persist) + S2 (mid-segment close); §5 tests distributed across S1–S4 incl. the sitting-dedupe assertion (S1 test asserts `next_title != _ANCHOR_TITLE`), arc-restart spy, idempotency, reap-join, honest static close, L-13 title check. **Placeholders:** none. **Type consistency:** `continue_session(session_id, menu: bool = False)` matches app.py's `_Cont.menu` and the tests; `_next_pick` holds a ref (str) consumed by `menu_index`; `_on_done` mutates the same `data` dict returned to `_emit`; `_STATIC_SITTING_CLOSE` substring matches the S2 test's `"stepped away mid-problem"`.
