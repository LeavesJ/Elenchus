"""Durable sittings: the persistence module (spec 2026-07-01-durable-sittings-design §2a).

The store mirrors the PROJECTED client wire and the landed-segment state — never engine
internals. `:memory:` makes it inert (per-op connections would each see an empty db), which is
what the shell-only tests rely on.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone

from retnovation.web.sitting_store import SittingStore

NOW = datetime(2026, 7, 1, 21, 0, 0, tzinfo=timezone.utc)


def _store(tmp_path, name="s.db"):
    return SittingStore(str(tmp_path / name))


def test_memory_path_is_inert():
    st = SittingStore(":memory:")
    assert st.inert
    assert st.live_sitting() is None
    sid = st.create_sitting(NOW)  # returns an id but persists nothing
    assert st.live_sitting() is None
    st.append_turn(sid, "vera", {"text": "hello"}, NOW)
    assert st.turns(sid) == []
    st.log_converged(sid, "veldra:x", NOW)
    assert st.converged_within(NOW) == set()
    state = st.read_state(sid)
    assert state["record"] is None and state["inflight"] is None


def test_sitting_lifecycle_one_live_at_a_time(tmp_path):
    st = _store(tmp_path)
    assert not st.inert
    assert st.live_sitting() is None
    sid1 = st.create_sitting(NOW)
    live = st.live_sitting()
    assert live is not None and live["id"] == sid1 and live["status"] == "live"
    st.close_sitting(sid1)
    assert st.live_sitting() is None
    sid2 = st.create_sitting(NOW + timedelta(minutes=1))
    assert sid2 != sid1  # ids are never reused (L-3: the closed sitting's rows survive)
    assert st.live_sitting()["id"] == sid2


def test_turns_round_trip_order_and_kinds(tmp_path):
    st = _store(tmp_path)
    sid = st.create_sitting(NOW)
    st.append_turn(sid, "seam", {"text": "Same sitting — next door."}, NOW)
    st.append_turn(sid, "vera", {"text": "opening"}, NOW)
    st.append_turn(sid, "you", {"text": "my position"}, NOW)
    st.append_turn(sid, "landing", {"text": "you owned the tradeoff"}, NOW)
    st.append_turn(sid, "muted", {"text": "door chosen"}, NOW)
    got = st.turns(sid)
    assert [t["kind"] for t in got] == ["seam", "vera", "you", "landing", "muted"]
    assert got[1]["payload"]["text"] == "opening"
    # turns bump the sitting's freshness (the 18h staleness clock)
    assert st.live_sitting()["updated_at"] == NOW.isoformat()


def test_turns_are_scoped_to_their_sitting(tmp_path):
    st = _store(tmp_path)
    sid1 = st.create_sitting(NOW)
    st.append_turn(sid1, "vera", {"text": "old sitting"}, NOW)
    st.close_sitting(sid1)
    sid2 = st.create_sitting(NOW + timedelta(hours=1))
    st.append_turn(sid2, "vera", {"text": "new sitting"}, NOW + timedelta(hours=1))
    assert [t["payload"]["text"] for t in st.turns(sid2)] == ["new sitting"]
    # the closed sitting's turns are retained, not deleted (L-3)
    assert [t["payload"]["text"] for t in st.turns(sid1)] == ["old sitting"]


def test_state_partial_updates(tmp_path):
    st = _store(tmp_path)
    sid = st.create_sitting(NOW)
    empty = st.read_state(sid)
    assert empty == {"record": None, "next_pick": None, "inflight": None, "theme": None}
    record = {
        "experience_id": "decision_under_stakes",
        "posture": "operator",
        "recent": [["student", "hi"], ["Vera", "welcome"]],
        "stop_reason": "converged",
        "terrain": [{"render": "rendered"}],
    }
    st.write_state(sid, record=record, next_pick=("veldra:x", "Some door"))
    st.write_state(sid, inflight={"experience_id": "e2", "ledger_ref": "veldra:y"})
    got = st.read_state(sid)
    assert got["record"] == record  # survives the inflight-only update
    assert got["next_pick"] == ("veldra:x", "Some door")
    assert got["inflight"] == {"experience_id": "e2", "ledger_ref": "veldra:y"}
    st.write_state(sid, inflight=None, theme={"accent": "slate"})
    got = st.read_state(sid)
    assert got["inflight"] is None and got["record"] == record
    assert got["theme"] == {"accent": "slate"}


def test_converged_window_rolls_24h_across_utc_midnight(tmp_path):
    """The founder's incident shape: 14:18 local converged is UTC July 1; the evening sitting is
    UTC July 2 — a UTC DATE bucket would exclude nothing. The rolling window must."""
    st = _store(tmp_path)
    sid = st.create_sitting(NOW)
    # converged at 21:18 UTC July 1 (14:18 local); read at 03:55 UTC July 2 (20:55 local)
    st.log_converged(sid, "veldra:pricing", datetime(2026, 7, 1, 21, 18, tzinfo=timezone.utc))
    read_at = datetime(2026, 7, 2, 3, 55, tzinfo=timezone.utc)
    assert st.converged_within(read_at) == {"veldra:pricing"}  # date changed, window holds
    # a >24h-old convergence falls out of the window
    assert st.converged_within(read_at + timedelta(hours=22)) == set()
    # the log spans sittings: a second sitting sees the first's rows
    st.close_sitting(sid)
    sid2 = st.create_sitting(read_at)
    st.log_converged(sid2, "veldra:license", read_at)
    assert st.converged_within(read_at) == {"veldra:pricing", "veldra:license"}


def test_payloads_survive_json_round_trip_verbatim(tmp_path):
    st = _store(tmp_path)
    sid = st.create_sitting(NOW)
    text = 'She said: "commit — 2%" & <held>\nnewline'
    st.append_turn(sid, "vera", {"text": text, "theme": {"accent": "amber"}}, NOW)
    assert st.turns(sid)[0]["payload"] == {"text": text, "theme": {"accent": "amber"}}
    # stored as JSON, not repr (a reader in another process can parse it)
    assert json.loads(json.dumps(text)) == text


# --- Living sitting Task L3: the world, generated problems, territory window (spec §2f/§2c) ---


def test_world_round_trip_and_upsert(tmp_path):
    st = _store(tmp_path)
    sid = st.create_sitting(NOW)
    assert st.read_world(sid) is None  # no world yet
    st.write_world(sid, "signing a delivery commitment Thursday", NOW)
    assert st.read_world(sid) == "signing a delivery commitment Thursday"
    # the world persists and updates in place — one world per sitting, situation may sharpen
    st.write_world(sid, "the penalty clause is the fight", NOW + timedelta(minutes=5))
    assert st.read_world(sid) == "the penalty clause is the fight"
    assert st.read_world("no-such-sitting") is None


def test_generated_problem_round_trip(tmp_path):
    st = _store(tmp_path)
    sid = st.create_sitting(NOW)
    st.add_generated_problem(f"gen:{sid}:1", sid, "license_continuity", "You signed Thursday…", NOW)
    got = st.read_generated_problem(f"gen:{sid}:1")
    assert got == {"experience_id": "license_continuity", "scenario": "You signed Thursday…"}
    assert st.read_generated_problem("gen:unknown:9") is None  # missing row -> M2's static path


def test_territories_within_windows_by_experience_id_across_sittings(tmp_path):
    st = _store(tmp_path)
    sid1 = st.create_sitting(NOW)
    st.log_converged(sid1, f"gen:{sid1}:1", NOW, experience_id="license_continuity")
    st.close_sitting(sid1)
    sid2 = st.create_sitting(NOW + timedelta(hours=2))
    st.log_converged(
        sid2, f"gen:{sid2}:1", NOW + timedelta(hours=2), experience_id="irreversible_anchor"
    )
    read_at = NOW + timedelta(hours=3)
    # the window spans sittings and keys on the TERRITORY (M3: the only rotation mechanism)
    assert st.territories_within(read_at) == {"license_continuity", "irreversible_anchor"}
    # a >24h-old convergence falls out; the ref-keyed window still sees both refs meanwhile
    assert st.territories_within(NOW + timedelta(hours=25)) == {"irreversible_anchor"}
    assert st.converged_within(read_at) == {f"gen:{sid1}:1", f"gen:{sid2}:1"}
    # rows logged without a territory (pre-forge curated path) never enter the territory window
    st.log_converged(sid2, "veldra:pricing", read_at)
    assert "" not in st.territories_within(read_at + timedelta(minutes=1))
    assert st.territories_within(read_at + timedelta(minutes=1)) == {
        "license_continuity",
        "irreversible_anchor",
    }


def test_existing_db_gains_the_experience_id_column(tmp_path):
    # A db created BEFORE the living sitting has web_converged without experience_id; the
    # defensive ALTER must migrate it and keep the old rows readable.
    path = tmp_path / "old.db"
    c = sqlite3.connect(str(path))
    c.execute(
        "CREATE TABLE web_converged "
        "(sitting_id TEXT NOT NULL, ref TEXT NOT NULL, converged_at TEXT NOT NULL)"
    )
    c.execute(
        "INSERT INTO web_converged VALUES ('s0', 'veldra:pricing', ?)",
        ((NOW - timedelta(hours=1)).isoformat(),),
    )
    c.commit()
    c.close()
    st = SittingStore(str(path))
    assert not st.inert
    st.log_converged("s1", "gen:s1:1", NOW, experience_id="license_continuity")
    assert st.converged_within(NOW) == {"veldra:pricing", "gen:s1:1"}  # old rows survive
    assert st.territories_within(NOW) == {"license_continuity"}  # old rows: no territory


def test_l3_surfaces_are_inert_on_memory():
    st = SittingStore(":memory:")
    assert st.inert
    st.write_world("s1", "her situation", NOW)
    assert st.read_world("s1") is None
    st.add_generated_problem("gen:s1:1", "s1", "license_continuity", "scenario", NOW)
    assert st.read_generated_problem("gen:s1:1") is None
    st.log_converged("s1", "gen:s1:1", NOW, experience_id="license_continuity")
    assert st.territories_within(NOW) == set()
