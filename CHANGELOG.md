# Changelog

All notable changes to this project will be documented in this file.

## [3.2.4] - 2024-11-27

### Fixed
- **Critical**: LastUpdateSensor returning string instead of datetime object
- Discovery now shows already configured devices in logs
- Improved debug logging during device scan

### Changed
- Discovery scan time increased to 10 seconds for reliability
- Better error messages during setup

## [3.2.0] - 2024-11-27

### Fixed
- Settings no longer overwrite device values with defaults
- Each setting change now sends only that specific setting (not all)
- Connectivity status reliability improved

### Changed
- Config entities show "unavailable" until device sends Type 28
- Periodic refresh reduced from 1 min to 5 min (less traffic)

## [3.1.0] - 2024-11-27

### Added
- Complete settings panel with 28 configuration entities
- Type 28 device settings discovery and display
- Full device control from Home Assistant

### Fixed
- Screensaver options mapping corrected

## [3.0.0] - 2024-11-27

### Added
- Configurable update intervals (30s - 3600s)
- Auto-discovery of Qingping devices via MQTT
- Bilingual documentation (English/German)

## [2.0.0] - 2024-11-26

### Added
- Initial MQTT integration
- Basic sensor support (Temperature, Humidity, CO2, PM2.5, PM10)
- Battery and WiFi diagnostics

---

The format is based on [Keep a Changelog](https://keepachangelog.com/).
