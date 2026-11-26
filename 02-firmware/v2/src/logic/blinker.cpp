#include "blinker.h"

namespace v2 {

const char* turnName(Turn t) {
  switch (t) {
    case Turn::Off: return "off";
    case Turn::Left: return "left";
    case Turn::Right: return "right";
    case Turn::Hazard: return "hazard";
  }
  return "?";
}

BlinkerDetector::BlinkerDetector(const BlinkerConfig& cfg) : cfg_(cfg) {}

namespace {
// The later of two millis() timestamps, correct across the 49.7-day wrap.
uint32_t later(uint32_t a, uint32_t b) { return (int32_t)(a - b) >= 0 ? a : b; }
}  // namespace

bool BlinkerDetector::filter(Side& s, bool lit, uint32_t now) {
  if (lit) {
    s.lastLitMs = now;
    s.everLit = true;
  }
  const bool bridged = lit || (s.everLit && (uint32_t)(now - s.lastLitMs) < cfg_.pwmBridgeMs);
  if (bridged != s.raw) {
    s.raw = bridged;
    s.rawSince = now;
  }
  bool rose = false;
  if (s.raw != s.stable && (uint32_t)(now - s.rawSince) >= cfg_.debounceMs) {
    s.stable = s.raw;
    if (s.stable) {
      s.lastRise = s.rawSince;   // edge time, so both sides are compared at the same point
      s.everRose = true;
      rose = true;
    } else {
      s.lastFall = s.rawSince;
    }
  }
  s.active = s.stable || (s.everRose && (uint32_t)(now - s.lastFall) < cfg_.holdOffMs);
  // A lamp that never goes dark isn't flashing (see stuckLitMs).
  if (!s.fault && s.raw && (uint32_t)(now - s.rawSince) >= cfg_.stuckLitMs) s.fault = true;
  else if (s.fault && !s.raw && (uint32_t)(now - s.rawSince) >= cfg_.stuckClearMs) s.fault = false;
  return rose && !s.fault;
}

void BlinkerDetector::update(uint32_t now, bool leftLit, bool rightLit) {
  if (!started_) {
    started_ = true;
    left_.rawSince = right_.rawSince = now;
    since_ = now;
  }
  const bool leftRose = filter(left_, leftLit, now);
  const bool rightRose = filter(right_, rightLit, now);
  // A faulted (stuck) input counts as dark.
  const bool leftLitNow = left_.raw && !left_.fault, rightLitNow = right_.raw && !right_.fault;
  const bool leftActive = left_.active && !left_.fault, rightActive = right_.active && !right_.fault;

  // Hazard: both lamps lit at the same time for hazardOverlapMs. A turn signal never lights both sides.
  const bool wasHazard = hazard_;
  if (leftLitNow && rightLitNow &&
      (uint32_t)(now - later(left_.rawSince, right_.rawSince)) >= cfg_.hazardOverlapMs) {
    hazard_ = true;
  }
  if (!leftActive || !rightActive) hazard_ = false;
  // When the hazards end, the two sides release a few ms apart. Report a single side only after a fresh flash,
  // otherwise the side that releases last would show up as a brief turn (and could trigger a danger beep).
  if (wasHazard && !hazard_) afterHazard_ = true;
  else if (afterHazard_ && (leftRose || rightRose)) afterHazard_ = false;

  Turn next;
  if (hazard_) {
    next = Turn::Hazard;
  } else if (afterHazard_) {
    next = Turn::Off;
  } else {
    // The side that lit most recently. It is reported only once the other side had its chance to join: the hazard
    // window after its lamp edge, and not while the other lamp is lit (lit mid-flash, or the tail of a quick
    // change). Until then the previous state holds, so hazards never show up as a brief turn to either side.
    Turn candidate = Turn::Off;
    if (leftActive && rightActive) {
      candidate = (int32_t)(left_.lastRise - right_.lastRise) >= 0 ? Turn::Left : Turn::Right;
    } else if (leftActive) {
      candidate = Turn::Left;
    } else if (rightActive) {
      candidate = Turn::Right;
    }
    bool settled = true;
    if (candidate == Turn::Left) {
      settled = (uint32_t)(now - left_.lastRise) >= cfg_.hazardWindowMs && !rightLitNow;
    } else if (candidate == Turn::Right) {
      settled = (uint32_t)(now - right_.lastRise) >= cfg_.hazardWindowMs && !leftLitNow;
    }
    next = settled ? candidate : state_;
  }

  if (next != state_) {
    if (next != Turn::Off) activation_++;
    state_ = next;
    since_ = now;
  }
}

}  // namespace v2
