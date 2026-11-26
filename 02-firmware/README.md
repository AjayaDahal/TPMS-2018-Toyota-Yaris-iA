# 02 — Firmware (TPMS Monitor Panel)

- [bringup/README.md](bringup/README.md) — PlatformIO ESP32 bring-up self-test and 315 MHz GM/Schrader EG53MA4 TPMS receiver decoder (v1 panel; the v2 board reuses the same radio pins and decoder)
- [v2/README.md](v2/README.md) — v2 ESP32 safety logic (blinker detector, Pi power sequencing, blind-spot/TPMS alert arbiter, ESP32 ↔ Pi protocol, ELM327 client for the car's speed from your OBD-II dongle), audited pin map and 120 host unit tests
