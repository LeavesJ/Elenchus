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
LATER = NOW + timedelta(hours=1)


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
    assert empty == {
        "record": None,
        "next_pick": None,
        "inflight": None,
        "theme": None,
        "territory_rank": None,
    }
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
    st.write_state(sid, territory_rank=["decision_under_stakes", "continuity_lock_in"])
    got = st.read_state(sid)
    assert got["territory_rank"] == ["decision_under_stakes", "continuity_lock_in"]
    assert got["record"] == record  # survives the rank-only update


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


def test_existing_db_gains_the_territory_rank_column(tmp_path):
    # A db created BEFORE the rank persisted (triage fold 2026-07-03) has web_sitting_state
    # without territory_rank_json; the defensive ALTER must migrate it in place.
    path = tmp_path / "old-rank.db"
    c = sqlite3.connect(str(path))
    c.execute(
        "CREATE TABLE web_sitting_state "
        "(sitting_id TEXT PRIMARY KEY, record_json TEXT, next_pick_ref TEXT, "
        "next_pick_title TEXT, inflight_json TEXT, theme_json TEXT)"
    )
    c.execute("INSERT INTO web_sitting_state (sitting_id, theme_json) VALUES ('s0', '{}')")
    c.commit()
    c.close()
    st = SittingStore(str(path))
    assert not st.inert
    assert st.read_state("s0")["territory_rank"] is None  # old row readable, key present
    st.write_state("s0", territory_rank=["irreversible_anchor"])
    assert st.read_state("s0")["territory_rank"] == ["irreversible_anchor"]
    assert st.read_state("s0")["theme"] == {}  # old columns survive


def test_l3_surfaces_are_inert_on_memory():
    st = SittingStore(":memory:")
    assert st.inert
    st.write_world("s1", "her situation", NOW)
    assert st.read_world("s1") is None
    st.add_generated_problem("gen:s1:1", "s1", "license_continuity", "scenario", NOW)
    assert st.read_generated_problem("gen:s1:1") is None
    st.log_converged("s1", "gen:s1:1", NOW, experience_id="license_continuity")
    assert st.territories_within(NOW) == set()


def test_latest_terrain_quotes_the_most_recent_landed_village(tmp_path):
    """The return-visit line's regions clause quotes the frozen village the user last SAW —
    latest_terrain returns the most recently updated sitting's record terrain, skipping
    record-less sittings, and None when nothing ever landed."""
    st = _store(tmp_path)
    assert st.latest_terrain() is None
    sid1 = st.create_sitting(NOW)
    st.write_state(
        sid1,
        record={
            "experience_id": "e1",
            "recent": [],
            "stop_reason": "converged",
            "terrain": [{"render": "rendered"}, {"render": "seed"}],
        },
    )
    st.close_sitting(sid1)
    sid2 = st.create_sitting(NOW + timedelta(hours=1))
    st.append_turn(
        sid2, "vera", {"text": "newer sitting, nothing landed yet"}, NOW + timedelta(hours=1)
    )
    # sid2 is more recent but has NO record -> the landed village still wins
    assert st.latest_terrain() == [{"render": "rendered"}, {"render": "seed"}]
    st.write_state(
        sid2,
        record={
            "experience_id": "e2",
            "recent": [],
            "stop_reason": "converged",
            "terrain": [{"render": "rendered"}, {"render": "rendered"}],
        },
    )
    st.append_turn(sid2, "you", {"text": "bump freshness"}, NOW + timedelta(hours=2))
    assert st.latest_terrain() == [{"render": "rendered"}, {"render": "rendered"}]
    assert SittingStore(":memory:").latest_terrain() is None


def test_latest_homebase_returns_terrain_and_houses_from_the_same_record(tmp_path):
    """The homebase snapshot is the frozen (terrain, houses) pair a close already persisted
    (session_runner.py:1072-1086) — read BOTH from ONE record so every house.region ordinal
    indexes into the served terrain (spec §3 consistency)."""
    store = _store(
        tmp_path
    )  # the file's helper: SittingStore(str(tmp_path / name)); NO store.close()
    sit = store.create_sitting(NOW)  # NOW is the module datetime; create_sitting(now) -> sitting_id
    terrain = [
        {"region_id": "r0", "render": "rendered", "vitality": 2, "elevation": 1},
        {"region_id": "r1", "render": "seed", "vitality": None, "elevation": None},
    ]
    houses = [{"region": 0, "bucket": 2, "height_bucket": 2}]
    # persist a landed record exactly as _serialize_record/_on_done leaves it (terrain+houses keys)
    store.write_state(sit, record={"terrain": terrain, "houses": houses})
    home = store.latest_homebase()
    assert home["terrain"] == terrain
    assert home["houses"] == houses
    assert all(0 <= h["region"] < len(home["terrain"]) for h in home["houses"])


