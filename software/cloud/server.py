"""Run:  python -m cloud.server     (reads env vars, see .env.example)"""
import os
import secrets
import json, os, ssl, threading, time
import paho.mqtt.client as mqtt
from . import config as C
from .engine import DeviceTracker
from .geo import UnwiredLocator, MockLocator
from .payload import decode
from .threat import load_model
from .notify import Notifier

LOCK, TRACKERS = threading.Lock(), {}
LOG_PATH = os.environ.get("RESULT_LOG", "logs/results.jsonl")

def make_locator():
    if C.GEO_MODE == "mock":
        return MockLocator.from_file(C.MOCK_ROUTERS)
    if not C.UNWIRED_TOKEN:
        raise SystemExit("UNWIRED_TOKEN not set (or use GEO_MODE=mock)")
    return UnwiredLocator(C.UNWIRED_TOKEN, C.UNWIRED_URL)

LOCATOR, MODEL = None, None
tb = None
NOTIFY = Notifier(C.TELEGRAM_TOKEN, C.TELEGRAM_CHAT_ID, C.NOTIFY_UPDATE_S)

def publish_result(res):
    os.makedirs(os.path.dirname(LOG_PATH) or ".", exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(res) + "\n")
    print("[result]", {k: (round(v, 5) if isinstance(v, float) else v) for k, v in res.items()})
    if NOTIFY is not None:
        NOTIFY.on_result(res)
    if tb is not None:
        tele = {"latitude": res["lat"], "longitude": res["lon"], "speed": res["speed"],
                "accel": res["accel"], "threat_class": res["class"], "threat_prob": res["prob"],
                "alert_level": res["alert_level"], "sos_alert": 1 if res["alert_level"] == 2 else 0,
                "sos_pressed": res["sos"], "gated": int(res["gated"]), "fix_source": res["src"], "accuracy_m": res["accuracy"]}
        tele = {k: v for k, v in tele.items() if v is not None}
        tb.publish("v1/devices/me/telemetry", json.dumps(tele), qos=1)

def on_connect(client, userdata, flags, rc, props=None):
    print("[mqtt] connected:", rc)
    client.subscribe(C.UPLINK_TOPIC, qos=1)

def on_message(client, userdata, msg):
    device = msg.topic.split("/")[1] if msg.topic.count("/") >= 2 else "device"
    try:
        decode(msg.payload)  # validate early
    except Exception as e:
        print("[mqtt] bad payload on", msg.topic, e)
        return
    with LOCK:
        tr = TRACKERS.setdefault(device, DeviceTracker(device, LOCATOR, MODEL))
        res = tr.on_uplink(msg.payload, time.time())
    if res:
        publish_result(res)

def watchdog():
    while True:
        time.sleep(3)
        with LOCK:
            outs = [r for r in (t.tick(time.time()) for t in TRACKERS.values()) if r]
        for r in outs:
            publish_result(r)

def main():
    global LOCATOR, MODEL, tb
    LOCATOR, MODEL = make_locator(), load_model(C.MODEL_PATH, C.SCALER_PATH)
    if C.TB_TOKEN:
        tb = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sos-server-tb")
        tb.username_pw_set(C.TB_TOKEN)
        tb.connect(C.TB_HOST, C.TB_PORT, 60)
        tb.loop_start()
    else:
        print("[tb] TB_TOKEN not set -> dashboard publishing disabled")
    threading.Thread(target=watchdog, daemon=True).start()
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=os.environ.get("MQTT_CLIENT_ID") or "sos-server-" + secrets.token_hex(3))
    if C.HIVEMQ_USER:
        c.username_pw_set(C.HIVEMQ_USER, C.HIVEMQ_PASS)
    if C.HIVEMQ_TLS:
        c.tls_set(cert_reqs=ssl.CERT_REQUIRED)
    elif "+" in C.UPLINK_TOPIC or "#" in C.UPLINK_TOPIC:
        print("[mqtt] WARNING: plain broker + wildcard topic: anyone can inject packets. Set UPLINK_TOPIC to your exact device topic.")
    c.on_connect, c.on_message = on_connect, on_message
    c.connect(C.HIVEMQ_HOST, C.HIVEMQ_PORT, 60)
    c.loop_forever()

if __name__ == "__main__":
    main()
