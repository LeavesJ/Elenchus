# The Living Sitting — generated problems over curated rubrics — Design (v2)

Date: 2026-07-02
Status: design v2. Founder-brainstormed live (five forks: free-text front door; same-world next
pressure; earned press + adaptive difficulty; screen + regenerate-once with offline audit
deferred; "the living sitting" MVP slice). 3-lens adversarial review RUN (doctrine / mechanics /
product) — verdict on v1 was NOT READY; **all must-fixes and accepted should-fixes are FOLDED
below** (§9 review ledger). Awaiting founder read → writing-plans.
Related: chained + durable sittings (the substrate); the Cartographer vision (valley-as-homepage
— deferred, compatible); the case-library/mining thread (the territory growth axis); L-6 (the
unlabeled problem is the moat).

## 0. Why now (founder dogfood 2026-07-02, evidenced)

1. **One-turn exits.** `_converged` runs at the top of the judgment loop; the founder's intake
   answers closed every target frame → zero presses, instant landing. Correct mechanics, felt as
   a quiz.
2. **Two convergences, one house.** Terrain regions group frames by shared-problem breadth;
   the two problems share frames → one region, vitality 2. The reward loop breaks where it's
   felt.
3. **The close answers one question** (mirrors the final segment only — the deferred synthesis).
4. **The ceiling: the fixed-door menu** (five curated rubrics; four on the picker). The final
   format is the user choosing what to approach and the model generating the problem impromptu.
   The engine has always been ready for this: `run_session` grades an `Experience` and does not
   care where `exp.prompt` came from.

## 1. Goal, premise, slice

**Goal:** a sitting is one generated WORLD. The user says what she's facing; the system maps it
to the closest curated territory and generates the scenario around HER situation; the
byte-untouched engine grades against the same curated rubric; Continue applies the next pressure
to the same world; End tells the whole sitting's story over a village where every convergence is
a house.

**The premise that does not move:** the moat stays curated — frames, rubrics, traps, corpus
anchors, gates. What becomes generated is the scenario surface. **MVP granularity is the
RUBRIC:** a forged experience reuses one whole curated rubric (angle-complete, anchored) and
swaps only the prompt; frame-level composition is a later arc.

