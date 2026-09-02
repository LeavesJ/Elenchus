"""How many paid model calls one process may make before it refuses.

The web surface has no authentication -- the invitee hostname is the only credential -- so anyone
forwarded a link can loop POSTs, and each learner turn is roughly five or six Opus calls. Auth
belongs in front of the tunnel (Cloudflare Access) and is not this module's job. This is the bound
that still holds when auth is absent or misconfigured, which is exactly the state a beta is in
most often.

Deliberately a CALL count and not a token count. Every call already carries its own `max_tokens`,
so calls bound cost to within a known factor, and a count is checkable by reading one number. A
token ceiling would be tighter and would need usage parsed off every response, including the ones
that raise -- more surface for the thing whose entire job is to be trustworthy under abuse.

Per PROCESS, which is per INVITEE, because the beta runs one process and one database per person.
That is the same fact the isolation argument already rests on; if that ever stops being true this
ceiling stops meaning what it says. "Per process" is only true because `web.app` mints the Budget
ONCE and closes the model factory over it -- a Budget minted inside the factory is per segment and
resets on every Continue, which is exactly what the first version did.
"""

from __future__ import annotations

# Enough for a long real sitting and nowhere near enough to matter as a bill. Measured basis: the
# founder's own live sitting on 2026-08-30 ran 16 turns; at ~6 calls per turn that is ~100 calls,
# so this leaves roughly a 5x headroom over the longest sitting anyone has actually had.
DEFAULT_MAX_CALLS = 500


class BudgetExceeded(RuntimeError):
    """Raised in place of dispatching a call that would cross the ceiling."""


class Budget:
    """A counter with a ceiling. Not thread-safe by design: the single-flight guard already
    serialises a sitting's model calls, and a lock here would imply a concurrency story the rest
    of this process does not have."""

    def __init__(self, max_calls: int = DEFAULT_MAX_CALLS):
        self.max_calls = max_calls
        self.spent = 0

    def charge(self) -> None:
        """Count one call, or refuse. Checked BEFORE dispatch: a ceiling enforced afterwards has
        already paid for the call it existed to prevent."""
        if self.spent >= self.max_calls:
            raise BudgetExceeded(
                f"spend budget exhausted: this process has made {self.spent} model calls and "
                f"its per-process ceiling is {self.max_calls}. Raise ELENCHUS_MAX_CALLS for this "
                "invitee, or look at why one room is making this many calls."
            )
        self.spent += 1


def from_env(env) -> Budget | None:
    """A budget when the operator asked for one, else None meaning unbounded.

    Absent must mean unbounded and never zero: the suite, the probes and the CLI all construct
    models with no budget, and a default that refused every call would take the product down
    rather than bound it.
    """
    raw = (env.get("ELENCHUS_MAX_CALLS") or "").strip()
    if not raw:
        return None
    # Refuse at boot, never at the first learner's click. `int("abc")` used to raise inside the
    # segment worker AFTER /api/health had said ok; `0` and `-1` built a ceiling that refused the
    # very first call. Either way the process looked healthy while every door died -- L-18's shape
    # with a new cause. `isdigit` rather than int(): it rejects "1.5", "-1", "1_0" and non-ASCII
    # digits alike, and a ceiling is a plain count or it is nothing.
    if not raw.isascii() or not raw.isdigit() or int(raw) < 1:
        raise ValueError(
            f"ELENCHUS_MAX_CALLS={raw!r} is not a ceiling. It must be a positive integer; leave it "
            "unset for no ceiling at all."
        )
    return Budget(max_calls=int(raw))
