#pragma once
// Blind-spot and TPMS alert arbiter: decides what the two amber LEDs and the buzzer do.
//
// Inputs: the turn state and input faults (BlinkerDetector), the latest Pi vision report, whether the Pi is powered
// (PiPowerSequencer), the vehicle speed (OBD-II dongle and/or GPS), the mute button and the TPMS alarm. Rules (each
// one is a premortem or audit fix, see 00-project-management/PREMORTEM_v2.md and 05-Audit-Subsystems/):
//   - a vehicle in a blind spot lights that side steady; signalling towards it flashes the LED and sounds the
//     buzzer (repeated at most every dangerRepeatMs; a new event needs dangerMinGapMs after the last beep)
//   - nothing below 8 mph and nothing until 12 mph (hysteresis), so parking lots and drive-thrus stay quiet
//   - speed: the car's own (OBD-II PID 0x0D) while it is fresh, else GPS. A dongle that stops answering hands over
//     to the GPS, which then decides (inside the 8-12 mph hysteresis band the two can disagree)
//   - no fresh speed for longer than gpsHoldMs: LEDs keep working, the buzzer stays quiet (no nuisance without speed)
//   - hazard flashers never sound the buzzer; nor does signalling while a blinker input is faulted (a stuck input
//     makes hazards and turns indistinguishable), and that side shows the fault pattern
//   - the mute button silences the buzzer for the current turn activation only; it also acknowledges a TPMS
//     alarm (no more reminders until it clears or another tyre goes low), which works while the Pi is down
//   - a lamp test when the Pi first reports ready. A stale or frozen Pi link, a faulted camera, a faulted blinker
//     input, or a Pi powered for piBootTimeoutMs that never became ready shows the fault pattern on that side and
//     gives one fault beep. Another fault beep only after faultRearmMs without any fault, so a flapping link
//     doesn't nag. The system never fails silently
//   - buzzer priority: danger, then fault, then TPMS. A pattern plays for its full length; only a higher priority
//     cuts it, and the cut pattern is played again afterwards
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
  bool ready = false;                  // vision pipeline running (each camera's health is in camFault*)
  bool occLeft = false, occRight = false;
  bool camFaultLeft = false, camFaultRight = false;  // camera missing, frozen or misaligned
  uint8_t ledLevel = 255;              // LED brightness 0-255 chosen by the Pi (night dimming), floored at minLedLevel
};

struct AlertConfig {
  uint32_t piStaleMs = 1000;           // a report older than this, or a frame counter that hasn't moved, is stale
  uint32_t piBootTimeoutMs = 90000;    // Pi powered this long and never ready: fault
  uint16_t speedOnDmph = 120;          // 12.0 mph
  uint16_t speedOffDmph = 80;          // 8.0 mph
  uint32_t gpsStaleMs = 2000;          // older GPS speed is not "fresh"
  uint32_t obdStaleMs = 1000;          // older OBD speed is not "fresh" (polled at ~5 Hz): the GPS takes over
  uint32_t gpsHoldMs = 10000;          // keep the last moving / slow decision this long without a fresh speed
  uint32_t dangerRepeatMs = 3000;
  uint32_t dangerMinGapMs = 1000;
  uint32_t faultRearmMs = 30000;       // no fault for this long before another fault beep
  uint32_t tpmsRepeatMs = 600000;
  uint32_t tpmsClearHoldMs = 60000;    // an alarm that clears and comes back within this is the same alarm
  uint32_t lampTestMs = 1000;
  uint32_t dangerBeepMs = 400;         // pattern lengths: the buzzer player must play each one for exactly this long
  uint32_t faultBeepMs = 600;
  uint32_t tpmsBeepMs = 800;
  uint8_t minLedLevel = 48;            // LED level floor, so a flash or a fault is never invisible
};

struct AlertOutput {
  LedMode left = LedMode::Off, right = LedMode::Off;
  uint8_t level = 255;
  Beep beep = Beep::None;              // pattern to start now (edge), None if nothing new
  uint32_t beepMs = 0;                 // its length
  bool bsmAvailable = false;
  bool dangerLeft = false, dangerRight = false;
  bool speedKnown = false, audioAllowed = false;
  SpeedSource speedSource = SpeedSource::None;  // where the fresh speed comes from right now
  int speedDmph = -1;                  // that speed, -1 = no fresh speed (the moving decision may still be held)
};

class AlertArbiter {
 public:
  explicit AlertArbiter(const AlertConfig& cfg = AlertConfig());

  // A $BSM report. seq is the Pi's vision frame counter (not a message counter): a report whose seq hasn't moved
  // doesn't count as fresh, so a frozen vision loop whose reporting thread still says "ready" shows as a fault.
  void piReport(uint32_t nowMs, uint32_t seq, const PiStatus& status);
  // Whether the Pi's 5 V rail is on (PiPowerSequencer not inhibiting). Starts the boot timeout.
  void piPower(uint32_t nowMs, bool on);
  void gpsSpeed(uint32_t nowMs, bool fixValid, uint16_t speedDmph);
  // Vehicle speed from the OBD-II dongle (ELM327, PID 0x0D, see obd.h). valid = false when it stopped answering.
  void obdSpeed(uint32_t nowMs, bool valid, uint16_t speedDmph);
  void mutePressed();
  // lowWheels: bit mask of the low tyres (FL 1, FR 2, RL 4, RR 8). A tyre that wasn't low before in this alarm
  // re-raises it once. Apply per-wheel hysteresis in the caller; flapping is also limited here (tpmsClearHoldMs).
  void tpmsAlarm(bool active, uint8_t lowWheels = 0x1);

  // blinkerFault: BlinkerDetector::faultMask() (bit 0 left, bit 1 right).
  AlertOutput update(uint32_t nowMs, Turn turn, uint32_t turnActivation, uint8_t blinkerFault = 0);

 private:
  void startBeep(AlertOutput& out, Beep b, uint32_t ms, uint32_t now);

  AlertConfig cfg_;
  PiStatus pi_;
  bool havePi_ = false;
  uint32_t piMs_ = 0, piSeq_ = 0;
  bool piPowered_ = false;
  uint32_t piPoweredMs_ = 0;
  bool everAvailable_ = false;
  bool lampTest_ = false;
  uint32_t lampTestStart_ = 0;
  uint8_t faultsWas_ = 0;
  bool everFaultBeep_ = false, faultRearmed_ = false, faultBeepPending_ = false;
  uint32_t healthySince_ = 0;
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
  Beep playing_ = Beep::None;
  uint32_t playingUntil_ = 0;
  bool tpmsReq_ = false, tpmsReqActive_ = false;
  uint8_t tpmsReqMask_ = 0;
  bool tpmsActive_ = false, tpmsEverActive_ = false, tpmsPending_ = false, tpmsAcked_ = false;
  uint8_t tpmsSeen_ = 0;
  uint32_t tpmsClearMs_ = 0, lastTpmsBeep_ = 0;
  uint8_t level_ = 255;
};

}  // namespace v2
