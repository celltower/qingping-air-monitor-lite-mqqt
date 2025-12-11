# Qingping Air Monitor - Home Assistant Integration v4.0.0

## Kompletter Projektkontext für Weiterarbeit

---

## 📋 Projektübersicht

**Was ist das?**
Eine Home Assistant Custom Integration für den **Qingping Air Monitor Lite (CGDN1)** - ein Luftqualitätssensor der Temperatur, Luftfeuchtigkeit, CO2, PM2.5 und PM10 misst.

**Besonderheit:**
- **One-Click Setup** - Nutzer gibt nur Qingping Login + MQTT Broker an
- Integration erstellt automatisch die MQTT-Konfiguration im Qingping Developer Portal
- Bindet Geräte automatisch an den eigenen MQTT Broker
- Kein manuelles Setup im Developer Portal mehr nötig!

**GitHub Repo:** `https://github.com/celltower/qingping-air-monitor-lite-mqqt`

---

## 🏗️ Architektur

### Dateistruktur (HACS-konform)
```
qingping-air-monitor-lite-mqqt/
├── .github/workflows/
│   ├── hacs.yml              # HACS Validation Action
│   └── release.yml           # Auto-Release bei Tags
├── custom_components/
│   └── qingping_monitor/
│       ├── __init__.py       # Integration Setup
│       ├── manifest.json     # HA Manifest
│       ├── const.py          # Konstanten
│       ├── sensor.py         # Sensor-Entities + MQTT Handler
│       ├── number.py         # Number-Entities (Intervalle etc.)
│       ├── switch.py         # Switch-Entities (Toggles)
│       ├── select.py         # Select-Entities (Dropdowns)
│       ├── text.py           # Text-Entities
│       ├── config_flow.py    # Setup-Wizard UI
│       ├── developer_api.py  # Qingping Developer Portal API
│       ├── api.py            # Qingping Cloud API (OAuth)
│       ├── watchdog.py       # Connection Monitoring
│       ├── strings.json      # UI Strings
│       └── translations/
│           ├── en.json
│           └── de.json
├── images/
│   ├── logo.png              # 256x256 Logo
│   └── icon.png              # 128x128 Icon
├── hacs.json                 # HACS Config
├── LICENSE                   # MIT
└── README.md                 # Dokumentation
```

---

## 🔑 Wichtige APIs

### 1. Qingping Developer Portal API (Intern/Reverse-Engineered)
**Base URL:** `https://developer.cleargrass.com`

Diese API ist NICHT offiziell dokumentiert, wurde durch Browser DevTools reverse-engineered.

#### Login
```
POST /account/login
Content-Type: application/x-www-form-urlencoded

Body: account={email}&password={password}&cid=&country_code=86

Response:
{
  "code": 0,
  "data": {
    "token": "eyJ...",      # JWT, ~30 Tage gültig
    "qing_user_id": 446123,
    "display_name": "..."
  }
}
```

#### MQTT Config erstellen
```
POST /v1/private/config
Authorization: Bearer {token}
Content-Type: application/json

Body:
{
  "name": "Home Assistant",
  "product": {"code": "CGDN1"},
  "networkConfig": {
    "type": 1,
    "mqttConfig": {
      "host": "192.168.1.100",
      "port": 1883,
      "username": "mqtt_user",
      "password": "mqtt_pass",
      "clientId": "qingping-{mac}",
      "topicUp": "qingping/{mac}/up",
      "topicDown": "qingping/{mac}/down"
    }
  },
  "reportConfig": {
    "reportInterval": 1,
    "collectInterval": 1
  }
}

Response: {"code": 200, "data": {"id": 3567}}
```

#### Geräte abrufen
```
GET /v1/private/devices?hadPrivate=false&productCode=CGDN1
Authorization: Bearer {token}

# hadPrivate=false → Ungebundene Geräte
# hadPrivate=true  → Bereits gebundene Geräte

Response:
{
  "code": 200,
  "data": {
    "devices": [
      {
        "mac": "CCB5D131534A",
        "product": {"code": "CGDN1", "en_name": "Qingping Air Monitor Lite"},
        "privateConfig": {"id": 3567, "name": "Mainmode"}  # nur bei hadPrivate=true
      }
    ]
  }
}
```

#### Gerät an Config binden
```
PUT /v1/private/devices
Authorization: Bearer {token}
Content-Type: application/json

Body: {"macList": ["CCB5D131534A"], "privateConfigId": 3567}

Response: {"code": 200}
```

#### Gerät entbinden
```
DELETE /v1/private/devices
Authorization: Bearer {token}
Content-Type: application/json

Body: {"macList": ["CCB5D131534A"]}

Response: {"code": 200}
```

