# Change Log

## v0.3.1
 * implementation of feature request #10: config options of initial states

## v0.3.0
 * Feature update: moved image snapshot-timer, -counter and
   video timer settings from config.json to HASS integration
 * Feature update: time elapse video creation based on
   a set of snapshot images or video speed factor
 * new record status entity
 * MQTT hass discovery code re-design (new class MQTTClient )
 * more stable handling of MQTT broker connection / disconnection problems

## v0.2.5
 * TLS bugfix of issue #9

## v0.2.4
 * bugfix without TLS of issue #9

## v0.2.3

### Changed
 * MQTT publish fixes
 * client MQTT HA available fix
 * check json config design update

## v0.2.2

### Changed
 * min/max pan type bugfix

## v0.2.1

### Added
 * consider tilt/pan flip due to camera hflip/vflip

### Changed
 * thread & events reworked
 * pan auto None ref bugfix
 * to min/max pan angle
 * to high/low tilt angle

## v0.2.0

### Added
 * general tilt support
 * Waveshare's Pan-Tilt Hat
 * Waveshare's lightsensor

### Changed
 * pan redesign

## v0.1.1

### Added
 * pan cam support

### Changed
 * clean up ThreadEvents
 * addition wait time during motion detection
 * motion enable switch dependencies changed (child app must not be active)

## v0.1.0 first release
