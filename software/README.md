# SOS wearable: software side

## Run order
1. Offline check (no accounts, no network): `pip install -r requirements.txt` then `python -m tools.test_pipeline` and `python -m tools.demo_offline`
2. Put your Colab model in `model.keras` (or run `python -m tools.make_dummy_model` for a stand-in) and re-run step 1. Without a model file the server falls back to a speed-threshold rule, and prints that it did.
3. Copy `.env.example` to `.env`, fill HiveMQ/Unwired/ThingsBoard values, `set -a; source .env; set +a`, then `python -m cloud.server`
4. Without hardware: `GEO_MODE=mock python -m cloud.server` in one terminal, `python -m tools.simulate_device --scenario vehicle --period 1` in another (it writes mock_routers.json first, start the server after the simulator has created it).
5. Wokwi: new ESP32-S3 project, paste `firmware/wokwi/*` (sketch.ino, diagram.json, libraries.txt), set the HiveMQ host/user/pass at the top, press the red button.

## HiveMQ Cloud
Create a free Serverless cluster, add credentials (Access Management), note the host. Topic: `sos/<device_id>/uplink`, payload: 42-char hex string.

## ThingsBoard
1. Devices, add device "wearable-01", copy its access token into TB_TOKEN (TB_HOST: demo.thingsboard.io, or thingsboard.cloud, or your own docker install).
2. Dashboard, add widget, Maps, "OpenStreetMap" (or Route map), datasource = that device, keys latitude / longitude. In the marker settings use a colour function such as `return data['sos_alert'] == 1 ? 'red' : 'orange';`
3. Add a "Value card" or "Entities table" showing alert_level, threat_class, speed.
4. Flashing red alert: Profiles, Device profiles, your profile, Alarm rules, add rule "SOS_CONFIRMED", severity Critical, create condition `sos_alert > 0`, clear condition `sos_alert == 0`. Then add an "Alarms table" widget filtered to the device. (Menu names move between ThingsBoard versions; the telemetry keys are what matter.)

## What the server publishes (ThingsBoard keys)
latitude, longitude, speed, accel, threat_class, threat_prob, alert_level (1 = SOS pressed, 2 = threat confirmed by 2 consecutive LSTM windows), sos_alert (1 only when alert_level is 2), fix_source (wifi / wifi-cache / dead-reckoning / hold), accuracy_m. Every result is also appended to logs/results.jsonl for your report metrics.

## Before you trust the numbers
- CLASS_NAMES order in cloud/config.py must match the label order in your notebook.
- If the notebook scaled features (StandardScaler), save mean/std to scaler.json as {"mean":[..],"std":[..]} and set SCALER_PATH.
- Model with 2 inputs uses (speed, accel); with 3 uses (speed, accel, heading delta). It adapts to model.input_shape.

## Added in v2 (after review)
- `cloud/notify.py`: Telegram alerts to contacts. Create a bot with @BotFather, message it once, put TELEGRAM_TOKEN and TELEGRAM_CHAT_ID in `.env` (chat id: open https://api.telegram.org/bot<TOKEN>/getUpdates after messaging the bot). Sends: SOS pressed (first fix), threat confirmed, update every 60 s.
- Accuracy gate (`ACC_GATE`, default 1.5): a threat class is ignored when the path over the window is shorter than 1.5 x the worst reported position error. Stops Wi-Fi jitter looking like running. Set 0 to disable.
- `CLASS_NAMES`, `SMOOTH`, `LATCH` now settable from `.env`.
- Tests: `python -m tools.test_pipeline` (9 tests, all offline).

## Known limits (state these in the report)
- Never tested against real HiveMQ, Unwired Labs, ThingsBoard, Telegram or Wokwi from the build sandbox: run steps 3-5 yourself and fix credentials.
- Wokwi firmware sends fixed fake BSSIDs, so it proves button -> payload -> MQTT only. Motion scenarios come from `tools.simulate_device`.
- The LSTM here is a dummy until you drop in your Colab `model.keras`.
- Wi-Fi-scan time under 400 ms is not verifiable in Wokwi; measure on hardware.

## Dashboard (v3): login, contacts, live map, 112 card
```
DASH_USER=admin DASH_PASS=choose-a-password python -m dashboard.app      # http://localhost:5000
```
Run it in a third terminal next to `cloud.server`. It reads `logs/results.jsonl` and shares `data/contacts.json` with the notifier,
so contacts you add in the browser are alerted by the server on the next SOS. Contacts get Telegram (needs their chat id) and/or Twilio SMS
(`TWILIO_SID`, `TWILIO_TOKEN`, `TWILIO_FROM`; trial accounts only reach verified numbers).
112 is pinned and manual only: the system never auto-dials emergency services; the dashboard shows a call button and a ready message.
Tests: `python -m tools.test_dashboard`. Single admin account; keep it on localhost unless you put HTTPS in front.

## v4 changes
- Plain MQTT supported for public test brokers: `HIVEMQ_HOST=broker.emqx.io HIVEMQ_PORT=1883 HIVEMQ_TLS=0` (user/pass optional).
  On a public broker set `UPLINK_TOPIC` to your exact topic (e.g. `sos/w01-k7f3/uplink`), never the `sos/+/uplink` wildcard,
  and use the same device id in the sketch. Public brokers let anyone read or inject packets: demo data only.
- Acceleration now defaults to speed change per step (`ACC_PER_STEP=1`) to match the Colab `np.diff`. If your notebook divides by dt, set `ACC_PER_STEP=0`.
- `python -m tools.wokwi_aps --lat 12.9716 --lon 77.5946` prints a FAKE[] table for the sketch whose BSSIDs exist in the mock DB,
  so Wokwi packets resolve to a real map position when the server runs with `GEO_MODE=mock`.
- Verified here through a real local broker: simulator -> server -> LSTM -> red alert (vehicle, 12 packets).
