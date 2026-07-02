# Durable Sittings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The sitting survives page reloads and server restarts — persisted transcript + sitting
state, a resume-aware front door, rolling-24h repeat guard, and stale-build/stale-shell hardening.

**Architecture:** A new `sitting_store.py` persists the PROJECTED client wire (turns) plus the
landed-segment record and a converged log (SQLite, same db file, open-per-op, WAL). The registry
writes through at the emit/input layer and rebuilds lazily across restarts; `POST /api/session`
resumes a live sitting instead of cold-starting. Engine byte-untouched.

**Tech Stack:** Python 3.14 (`PYTHONPATH=src .venv/bin/...`), FastAPI/TestClient, sqlite3, pytest, ruff.

## Global Constraints

- **Engine byte-untouched:** `orchestration.py`, `assessment/`, graded methods — empty diff.
- **L-13:** persisted `payload_json` mirrors the PROJECTED client payload only — never registry
  tags/data (menu emits carry refs; done emits carry state/assessment). Worker `error` emissions
  are NEVER persisted (L-14: exception text can carry frame codes).
- **Spec must-fixes are binding (spec §8):** `continued` flag is in-memory only (rebuild clears);
  per-sitting generated id + partial unique live index; terminal-error-channel resume state +
  stale-tab soft fails; MF-5 across restart via the persisted `inflight` discriminator;
  converse→`record_json` write-through; rolling-24h window on full timestamps (NOT UTC date);
  branch-accurate honesty copy; done-drain before branching in close/continue.
- Per commit: `ruff format . && ruff check .`, `PYTHONPATH=src .venv/bin/pytest -q` green **with
  real exit codes (L-23)**; confidential-docs guard; explicit paths. Baseline: **339 passed /
  25 skipped**. Repo `~/Documents/Retnovation`, branch `main`, hold push (founder-gated).

---

### Task D1: `sitting_store.py` — the persistence module

**Files:**
- Create: `src/retnovation/web/sitting_store.py`
- Test: `tests/test_sitting_store.py` (NEW)

**Interfaces (Produces):**
```python
class SittingStore:
    def __init__(self, db_path: str): ...          # ":memory:" -> inert no-op store
    @property
    def inert(self) -> bool: ...
    # sitting lifecycle
    def live_sitting(self) -> dict | None          # {"id","status","updated_at"} or None
    def create_sitting(self, now: datetime) -> str # returns new id; caller holds registry lock
    def close_sitting(self, sitting_id: str) -> None
    # turns (kind in vera|you|muted|landing|seam)
    def append_turn(self, sitting_id: str, kind: str, payload: dict, now: datetime) -> None
    def turns(self, sitting_id: str) -> list[dict]  # [{"kind","payload"}...] in seq order
    # landed-segment state
    def write_state(self, sitting_id: str, record: dict | None = ..., next_pick: tuple[str,str] | None = ...,
                    inflight: dict | None = ..., theme: dict | None = ...) -> None   # sentinel-partial update
    def read_state(self, sitting_id: str) -> dict   # {"record","next_pick","inflight","theme"} (None-able)
    # converged log + window
    def log_converged(self, sitting_id: str, ref: str, now: datetime) -> None
    def converged_within(self, now: datetime, hours: int = 24) -> set[str]
```
`record` (serialized): `{"experience_id","posture","recent":[[who,text],...],"stop_reason","terrain"}`.
`inflight`: `{"experience_id","ledger_ref"}`. All timestamps `datetime.isoformat()` UTC.

- [ ] **Step 1: Failing tests** (`tests/test_sitting_store.py`): construction creates tables +
  WAL on a tmp file; `":memory:"` → `inert` and every method no-ops (`live_sitting() is None`,
  `turns()==[]`, `converged_within()==set()`); create/live/close lifecycle (at most one live —
  second `create_sitting` after close works, same id never reused); `append_turn`/`turns`
  round-trip preserves order + kinds under interleaved appends; `write_state` partial updates
  (record only, then inflight only — the other fields survive); `log_converged` +
  `converged_within` respects the 24h window on timestamps that STRADDLE a UTC date boundary
  (e.g. converged 23:50Z read at 00:10Z next day → excluded from re-offer; converged 25h ago →
  offered) — the founder's incident shape; rows are never deleted (close retains turns).
