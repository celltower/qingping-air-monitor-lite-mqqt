# ============================================================
# QINGPING AIR MONITOR LITE - TYPE 28 SETTINGS
# ============================================================
# Diese Settings können über MQTT konfiguriert werden!
# Normalerweise nur über die Qingping+ App zugänglich.
# ============================================================

## EXAMPLE MESSAGE (received from device):

```json
{
    "type": "28",
    "id": 73,
    "setting": {
        "temperature_unit": "C",
        "report_interval": 150,
        "collect_interval": 150,
        "pm_sampling_interval": 150,
        "power_off_time": 60,
        "night_mode_start_time": 0,
        "night_mode_end_time": 0,
        "display_off_time": 600,
        "auto_slideing_time": 120,
        "timezone": 10,
        "screensaver_type": 0,
        "is_12_hour_mode": 0,
        "pm25_standard": 1,
        "need_ack": 1,
        "co2_asc": 1,
        "co2_offset": 0,
        "co2_zoom": 0,
        "pm25_offset": 0,
        "pm25_zoom": 0,
        "pm10_offset": 0,
        "pm10_zoom": 0,
        "pm25_calib_mode": 0,
        "temperature_offset": 0,
        "temperature_zoom": 0,
        "humidity_offset": 0,
        "humidity_zoom": 0,
        "page_sequence": "pm25,pm10,co2,temp,pm25",
        "temp_led_th": "2300,2650,2800",
        "humi_led_th": "2000,4000,6000",
        "co2_led_th": "1000,2000,3000",
        "pm25_led_th": "35,75,115,150,250",
        "pm10_led_th": "50,150,250,350,450"
    }
}
```

---

## SETTINGS DOCUMENTATION

### BASIC INTERVALS

| Setting | Value | Description |
|---------|-------|-------------|
| `report_interval` | 150 | Sekunden - wie oft Daten via MQTT gesendet werden |
| `collect_interval` | 150 | Sekunden - wie oft Sensoren messen |
| `pm_sampling_interval` | 150 | Sekunden - PM Sensor Messinterval |

### TEMPERATURE

| Setting | Value | Description |
|---------|-------|-------------|
| `temperature_unit` | "C" | "C" = Celsius, "F" = Fahrenheit |

### POWER & DISPLAY

| Setting | Value | Description |
|---------|-------|-------------|
| `power_off_time` | 60 | Sekunden bis Auto-Off? (0 = nie?) |
| `display_off_time` | 600 | Sekunden bis Display aus (600 = 10 min) |
| `auto_slideing_time` | 120 | Sekunden zwischen Seiten-Wechsel (120 = 2 min) |
| `screensaver_type` | 0 | Screensaver Typ (0 = aus?) |

### NIGHT MODE

| Setting | Value | Description |
|---------|-------|-------------|
| `night_mode_start_time` | 0 | Startzeit (0 = deaktiviert?) |
| `night_mode_end_time` | 0 | Endzeit (Format unklar: HHMM? Minuten?) |

### TIME & FORMAT

| Setting | Value | Description |
|---------|-------|-------------|
| `timezone` | 10 | Zeitzone Offset (10 = UTC+1 Berlin?) |
| `is_12_hour_mode` | 0 | 0 = 24h Format, 1 = 12h AM/PM |

### DISPLAY PAGES

| Setting | Value | Description |
|---------|-------|-------------|
| `page_sequence` | "pm25,pm10,co2,temp,pm25" | Reihenfolge der Anzeige-Seiten |

Mögliche Seiten: `pm25`, `pm10`, `co2`, `temp`, `humi`, `tvoc` ?

### PM2.5 STANDARD

| Setting | Value | Description |
|---------|-------|-------------|
| `pm25_standard` | 1 | Grenzwert-Standard: 0=China? 1=US EPA? 2=EU? |

### SENSOR CALIBRATION - OFFSETS

| Setting | Value | Description |
|---------|-------|-------------|
| `co2_offset` | 0 | CO2 Offset (addiert zum Messwert) |
| `pm25_offset` | 0 | PM2.5 Offset |
| `pm10_offset` | 0 | PM10 Offset |
| `temperature_offset` | 0 | Temperatur Offset |
| `humidity_offset` | 0 | Luftfeuchtigkeit Offset |

### SENSOR CALIBRATION - ZOOM/SCALE

