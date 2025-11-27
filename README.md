<p align="center">
  <img src="docs/logo.png" alt="Qingping Air Monitor Lite" width="200"/>
</p>

<h1 align="center">Qingping Air Monitor</h1>

<p align="center">
  <strong>Home Assistant integration for Qingping Air Monitor Lite via MQTT</strong>
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Custom"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/version-3.2.4-green.svg" alt="Version">
  <img src="https://img.shields.io/badge/HA-2024.1+-blue.svg" alt="HA Version">
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-installation">Installation</a> •
  <a href="#-device-setup">Device Setup</a> •
  <a href="#-entities">Entities</a> •
  <a href="#-troubleshooting">Troubleshooting</a>
</p>

---

## ✨ Features

| | |
|---|---|
| 🌡️ **Environmental Monitoring** | Temperature, Humidity, CO2, PM2.5, PM10, Battery |
| 📡 **100% Local** | MQTT-based, no cloud dependency after setup |
| ⚙️ **Full Device Control** | 28 settings configurable from Home Assistant |
| 🔍 **Auto-Discovery** | Automatic device detection via MQTT |
| 🌐 **Multi-Language** | English & German included |

---

## 📦 Installation

### HACS (Recommended)

1. Open **HACS** → **Integrations** → ⋮ → **Custom repositories**
2. Add this repository URL, select **Integration**
3. Search "Qingping Monitor" → **Install**
4. **Restart Home Assistant**

### Manual

```bash
# Download and extract to config/custom_components/
config/
└── custom_components/
    └── qingping_monitor/
        ├── __init__.py
        ├── sensor.py
        └── ...
```

Restart Home Assistant after installation.

---

## 🔧 Device Setup

> ⚠️ **Important:** Before adding the integration, you must configure your Qingping device for MQTT via the Developer Portal. This is a one-time setup.

### Prerequisites

- ✅ Qingping Air Monitor Lite
- ✅ Qingping+ App (iOS/Android) with device paired
- ✅ MQTT Broker (e.g., Mosquitto)
- ✅ Qingping Developer Account

### Quick Overview

```
1. Create Developer Account    →  developer.qingping.co
2. Create MQTT Configuration   →  Enter your broker details
3. Bind Device to Config       →  Link your device to MQTT
4. Wait 1-2 minutes           →  Device syncs with cloud
5. Add HA Integration          →  Auto-discovery or manual MAC
```

### Step-by-Step Guide

<details>
<summary>📖 <strong>Click to expand full setup instructions</strong></summary>

#### Step 1: MQTT Broker

Make sure you have an MQTT broker running. Example for Mosquitto:

```bash
# Create MQTT user
mosquitto_passwd -c /etc/mosquitto/passwd qingping_user
```

#### Step 2: Developer Account

1. Go to **https://developer.qingping.co**
2. Create an account

> ⚠️ **Use the same email as your Qingping+ App account!**

#### Step 3: Create MQTT Configuration

1. Go to **https://developer.qingping.co/private/access-configuration**
2. Click **"Add Configuration"**
3. Fill in:

| Field | Value |
|-------|-------|
| Name | `home-assistant` (any name) |
| Device Model | `Qingping Air Monitor Lite` |
| Private Type | `Self-built MQTT` |
| Host | Your MQTT broker IP |
| Port | `1883` |
| User Name | Your MQTT username |
| Password | Your MQTT password |
| Client ID | `qingping-{mac}` |
| Up Topic | `qingping/{mac}/up` |
| Down Topic | `qingping/{mac}/down` |
| Interval of Uploading | `1 minute` |
| Interval of Recording | `1 minute` |

4. Click **"Test"** to verify connection
5. Click **"Confirm"** to save

#### Step 4: Bind Device

1. Go to **https://developer.qingping.co/private/device-binding**
2. Click **"Add Device"**
3. Select **Qingping Air Monitor Lite**
4. Select your device from the list
5. Select the MQTT config from Step 3
6. Click **"Confirm"**

> 💡 Device not showing? Open Qingping+ App and re-add/refresh the device.

#### Step 5: Wait for Sync

The device receives the MQTT config on next cloud sync (~1-2 minutes).

Verify data is flowing in MQTT Explorer:
```
Topic: qingping/{MAC}/up
```

</details>

📖 **Detailed guides:** [English](docs/SETUP_EN.md) | [Deutsch](docs/SETUP_DE.md)

---

## 🏠 Add Integration

Once your device is sending MQTT data:

1. **Settings** → **Devices & Services** → **Add Integration**
2. Search **"Qingping Monitor"**
3. Choose **Auto-Scan** (recommended) or enter MAC manually
4. Done! 🎉

---

## 📊 Entities

### Sensors

| Entity | Description | Unit |
|--------|-------------|------|
| 🌡️ Temperature | Current temperature | °C/°F |
| 💧 Humidity | Relative humidity | % |
| 💨 CO2 | Carbon dioxide | ppm |
| 🌫️ PM2.5 | Fine particles | µg/m³ |
| 🌫️ PM10 | Coarse particles | µg/m³ |
| 🔋 Battery | Battery level | % |

### Diagnostics

WiFi Signal • Firmware Version • Last Update • Availability Status

### ⚙️ Configuration (28 Settings)

<details>
<summary><strong>Click to expand all settings</strong></summary>

**Intervals**
- Report/Collect/PM Sampling Interval (30-3600s)

**Display**
- Display Off Time, Auto Slide Time
- Screensaver Type, Night Mode

**Calibration**
- Temperature/Humidity/CO2/PM Offset & Zoom

**LED Thresholds**
- Custom thresholds for all sensors

**Other**
- Temperature Unit, 12/24h Mode, PM Standard, Timezone

</details>

---

## 🎨 Dashboard Example

```yaml
type: entities
title: 🌿 Air Quality
entities:
  - entity: sensor.qingping_air_monitor_temperature
  - entity: sensor.qingping_air_monitor_humidity  
  - entity: sensor.qingping_air_monitor_co2
  - entity: sensor.qingping_air_monitor_pm25
  - entity: sensor.qingping_air_monitor_battery
```

---

## 🐛 Troubleshooting

<details>
<summary><strong>Device not sending data?</strong></summary>

- Verify MQTT config at developer.qingping.co
- Check that device is bound to the config
- Wait 1-2 minutes for cloud sync
- Check MQTT broker for incoming messages
</details>

<details>
<summary><strong>Device not discovered?</strong></summary>

- Verify data arrives at `qingping/{MAC}/up`
- MAC must be uppercase without colons
- Use manual MAC entry as fallback
</details>

<details>
<summary><strong>Settings not saving?</strong></summary>

- Settings publish to `qingping/{MAC}/down`
- Device responds with Type 18 ACK
- Check HA logs for confirmation
</details>

<details>
<summary><strong>Factory Reset (last resort)</strong></summary>

If device stops working:
1. Press and hold power button for 10 seconds
2. While holding, also press the touch bar on top
3. Keep holding until device resets
4. Re-add in Qingping+ App
5. Re-bind MQTT config in Developer Portal
</details>

---

## 🤝 Contributing

Contributions welcome! Fork → Branch → Commit → Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  Made with ❤️ for the Home Assistant community
</p>
