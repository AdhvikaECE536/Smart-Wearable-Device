**To get model.keras from the colab notebook**
```
lstm_real.save("model.keras")
from google.colab import files
files.download("model.keras")
print(lstm_real.input_shape)
import tensorflow as tf; print(tf.__version__)
```

**for the python packages**
```
cd sos
python --version
pip install -r requirements.txt
python -m tools.test_pipeline
```

**after adding model.keras to the sos folder (same level as cloud, README, .env)**
```
python -c "import tensorflow as tf; m=tf.keras.models.load_model('model.keras'); print(m.input_shape)"
```

You want (None, 5, 2). If you get a version error, run pip install tensorflow==<the version Colab printed> and try again.

rerun the pipeline
```
python -m tools.test_pipeline
```

### Part A: Terminal 1 (server)

Open a terminal in VS Code. It must show (run_environment) and end in ...\sos_software_v3_1\sos>.

**A1. Create/Check .env (should be in sos folder)**

```
HIVEMQ_HOST=broker.emqx.io
HIVEMQ_PORT=1883
HIVEMQ_TLS=0
UPLINK_TOPIC=sos/w01-k7f3/uplink
GEO_MODE=mock
MODEL_PATH=model.keras
```

Run:

```
Get-Content .env | Where-Object {$_ -match '^\w+='} | ForEach-Object { $k,$v = $_ -split '=',2; Set-Item "env:$k" $v }
echo $env:UPLINK_TOPIC
```

_If any fixes required:_

In the terminal, move it down one level:
```
move ..\.env .
dir .env
```

dir .env should now list the file. (Moving it from the Explorer also works. Drag .env onto the sos folder.)

Then run the two lines again:
```
Get-Content .env | Where-Object {$_ -match '^\w+='} | ForEach-Object { $k,$v = $_ -split '=',2; Set-Item "env:$k" $v }
echo $env:UPLINK_TOPIC
```

Check: the last line prints sos/w01-k7f3/uplink.


**A2. Make the router list and start the server:**
```
python -c "import json;from cloud.simlib import build_routers;json.dump(build_routers(),open('mock_routers.json','w'))"
python -m cloud.server
```

Check: the terminal shows [mqtt] connected: Success. Leave it running and don’t type in it.


### Part B: Terminal 2 (helper)

Click the + in the terminal panel to open a second terminal. Check the prompt shows (run_environment) and ends in ...\sos>.

**B1. Generate the fake router table:**
```
python -m tools.wokwi_aps --lat 12.9716 --lon 77.5946
```

Copy the whole line that starts with const AP FAKE[3] = {.

### Part C: Wokwi

Fake routers; Replace the existing const AP FAKE[3] = ... line (around line 30) with the line you copied in B1.

### Part D: Telegram

In Telegram, message @BotFather, send /newbot, and copy the token.
Send any message to your new bot from your phone.
Open https://api.telegram.org/bot<TOKEN>/getUpdates in a browser and copy the "chat":{"id": number.
In the dashboard, add yourself as a contact with that chat id.
Add these two lines to .env, then reload .env in the server terminal and restart the server:
```
  TELEGRAM_TOKEN=your-token
  TELEGRAM_CHAT_ID=your-chat-id
```

Tailoring to my work:
```
TELEGRAM_TOKEN=8845634403:AAHR3W1KAHwOnf-sC1PGRzDkN1IRrRiSAJA 
TELEGRAM_CHAT_ID=9132806584
```

Restart the server so it picks them up. In the server terminal:
Press Ctrl+C to stop it.

Reload .env:
```
  Get-Content .env | Where-Object {$_ -match '^\w+='} | ForEach-Object { $k,$v = $_ -split '=',2; Set-Item "env:$k" $v }
```
Run python -m cloud.server and wait for [mqtt] connected: Success.


### Part E: Dashboard

Use a new terminal in sos with the venv active. Keep the server terminal running as it is.

**1. Set a password and start it:**
```
$env:DASH_USER="admin"
$env:DASH_PASS="pick-a-password"
python -m dashboard.app
```
Open http://localhost:5000 and sign in. It must run from the sos folder, so it can find logs/results.jsonl. It uses your existing logs, so the map should already show your earlier packets.

Fill in the contact form:

Name: your name
Phone: your number with country code, for example +91...
Telegram chat id: 9132806584

Leave “also SMS” unticked and click Add contact.

Test it. Click Send test alert. Your phone should get a Telegram message from sos536_bot within a few seconds. The dashboard’s dispatch log should show a green “sent” row for you.


**A valid token here is 46 characters: 10 digits, a colon, and 35 letters or symbols.**

Clean it in this terminal, which removes anything that can’t belong in a token:
```
$env:TELEGRAM_TOKEN = $env:TELEGRAM_TOKEN -replace '[^0-9A-Za-z:_-]',''
$env:TELEGRAM_TOKEN.Length
```
Check: it now prints 46.

**2. Test the token without the app:**
```
Invoke-RestMethod "https://api.telegram.org/bot$env:TELEGRAM_TOKEN/sendMessage?chat_id=9132806584&text=test"
```

Your phone should buzz and the command should print ok True. If it says Unauthorized, the token has a wrong character, so recopy it from BotFather by clicking on the token text.

# LOADER
Get-Content .env | Where-Object {$_ -match '^\w+='} | ForEach-Object { $k,$v = $_ -split '=',2; Set-Item "env:$k" $v.Trim() }
$env:TELEGRAM_TOKEN.Length

### Restart both processes, each in its own terminal:

1. Server: Ctrl+C, run the loader above, then python -m cloud.server. Wait for [mqtt] connected: Success.
2. Dashboard: Ctrl+C, run the loader above, then:
   ```
   $env:DASH_USER="admin"; $env:DASH_PASS="your-password"
   python -m dashboard.app
   ```
3. In the dashboard, click Send test alert. The log should show a green “sent” and your phone should buzz.

### FULL DEMO
``
python -m tools.simulate_device --scenario vehicle --period 10 --device w01-k7f3
```