- [ ] **Step 2: Verify fail** — ModuleNotFoundError.
- [ ] **Step 3: Implement.** Open-per-op `sqlite3.connect(self._path, timeout=5)`; first open:
  `PRAGMA journal_mode=WAL`; every open: `PRAGMA busy_timeout=5000; PRAGMA synchronous=NORMAL`.
  Tables per spec §2a (`web_sitting`, `web_sitting_turn` with SQL-side
  `COALESCE(MAX(seq),0)+1`, `web_sitting_state`, `web_converged` with `sitting_id, ref,
  converged_at`); partial unique index `ux_web_sitting_live ON web_sitting(status) WHERE
  status='live'`. Sitting id: `now.strftime("%Y%m%dT%H%M%S%f")`. `inert` when
  `db_path == ":memory:"` (every public method returns early). `append_turn` also bumps
  `web_sitting.updated_at`. `converged_within` compares ISO strings against
  `(now - timedelta(hours=hours)).isoformat()`.
- [ ] **Step 4: Gate** (real exit codes) — expect ~**348 passed / 25 skipped**.
- [ ] **Step 5: Commit** — `feat(web): sitting_store — durable transcript, landed state, converged log (WAL, open-per-op, :memory: inert)`.

---

### Task D2: Write-through at the projection layer

**Files:**
- Modify: `src/retnovation/web/session_runner.py` (registry gains a `SittingStore`; worker sets
  `ch.inflight_exp`; `_on_done` persists; `converse` persists; `close` closes the sitting;
  drain-then-branch in `close`/`continue_session`; seam plumbing)
- Modify: `src/retnovation/web/app.py` (you-turn capture on say/converse; choose marker)
- Test: `tests/test_session_runner.py`, `tests/test_web_api.py`

**Interfaces:**
- Consumes: D1's `SittingStore`.
- Produces: `SessionRegistry.__init__` gains `self._store = SittingStore(db_path)` and
  `self._sitting_id: dict[str, str] = {}` (sid → live sitting id) and
  `self._seam_pending: dict[str, str] = {}`; `_Channel.inflight_exp: tuple[str, str] | None`
  (worker-set at `present()` top, happens-before the opening emit); continue/choose `say`
  responses gain `"seam": str` when a seam is pending (shell renders muted line before the
  bubble); worker comment pinning the queue-handshake invariant.

- [ ] **Step 1: Failing tests.** `tests/test_session_runner.py`: drive a FakeModel session to
  done on a tmp db; assert `store.turns(sid)` contains, in order: muted door-invite is NOT
  persisted (menus unpersisted), `vera` opening, `you` reply(ies), `vera` probes, `landing`
  (non-empty only), and NO `error`/refs anywhere (`"veldra" not in json.dumps(turns)`);
  `read_state()` has `record` (experience_id/stop_reason/recent) + `next_pick`, `inflight is
  None` after done; `converged_within(now)` contains the anchor ref iff converged (drive the
  plateau fake too — F1: no row). Continue path: after `continue_session`, turns gain `seam` +
  muted `Continue → {title}` + the new opening; the swallowed internal menu never appears.
  Converse: turns gain the you/vera pair AND `read_state()["record"]["recent"]` includes it
  (same transaction). Error segment: a raising model's emission leaves NO turn (static marker
  optional per spec). Close: sitting `status=='closed'`. Done-drain: converge, then call
  `close()` BEFORE dequeuing done via a registry-level test using channel priming (drive with
  `step` until the say before convergence, then `close` after worker banks — simulate by calling
  `close` when `from_worker` holds an undequeued `done`) → `web_converged` still gains the row.
- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement.**
  (a) Worker: first line of `present(exp)`: `ch.inflight_exp = (exp.experience_id, exp.ledger_ref)`.
  Above the worker def, the invariant comment: *"every emission is dequeued inside the HTTP
  request that triggered it (one put per consumed get; done is put while the last step() is still
  blocked) — write-through lives at the dequeue/endpoint layer and needs no worker-side
  persistence; a proactive emission would break it."*
  (b) Registry `_persist_say(sid, data, seam)` helper: appends optional `seam` turn then the
  `vera` turn (text only; updates theme when present); called from `start`/`step`/
  `continue_session` return paths for `say` tags; on first persist of a new `ch.inflight_exp`,
  `write_state(inflight={...})`.
  (c) `_on_done`: existing logic PLUS `write_state(record=serialized, next_pick=pick,
  inflight=None)`; `log_converged(...)` only when `stop_reason=="converged"`; append `landing`
  turn when non-empty. Serialization: `{"experience_id": rec["exp"].experience_id, "posture":
  rec["posture"], "recent": rec["recent"], "stop_reason": rec["stop_reason"], "terrain":
  rec["terrain"]}`.
  (d) `converse`: after the reply, append you+vera turns and `write_state(record=...)` re-serialized.
  (e) `close`: drain `from_worker` first —
  ```python
  ch = self._ch.get(session_id)
  if ch is not None:
      try:
          tag, data = ch.from_worker.get_nowait()
      except queue.Empty:
          pass
      else:
          if tag == "menu":
              ch.last_menu, ch.last_menu_refs = data["problems"], data.get("refs", [])
          if tag == "done":
              self._on_done(session_id, ch, data)
              ch.terminal = True
  ```
  (same drain at the top of `continue_session`, before the idempotency check); then the existing
  branch logic; finally `self._store.close_sitting(...)` + drop `self._sitting_id[sid]`.
  (f) `continue_session`: set `self._seam_pending[sid] = "Same sitting — next door."` after the
  idempotency gate; the next opening say consumes it (rides the response as `"seam"` and persists
  as a `seam` turn). The muted `Continue → {title}` marker turn is appended at continue time
  (one-click path only).
  (g) `app.py`: `/say` and `/converse` persist the `you` turn AFTER the blank-guard (and converse's
  record-exists check succeeds — persist on `tag == "say"` return); `choose` persists muted
  `door chosen` + `you` title turn on a non-error return. `_emit` say branch passes `seam` through
  when present in data.
  (h) Sitting row creation: in `start()` when no live sitting is tracked/found —
  under `self._lock`, `live_sitting()` else `create_sitting(now)`; map `self._sitting_id[sid]`.
- [ ] **Step 4: Gate** — expect ~**357 passed / 25 skipped**; existing CS/converse/close tests
  green (write-through is additive); `:memory:` shell tests green (inert store).
- [ ] **Step 5: Commit** — `feat(web): sitting write-through at the projection layer (turns, landed state, converged log, seam, done-drain)`.

---

### Task D3: Resume front door, rebuild, guards

**Files:**
- Modify: `src/retnovation/web/session_runner.py` (`resume_or_start`; `_rebuild`; window dedupe in
  `_on_done`; next_pick revalidation; stale-tab soft fails; menu nonce; MF-5 discriminator;
  interrupted-adjacent converse union screen; 18h staleness)
- Modify: `src/retnovation/web/app.py` (`POST /api/session` → `resume_or_start`; `_emit` gains
  `nudge` + `resume` branches + menu `nonce`)
- Test: `tests/test_session_runner.py`, `tests/test_web_api.py`

**Interfaces:**
- Produces: `SessionRegistry.resume_or_start(session_id, now=None) -> tuple[str, dict]` with tags
  `menu` (cold start) or `resume`
  (`{"turns","next_title","end_visible","mode","theme","honesty"}` — `honesty` = the
  branch-accurate muted line or `""`); `step`/`converse` on missing/terminal channels →
  `("nudge", {"message": "This room went stale — refresh to pick up where you left off."})`;
  menu payloads carry `"nonce": int`, `_Choice` gains `nonce: int | None`; `voice` imports used:
  `SAFE_CONTRACT`, `egress_safe_reply`.
- Consumes: D1 store, D2 write-through.

- [ ] **Step 1: Failing tests** (the crown — restart == a NEW registry/app over the same db):
  (a) converge → new registry → `resume_or_start` returns `resume` with the verbatim turns,
  `end_visible=True`, `mode=="converse"`, `next_title` non-empty, no `veldra:`/frame codes in the
  payload; (b) converse works post-restart AND a converse exchange survives a SECOND restart;
  (c) `continue` works post-restart (flag cleared by rebuild) and double-continue within a
  process still refuses; (d) two-house terrain across a restart (converge → restart → continue →
  converge → End: both houses); (e) restart mid-segment (drive one probe, then new registry):
  `resume` carries the interrupted honesty line; with a prior landed record → `mode=="converse"`
  and `close()` returns the STATIC "closed unfinished" variant (never a mirrored close); restart
  mid-FIRST-segment → honesty line + fresh menu payload; (f) dedupe: seed `log_converged` in
  process 1, new registry, drive to done → `next_title` skips refs converged <24h (including a
  UTC-midnight-straddling timestamp) and a stale persisted `next_pick` into a since-converged ref
  drops to the menu on continue; (g) rebuild failure: state row with unknown `experience_id` →
  converse returns `SAFE_CONTRACT`-safe static, close returns static + persisted terrain, no
  exception; (h) same-process errored-first-segment: `resume_or_start` yields a usable path
  (fresh menu, no "session already ended" dead end); stale-tab `/say` after restart → nudge kind,
  no 500; (i) stale menu nonce → menu re-served, no door opened.
- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement.**
  (a) `resume_or_start`: under `self._lock` — no live sitting (or >18h stale → `close_sitting`)
  → cold start path (existing `start`, sitting row created). Live sitting → build the resume
  payload: `turns` from store; state machine per spec §2c (discriminator: `inflight` in state;
  channel liveness/terminality for same-process states 1–4). State 3 (live pending menu):
  payload appends the menu re-derived from `ch.last_menu` (+nonce). States 4/6/7: honesty copy
  per spec; no-record branches embed a FRESH menu (internal `start()`); `mode` and `end_visible`
  from the rebuilt/checked record; `_lost_ref[sid]` set on state 6 so the reopen seam variant
  fires when the next segment opens the same ref ("Starting this one over — restate your
  position, or build on what you wrote above.").
  (b) `_rebuild(sid)` (idempotent, under `self._lock`): from `read_state()["record"]` —
  `model_factory()`, `load_library()` match on `experience_id` (miss → mark
  `rec["degraded"]=True` with exp=None), recent as tuples, no `continued` key. `converse`/`close`
  on a degraded record → statics (never author, never 500).
  (c) `_on_done` guard becomes: `done_refs = self._sitting_done.get(...) | self._store.converged_within(now)`
  — wait, per spec §2e the table query SUBSUMES this sitting (every this-sitting convergence is
  logged); keep `_sitting_done` untouched/in-memory for its own semantics and use
  `self._store.converged_within(datetime.now(timezone.utc))` unioned with the in-memory set (the
  union is belt-and-suspenders for inert stores where the table is empty — `:memory:` keeps
  today's behavior).
  (d) `continue_session`: re-validate `pick` against `converged_within` → drop to menu (MF-3 path).
  (e) `step`/`converse`: `self._ch.get(...)` missing or (`terminal` and not a drained done) →
  `("nudge", {...})`. `menu_index` unchanged.
  (f) Nonce: registry counter bumped per menu emission, stored on the channel; `_emit` menu branch
  adds it; `choose` with a mismatched non-None nonce → re-serve current menu (`("menu",
  {...last_menu...})`).
  (g) Interrupted-adjacent converse: when `_lost_ref` context exists for the sid, after
  `voice.converse` returns, additionally `egress_safe_reply(model, lost_exp, reply)` (lost_exp
  rebuilt from the persisted inflight experience_id; unknown → skip) → fail → `SAFE_CONTRACT`.
  (h) `app.py`: `POST /api/session` → `resume_or_start`; `_emit` gains
  `if tag == "resume": return {"kind":"resume", **data}` and
  `if tag == "nudge": return {"kind":"nudge","message":data["message"]}`; `_Choice` gains `nonce`.
- [ ] **Step 4: Gate** — expect ~**368 passed / 25 skipped**; every pre-existing test green
  (fresh-db tests always cold-start; `:memory:` inert).
- [ ] **Step 5: Commit** — `feat(web): resume front door — the sitting survives reloads and restarts (rebuild, honesty branches, rolling-24h dedupe, soft fails)`.

---

### Task D4: The shell — resume rendering + affordances

**Files:**
- Modify: `src/retnovation/web/static/index.html`
- Modify: `src/retnovation/web/app.py` (menu title suffix; `Cache-Control: no-store` on `/`;
  `build` on health + session payloads)
- Test: `tests/test_web_api.py`

- [ ] **Step 1: Failing tests:** served shell contains `kind==='resume'` handling,
  `DocumentFragment`, `renderSeam(`/seam handling, and renders "other doors…" when `next_title`
  is empty (`renderContinue` split: doors link always shown post-landing); `GET /` carries
  `Cache-Control: no-store`; `/api/health` and the `POST /api/session` cold payload carry a
  non-empty `build`; menu titles converged <24h carry `" · just worked"` (seed `log_converged`,
  restart app over same db, fetch menu) while fresh titles don't; L-13: suffixed titles still
  carry no `veldra:`.
- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement.**
  (a) Shell `advance` gains: `if(r.kind==='resume'){ renderResume(r); return; }` and
  `if(r.kind==='nudge')` already handled; `renderResume(r)`: DocumentFragment; per turn — `vera`/
  `landing` → vera bubble, `you` → you bubble, `muted`/`seam` → muted; then `applyTheme(r.theme)`,
  `mode=r.mode`, `nextTitle=r.next_title||''`, `showComposer(true)`, `showEnd(!!r.end_visible)`,
  `if(r.honesty) muted(r.honesty)`, embedded menu rendered when present, then
  `if(mode==='converse') renderContinue(nextTitle)`; ONE scroll at the end.
  (b) `say` handling renders `r.seam` as a muted line before the bubble when present.
  (c) `renderContinue`: render the "other doors…" link even when `title` is empty (button only
  when non-empty).
  (d) `choose()` sends `{index:i, nonce:menuNonce}` (captured from the menu payload).
  (e) `start()` tucks `r.build` into `#mark`'s title and `console.info`.
  (f) `app.py`: `_build_stamp()` — `subprocess.run(["git","describe","--always","--dirty"],
  capture_output=True, timeout=1)` in a try/except at `create_app`, fallback `"unknown"`; health +
  cold-start/resume payloads carry it. `index()` returns
  `FileResponse(..., headers={"Cache-Control": "no-store"})`. Menu emission: registry suffixes
  labels whose SERVER-SIDE ref is in `converged_within` with `" · just worked"` (at the emit
  layer, zipping `data["refs"]`/`data["problems"]` — refs never leave the server).
- [ ] **Step 4: Gate** — expect ~**374 passed / 25 skipped**.
- [ ] **Step 5: Commit** — `feat(web): resume rendering, seam + just-worked affordances, no-store shell, build stamp`.

---

### Task D5: Smoke, docs, batch review

- [ ] Health smoke: documented launch (`PYTHONPATH=src .venv/bin/python -m retnovation.web` on a
  scratch port/db) → `/api/health` has `ok` + `build`; a FakeModel resume round-trip through the
  HTTP API if not already covered.
- [ ] DEVLOG entry: the incident forensics (§0), the three-layer root cause, what shipped, the
  founder's re-dogfood gate (restart server AFTER this lands — restarts stop being destructive
  from now on).
- [ ] lessons.md **L-25**: a founder-gated dogfood that spans a server restart tests the WRONG
  build and (pre-durability) destroyed the experience under test; prevention — build stamp on
  health/payload + no-store shell + persist experience-critical state; when handing a dogfood
  gate, state the exact restart choreography.
- [ ] Worktree-isolated batch adversarial review (L-21) over the D1..D4 commits; fold findings.
- [ ] SESSION_HANDOFF + memory updates. Founder gates: re-dogfood (chained sitting incl. a
  deliberate mid-sitting reload AND a server restart), then push.

## Self-Review (planner)

**Spec coverage:** §2a → D1 (schema, pragmas, inert, window); §2b → D2 (projection-layer
write-through, enumeration, seam, converse record rewrite, done-drain, invariant comment, no
error/menu persistence); §2c → D3 (resume states 1–8, rebuild, honesty copy, lost-ref reopen,
next_pick revalidation, stale-tab nudges, nonce, 18h, MF-5 discriminator, union screen) + D4
(shell rendering, nextTitle restore); §2d → D2/D4 (seam server-decided, muted register); §2e → D3
(window guard) + D4 (suffix, other-doors-when-empty); §2f → D4 (build, no-store, tuck-away); §3 →
structural + D2 L-13 tests; §4 test list distributed D1–D5; §5 residuals need no code. **Types:**
`SittingStore` signatures consumed in D2/D3 match D1; `resume_or_start` tag/payload matches D4's
`renderResume`; `_Choice.nonce` matches the shell's choose body; serialized record keys match
`_rebuild`. **Placeholders:** none — every step names exact code or exact assertions. Suite-count
expectations are estimates; the gate is exit-0 + no regressions, counts recorded at commit time.