### 2. Qingping Cloud API (Offiziell)
**Base URL:** `https://apis.cleargrass.com`
**OAuth URL:** `https://oauth.cleargrass.com`

Wird für Watchdog/Recovery verwendet - kann Geräte-Settings pushen.

```
POST /oauth2/token
grant_type=client_credentials&client_id={app_key}&client_secret={app_secret}

GET /v1/apis/devices
Authorization: Bearer {access_token}

PUT /v1/apis/devices/settings
```

---

## 📡 MQTT Protokoll

### Topics
```
Up (Gerät → Server):   qingping/{MAC}/up
Down (Server → Gerät): qingping/{MAC}/down
```

### Message Types

| Type | Name | Richtung | Beschreibung |
|------|------|----------|--------------|
| 10 | Heartbeat | Up | Gerät ist online |
| 12 | Realtime Data | Up | Aktuelle Sensordaten |
| 13 | Status | Up | Gerätestatus |
| 17 | History Data | Up | Gepufferte Daten |
| 18 | ACK | Down | **Server MUSS antworten!** |
| 28 | Settings | Both | Konfiguration |

### Type 12/17 - Sensordaten
```json
{
  "type": "12",
  "id": 1234,
  "mac": "CCB5D131534A",
  "need_ack": 1,
  "sensorData": [{
    "temperature": {"value": 23.5},
    "humidity": {"value": 45.2},
    "co2": {"value": 650},
    "pm25": {"value": 12},
    "pm10": {"value": 18}
  }]
}
```

### Type 18 - ACK (KRITISCH!)
```json
{
  "type": "18",
  "ack_id": 1234,
  "code": 0,
  "timestamp": 1736493637,
  "desc": ""
}
```

**WICHTIG:** Wenn der Server keine ACK sendet, denkt das Gerät der Server ist offline und sendet dieselben Daten erneut. Nach längerer Zeit ohne ACK "vergisst" das Gerät die MQTT-Verbindung!

---

## 🔧 Wichtige Code-Stellen

### sensor.py - ACK Handler
```python
# In _on_state() Callback:
if msg_type in ("12", "17"):
    # Process sensor data...
    
    # Send ACK if requested
    if data.get("need_ack") == 1:
        msg_id = data.get("id")
        if msg_id:
            hass.async_create_task(_send_ack(msg_id))

async def _send_ack(msg_id: int) -> None:
    ack_payload = {
        "type": "18",
        "ack_id": msg_id,
        "code": 0,
        "timestamp": int(time.time()),
        "desc": ""
    }
    await mqtt.async_publish(hass, down_topic, json.dumps(ack_payload))
```

### config_flow.py - Auto-Setup Flow
```
Step 1: user          → Methode wählen (Auto/Scan/Manual)
Step 2: qingping_login → Email + Password
Step 3: mqtt_config    → MQTT Broker Details
        → Lädt automatisch existierende Cloud-Config
        → Füllt Formular mit Cloud-Werten vor
        → Bei Änderungen: Update der Cloud-Config
Step 4: discover_cloud_devices → Geräte von Cloud holen
Step 5: no_devices    → Falls leer: Rescan/Switch zu MQTT/Manual
Step 6: select_devices → Auswählen welche zu installieren
        → _provision_devices() → Config nutzen/updaten + Geräte binden
```

### developer_api.py - Wichtige Methoden
```python
login(email, password)           # Login → JWT Token
get_configs()                    # Existierende MQTT Configs
create_mqtt_config(...)          # Neue Config erstellen
get_devices(has_private, code)   # Geräte abrufen
bind_device_to_config(mac, id)   # Gerät binden
unbind_device(mac)               # Gerät entbinden
rebind_device(mac, config_id)    # Unbind + Bind (forciert Resync)
find_or_create_config(...)       # Sucht existierende oder erstellt neue
auto_provision_devices(...)      # Kompletter Auto-Flow
```

---

## 🐕 Watchdog System

**Problem:** Geräte stoppen nach ~2 Wochen wenn MQTT Broker kurz offline war.

**Lösung:**
1. **Keep-Alive:** Alle 5 Min Config an Gerät publishen
2. **Monitoring:** Prüft alle 5 Min ob Daten kommen
3. **Warning:** Nach 10 Min ohne Daten → HA Notification
4. **Critical:** Nach 30 Min → Cloud API triggert Resync

```python
# watchdog.py
class QingpingWatchdog:
    WARNING_THRESHOLD = 600   # 10 min
    CRITICAL_THRESHOLD = 1800 # 30 min
    CHECK_INTERVAL = 300      # 5 min
```

---

## 📊 Entities