**Two identities, two grains (load-bearing; review D2/M3):**
- **World grain — what the ENGINE grades:** a forged experience's `ledger_ref` is
  `gen:{sitting}` — ONE ref per world. Breadth and `unprompted_breadth` then dedupe per world
  automatically: five re-skins of one situation can never mint the strong tier ("repeated AND
  cross-context" — the engine's own bar) or pump terrain accretion. Cross-WORLD deployments
  still accrue real transfer.
- **Instance grain — what the PRODUCT tracks:** each generated problem is
  `gen:{sitting}:{n}` in the sitting store (`web_generated_problem`): scenario text, base
  `experience_id`, timestamps. Dedupe, resume, honesty branches, and houses key here and on
  `experience_id` (territory) — never on breadth.

**In scope:** front door + mapper + heard-you beat; the forge (generation + gates + honest
fallback); same-world Continue with territory-window dedupe; the arc floor (decision_frame
matrix); bounded coarse difficulty; durable identity; houses-per-convergence; sitting-level
close; the shell for all of it. **Out of scope (deferred, named):** valley-as-homepage
(compatible — worlds are durable rows); the offline generator-audit harness (incl. the cue-parity
probe, §3); frame-level rubric composition; fine difficulty tuning; CS regime; multi-user.

## 2. Design

### 2a. The front door

- Vera's front-door ask is **STATIC** (the coldest beat pays zero model calls): *"What are you
  facing right now? Describe the decision."* The composer is the emphasized first beat; **the
  curated doors render small beneath it** ("or start from one of these") — genre orientation and
  a zero-effort ramp for the cold user; no "you pick" incantation to mis-parse.
- **The mapper** (server-side; sees frame codes — L-13 governs learner-facing surfaces): ONE
  batched `messages.parse` call in the `screen_moves` pattern (`_MED_PARAMS`, 4096, numbered
  candidates, `_require` fails LOUD — L-17). Input: her text + territory descriptions. Output:
  ranked `experience_id`s, fit confidence, and a reflection line.
- **The heard-you beat (load-bearing):** the reflection renders as Vera's bridge BEFORE the
  scenario — *"So: you're signing a delivery commitment Thursday and the penalty clause is the
  fight. Stand in it:"* — the system proves it understood her before the generated room appears.
  **The reflection is gated** (review D9 — it is learner-facing text from a frame-aware call):
  composed extractively from HER words wherever possible, screened via `screen_moves` against the
  mapped territory's moves, static bridge fallback on failure.
- **Honest fit, user-centric:** low confidence → *"There's more in that than one sitting can
  press. The sharpest pressure I can put on it: {territory description}. Start there — or look
  at the other doors first?"* Her situation stays the world; "grade" never reaches the wire; no
  silent stretching.
- **Territory descriptions** (`content/territories/{experience_id}.md`, loader mirrors
  `load_role_text`) are STIMULUS-level by rule — they describe the kind of decision (what curated
  prompts already disclose openly), never the response shape. **Three teeth (review D10):**
  (1) code checks per description against its OWN rubric (frame/trap phrases, scaffold denylist,
  wrappers — `validate_scene` shape); (2) `screen_moves(moves(exp), description)` must be empty;
  (3) a behavioral @live intake-shift probe (openings with {description+prompt} vs {prompt} must
  not shift intake toward the rubric's frames) via the elicitation harness (§2d keeps it alive).
  The 1-frame territory (`continuity_lock_in`) is the highest-risk description — written last,
  reviewed hardest.

### 2b. The forge

New `src/retnovation/forge.py`. `forge_experience(base, world, brief, model) -> Experience`
clones the curated rubric byte-identically, sets `experience_id = base.experience_id`,
`ledger_ref = "gen:{sitting}"` (world grain), **nulls `scene`** (a cloned curated scene would
feed the WRONG situation into every push and classify call — review D5), and swaps the prompt.

- **The brief is frame-blind and Vera-free (review D3):** territory description, her situation,
  her committed positions **defined as her final substantive STUDENT turns** (`you` turns from
  the store — never landing or any Vera-authored text, which lawfully performs her own moves),
  the role register, and the bounded level line (§2e). Never frame/trap details, rubric text, or
  engine state. Doctrine in `content/prompts/forge_scenario.md`: second person, concrete stakes,
  one real decision, no advice, no move-naming; **the world carries her situation and OUTCOMES,
  never restates her reasoning as setup** (review D1 — echoing her segment-N solution as world
  history is the main injection vector); the world may WIDEN — move time forward, shift to an
  adjacent situation in the same company/role, carrying her committed positions as consequences
  ("You capped the penalty Thursday; three weeks on, your second-largest customer wants the same
  terms…") — decisions propagating is a story; five plagues on one afternoon is a telenovela
  (review P9).
- **The scenario authors IN OPENING VOICE** — it IS the opening say (review M6): one generation,
  one screen; no separate `concierge_open` pass on generated content.
- **Gates, cheapest first (review D4/D12/M4):**
  1. Code: structural (second person, decision ask, length) + the prompt-facing anti-label
     checks — `validate_scene`'s shape (framework denylist, frame/trap codes, scaffold, wrapper
     words), which needs no corpus entry. Ownedness is inherited from the honest-fit mapping —
     her real situation IS the owned problem — and is not machine-checked (stated, not hidden).
  2. **Fit (reject-only, server-side, frame-aware):** does the scenario give natural occasion
     for each of the base's frames and satisfy the mode's binding premise (a deadline for
     `commit_under_the_deadline`; an undemonstrated capability for `bounded_error`'s binding) —
     a generated scenario that drifts from the binding turns grading into scenario-fit noise and
     invites false `hard_wrong` (review D5). Regen steers use precondition/situation-structure
     language only (the stimulus, never the move).
  3. **Union egress:** `screen_moves` over the base's moves **∪ every frame she engaged this
     sitting** (review D1 — the cross-segment echo is the common case; the union machinery
     shipped with the sitting close).
  - One steered regeneration → then the **honest fallback** (review P1): the curated base serves
    with a one-line Vera bridge — *"I'll hold your situation — first, work this one; it's the
    same pressure you're standing in."* — and the world row persists so the NEXT Continue retries
    the forge on her world; a fallback never poisons the sitting.
- **The seam into the engine (review M1):** the worker's `decide()` returns a Selection whose
  chosen spec carries `ledger_ref = "gen:{sitting}:{n}"` (instance key, honest in
  `selection_log`); `generator.select_open_ended` gains one branch — a `gen:` spec pops the
  forged Experience from a process-local forge registry populated before the selection step.
  `orchestration.py`/`assessment/` untouched; `generator.py`/`experience.py` are legal seams
  (the engine-diff gate pins orchestration + assessment). The curated `experience_id` bypass in
  `select_open_ended` is **not reintroduced** for forged content (the forge gates before
  registering); the pre-existing curated bypass stays as-is (closing it is its own L-14 change —
  review D13).
- **Seeding:** the forge (running in the worker thread — it reuses the worker's store connection;
  review M9) writes the `gen:{sitting}` LedgerEntry (once per world) and the instance row in
  `web_generated_problem`. `run_session`'s ledger snapshot predates decide-time seeding —
  harmless (selection doesn't read the ledger), stated.

### 2c. Same-world Continue

- The world persists (`web_world`: situation, updated_at). Continue targets the **next
  territory**: ranked by mapper relevance × policy need combined RANK-BASED (raw `V` can be
  negative — a raw product flips order; review M10), excluding territories inside the window.
- **Territory-window dedupe has real machinery (review M3):** `web_converged` gains
  `experience_id` alongside the ref; `ch.next_menu` carries it; every window check compares
  territory by `experience_id` and instance by `gen:` ref. Load-bearing: within a sitting the
  policy clock is frozen — the window is the ONLY rotation mechanism.
- The Continue button is **subtitled with the target's curated territory description** (review
  P4 — consent doctrine: "consent via the titled button"; zero latency, zero new leak class):
  *"Continue — next pressure: where this can't be undone."*
- **All-territories-windowed is a defined state (review P3):** informed re-serve, never refusal,
  never a false door — *"You worked this pressure this morning — pressing it again now will echo
  more than it reveals. Work it anyway, or come back tomorrow?"* A re-served territory forges a
  NEW instance (real new problem; the honest residual is the short-horizon memory prime, named).
  "Bring a fresh situation" is offered only when it can be honored.
- Reopen/lost-door comparisons key on `experience_id` (a forged lost segment's `gen:` ref never
  equals a menu ref — review M8).

### 2d. The arc floor — the decision_frame matrix (content; engine untouched)

`_converged` refuses to bank until the rubric's `decision_frame` is stressed; `_select_target`
stress-probes it even when `present_reasoned`. Adding it is 4 YAML edits + the forge clone. But
the assignment is **signal-load-bearing** (review D6): a DF frame loses its `reasoned_unprompted`
read on that territory (the deliberate L-9 exclusion), and a stress probe answered "unchanged"
banks nothing.

- **The rule:** no frame is DF on every territory where it appears; the spine frame keeps an
  unprompted channel somewhere.
- **Pinned:** `license_continuity` keeps `commit_under_the_deadline` (existing).
  `continuity_lock_in` is 1-frame — its DF is FORCED to `embed_credentials_as_a_list`; accepted
  cost: embed loses unprompted THERE, and therefore `irreversible_anchor`'s DF MUST be
  `choose_the_failure_default_deliberately` (embed's other home keeps the channel — the
  13/13-confirmed elicitation target stays readable). The remaining two assignments follow the
  rule in the plan.
- **Named behavior change:** DF pre-empts tripped traps and the binding constraint in press
  ordering — the sequence changes for normal users too, not only intake-complete ones. Accepted
  as part of the founder-chosen floor.
- **The floor is a floor, not the arc (review P7):** the felt arc lives at the SITTING level
  (one world, accumulating positions, one story at the close). Where prior segments exist, the
  stress press draws on her accumulated world (her Tuesday commitment), not a generic tripwire —
  rigor, not theater. Honest §5 note: a top-percentile user's segment is intake + one press.
- **L-14/L-22 break set, enumerated (review D7):** `test_guard_passes_the_two_real_rubrics`
  fails the moment its rubrics gain a DF (`assert_intake_equivalence` refuses DF rubrics) — the
  elicitation harness gets **DF-free rubric variants** (content copies used only by the harness),
  keeping the confirmed-claim instrument and §2a's intake-shift probe alive; the key-gated
  acceptance test is updated in the same commit (L-22); `make_fake` scripts only
  `choose_the_failure_default_deliberately` responses — the pinned irreversible_anchor DF keeps
  the fixture alive, and every exact turn-sequence assertion shifts one press (enumerated in the
  plan, updated same-commit per L-10/L-14).

### 2e. Bounded coarse difficulty (review P8)

The level line is a **3-value enum** — base / firm / tight — never a prose delta: it moves at
most one step between segments, snaps back one step immediately on any non-converged stop, and
every new world opens at base. Derived from sitting-store process signals only (press counts,
stop reasons — the L-4 boundary the landing already established; stop_reason is an engine OUTPUT
used as a process signal, stated honestly). An unbounded "one notch past" is an integrator that
terminates only in failure and then whipsaws.

### 2f. Identity, houses, close

- **Sitting store:** `web_world(sitting_id, situation, updated_at)`;
  `web_generated_problem(ref, sitting_id, experience_id, scenario, created_at)`;
  `web_converged` gains `experience_id`. L-3: retained forever. **Restart-rebuild fidelity
  (review M2 — must-fix):** `_serialize_record` adds `ledger_ref`; `_rebuild` on a `gen:` ref
  loads the scenario from `web_generated_problem` and rebuilds the exp with
  `model_copy(update={"prompt": scenario, "ledger_ref": ref})` over the curated base — a missing
  row degrades to statics. Without this, post-restart converse/close author about the CURATED
  scenario under her generated conversation — the amnesia class again.
- **Houses are converged segments (review M7/D2):** one house per `web_converged` row — the
  founder's rule ("every convergence is a house"), converged-only by construction (plateaued
  problems don't render), ordered by `converged_at` (a public time signal; append-stable across
  sittings), bucketed by the region they belong to (via the territory's frames), positioned
  ordinally within the region cluster with a layout rule + a many-cue cap. No `gen:` refs, no
  codes on the wire. **Honest residual (review D11):** exact converged-count per region and
  problem-to-region GROUPING become public — rename-invariance protects codes, not structure;
  justified as user-known (she lived each convergence; the close narrates them) and as the
  intended reward. The close copy counts houses — "two houses raised" — and the founder's
  two-convergence dogfood is the regression test for geometry AND copy (review P12).
- **Sitting-level close:** the author receives the whole sitting (kind-filtered `you`/`vera`
  turns per segment + the situation), tells the world's story — retrospective, no verdicts
  (L-4), egress-screened against the union of the sitting's territories' moves. **The union
  scale is measured before trusting** (review M13): a 5-territory union is ~30–45 moves in one
  screen call vs the ~6 the "solid" measurement covered; fail-loud truncation exists; measure
  per L-17/L-20. Static fallback preserved.
- **The return visit is not amnesiac (review P10):** a cold start with closed worlds renders one
  muted line above the ask — *"Your world so far: two houses, one region alight."* — text-only
  for MVP (the village strip is optional-if-cheap; the full homepage is the deferred arc). The
  projection was already seen at her last close; pre-session, so two-phase timing holds.

### 2g. Worker lifecycle and wire (review M5)

- **The front door lives IN the worker** (the less invasive choice): `decide()` becomes a
  multi-turn loop — emit the static ask, collect her text, run mapper (+ optional honest-fit
  round-trip), forge, then return the Selection. The one-put-per-consumed-get handshake is
  preserved; `_persist_emit` persists the asks/bridges as turns for free.
- **New durable state: "world open, mid-front-door"** — a session parked in the front-door loop
  has no menu, no inflight, no record; the resume state machine gains the state (her typed text
  is persisted as `you` turns; cross-restart resume re-serves the ask over her visible words with
  the honesty line). `continue_session`'s menu-index branch no longer fires on the forge path;
  the pending-seam rule is stated: the seam attaches to the forged opening say; a Continue that
  re-enters the front door clears it.
- Cold payload: `{kind:"frontdoor", say: <static ask>, menu: <small doors>, build}`; the
  nonce/stale-tab machinery is unaffected (free text carries no nonce).
- **Latency, honestly counted (review M6):** first door = mapper + forge + screen = **3 calls**
  (the scenario IS the opening; the ask is static); each Continue = forge + screen = **2**; a
  regen retry +2. Today's baseline is 2/2 — measured in the health smoke before any tuning
  (L-20).
- L-13 wire discipline unchanged: `gen:` refs never reach the client; territory descriptions are
  the only new learner-facing text class and carry §2a's three teeth.

## 3. Signal integrity (the whole point)

- The graded path is code-identical; **measurement is prompt-relative** (review D5) — the fit
  gate exists because a rubric's meaning presumes preconditions the scenario must establish.
- The scenario is the only PRE-INTAKE authored surface — **a genuinely new residual class**
  (review D8), not "the same as every authored surface": the curated prompt was the calibrated
  half of the instrument, and the flat screen passes topic-cueing by design. Mitigations: the
  union screen, the decisions-only brief, the fit gate, the fallback — and the deferred offline
  generator audit MUST include a cue-parity probe vs curated prompts (frame-naive intake-shift;
  the elicitation machinery is this instrument, kept alive by §2d's DF-free variants). Zero is
  not claimed.
- World-grain grading (§1) is what keeps breadth/`unprompted_breadth`/accretion honest under
  re-skins; cross-world transfer still accrues. Named MVP distortion (review M10): under
  all-forged play the curated refs never enter breadth, so the policy's deploy term is uniformly
  inflated — the territory window is the real rotation; accepted and stated.
- The mapper and fit gate see frame codes server-side; their learner-facing outputs (reflection,
  honest-fit line) are gated (§2a).
- Privacy (review P13): the front door invites real, possibly counterparty-named situations into
  permanent storage and model calls. Single-user local MVP: acceptable; the beta version of this
  beat needs a retention/consent stance — named now, not discovered later.

## 4. Content gate (review P5)

Five territories is enough to **dogfood** and not enough to invite anyone: the sitting exhausts
them in five convergences, and by day 2–3 a meta-aware user names the costume trick. **MVP ships
and is dogfooded at 5; no external beta until the territory library clears ~10–12 with ≥2
distinct role/register families.** The mining/case-library thread is that gate's owner.

## 5. Testing

- **Forge:** gated experience (rubric byte-equal, scene nulled, world-grain ref); leaking
  scenario caught (inject move-performing fake → regen → honest fallback with bridge); a
  scenario restating a prior segment's mechanism caught by the UNION screen (review D1's test);
  fit-gate reject path; brief purity (spy: no Vera/landing text, no frame details, enum level
  line only); fallback does not poison Continue.
- **Identity:** ledger seeded once per world; breadth dedupes re-skins (two convergences, one
  world → `unprompted_breadth` grows ≤1 per frame); selection_log records instance refs;
  restart-rebuild serves the GENERATED prompt (review M2's test); territory window blocks
  just-converged territories (M3) and reopen-seam keys on experience_id (M8).
- **Arc floor:** the intake-complete fake (the founder's dogfood shape) gets ≥1 press on every
  territory; the DF matrix holds the rule; the elicitation harness runs green on its DF-free
  variants; every turn-sequence test updated same-commit (enumerated in the plan).
- **Front door:** heard-you bridge renders (and is screened); low-confidence copy path; doors
  visible under the composer; mid-front-door restart resumes honestly; all-windowed state serves
  the informed re-serve, never a false fresh-situation door.
- **Terrain/close:** two convergences → two houses AND the copy says so; houses carry no refs or
  codes; ordering by converged_at stable across sittings; sitting close receives all segments
  (spy) and passes the measured union screen.
- Bridge-transparency per segment unchanged; engine-diff gate
  (`git diff -- src/retnovation/orchestration.py src/retnovation/assessment/`) empty; suite green
  at every commit; `:memory:` shell tests untouched (forge tests use tmp-file dbs — the inert
  store).
- **@live (founder-gated):** one real free-text sitting; generator quality eyeball; per-beat
  latency counts; intake-shift probe on territory descriptions; no-verdict/no-move behavioral
  checks on the new authored surfaces.

## 6. Honest residuals

Generation quality variance until the offline audit lands (fallback + dogfood are the floor);
one-press segments for top-percentile users (the sitting carries the arc); coarse 3-step
difficulty; the deploy-term drift under all-forged play; scenario-level cue calibration is
unproven until the cue-parity probe runs; short-horizon memory prime on informed re-serves;
houses expose counts and grouping (justified above); five territories (the §4 gate); the valley
homepage deferred — worlds are durable rows, nothing is throwaway.

## 7. Files touched

- NEW `src/retnovation/forge.py`; `content/prompts/forge_scenario.md`,
  `content/prompts/concierge_sitting_close.md`, `content/territories/{5}.md`; elicitation DF-free
  rubric variants; `tests/test_forge.py`.
- `content/rubrics/*.yaml` — `decision_frame` per the §2d matrix (4 edits).
- `src/retnovation/generator.py` — the `gen:` registry branch in `select_open_ended` (legal
  seam); `src/retnovation/model.py` — `map_territories`, `forge_scenario` (opening-voice),
  `fit_check`, `concierge_sitting_close` (+ FakeModel constant-return counterparts; L-17 budgets;
  wire models with `_require`).
- `src/retnovation/terrain.py` + `web/static/terrain3d.js` — houses from the converged log,
  region-cluster layout, many-cue.
- `src/retnovation/web/session_runner.py` / `sitting_store.py` / `app.py` / `voice.py` /
  `static/index.html` — front-door worker loop + new resume state, world persistence, forge-backed
  continue + subtitled button, `web_converged.experience_id`, record `ledger_ref`, sitting close,
  return-visit line, wire changes.
- Tests across the existing web/session/terrain suites + the enumerated DF-shift updates.

## 8. Doctrine carried in

Engine byte-untouched (orchestration + assessment; generator/experience are declared seams).
L-1 (territories, briefs, matrix are content). L-3. L-4 (process signals only; no verdicts).
L-5/L-13 (union screens; gated reflections; stimulus-level descriptions with three teeth; refs
server-side; houses positional). L-6 (the generated problem stays unlabeled — the gates exist
for exactly this). L-9 (the DF matrix names its unprompted-channel costs instead of hiding
them). L-10/L-14/L-22 (the break set is enumerated and updated same-commit). L-17/L-20 (measured
budgets and call counts). User-owned closure and the durable-sitting substrate ride unchanged.

## 9. Review ledger (3-lens, 2026-07-02)

Doctrine: D1 union screen + decisions-only brief (§2b); D2 world-grain grading + houses from the
converged log (§1/§2f); D3 committed positions = student turns only (§2b); D4 prompt-facing
gates, not anti_label_gate (§2b); D5 fit gate + scene nulling (§2b/§3); D6 DF matrix + named
costs (§2d); D7 break-set enumeration + DF-free elicitation variants (§2d); D8 new residual
class + cue-parity audit (§3); D9 gated reflection (§2a); D10 three teeth on territory
descriptions (§2a); D11 houses residual honesty (§2f); D12 gate order (§2b); D13 bypass claim
corrected (§2b).

Mechanics: M1 the forge registry seam (§2b); M2 restart-rebuild fidelity (§2f); M3 territory-
window machinery (§2c/§2f); M4 validate_scene shape (§2b); M5 in-worker front door + new resume
state (§2g); M6 honest latency + scenario-as-opening + static ask (§2b/§2g); M7 houses from
converged log, converged_at ordering, layout cap (§2f); M8 experience_id comparisons (§2c); M9
seeding thread rule (§2b); M10 rank-based combination + deploy-term drift named (§2c/§3); M11
count fix (§7); M12 FakeModel pattern (§7); M13 union-scale measurement (§2f).

Product: P1 honest fallback + no poisoning (§2b); P2 heard-you beat (§2a); P3 all-windowed
state + informed re-serve (§2c); P4 subtitled Continue (§2c); P5 the content gate as numbers
(§4); P6 user-centric low-confidence copy (§2a); P7 floor-not-arc + world-drawn stress press
(§2d); P8 bounded difficulty enum (§2e); P9 the world widens (§2b); P10 return-visit line
(§2f); P11 doors under the composer (§2a); P12 house copy + regression (§2f); P13 privacy
stance named (§3); P14 door count corrected (§0).
