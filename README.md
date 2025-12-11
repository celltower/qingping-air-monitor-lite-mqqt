# 🌿 Qingping Air Monitor for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/celltower/qingping-air-monitor-lite-mqqt)](https://github.com/celltower/qingping-air-monitor-lite-mqqt/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**The ultimate Home Assistant integration for Qingping Air Monitor Lite (CGDN1)**

<p align="center">
  <img src="https://raw.githubusercontent.com/celltower/qingping-air-monitor-lite-mqqt/main/images/logo.png" width="200">
</p>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🚀 **One-Click Setup** | Enter Qingping credentials → Done! |
| 🌡️ **All Sensors** | Temperature, Humidity, CO2, PM2.5, PM10, Battery |
| ⚙️ **28 Settings** | Full device control from Home Assistant |
| 🐕 **Watchdog** | Alerts when devices go offline |
| 🔄 **Keep-Alive** | Prevents connection drops |
| ✅ **Type 18 ACK** | Proper MQTT protocol compliance |
| 🌐 **Bilingual** | English & German |

---

## 🚀 One-Click Setup

No more manual MQTT configuration on the Qingping Developer Portal!

```
You provide:              Integration does automatically:
┌────────────────────┐    ┌─────────────────────────────────┐
│ • Qingping Email   │    │ ✅ Login to Qingping Cloud      │
│ • Qingping Password│ →  │ ✅ Create MQTT configuration    │
│ • MQTT Broker IP   │    │ ✅ Find all your devices        │
│ • MQTT Credentials │    │ ✅ Bind devices to your broker  │
└────────────────────┘    │ ✅ Auto-discover in HA          │
                          │ ✅ Create all entities          │
                          └─────────────────────────────────┘
```

---

## 📦 Installation

### HACS (Recommended)

1. Open **HACS** → **Integrations**
2. Click the **⋮** menu → **Custom repositories**
3. Add: `https://github.com/celltower/qingping-air-monitor-lite-mqqt`
4. Select category: **Integration**
5. Click **Add**
6. Search for "Qingping Air Monitor" → **Download**
7. **Restart Home Assistant**

### Manual Installation

1. Download the [latest release](https://github.com/celltower/qingping-air-monitor-lite-mqqt/releases)
2. Extract `custom_components/qingping_monitor` to your HA `config/custom_components/`
3. Restart Home Assistant

---

## 🔧 Setup

### Prerequisites

1. ✅ Device paired in **Qingping+** or **Qingping IoT** app
2. ✅ **MQTT Broker** running (e.g., Mosquitto add-on)
3. ✅ **MQTT Integration** configured in Home Assistant

### Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **"Qingping Air Monitor"**
3. Choose **"🚀 Automatic Setup"** (recommended)
4. Enter your **Qingping account** credentials
5. Enter your **MQTT broker** details
6. Select devices to set up
7. **Done!** Data arrives within 1-2 minutes

### Alternative Setup Methods

- **🔍 Scan MQTT** - For devices already sending to your broker
- **✏️ Manual** - Enter MAC address directly

---

## 📊 Entities

### Sensors
| Entity | Description | Unit |
|--------|-------------|------|
| 🌡️ Temperature | Current temperature | °C |
| 💧 Humidity | Relative humidity | % |
| 💨 CO2 | Carbon dioxide | ppm |
| 🌫️ PM2.5 | Fine particles | µg/m³ |
| 🌫️ PM10 | Coarse particles | µg/m³ |
| 🔋 Battery | Battery level | % |

### Diagnostics
- WiFi Signal Strength
- WiFi SSID
- Firmware Version
- Last Update Timestamp

### Configuration (28 Settings)
- Report/Collect Intervals
- Display Settings (Brightness, Auto-Off)
- Night Mode (Schedule, Brightness)
- Temperature Unit & Offset
- CO2/PM2.5 Calibration
- LED Thresholds
- And more...

---

## 🐕 Watchdog

The integration monitors device connectivity:

| State | Trigger | Action |
|-------|---------|--------|
| ⚠️ Warning | 10 min without data | HA notification |
| 🚨 Critical | 30 min without data | Detailed notification + Cloud re-sync |
| ✅ Recovered | Data received | Notification dismissed |

**Keep-Alive**: Sends config to device every 5 minutes to prevent timeouts.

---

## 🔧 Troubleshooting

### Login failed?
- Use the same credentials as in the Qingping+ app
- Check your email address is correct

### No devices found?
- Ensure device is paired in Qingping+ app first
- Device must be online and connected to WiFi

### Device not sending data?
- Wait 1-2 minutes after setup for cloud sync
- Check MQTT broker is accessible from device's network
- Try power cycling the device

### Device stopped after some time?
- This is usually fixed by the Type 18 ACK feature in v4.0.0
- The watchdog will alert you and attempt recovery

---

## 📝 Changelog

### v4.0.0
- 🚀 **One-Click Setup** - Automatic device provisioning via Qingping Developer API
- ✅ **Type 18 ACK** - Proper MQTT protocol acknowledgment (fixes devices stopping)
- 🐕 **Watchdog** - Connection monitoring with alerts
- 🔄 **Keep-Alive** - Prevents connection timeouts
- 🔗 **Rebind Support** - Re-provision devices with new MQTT config

### v3.x
- 28 configuration entities
- Bilingual support (EN/DE)
- MQTT auto-discovery

---

## 🤝 Contributing

Contributions are welcome! Please open an issue or PR.

---

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

<p align="center">
  Made with ❤️ for the Home Assistant community
</p>