def test_latest_homebase_is_empty_when_no_landed_record(tmp_path):
    assert _store(tmp_path).latest_homebase() == {"terrain": [], "houses": []}


def test_latest_homebase_pairs_terrain_and_houses_from_the_SAME_newest_record(tmp_path):
    """The DISCRIMINATING fixture (spec §3 consistency — the red-able test the shared-private
    refactor exists for): TWO landed sittings with DISTINCT terrain lengths and a house at
    region>0. latest_homebase MUST return the newer record's terrain AND its houses (never a fresh
    terrain paired with stale houses), and agree with latest_terrain. Fails if the two reads ever
    diverge OR if a house mis-indexes a wrong-length terrain (the terrain3d.js:207 silent-drop
    hazard). A single-record fixture cannot exercise this — it is tautological."""
    store = _store(tmp_path)
    # OLDER saga: a 2-region terrain, house at region 1
    old = store.create_sitting(NOW)
    store.write_state(
        old,
        record={
            "terrain": [
                {"region_id": "r0", "render": "rendered", "vitality": 1, "elevation": 1},
                {"region_id": "r1", "render": "rendered", "vitality": 2, "elevation": 1},
            ],
            "houses": [{"region": 1, "bucket": 2, "height_bucket": 1}],
        },
    )
    # NEWER saga: a 3-region terrain, house at region 2 — OUT OF RANGE against the old 2-region
    # terrain, so a mis-paired read would produce an invalid house. Make this record the newest
    # (mirror test_latest_terrain_quotes_the_most_recent_landed_village's updated_at ordering).
    new = store.create_sitting(LATER)  # LATER > NOW — match the existing test's ordering mechanism
    new_terrain = [
        {"region_id": "r0", "render": "rendered", "vitality": 1, "elevation": 1},
        {"region_id": "r1", "render": "rendered", "vitality": 2, "elevation": 1},
        {"region_id": "r2", "render": "rendered", "vitality": 3, "elevation": 2},
    ]
    new_houses = [{"region": 2, "bucket": 3, "height_bucket": 2}]
    store.write_state(new, record={"terrain": new_terrain, "houses": new_houses})
    home = store.latest_homebase()
    assert home["terrain"] == new_terrain  # newest terrain
    assert home["houses"] == new_houses  # newest houses — from the SAME record
    assert home["terrain"] == store.latest_terrain()  # both readers pick the same record
    assert all(0 <= h["region"] < len(home["terrain"]) for h in home["houses"])  # region 2 < 3


def test_compose_houses_over_a_real_store_groups_mixed_ontology_sittings(tmp_path):
    """Retrofit gate (spec §7/§9): over a REAL SittingStore, compose_houses must yield ONE house per
    SITTING — (a) a sitting mixing a curated ref and a forged gen: ref stays ONE house (never split by
    ref-prefix), (b) a multi-chapter forged saga is ONE house, (c) a legacy curated-only sitting is ONE
    house — in first-arrival order, NEVER one house per row (the '6 for 3' bug)."""
    from datetime import datetime, timedelta, timezone

    from retnovation.terrain import compose_houses, project_terrain
    from retnovation.types import LearnerState
    from retnovation.web.sitting_store import SittingStore

    store = SittingStore(str(tmp_path / "retrofit.db"))
    wall = datetime.now(timezone.utc)
    # sitting "mix": curated + forged rows in ONE sitting -> must stay ONE house (not split)
    store.log_converged(
        "mix", "veldra:license_fork_risk", wall - timedelta(hours=6), "license_continuity"
    )
    store.log_converged("mix", "gen:mix:1", wall - timedelta(hours=5), "license_continuity")
    # sitting "saga": three forged chapters -> ONE house
    store.log_converged("saga", "gen:saga:1", wall - timedelta(hours=4), "irreversible_anchor")
    store.log_converged("saga", "gen:saga:2", wall - timedelta(hours=3), "irreversible_anchor")
    store.log_converged("saga", "gen:saga:3", wall - timedelta(hours=2), "irreversible_anchor")
    # sitting "legacy": curated-only -> ONE house
    store.log_converged(
        "legacy", "veldra:proof_before_promise", wall - timedelta(hours=1), "proof_before_promise"
    )

    rows = store.converged_log()
    assert len(rows) == 6  # six convergence rows across three sittings
    houses = compose_houses(project_terrain(LearnerState(frames={}), wall).regions, rows, {})
    assert (
        len(houses) == 3
    )  # THREE sagas -> THREE houses (NOT six) — mixed sitting NOT split, saga NOT fragmented
    for h in houses:
        assert set(h) == {"region", "bucket", "height_bucket"}
    # empty projection -> every house lands region 0 with bucket None (seed) -> height floored to 1
    assert all(h["height_bucket"] == 1 for h in houses)


