#pragma once
// Blind-spot and TPMS alert arbiter: decides what the two amber LEDs and the buzzer do.
//
// Inputs: the turn state (BlinkerDetector), the latest Pi vision report, the vehicle speed (OBD-II dongle and/or
// GPS), the mute button and the TPMS alarm. Rules (each one is a premortem fix, see
// 00-project-management/PREMORTEM_v2.md):
//   - a vehicle in a blind spot lights that side steady; signalling towards it flashes the LED and sounds the
//     buzzer (repeated at most every dangerRepeatMs; a new event needs dangerMinGapMs after the last beep)
//   - nothing below 8 mph and nothing until 12 mph (hysteresis), so parking lots and drive-thrus stay quiet
//   - speed: the car's own (OBD-II PID 0x0D) while it is fresh, else GPS. A dongle that stops answering only
//     hands over to the GPS, so it can make the buzzer quieter, never louder
//   - no fresh speed for longer than gpsHoldMs: LEDs keep working, the buzzer stays quiet (no nuisance without speed)
//   - hazard flashers never sound the buzzer
//   - the mute button silences the buzzer for the current turn activation only; it also acknowledges a TPMS
//     alarm (no more reminders until it clears or another tyre goes low), which works while the Pi is down
//   - a lamp test when the Pi first reports ready; afterwards a stale Pi link or a faulted camera shows the
//     fault pattern and gives one fault beep, so the system never fails silently
#include <cstdint>

#include "blinker.h"

namespace v2 {

enum class LedMode : uint8_t { Off, Steady, Flash, LampTest, Fault };
enum class Beep : uint8_t { None, BsmDanger, Fault, TpmsLow };
enum class SpeedSource : uint8_t { None, Gps, Obd };
const char* ledModeName(LedMode m);
const char* beepName(Beep b);
const char* speedSourceName(SpeedSource s);

struct PiStatus {
  bool ready = false;                  // vision pipeline running with both cameras
  bool occLeft = false, occRight = false;
  bool camFaultLeft = false, camFaultRight = false;  // camera missing, frozen or misaligned
  uint8_t ledLevel = 255;              // LED brightness 0-255 chosen by the Pi (night dimming)
};

struct AlertConfig {
  uint32_t piStaleMs = 1000;
  uint16_t speedOnDmph = 120;          // 12.0 mph
  uint16_t speedOffDmph = 80;          // 8.0 mph
  uint32_t gpsStaleMs = 2000;          // older GPS speed is not "fresh"
  uint32_t obdStaleMs = 1000;          // older OBD speed is not "fresh" (polled at ~5 Hz): the GPS takes over
  uint32_t gpsHoldMs = 10000;          // keep the last moving / slow decision this long without a fresh speed
  uint32_t dangerRepeatMs = 3000;
  uint32_t dangerMinGapMs = 1000;
  uint32_t tpmsRepeatMs = 600000;
  uint32_t lampTestMs = 1000;
};

struct AlertOutput {
  LedMode left = LedMode::Off, right = LedMode::Off;
  uint8_t level = 255;
  Beep beep = Beep::None;              // pattern to start now (edge), None if nothing new
  bool bsmAvailable = false;
  bool dangerLeft = false, dangerRight = false;
  bool speedKnown = false, audioAllowed = false;
  SpeedSource speedSource = SpeedSource::None;  // where the fresh speed comes from right now
  int speedDmph = -1;                  // that speed, -1 = no fresh speed (the moving decision may still be held)
};

class AlertArbiter {
 public:
  explicit AlertArbiter(const AlertConfig& cfg = AlertConfig());

  void piReport(uint32_t nowMs, const PiStatus& status);
  void gpsSpeed(uint32_t nowMs, bool fixValid, uint16_t speedDmph);
  // Vehicle speed from the OBD-II dongle (ELM327, PID 0x0D, see obd.h). valid = false when it stopped answering.
  void obdSpeed(uint32_t nowMs, bool valid, uint16_t speedDmph);
  void mutePressed();
  // lowWheels: bit mask of the low tyres (FL 1, FR 2, RL 4, RR 8). A tyre that wasn't low before re-raises the alarm.
  void tpmsAlarm(bool active, uint8_t lowWheels = 0x1);

  AlertOutput update(uint32_t nowMs, Turn turn, uint32_t turnActivation);

 private:
  AlertConfig cfg_;
  PiStatus pi_;
  bool havePi_ = false;
  uint32_t piMs_ = 0;
  bool everAvailable_ = false, wasAvailable_ = false;
  bool lampTest_ = false;
  uint32_t lampTestStart_ = 0;
  bool faultBeepPending_ = false;
  bool haveGps_ = false, gpsFix_ = false;
  uint32_t gpsMs_ = 0;
  uint16_t gpsSpeed_ = 0;
  bool haveObd_ = false, obdValid_ = false;
  uint32_t obdMs_ = 0;
  uint16_t obdSpeed_ = 0;
  bool moving_ = false, movingKnown_ = false;
  uint32_t movingKnownMs_ = 0;
  bool mutePending_ = false, muted_ = false;
  uint32_t mutedActivation_ = 0;
  bool dangerWas_ = false, everDangerBeep_ = false;
  uint32_t lastDangerBeep_ = 0;
  bool tpmsActive_ = false, tpmsPending_ = false, tpmsAcked_ = false;
  uint8_t tpmsMask_ = 0;
  uint32_t lastTpmsBeep_ = 0;
  uint8_t level_ = 255;
};

}  // namespace v2
