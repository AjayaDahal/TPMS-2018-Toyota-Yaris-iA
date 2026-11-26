#include "pi_power.h"

namespace v2 {

const char* piPowerName(PiPowerState s) {
  switch (s) {
    case PiPowerState::NoAcc: return "no-acc";
    case PiPowerState::WaitStart: return "wait-start";
    case PiPowerState::HotHold: return "hot-hold";
    case PiPowerState::On: return "on";
  }
  return "?";
}

PiPowerSequencer::PiPowerSequencer(const PiPowerConfig& cfg) : cfg_(cfg) {}

void PiPowerSequencer::enter(PiPowerState s, uint32_t now) {
  state_ = s;
  since_ = now;
}

void PiPowerSequencer::update(uint32_t now, uint16_t accMv, bool tempValid, int16_t tempC) {
  if (!accPresent_) {
    if (accMv >= cfg_.accOnMv) {
      accPresent_ = true;
      lowPending_ = runPending_ = false;
      enter(PiPowerState::WaitStart, now);
    }
  } else if (accMv < cfg_.accOffMv) {
    if (!lowPending_) {
      lowPending_ = true;
      lowSince_ = now;
    } else if ((uint32_t)(now - lowSince_) >= cfg_.accLossMs) {
      accPresent_ = false;
      enter(PiPowerState::NoAcc, now);
      return;
    }
  } else {
    lowPending_ = false;
  }

  if (state_ == PiPowerState::WaitStart) {
    bool start = (uint32_t)(now - since_) >= cfg_.accOnlyReleaseMs;
    if (accMv >= cfg_.engineRunMv) {
      if (!runPending_) {
        runPending_ = true;
        runSince_ = now;
      }
      if ((uint32_t)(now - runSince_) >= cfg_.engineRunStableMs) start = true;
    } else {
      runPending_ = false;
    }
    if (start) {
      if (tempValid && tempC >= cfg_.hotHoldC) enter(PiPowerState::HotHold, now);
      else enter(PiPowerState::On, now);
    }
  } else if (state_ == PiPowerState::HotHold) {
    if (!tempValid || tempC <= cfg_.hotReleaseC || (uint32_t)(now - since_) >= cfg_.hotHoldMaxMs) {
      enter(PiPowerState::On, now);
    }
  }
}

}  // namespace v2
