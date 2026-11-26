#pragma once
// Start-up sequencing of the Raspberry Pi 5 V rail on the ACC-only (P1) power design.
//
// Hardware: the Pi regulator is ON by default whenever ACC is present (after an RC delay of ~1.5 s); the ESP32 can
// only hold it off through PI_INHIBIT. This logic decides how long to hold it off:
//   - not while the key is passing through ACC on its way to START (the crank would brown the Pi out mid-boot),
//   - start as soon as the engine runs (alternator voltage), or after accOnlyReleaseMs in ACC without the engine,
//   - optionally wait for a hot car to cool a little (board temperature), but never longer than hotHoldMaxMs.
// Every hold has a deadline, so a bad sensor or reading can delay the Pi but never keep it off for the whole drive.
#include <cstdint>

namespace v2 {

enum class PiPowerState : uint8_t { NoAcc, WaitStart, HotHold, On };
const char* piPowerName(PiPowerState s);

struct PiPowerConfig {
  uint16_t accOnMv = 9000;            // ACC counts as present above this ...
  uint16_t accOffMv = 7500;           // ... and as lost below this (hysteresis)
  uint32_t accLossMs = 200;           // ACC must stay low this long to count as lost (contact bounce, short dips)
  uint16_t engineRunMv = 13000;       // alternator charging: engine running (calibrate for the wiring drop)
  uint32_t engineRunStableMs = 1000;  // ... for this long
  uint32_t accOnlyReleaseMs = 15000;  // key in ACC/ON without the engine: start the Pi after this anyway
  int16_t hotHoldC = 60;              // board at or above this when starting: wait ...
  int16_t hotReleaseC = 55;           // ... until it is at or below this ...
  uint32_t hotHoldMaxMs = 600000;     // ... but at most 10 minutes
};

class PiPowerSequencer {
 public:
  explicit PiPowerSequencer(const PiPowerConfig& cfg = PiPowerConfig());

  // accMv: ACC voltage at the board. tempValid = false when no temperature sensor is fitted or it fails.
  void update(uint32_t nowMs, uint16_t accMv, bool tempValid, int16_t tempC);

  bool inhibit() const { return state_ != PiPowerState::On; }
  PiPowerState state() const { return state_; }
  uint32_t stateSinceMs() const { return since_; }

 private:
  void enter(PiPowerState s, uint32_t now);

  PiPowerConfig cfg_;
  PiPowerState state_ = PiPowerState::NoAcc;
  uint32_t since_ = 0;
  bool accPresent_ = false;
  bool lowPending_ = false;
  uint32_t lowSince_ = 0;
  bool runPending_ = false;
  uint32_t runSince_ = 0;
};

}  // namespace v2
