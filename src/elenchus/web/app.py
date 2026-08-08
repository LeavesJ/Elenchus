from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .session_runner import SessionRegistry

_STATIC = Path(__file__).parent / "static"
_SID = "single"  # one user, one session (MVP)

# D1: a blank opening/reply must never reach classify_intake/classify_response — the live
# Anthropic API rejects empty content with a 400 ("user messages must have non-empty content"),
# which the worker surfaces as a terminal error and bricks the session. Guard at the HTTP
# boundary (defense-in-depth alongside the frontend) so the engine is never called with blank
# input and the session stays alive. (Placeholder copy; the conversational front door supersedes
# this with real orientation.)
_BLANK_NUDGE = {
    "kind": "nudge",
    "message": "Take a position — even a rough first instinct. An empty answer can't be read.",
}


class _Choice(BaseModel):
    index: int | None = None
    nonce: int | None = None  # stale-menu guard: mismatch re-serves the menu (durable sittings)


class _Text(BaseModel):
    text: str


class _Cont(BaseModel):
    menu: bool = False
    work_anyway: bool = False  # the informed re-serve's first choice (living sitting §2c)


class _Memory(BaseModel):
    index: int


class _Expectation(BaseModel):
    """The forecast frozen at convergence. Free TEXT only, and deliberately no confidence number
    and no structured fields: v0 is establishing whether people give interpretable prospective
    predictions at all, and a confidence widget would presuppose that they do. No index either --
    the server targets the convergence it just wrote for this session."""

    text: str
    # Echoes the token the landing handed out. It names WHICH convergence this forecast is for, so
    # a stale box left in the append-only thread can only ever address its own (already answered,
    # therefore refused) row instead of whatever the server happens to be holding.
    token: str = ""


class _Outcome(BaseModel):
    """What became of the decision. `kind` is a Literal so a grading word ('worked', 'correct')
    is refused by FastAPI with a 422 before it ever reaches the store — the constraint that
    keeps outcomes from becoming verdicts lives at the boundary, not in a docstring."""

    index: int
    outcome: str
    kind: Literal["held", "reversed", "overtaken", "too_early"]


def _default_model():
    from ..model import AnthropicModel

    return AnthropicModel()


