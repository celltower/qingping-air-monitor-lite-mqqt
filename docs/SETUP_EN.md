# Qingping Air Monitor Lite - MQTT Setup

## Requirements
- Qingping Air Monitor Lite
- MQTT Broker (e.g. Mosquitto)
- Qingping+ App (iOS/Android)

---

## Step 1: Prepare MQTT Broker

Create a user in Mosquitto:

```bash
mosquitto_passwd -c /etc/mosquitto/passwd qingping_user
```

---

## Step 2: Qingping Developer Account

1. Create account: **https://developer.qingping.co**
   
   ⚠️ **Important:** Use the same email as your Qingping+ App account!

---

## Step 3: Create MQTT Config

1. Go to: **https://developer.qingping.co/private/access-configuration**
2. Click **"Add Configuration"**
3. Settings:

| Field | Value |
|-------|-------|
| Name | `airmonitor` (or any name) |
| Device Model | `Qingping Air Monitor Lite` |
| Private Type | `Self-built MQTT` |
| Host | Your MQTT Broker IP |
| Port | `1883` |
| User Name | Your MQTT user |
| Password | Your MQTT password |
| Client ID | `qingping-{mac}` |
| Up Topic | `qingping/{mac}/up` |
| Down Topic | `qingping/{mac}/down` |
| **Interval of Uploading** | `1 minute` ⚠️ |
| **Interval of Recording** | `1 minute` ⚠️ |

4. Click **"Test"** → then **"Confirm"**

![MQTT Config](mqtt_config.png)

---

## Step 4: Bind Device

1. Go to: **https://developer.qingping.co/private/device-binding**
2. Click **"Add Device"**
3. Select **"Qingping Air Monitor Lite"**
4. Select your device from the list
5. Select the config from Step 3
6. **Confirm**

### Device not visible?

→ Open Qingping+ App → Re-add/bind device

---

## Step 5: Wait

The device receives the MQTT config on next cloud sync.  
**Takes about 1-2 minutes.**

After that, data appears in MQTT Explorer at:
```
qingping/{MAC}/up
```

---

## Done! 🎉

Now you can add the Home Assistant integration.

---

## Factory Reset (if needed)

If device stops sending sensor data:

1. **Press and hold** power button for **10 seconds**
2. **While holding power**, also hold the **touch bar** on top
3. Keep holding until device resets
4. Re-add in Qingping+ app, then re-bind MQTT config
