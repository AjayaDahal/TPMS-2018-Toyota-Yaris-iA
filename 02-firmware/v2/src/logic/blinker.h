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
  // (which the bridge stretches by pwmBridgeMs) can never pass.
  uint32_t debounceMs = 50;
  // Stay active this long after the lamp goes dark, so the off phase (0.33 s at 90/min, 0.5 s at 60/min) does not
  // drop the camera view between flashes.
  uint32_t holdOffMs = 900;
  // Left and right switching on within this window means hazard flashers. A single side is reported only after
  // this window has passed without the other side, so hazards never show up as a brief left or right turn.
  uint32_t hazardWindowMs = 150;
};

class BlinkerDetector {
 public:
  explicit BlinkerDetector(const BlinkerConfig& cfg = BlinkerConfig());

  // Call at 1 kHz (at least 4x the lamp PWM frequency) with true = lamp lit.
  void update(uint32_t nowMs, bool leftLit, bool rightLit);

  Turn state() const { return state_; }
  uint32_t stateSinceMs() const { return since_; }
  // Counts every new left / right / hazard activation, so a "mute" can be limited to the current one.
  uint32_t activation() const { return activation_; }

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
  };
  bool filter(Side& s, bool lit, uint32_t now);  // returns true on a debounced rising edge

  BlinkerConfig cfg_;
  Side left_, right_;
  bool started_ = false;
  bool hazard_ = false;
  bool afterHazard_ = false;
  bool pending_ = false;
  uint32_t pendingSince_ = 0;
  Turn state_ = Turn::Off;
  uint32_t since_ = 0;
  uint32_t activation_ = 0;
};

}  // namespace v2
