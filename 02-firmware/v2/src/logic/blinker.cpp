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
  return rose;
}

void BlinkerDetector::update(uint32_t now, bool leftLit, bool rightLit) {
  if (!started_) {
    started_ = true;
    left_.rawSince = right_.rawSince = now;
    since_ = now;
  }
  const bool leftRose = filter(left_, leftLit, now);
  const bool rightRose = filter(right_, rightLit, now);

  // Hazard: both sides switched on together.
  const bool wasHazard = hazard_;
  if ((leftRose || rightRose) && left_.everRose && right_.everRose) {
    const uint32_t a = left_.lastRise, b = right_.lastRise;
    if ((a >= b ? a - b : b - a) <= cfg_.hazardWindowMs) hazard_ = true;
  }
  if (!left_.active || !right_.active) hazard_ = false;
  // When the hazards end, the two sides release a few ms apart. Report a single side only after a fresh flash,
  // otherwise the side that releases last would show up as a brief turn (and could trigger a danger beep).
  if (wasHazard && !hazard_) afterHazard_ = true;
  else if (afterHazard_ && (leftRose || rightRose)) afterHazard_ = false;

  // A side that switches on alone might be the first half of a hazard pair: wait for the window first.
  if (leftRose && !right_.active) {
    pending_ = true;
    pendingSince_ = left_.lastRise;
  }
  if (rightRose && !left_.active) {
    pending_ = true;
    pendingSince_ = right_.lastRise;
  }
  if (hazard_ || (pending_ && (uint32_t)(now - pendingSince_) >= cfg_.hazardWindowMs)) pending_ = false;

  Turn next;
  if (hazard_) next = Turn::Hazard;
  else if (afterHazard_) next = Turn::Off;
  else if (pending_) next = state_;
  else if (left_.active && right_.active) next = left_.lastRise >= right_.lastRise ? Turn::Left : Turn::Right;
  else if (left_.active) next = Turn::Left;
  else if (right_.active) next = Turn::Right;
  else next = Turn::Off;

  if (next != state_) {
    if (next != Turn::Off) activation_++;
    state_ = next;
    since_ = now;
  }
}

}  // namespace v2
