#pragma once
// Turn-signal detector for the two opto-isolated lamp inputs.
//
// The lamp feed blinks (about 0.33 s on / 0.33 s off), may be PWM-driven by the body control module while "on",
// and can pick up short spikes. This turns the two raw inputs into one steady state: off, left, right or hazard.
// Pure logic with no hardware access, so it is unit-tested on a PC (test/host/test_logic.cpp).
#include <cstdint>

namespace v2 {

enum class Turn : uint8_t { Off, Left, Right, Hazard };
const char* turnName(Turn t);

struct BlinkerConfig {
  // Gaps shorter than this inside an "on" phase are bridged (lamps PWM-driven by the BCM at >= 40 Hz).
  uint32_t pwmBridgeMs = 25;
  // The bridged signal must stay on (or off) this long to count. Longer than pwmBridgeMs, so a single spike
  // (which the bridge stretches by pwmBridgeMs) can never pass: a lamp must be lit for more than 25 ms.
  uint32_t debounceMs = 50;
  // Stay active this long after the lamp goes dark, so the off phase (0.33 s at 90/min, 0.5 s at 60/min) does not
  // drop the camera view between flashes.
  uint32_t holdOffMs = 900;
  // Hazard flashers light both sides at the same time; a turn signal never does. Both lamps lit together (after the
  // PWM bridge) for this long means hazard. Keep pwmBridgeMs < hazardOverlapMs <= debounceMs:
  //   - above the bridge, so the bridged tail of the old side meeting the new side's first flash in a quick
  //     left -> right change can't pass (the two lamps would have to be lit together for 25 ms; the stalk passes
  //     through neutral, so they never are);
  //   - at most the debounce, so a lamp joining in the last ms of the other's flash (hazards pressed mid-flash) is
  //     a hazard as soon as it is long enough to count as a flash at all.
  uint32_t hazardOverlapMs = 50;
  // A side that lights is reported only once this long has passed since its lamp edge and the other lamp is dark,
  // so the other side can still join: hazards switched on with up to this much skew, or pressed mid-flash.
  uint32_t hazardWindowMs = 150;
  // A lamp lit without a break for this long isn't flashing: a failed opto, a shorted input, a broken pull-up or a
  // wire that isn't a turn-signal feed (e.g. a combined brake/turn lamp while braking). The side is then treated
  // as dark and reported as an input fault ...
  uint32_t stuckLitMs = 1500;
  // ... until its input has been dark for this long.
  uint32_t stuckClearMs = 2000;
};

class BlinkerDetector {
 public:
  explicit BlinkerDetector(const BlinkerConfig& cfg = BlinkerConfig());

  // Call at 1 kHz with true = lamp lit. A lit pulse must last at least one call interval to be seen: with a
  // low-duty PWM lamp drive, the opto's RC filter has to stretch the pulses (measure the car's lamps on the bench).
  void update(uint32_t nowMs, bool leftLit, bool rightLit);

  Turn state() const { return state_; }
  uint32_t stateSinceMs() const { return since_; }
  // Counts every new left / right / hazard activation, so a "mute" can be limited to the current one.
  uint32_t activation() const { return activation_; }
  // Inputs stuck lit (see stuckLitMs): bit 0 left, bit 1 right. Pass it to AlertArbiter::update.
  uint8_t faultMask() const { return (uint8_t)((left_.fault ? 1 : 0) | (right_.fault ? 2 : 0)); }

 private:
  struct Side {
    bool everLit = false;
    uint32_t lastLitMs = 0;
    bool raw = false;        // bridged level
    uint32_t rawSince = 0;
    bool stable = false;     // debounced level
    bool everRose = false;
    uint32_t lastRise = 0, lastFall = 0;
    bool active = false;     // stable, or within holdOffMs of going dark
    bool fault = false;      // stuck lit
  };
  bool filter(Side& s, bool lit, uint32_t now);  // returns true on a debounced rising edge

  BlinkerConfig cfg_;
  Side left_, right_;
  bool started_ = false;
  bool hazard_ = false;
  bool afterHazard_ = false;
  Turn state_ = Turn::Off;
  uint32_t since_ = 0;
  uint32_t activation_ = 0;
};

}  // namespace v2