def _build_stamp() -> str:
    """Best-effort build identity (durable sittings §2f): tonight's incident was undiagnosable in
    the tab because nothing said WHICH build the process was running. Never raises."""
    import subprocess

    try:
        out = subprocess.run(
            ["git", "describe", "--always", "--dirty"],
            capture_output=True,
            timeout=1,
            text=True,
            cwd=str(Path(__file__).resolve().parents[3]),
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _emit(reg: SessionRegistry, tag: str, data: dict) -> dict:
    if tag == "menu":
        out = {"kind": "menu", "problems": data["problems"], "theme": data.get("theme", {})}
        if "nonce" in data:
            out["nonce"] = data["nonce"]
        return out
    if tag == "resume":  # durable sittings: the whole room, verbatim (already-projected payload)
        return {"kind": "resume", **data}
    if tag == "nudge":  # soft fail (stale tab) — the shell shows the message and recovers
        return {"kind": "nudge", "message": data.get("message", "")}
    if tag == "say" and data.get("frontdoor"):
        # The cold beat (living sitting §2a/§2g): the static ask + the small doors. The
        # embedded menu is projected title-only — refs stay server-side (L-13).
        out = {
            "kind": "frontdoor",
            "text": data["text"],
            "menu": {
                "problems": data["menu"]["problems"],
                "nonce": data["menu"].get("nonce", 0),
            },
            "theme": data.get("theme", {}),
        }
        if data.get("returning"):  # the return-visit muted line (§2f review P10)
            out["returning"] = data["returning"]
        # Phase 2 (spec §6): the world is the first screen. The frozen cumulative homebase rides
        # the load payload behind the SAME allowlist the close payload uses — positional/bucketed
        # only (terrain = coarse learner_view; houses = {region, bucket}); no refs,
        # no sitting_id, no raw count (L-13). Attached only when non-empty (first visit = no world).
        if data.get("terrain"):
            out["terrain"] = data["terrain"]
        if data.get("houses"):
            out["houses"] = data["houses"]
        if data.get("vessels"):
            out["vessels"] = {"count": data["vessels"]["count"]}
        return out
    if tag == "say":  # every Concierge-authored visible turn (opening, re-invite, probe, wind-down)
        out = {"kind": "say", "text": data["text"]}
        if "theme" in data:  # the opening say carries the role atmosphere (two-phase)
            out["theme"] = data["theme"]
        if "seam" in data:  # a continued segment's static seam line (durable sittings §2d)
            out["seam"] = data["seam"]
        if "bridge" in data:  # the heard-you / fallback bridge on a forged opening (§2a/§2b)
            out["bridge"] = data["bridge"]
        # The wind-down Continue label (user-steered chapters §2c): a steered/rotation label rides
        # the converse say. next_kind is a derived enum; next_desc is HER raw words or the territory
        # description — the distilled pressure and refs never appear (L-13).
        for k in ("next_title", "next_desc", "next_kind"):
            if k in data:
                out[k] = data[k]
        return out
    if tag == "reserve":  # every territory windowed: the informed re-serve question (§2c P3)
        return {
            "kind": "reserve",
            "copy": data.get("copy", ""),
            "choices": data.get("choices", []),
        }
    if tag == "done":  # the engine converged — the SESSION does not end; the user owns closure. The
        # felt landing rides the payload; the guarded next door (chained sittings) rides with it.
        out = {
            "kind": "done",
            "terminal": True,
            "landing": data.get("landing", ""),
            # The readable Continue label (spec §2d): SHORT title + description + kind
            # (chapter|pressure). next_kind is a derived enum — no ref/frame (L-13).
            "next_title": data.get("next_title", ""),
            "next_desc": data.get("next_desc", ""),
            "next_kind": data.get("next_kind", "pressure"),
        }
        # Attach-only-when-present, like confluence below. True exactly once per convergence:
        # the moment after the reasoning and before reality, which is the only window where a
        # forecast is neither a leaked reasoning move nor a hindsight reconstruction.
        if data.get("ask_expectation"):
            out["ask_expectation"] = True
            # Opaque per-convergence id. NOT a ref: an internal identifier must never reach the
            # client (L-13), and this one carries no problem identity at all.
            out["expectation_token"] = data.get("expectation_token", "")
        if data.get("confluence"):  # transient (Spec-2 §5): attach-only-when-present, two ints
            out["confluence"] = {
                "from_slot": data["confluence"]["from_slot"],
                "to_slot": data["confluence"]["to_slot"],
            }
        return out
    if tag == "expectation":  # the forecast landed (or was already frozen) — no content echoed
        return {"kind": "expectation", "recorded": bool(data.get("recorded"))}
    if tag == "memory":  # the memory bubble (Spec-1 5b/5d): a by-ref pure read, no identifiers
        if data.get("unavailable"):
            return {"kind": "memory", "unavailable": True}
        return {
            "kind": "memory",
            "situation": data["situation"],
            "position": data["position"],
            "when": data["when"],
            "origin": data.get("origin", ""),
            # The fourth field, projected explicitly like the rest — nulls until answered.
            "outcome": data.get("outcome"),
            "outcome_kind": data.get("outcome_kind"),
            "ask_outcome": bool(data.get("ask_outcome")),
        }
    if tag == "close":  # user-driven end: the honest close + the frozen-at-convergence village —
        # terrain regions plus one house per convergence (living sitting §2f; ordinal-only, L-13)
        out = {
            "kind": "close",
            "close": data.get("close", ""),
            "terrain": data.get("terrain", []),
            "houses": data.get("houses", []),
        }
        if data.get("confluence"):  # transient (Spec-2 §5): attach-only-when-present, two ints
            out["confluence"] = {
                "from_slot": data["confluence"]["from_slot"],
                "to_slot": data["confluence"]["to_slot"],
            }
        if data.get("vessels"):  # Spec-2 §6 (D-S2-4): attach-only-when-present, bare count
            out["vessels"] = {"count": data["vessels"]["count"]}
        return out
    return {"kind": "error", "message": data.get("message", "")}


class _NoStoreStaticFiles(StaticFiles):
    """Same staleness hazard the `/` route already guards against with `Cache-Control: no-store`
    (durable sittings §2f) — a bare `StaticFiles` mount only sends `etag`/`last-modified`, so a
    browser is free to serve terrain3d.js / ceremonies.js from heuristic cache without ever
    revalidating. That is invisible from a human's checking of the build: the shell is always
    fresh, /api/health reports the real running build, and the 3D renderer silently keeps
    executing yesterday's bytes underneath both. Force `no-store` on every static response
    (including 304s — StaticFiles.file_response mutates the same response object either way) so
    a cached renderer under a fresh shell can never happen again, undetected or otherwise."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["cache-control"] = "no-store"
        return response


def create_app(db_path: str, model_factory=None) -> FastAPI:
    app = FastAPI(title="Elenchus — Cartographer MVP")

    reg = SessionRegistry(db_path, model_factory or (lambda: _default_model()))
    build = _build_stamp()

    @app.get("/api/health")
    def health():
        return {"ok": True, "build": build}

    @app.get("/")
    def index():
        # no-store kills the stale-shell class structurally (durable sittings §2f) — a cached
        # shell that predates kind:"resume" would render every page load as an error line.
        return FileResponse(_STATIC / "index.html", headers={"Cache-Control": "no-store"})

    app.mount("/static", _NoStoreStaticFiles(directory=_STATIC), name="static")

    @app.post("/api/session")
    def start():
        # Durable sittings: a live sitting RESUMES (same room, whole conversation) — the
        # unconditional cold start was the founder's amnesia incident (spec §0).
        out = _emit(reg, *reg.resume_or_start(_SID))
        out["build"] = build  # visible in the tab (console/#mark tooltip) — §2f
        return out

    @app.post("/api/session/{sid}/choose")
    def choose(sid: str, body: _Choice):
        # choose() (not step) so the CLIENT-made choice persists to the sitting transcript.
        return _emit(
            reg, *reg.choose(_SID, body.index if body.index is not None else 0, nonce=body.nonce)
        )

    @app.post("/api/session/{sid}/say")
    def say(sid: str, body: _Text):
        if not body.text.strip():
            return _BLANK_NUDGE  # blank input never reaches the engine (D1 guard)
        return _emit(reg, *reg.step(_SID, body.text))

    @app.post("/api/session/{sid}/converse")
    def converse(sid: str, body: _Text):
        if not body.text.strip():
            return _BLANK_NUDGE  # blank never reaches the model (D1 guard); engine-free path
        return _emit(reg, *reg.converse(_SID, body.text))

    @app.post("/api/session/{sid}/continue")
    def continue_(sid: str, body: _Cont):
        # Chained sittings: the next bounded engine session in the same thread (one-click or
        # menu); work_anyway honors the informed re-serve's first choice (living sitting §2c).
        return _emit(reg, *reg.continue_session(_SID, body.menu, work_anyway=body.work_anyway))

    @app.post("/api/session/{sid}/close")
    def close_session(sid: str):
        return _emit(reg, *reg.close(_SID))

    @app.post("/api/session/{sid}/memory")
    def memory(sid: str, body: _Memory) -> dict:
        # Spec-1 5d: the click sends an INDEX; the server resolves it by-ref (L-13).
        return _emit(reg, *reg.memory(_SID, body.index))

    @app.post("/api/session/{sid}/outcome")
    def outcome(sid: str, body: _Outcome) -> dict:
        # Same index-only contract as the read (L-13). Returns the re-read memory, so the
        # client renders the annotated record rather than assuming the write landed.
        return _emit(reg, *reg.record_outcome(_SID, body.index, body.outcome, body.kind))

    @app.post("/api/session/{sid}/expectation")
    def expectation(sid: str, body: _Expectation) -> dict:
        # No index: the server writes to the convergence it just logged for this session, so a
        # stale-index failure mode does not exist here. Write-once in the store, so a replayed
        # POST cannot overwrite a forecast after the outcome is known.
        return _emit(reg, *reg.record_expectation(_SID, body.text, body.token))

    return app