### Sensors (sensor.py)
- Temperature, Humidity, CO2, PM2.5, PM10, Battery
- WiFi Signal, SSID, Firmware
- Last Update Timestamp

### Configuration (28 Entities)
| Typ | Entities |
|-----|----------|
| Number | report_interval, collect_interval, display_off_delay, night_start/end, temp_offset, co2_offset, pm25_offset, led_min/max für CO2/PM25 |
| Switch | night_mode_enabled, night_mode_auto, display_always_on, temp_unit_fahrenheit |
| Select | display_show (temp/humidity/co2/pm25/pm10) |
| Text | device_name |

---

## 🚨 Bekannte Probleme & Fixes

### Problem: Gerät sendet nach 2 Wochen nicht mehr
**Ursache:** Keine Type 18 ACK gesendet
**Fix:** v4.0.0 sendet jetzt ACK für alle Type 12/17 Messages

### Problem: Integration taucht nicht in HA auf
**Ursache:** HA Neustart vergessen nach HACS Install
**Fix:** Entwicklertools → Neustart

### Problem: Login failed
**Ursache:** Falsche Credentials oder API-Änderung
**Debug:** Logs prüfen unter `custom_components.qingping_monitor`

---

## 🔄 Release Workflow

1. Code ändern in `custom_components/qingping_monitor/`
2. Version in `manifest.json` erhöhen
3. Commit + Push
4. Tag erstellen: `git tag v4.0.1 && git push --tags`
5. GitHub Action erstellt automatisch Release
6. HACS zeigt Update an

---

## 🎯 v4.1.0 Updates (Dezember 2024)

### ✅ Reload-Funktionalität
- Integration kann jetzt neu geladen werden ohne HA Neustart!
- Bei Optionsänderungen lädt sich die Integration automatisch neu
- Manuelle Reload über UI: Einstellungen → Geräte & Dienste → ⋮ → Neu laden
- **WICHTIG:** Nach HACS Update ist EINMAL ein HA-Neustart nötig (Python Module Cache)

### ✅ Intelligenter Config Management (Auto-Sync)
- **Automatisches Laden**: Lädt existierende Cloud-Config beim Setup und füllt Formular vor
- **Smart Update**: 
  - Werte unverändert → Nutzt existierende Config
  - Werte geändert → Aktualisiert Cloud-Config automatisch
  - Keine Config vorhanden → Erstellt neue Config
- **Transparenz**: Zeigt an woher die Werte kommen (Cloud Config 'Mainmode' oder HA MQTT)
- **Zero-Duplikate**: Verhindert unnötige Config-Duplikate im Developer Portal

### ✅ Verbesserter Auto-Setup Flow
- **Rescan-Option**: Wenn keine Geräte gefunden werden, kann man neu scannen oder zur MQTT/manuellen Eingabe wechseln
- **Pre-filled Values**: MQTT-Werte werden aus existierender Cloud-Config oder HA MQTT Integration geladen
- **Seamless Experience**: Kein extra Dialog-Step mehr - alles in einem Flow

### Config Flow Struktur (v4.1.0)
```
Step 1: user                    → Methode wählen
Step 2: qingping_login         → Login
Step 3: mqtt_config            → 🆕 MQTT Details (auto-filled from cloud!)
                                  ├─ Lädt existierende Cloud-Config
                                  ├─ Füllt Formular vor
                                  └─ Bei Änderung: Auto-Update der Cloud-Config
Step 4: discover_cloud_devices → Geräte abrufen
Step 5: no_devices            → 🆕 Mit Rescan-Optionen
Step 6: select_devices        → Geräte auswählen
```

## 📝 TODO / Future Ideas

- [ ] Multiple Devices in einem Entry (aktuell 1 Entry pro Device)
- [ ] Bluetooth BLE Support (Gerät kann auch BLE)
- [ ] History/Statistik-Daten abrufen
- [ ] Automatischer Token-Refresh (JWT läuft nach 30 Tagen ab)
- [ ] Diagnostics für besseres Debugging

---

## 🧪 Testing

### Manuell testen
```bash
# MQTT Messages beobachten
mosquitto_sub -h localhost -u user -P pass -t "qingping/#" -v

# Config an Gerät senden
mosquitto_pub -h localhost -u user -P pass -t "qingping/CCB5D131534A/down" \
  -m '{"type":"17","timestamp":1234567890}'
```

### HA Logs
```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.qingping_monitor: debug
```

---

## 📞 Kontakt / Support

- GitHub Issues: https://github.com/celltower/qingping-air-monitor-lite-mqqt/issues
- HACS: Custom Repository

---

*Zuletzt aktualisiert: Dezember 2024*
*Version: 4.1.0*