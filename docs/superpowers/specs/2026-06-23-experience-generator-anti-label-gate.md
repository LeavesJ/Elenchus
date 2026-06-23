# Spec — Experience Generator + Anti-Label Gate (Build-order Step 3)

Status: Approved design, internal. Date: 2026-06-23.
Scope: Build-order Step 3 of the Retnovation MVP — "the experience generator and its
anti label gate" (Build Brief; Complete Picture §19). This retires the single fixed
experience and makes the gate hold the unlabeled test over everything the generator produces.

This spec was brainstormed and then verified from scratch against
`Retnovation_Complete_Picture.md` and the corpus via an adversarial multi-agent pass
(see "Verification provenance" at the end). Decisions that diverge from a naive reading of
the corpus are called out explicitly so a future reader does not mistake them for drift.

---

## 1. Goal and the one-line shape

`select_experience` currently returns one fixed experience (`veldra_licensing_continuity`)
loaded from `content/rubrics/`, ignoring the ledger. Step 3 replaces that with a
**deterministic generator** that, given the scheduler's `NextExperienceSpec`
(`target_frames`, `ledger_ref`, `regime`), selects an **authored** experience aimed at the
learner's weak/forming frames, binds it to a **real owned problem** from the ledger, and
**gates** it so it is genuinely unlabeled and rich enough to interrogate deeply.

Step 3 is proven on the **Founder CEO (`open_ended`)** side only. The `cs_technical`
checkable scorer is Step 4; the seam stays clean.

### The key insight that makes a deterministic gate sound

Three of the five anti-label rejects are semantic (`recoverable_label`,
`softened_ambiguity`, `cosmetic_engagement`) and cannot be decided by string matching.
They do not need to be: **the hard semantic judgment was already made by the curator when
they authored the corpus.** Each ledger owned-problem carries a curated `unlabeled`
rationale, a `why_owned` (real stakes), and a `provenance` (real source). The gate does
not re-judge unlabeledness — it **verifies every shipped experience is anchored to a
curated owned-problem and is structurally label-free.** Curation holds the doctrine; the
gate enforces anchoring + structure deterministically. This is "author content, gate
structurally," and it is consistent with "rent capability, gate doctrine" because the
rented model's capability lives downstream in the judgment loop, not in seed authoring
(see §7, Decision D1).

---

## 2. Module shape and data flow

A new module `src/retnovation/generator.py` owns selection + gating (its own boundary, per
the Build Brief's "experience generation" seam). `experience.py::select_experience` becomes
a thin deterministic selector that delegates gating to it.

```
scheduler.schedule_next → NextExperienceSpec{target_frames, ledger_ref, regime}
                                   │
select_experience(core, state, ledger, corpus, spec, root)
   1. load experience LIBRARY = all authored rubrics in content/rubrics/  (gated at load)
   2. filter to spec.regime           (open_ended for Step 3; cs_technical seam stays clean)
   3. rank by frame-coverage of spec.target_frames (weakest-first), tie-break by experience_id
   4. bind via the candidate's OWN authored ledger_ref (+ its corpus entry, for the gate)
   5. anti_label_gate(candidate, corpus_entry) → pass | reject(code)
   6. pass → return Experience ; reject → try next candidate ; none → raise GateError
                                   │
                       orchestration → judgment_loop (assessment interface unchanged)
```

**Selection & binding rules (deterministic, unambiguous):**
- **Selection** is driven by `spec.target_frames`: rank candidates by how many target frames
  their rubric covers, preferring coverage of the *weakest* frames first (the scheduler
  already orders `target_frames` weak-before-forming); tie-break by `experience_id` so the
  result is fully deterministic.
- **Binding** uses the **candidate experience's own authored `ledger_ref`** (a real seeded
  entry the gate verifies), *not* `spec.ledger_ref`. The curated experience↔owned-problem
  binding wins; `spec` only selects *which* experience. Re-binding an experience to a
  different owned problem (transfer) is deferred (FounderCEO §14).
- **Empty/first-session fallback:** if `spec` is `None` or `target_frames` is empty (no
  learner state yet), select the first gate-passing founder experience by `experience_id` —
  deterministic, never the retired fixed stub.

**New input — corpus.** The gate needs each owned-problem's `unlabeled` / `why_owned` /
`provenance`, which live in the `corpus` table. `select_experience` gains a
`corpus: list[CorpusEntry]` parameter, loaded by orchestration via `Store.load_corpus()`
(built in Step 2). Everything stays injectable/pure for tests — no model, no network in
Step 3.

