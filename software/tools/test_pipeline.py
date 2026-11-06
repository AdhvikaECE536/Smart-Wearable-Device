"""python -m tools.test_pipeline   (offline; uses model.keras if present else RuleModel)"""
import random
from cloud import config as C
from cloud.engine import DeviceTracker
from cloud.geo import MockLocator
from cloud.payload import encode, decode
from cloud.simlib import build_routers, trajectory, scan
from cloud.threat import load_model
from cloud.kinematics import haversine_m

def test_payload():
    aps = [{"bssid": "aa:bb:cc:dd:ee:01", "rssi": -45}, {"bssid": "aa:bb:cc:dd:ee:02", "rssi": -70}]
    h = encode(aps); assert len(h) == 42 and decode(h) == aps
    assert decode(bytes.fromhex(h)) == aps

def make(kind):
    r = build_routers(); rnd = random.Random(1)
    return r, rnd, DeviceTracker("t", MockLocator(r), load_model(C.MODEL_PATH))

def test_vehicle_latches_after_two_windows():
    r, rnd, tr = make("vehicle"); levels = []
    for i, p in enumerate(trajectory("vehicle")):
        levels.append(tr.on_uplink(encode(scan(r, p, rnd)), 1000 + 10 * i)["alert_level"])
    assert levels[0] == 1 and levels[-1] == 2
    assert levels.index(2) >= 6, "must not latch before 2 consecutive windows (needs 7 fixes)"

def test_stationary_never_red():
    r, rnd, tr = make("stationary")
    for i, p in enumerate(trajectory("stationary")):
        assert tr.on_uplink(encode(scan(r, p, rnd)), 1000 + 10 * i)["alert_level"] == 1

def test_dead_zone_fill_and_cap():
    r, rnd, tr = make("vehicle"); traj = trajectory("vehicle")
    for i in range(4):
        tr.on_uplink(encode(scan(r, traj[i], rnd)), 1000 + 10 * i)
    last_t = 1030.0
    outs = [tr.tick(last_t + 16 + 10 * k) for k in range(8)]   # device silent
    srcs = [o["src"] for o in outs if o]
    assert srcs[0] == "dead-reckoning" and len(srcs) == C.MAX_DEADRECKON
    truth = traj[3 + 1]
    assert haversine_m(outs[0]["lat"], outs[0]["lon"], *truth) < 60   # vehicle moved ~110 m; error is small

def test_no_ap_match_uses_dead_reckoning():
    r, rnd, tr = make("vehicle"); traj = trajectory("vehicle")
    for i in range(3):
        tr.on_uplink(encode(scan(r, traj[i], rnd)), 1000 + 10 * i)
    res = tr.on_uplink(encode([{"bssid": "de:ad:be:ef:00:01", "rssi": -50}, {"bssid": "de:ad:be:ef:00:02", "rssi": -60}]), 1030)
    assert res["src"] == "dead-reckoning"

def test_bounce_ignored():
    r, rnd, tr = make("vehicle"); p = trajectory("vehicle")[0]
    assert tr.on_uplink(encode(scan(r, p, rnd)), 1000) is not None
    assert tr.on_uplink(encode(scan(r, p, rnd)), 1001) is None

def test_accuracy_gate_blocks_jitter():
    from cloud.geo import Fix
    class Jitter:                       # stationary wearer, 30 m position error reported as accuracy
        def __init__(s): s.rnd = random.Random(5)
        def locate(s, aps, t):
            from cloud.kinematics import offset_m
            la, lo = offset_m(12.97, 77.59, s.rnd.gauss(0, 30), s.rnd.gauss(0, 30))
            return Fix(t, la, lo, "wifi", 60.0)
    tr = DeviceTracker("j", Jitter(), load_model(C.MODEL_PATH))
    for i in range(14):
        r = tr.on_uplink(encode([{"bssid": "aa:bb:cc:dd:ee:01", "rssi": -50}, {"bssid": "aa:bb:cc:dd:ee:02", "rssi": -60}]), 1000 + 10 * i)
    assert r["alert_level"] == 1, "jitter inside the reported accuracy must not raise a red alert"

def test_notifier_sequence():
    from cloud.notify import Notifier
    import tempfile, os
    d = tempfile.mkdtemp(); sent = []
    n = Notifier("t", "c", 60.0, sender=lambda text, c: sent.append(text) or True,
                 contacts_path=os.path.join(d, "c.json"), log_path=os.path.join(d, "d.jsonl"))
    base = {"device": "d", "lat": 12.9, "lon": 77.5, "accuracy": 30.0, "class": None}
    n.on_result({**base, "t": 1000.0, "alert_level": 1})
    n.on_result({**base, "t": 1010.0, "alert_level": 1})            # too soon: nothing
    n.on_result({**base, "t": 1020.0, "alert_level": 2, "class": "vehicle_kidnap"})
    n.on_result({**base, "t": 1030.0, "alert_level": 2})            # red already sent: nothing
    n.on_result({**base, "t": 1090.0, "alert_level": 2})            # periodic update
    assert [m.split()[1] for m in sent] == ["pressed", "THREAT", "update"], sent

def test_server_message_path():
    import json, os, tempfile
    from cloud import server
    r = build_routers(); rnd = random.Random(1)
    server.LOCATOR, server.MODEL, server.tb = MockLocator(r), load_model(C.MODEL_PATH), None
    server.LOG_PATH = os.path.join(tempfile.mkdtemp(), "r.jsonl")
    class Msg: topic = "sos/w01/uplink"
    import time as _t; clock = [1000.0]; real = _t.time; _t.time = lambda: clock[0]   # server stamps packets with time.time()
    try:
        for i, p in enumerate(trajectory("vehicle")):
            m = Msg(); m.payload = encode(scan(r, p, rnd)).encode()   # hex text, as the firmware publishes it
            server.on_message(None, None, m); clock[0] += 10
    finally:
        _t.time = real
    rows = [json.loads(l) for l in open(server.LOG_PATH)]
    assert len(rows) >= 10 and rows[-1]["device"] == "w01"

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("PASS", n)