def test_reopen_sitting_flips_closed_to_live_and_stamps_updated_at(tmp_path):
    store = _store(tmp_path)
    t0 = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    sit = store.create_sitting(t0)
    store.close_sitting(sit)
    assert store.live_sitting() is None
    t1 = datetime(2026, 7, 9, 9, 0, tzinfo=timezone.utc)
    assert store.reopen_sitting(sit, t1) == sit
    row = store.live_sitting()
    assert row is not None and row["id"] == sit
    # updated_at is stamped NOW: without it, resume_or_start's 18h idle reaper
    # would close a just-reopened old saga on the very next load.
    assert row["updated_at"] == t1.isoformat()


def test_reopen_sitting_adopts_the_winner_when_another_sitting_is_live(tmp_path):
    store = _store(tmp_path)
    t = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    old = store.create_sitting(t)
    store.close_sitting(old)
    winner = store.create_sitting(t)  # a different LIVE sitting exists
    # Flipping `old` to live would violate ux_web_sitting_live -> adopt the winner, never raise.
    assert store.reopen_sitting(old, t) == winner
    assert store.live_sitting()["id"] == winner
    # the target stayed closed (no second live row)
    import sqlite3

    with sqlite3.connect(str(tmp_path / "s.db")) as c:
        n = c.execute("SELECT COUNT(*) FROM web_sitting WHERE status='live'").fetchone()[0]
    assert n == 1


def test_reopen_sitting_is_a_noop_when_the_target_is_already_live(tmp_path):
    store = _store(tmp_path)
    t = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    sit = store.create_sitting(t)
    assert store.reopen_sitting(sit, t) == sit  # already live == success
    assert store.live_sitting()["id"] == sit


def test_reopen_sitting_unknown_id_with_no_live_returns_none(tmp_path):
    store = _store(tmp_path)
    t = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    assert store.reopen_sitting("nope", t) is None
    assert store.live_sitting() is None


def test_reopen_or_activity_on_an_older_saga_never_hides_a_newer_sagas_houses(tmp_path):
    """Cross-arc regression (hunt 2026-07-09): `_latest_landed_record` ordered by
    web_sitting.updated_at, which reopen_sitting (and every append_turn) bump WITHOUT a new
    landing. Re-entering (or conversing in) an OLDER saga promoted its stale, smaller frozen
    record ahead of the true cumulative one, so newer sagas' houses vanished from the homebase.
    The selector must key on the actual LANDING time (landed_at), immune to updated_at bumps."""
    store = _store(tmp_path)
    t1 = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 7, 1, 11, 0, tzinfo=timezone.utc)
    # Saga A landed first: its frozen record saw only A (1 house).
    a = store.create_sitting(t1)
    store.write_state(
        a,
        record={
            "terrain": [{"render": "rendered"}],
            "houses": [{"region": 0, "bucket": 2, "height_bucket": 1}],
        },
        now=t1,
    )
    store.close_sitting(a)
    # Saga B landed later: its frozen record is the CUMULATIVE village (2 houses) the user last saw.
    b = store.create_sitting(t2)
    store.write_state(
        b,
        record={
            "terrain": [{"render": "rendered"}, {"render": "rendered"}],
            "houses": [
                {"region": 0, "bucket": 2, "height_bucket": 1},
                {"region": 1, "bucket": 2, "height_bucket": 1},
            ],
        },
        now=t2,
    )
    store.close_sitting(b)
    assert len(store.latest_homebase()["houses"]) == 2  # B is the cumulative homebase

    # Re-enter the OLDER saga A: reopen bumps A.updated_at ahead of B (idle-reaper defense) but
    # lands NO new record. B's 2 houses must NOT vanish.
    t3 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    assert store.reopen_sitting(a, t3) == a
    assert len(store.latest_homebase()["houses"]) == 2  # still B — the fix
    assert store.latest_terrain() == [{"render": "rendered"}, {"render": "rendered"}]

    # And a plain turn on A (also bumps updated_at) must not regress the homebase either.
    store.append_turn(a, "you", {"text": "hi"}, t3 + timedelta(minutes=1))
    assert len(store.latest_homebase()["houses"]) == 2


def test_write_state_without_now_leaves_landed_at_null_ordering_falls_back(tmp_path):
    """Back-compat: a record written WITHOUT `now` (legacy callers / converse rewrites) does not
    stamp landed_at, so pure-legacy dbs order by updated_at exactly as before."""
    store = _store(tmp_path)
    t1 = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    a = store.create_sitting(t1)
    store.write_state(a, record={"terrain": [{"render": "rendered"}], "houses": []})  # no now
    assert store.latest_terrain() == [{"render": "rendered"}]  # still selectable