**Two enforcement points** (defense in depth): the gate runs at **library load**
(author-time — a thin or labeled rubric cannot enter the library; fails loud) *and* at
**selection** (a cheap assertion). Both emit the reject code.

---

## 3. The anti-label gate

A closed, schema-locked enum `GateCode` in `types.py` (extended only by deliberate
versioned migration + test, per FounderCEO §3's rule for the closed vocabulary). Each code
has a deterministic check and a class: `hard_reject` (does not ship) or `quality_floor`
(ships, flagged, ranked lower).

| Code | Class | Deterministic check |
|---|---|---|
| `recoverable_label` | hard | `ledger_ref` resolves to a curated corpus entry whose `unlabeled` rationale is non-empty. No anchor / empty rationale → trip. |
| `pre_named_framework` | hard | Prompt names no framework from `content/gate/framework_denylist.yaml` (method names only) **and** leaks none of its own `frame_code`/`trap_code` tokens as prose. Case-insensitive, word-boundary. |
| `type_hint_scaffold` | hard | Prompt contains no category-cueing scaffold from `content/gate/scaffold_denylist.yaml` ("this is a … problem", "apply the", "classic case of", a heading naming the type). |
| `softened_ambiguity` | hard | Mode honesty: `genuinely_open ⇒ binding_constraint is null`; `bounded_error ⇒ non-null`. **And** prompt supplies no resolution/method (preserves "No framework is named for you on purpose"). |
| `cosmetic_engagement` | hard | Owned-problem carries real stakes (corpus `why_owned` non-empty) **and** the experience has no wrapper/gamification fields or words (streak/points/badge/timer). |
| `owned_or_real` | floor | `ledger_ref` resolves to a corpus entry with non-empty `provenance`. Real-but-unanchored → downgrade, not reject. |
| `process_layer_load` | floor | Rubric has ≥1 frame (trains judgment, not declarative recall alone). |
| `insufficient_interrogation_depth` | **hard (user-added depth floor — see D3)** | `angle_count = len(frames) + len(traps) + (1 if binding_constraint else 0) + 4` (the 4 universal artifact dimensions) **must be ≥ `min_angle_count`** (`content/gate/depth.yaml`, default 8). |

**Result type** (`types.py`):
```python
class GateResult(BaseModel):
    passed: bool                 # no hard rejects
    rejects: list[GateCode]      # hard rejects tripped
    downgrades: list[GateCode]   # quality floors tripped (still ships, ranked lower)
    angle_count: int             # audit / future dashboard
```
The `hard_reject` vs `quality_floor` classification is a constant map in `generator.py`
(not in the enum), so the wire vocabulary stays a clean code list.

**Where it runs & the rejected path:**
- **Library load (author-time):** any hard reject → `raise GateError(code, experience_id)`
  — a thin or labeled rubric cannot enter the library. Downgrades pass through, flagged.
- **Selection:** candidates are pre-gated, so the gate re-runs as a cheap assertion. Top
  candidate rejects (should not) → try next; **no candidate passes for the regime →
  `raise GateError`.** Never silently ship a tripped experience; never fall back to a thin one.
- Every reject *and* downgrade emits its code (logged) for the future rejection-mix
  dashboard, keyed like verdict metrics (FounderCEO §5).

**Denylists & threshold are versioned content** (`content/gate/*.yaml`), never hardcoded
in `src/` (L-1, doctrine-is-data). The framework denylist holds *method names only*, so a
roleplay prompt that says "hostile takeover" or "leverage" is fine — only a named *method*
trips `pre_named_framework`.

---

## 4. Schema & config additions (kept minimal)

In `types.py`: `GateCode` (the 8 codes above) and `GateResult` (above).

Config & denylists as versioned content, loaded via small `content_loader` additions:
- `content/gate/depth.yaml` → `min_angle_count: 8` (optional future `per_regime:` overrides;
  not populated now).
- `content/gate/framework_denylist.yaml` → framework method names (SWOT, OODA, five-forces …).
- `content/gate/scaffold_denylist.yaml` → category-cueing phrases.

**Roleplay stays prompt-only for Step 3.** The scenario text sets the scene; no schema
field. A structured `persona` the judgment loop voices in-character belongs to Step 5
(where the loop changes); adding it now would be a field nothing reads (YAGNI).

---

## 5. Starter content — Founder-only thin seed

The MVP is "the engine plus a thin seed of content, never a content library"
(MVP Scope §3). The seed exists to exercise the generator, not to be exhaustive.

**(a) Gate content** — the three `content/gate/*.yaml` files above.

**(b) The founder thin seed** — `content/rubrics/*.yaml`, all `open_ended`/`founder_ceo`.
**Retire the orphan** `veldra_licensing_continuity` (its `ledger_ref`,
`veldra:licensing_continuity`, resolves to nothing — confirmed absent from both ledger and
corpus). Author **three** founder experiences, each gate-passing, ≥8 angles, bound to a
**real** seeded founder ledger entry (of the 7: `adoption_funnel_stalls`,
`berkeley_focus_allocation`, `concentrated_market_pricing_power`, `cross_pool_data_optics`,
`first_customer_proof_loop`, `license_fork_risk`, `opening_rate_decision`):

| # | Shape (retention function) | Anchor (real ledger entry) | Notes |
|---|---|---|---|
| 1 | Decision-under-ambiguity (transfer) — the proven licensing shape, re-homed | `veldra:license_fork_risk` | Replaces the orphan with the same proven rubric shape on a real anchor. |
| 2 | Bobby-Axe decision-rep under stakes (articulation) — thin, text "you're in the seat, call it" | `veldra:concentrated_market_pricing_power` | Founder instantiation of the posture-agnostic decision-under-stakes mechanic (see D2). *Thin* prompt, not an elaborate sim. |
| 3 | `bounded_error` decision — concrete binding constraint pinned to the **hard line** only | a third founder entry (e.g. `first_customer_proof_loop`) | Exercises the gate's mode-honesty path on real content. |

The selector needs ≥2 differently-framed experiences to discriminate on `target_frames`;
three gives clean discrimination + one `bounded_error` for coverage. Frame spine = the 3
founder process_frames (`choose_the_failure_default_deliberately`,
`lead_with_what_you_refuse_to_do`, `protect_the_core_lane`).
`choose_the_failure_default_deliberately` counts as an interrogation angle (quarantined for
generation *lift*, valid as an *assessment* angle). Traps are paired per frame; for a
`bounded_error` experience, every trap and the binding constraint pin to the hard line,
never to a default the experience lets the student flex (JudgmentLoop §3).

**Confidentiality boundary (load-bearing, L-2):** the tracked rubric YAML carries only the
**abstracted** scenario prompt + frame/trap codes + a `ledger_ref` *id*. The confidential
corpus text (`why_owned`, `provenance`, raw friction) stays in gitignored `data/` and is
read by the gate at runtime — never embedded in tracked content. "Sand off the domain to
the reasoning shape" (FounderCEO §7) is both the doctrine and the confidentiality guard.
The `git ls-files` confidential-docs check stays in the pre-commit gate.

**(c) Loop budget** — bump `MAX_PUSHES` 6→8 in `judgment_loop.py` so the budget never caps
below the 8-angle target. **Budget-only in Step 3** — the loop still pushes on frames/traps;
the loop actually exercising the 4 dimension-angles is Step 5. This is a core-path constant,
so it triggers the adversarial review. *Verification note:* `plateau` currently fires at
iteration 3 with only 2 frames; richer 3-frame/3-trap rubrics + the bump shift loop dynamics,
so the review must re-confirm the cooperative path stays green.

---

## 6. Testing & review (TDD, deterministic)

Every Step-3 test is **deterministic — no model, no network** (the generator and gate are
deterministic; the rented model is already covered by the judgment-loop tests).

- **`tests/test_generator.py`** — one test per `GateCode`: each hard reject trips on a
  crafted bad rubric and passes on a good one; `angle_count` math; mode-honesty
  (`genuinely_open ⇒ binding null`); denylist hits; `recoverable_label` tied to a
  missing/empty `corpus.unlabeled`; **library-load fails loud** on a thin/labeled rubric;
  selection ranks by frame-coverage of `target_frames`; rejected-path
  (try next → raise `GateError`).
- **Acceptance (the moat):** a parametrized test asserting **every** `content/rubrics/*.yaml`
  passes the full gate + clears ≥8 angles — this *is* "the gate holds the unlabeled test
  over everything the generator produces," and satisfies MVP §7's "a sampled Founder CEO
  experience passes the unlabeled test."
- **Update existing tests** that reference the retired `FIXED_EXPERIENCE`/orphan
  (`test_experience`, `test_dry_run`, `test_orchestration`) to the new seed + real anchors;
  confirm the six-link loop still closes.
- **`content_loader`** additions (depth/denylist loaders) get unit tests.
- **Adversarial review before commit** (core-path: generator + gate + `MAX_PUSHES`), against
  an explicit checklist: confidentiality (no corpus text in tracked rubrics; `git ls-files`
  clean), gate soundness, selection determinism, orphan-retirement does not break the loop,
  cooperative path still green.
- **Pre-commit gate** (lessons.md): `ruff format/check`, `pytest`, DEVLOG updated, no
  secrets, confidential-docs check, explicit paths only.

---

## 7. Decisions that diverge from a naive corpus reading (state them, don't hide them)

- **D1 — "Generation" = authored-seed selection.** §3 lists "the quality of a generated
  experience" under rented capability, which reads as model-generation on a naive scan.
  For the Step-3 thin seed, generation is deterministic selection of authored content; the
  rented Opus quality lives **downstream in the judgment loop** (`experience.py` makes zero
  model calls; `orchestration` calls the model only in assessment). Verified consistent with
  MVP §14 ("engine plus thin seed content"). The anti-label gate built here is precisely the
  piece that will later wrap model-generation (the scaling layer) so it cannot ship a labeled
  experience.
- **D2 — Bobby Axe is a FOUNDER experience, in scope.** It is the articulation /
  decision-rep-under-stakes function (Complete Picture §5, §8 axis 2), not executive. The
  mechanic (in-the-seat decision under stakes) is posture-agnostic; the founder/exec
  difference is how *labeled* the decision is. The MVP ships the founder instantiation; the
  exec instantiation arrives with the exec posture (deferred). Only the *elaborate sim*
  format is deferred — a *thin* text decision-rep is in-scope.
- **D3 — The 8-angle floor is a user addition with no corpus basis.** It is
  doctrine-*compatible*, not doctrine: it is the structural precondition for §13's
  "sophisticate → more varied angles" (the model can only push 8 varied angles if the
  experience affords 8), and it is complementary to FounderCEO atomicity ("one frame, one
  angle; bundles split before judging") — afford many, judge one at a time. Configurable
  (`depth.yaml`), default 8, counting the 4 universal artifact dimensions so a small frame
  spine is not forced to pad.

## 8. Out of scope (Step 3 does not do these)

- The `cs_technical` checkable scorer (Step 4); Step 3 keeps the regime seam clean.
- Model-generation of experiences (scaling layer; the gate is built to wrap it later).
- A structured `persona` field / in-character voicing (Step 5, with the loop changes).
- Experiences-mapping-to-retention-functions (§5: articulation / transfer / declarative /
  procedural / reactivation). Step 3 selects by frame-coverage only. **Known, deferred gap**,
  stated rather than silently shipped; the MVP itself softens this ("In the MVP this barely
  fires", §10).
- Deeper judgment-loop interrogation across the 8 angles (Step 5).

## 9. Acceptance criteria

- `select_experience` no longer returns a fixed experience; it selects deterministically from
  the founder seed by `target_frames`, binds to a real ledger owned-problem, and gates.
- Every `content/rubrics/*.yaml` passes the full gate and clears ≥8 angles (the moat test).
- The orphan `veldra_licensing_continuity` is retired; no tracked experience has a dangling
  `ledger_ref`.
- The six-link loop still closes end-to-end (`test_dry_run`, `test_orchestration` green).
- No confidential corpus text in any tracked file (`git ls-files` check clean).
- Full suite green; ruff clean; adversarial core-path review run and findings addressed.

## 10. Logged for later (found during verification, NOT Step-3 scope)

These are doc-vs-code gaps surfaced by the verification pass; recorded so they are not lost,
but they belong to other steps:
- **Core user-approval path is unimplemented** (§7/§16 list it as Settled). Derivation
  exists; user edit/approve/sign-off does not. Onboarding concern, not Step 3.
- **`regression` is a dead path** — `StopReason.regression` is never assigned and the
  `"regressed"` response outcome is never consumed (treated as `unchanged`). **`budget` stop
  is not actually exercised** by any passing test (the named budget test fires `plateau`).
  Both are Step-5 ("harden the judgment loop") territory.

---

## Verification provenance

Before finalizing, this design was cross-checked from scratch against
`Retnovation_Complete_Picture.md` and the corpus by five independent verifier subagents
(doctrine spine, six-link loop, judgment loop, MVP scope/postures, this Step-3 plan).
Baseline confirmed fresh: `pytest` 40 passed / 1 skipped, `ruff` clean, no training code.
The verification corrected one prior error (Bobby Axe is founder, not executive → D2),
confirmed the deterministic approach is not a spine violation (D1), confirmed the orphan and
that retiring it is cleaner than re-anchoring, and flagged the 8-angle floor's provenance
(D3) and the function-mapping gap (§8). The corpus docs are local-only and gitignored.