| Setting | Value | Description |
|---------|-------|-------------|
| `co2_zoom` | 0 | CO2 Skalierung (Multiplikator?) |
| `pm25_zoom` | 0 | PM2.5 Skalierung |
| `pm10_zoom` | 0 | PM10 Skalierung |
| `temperature_zoom` | 0 | Temperatur Skalierung |
| `humidity_zoom` | 0 | Luftfeuchtigkeit Skalierung |

### CO2 CALIBRATION

| Setting | Value | Description |
|---------|-------|-------------|
| `co2_asc` | 1 | Auto Self-Calibration: 1=AN, 0=AUS |
| `pm25_calib_mode` | 0 | PM2.5 Kalibrierungsmodus |

### LED THRESHOLDS

| Setting | Value | Description |
|---------|-------|-------------|
| `temp_led_th` | "2300,2650,2800" | Temperatur (x100): 23.0°C, 26.5°C, 28.0°C |
| `humi_led_th` | "2000,4000,6000" | Luftfeuchtigkeit (x100): 20%, 40%, 60% |
| `co2_led_th` | "1000,2000,3000" | CO2 in ppm |
| `pm25_led_th` | "35,75,115,150,250" | PM2.5 in µg/m³ (5 Stufen) |
| `pm10_led_th` | "50,150,250,350,450" | PM10 in µg/m³ (5 Stufen) |

#### LED Colors (vermutlich):
- **Grün**: Unter erstem Wert
- **Gelb**: Zwischen 1. und 2. Wert
- **Orange**: Zwischen 2. und 3. Wert
- **Rot**: Zwischen 3. und 4. Wert
- **Dunkelrot**: Über 4./5. Wert

---

## SENDING SETTINGS TO DEVICE

Um Settings zu ändern, sende **Type 17** an DOWN Topic:

**Topic:** `qingping/{MAC}/down`

### Beispiel - Report Interval ändern:
```json
{
    "type": "17",
    "id": 1,
    "need_ack": 1,
    "setting": {
        "report_interval": 60,
        "collect_interval": 60
    }
}
```

### Beispiel - Display Timeout ändern:
```json
{
    "type": "17",
    "id": 2,
    "need_ack": 1,
    "setting": {
        "display_off_time": 300
    }
}
```

### Beispiel - LED Thresholds ändern:
```json
{
    "type": "17",
    "id": 3,
    "need_ack": 1,
    "setting": {
        "co2_led_th": "800,1200,2000"
    }
}
```

### Beispiel - Temperatur auf Fahrenheit:
```json
{
    "type": "17",
    "id": 4,
    "need_ack": 1,
    "setting": {
        "temperature_unit": "F"
    }
}
```

---

## POSSIBLE FUTURE HOME ASSISTANT CONTROLS

Mit diesen Settings könnten wir UI Controls erstellen:

### Display Settings
- Display Timeout (Slider: 0-3600 sec)
- Auto-Slide Time (Slider: 30-600 sec)
- 12h/24h Mode (Switch)
- Temperature Unit C/F (Switch)
- Screensaver Type (Select)

### Night Mode
- Start Time (Time Picker)
- End Time (Time Picker)

### Sensor Calibration
- CO2 Offset (Number: -500 to +500)
- Temperature Offset (Number: -10 to +10)
- Humidity Offset (Number: -20 to +20)
- CO2 Auto-Calibration (Switch)

### LED Thresholds
- CO2 Warning Levels (3 Numbers)
- PM2.5 Warning Levels (5 Numbers)
- Temperature Warning Levels (3 Numbers)

### Page Order
- Custom page sequence (Text/Select)

---

## QUESTIONS TO INVESTIGATE

- [ ] Was ist der genaue Format für night_mode_start/end_time?
- [ ] Was bedeuten die zoom Werte genau? Prozent? Multiplikator?
- [ ] Welche screensaver_type Werte gibt es? (0, 1, 2...?)
- [ ] Welche Seiten gibt es für page_sequence?
- [ ] Was ist pm25_standard genau? (China=0, US=1, EU=2?)
- [ ] Kann man alle Settings einzeln senden oder müssen alle zusammen?
- [ ] Gibt es ein Type um Settings abzufragen (Request)?

---

## MESSAGE TYPES SUMMARY

| Type | Direction | Description |
|------|-----------|-------------|
| 10 | UP | Heartbeat |
| 12 | UP | Sensor Data (current) |
| 13 | UP | Device Status (network/firmware) |
| 17 | DOWN | **Send Settings to Device** |
| 17 | UP | Buffered Sensor Data |
| 18 | UP | Config ACK |
| 28 | UP | **All Device Settings** |
