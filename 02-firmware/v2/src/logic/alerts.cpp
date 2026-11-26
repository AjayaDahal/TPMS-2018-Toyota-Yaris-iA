#include "alerts.h"

namespace v2 {

const char* ledModeName(LedMode m) {
  switch (m) {
    case LedMode::Off: return "off";
    case LedMode::Steady: return "steady";
    case LedMode::Flash: return "flash";
    case LedMode::LampTest: return "lamp-test";
    case LedMode::Fault: return "fault";
  }
  return "?";
}

const char* beepName(Beep b) {
  switch (b) {
    case Beep::None: return "none";
    case Beep::BsmDanger: return "bsm-danger";
    case Beep::Fault: return "fault";
    case Beep::TpmsLow: return "tpms-low";
  }
  return "?";
}

const char* speedSourceName(SpeedSource s) {
  switch (s) {
    case SpeedSource::None: return "none";
    case SpeedSource::Gps: return "gps";
    case SpeedSource::Obd: return "obd";
  }
  return "?";
}

AlertArbiter::AlertArbiter(const AlertConfig& cfg) : cfg_(cfg) {}

void AlertArbiter::piReport(uint32_t now, const PiStatus& status) {
  pi_ = status;
  piMs_ = now;
  havePi_ = true;
}

void AlertArbiter::gpsSpeed(uint32_t now, bool fixValid, uint16_t speedDmph) {
  haveGps_ = true;
  gpsFix_ = fixValid;
  gpsSpeed_ = speedDmph;
  gpsMs_ = now;
}

void AlertArbiter::obdSpeed(uint32_t now, bool valid, uint16_t speedDmph) {
  haveObd_ = true;
  obdValid_ = valid;
  obdSpeed_ = speedDmph;
  obdMs_ = now;
}

void AlertArbiter::mutePressed() { mutePending_ = true; }

void AlertArbiter::tpmsAlarm(bool active, uint8_t lowWheels) {
  if (active) {
    const bool newWheel = (lowWheels & ~tpmsMask_) != 0;
    if (!tpmsActive_ || newWheel) {
      tpmsPending_ = true;
      tpmsAcked_ = false;
    }
    tpmsMask_ = lowWheels;
  } else {
    tpmsPending_ = false;
    tpmsAcked_ = false;
    tpmsMask_ = 0;
  }
  tpmsActive_ = active;
}

AlertOutput AlertArbiter::update(uint32_t now, Turn turn, uint32_t activation) {
  AlertOutput out;

  // Pi availability: lamp test the first time it is ready, one fault beep whenever it drops out afterwards.
  const bool available = havePi_ && pi_.ready && (uint32_t)(now - piMs_) <= cfg_.piStaleMs;
  if (available) level_ = pi_.ledLevel;
  if (available && !everAvailable_) {
    everAvailable_ = true;
    lampTest_ = true;
    lampTestStart_ = now;
  }
  if (!available && wasAvailable_) faultBeepPending_ = true;
  wasAvailable_ = available;
  if (lampTest_ && (uint32_t)(now - lampTestStart_) >= cfg_.lampTestMs) lampTest_ = false;

  // Speed gate with hysteresis. The car's own speed (OBD) wins while it is fresh: it is exact at walking pace and
  // needs no sky. Otherwise GPS. Hold the last decision through short gaps in both (bridges, tunnels, a dongle
  // reconnecting).
  const bool freshObd = haveObd_ && obdValid_ && (uint32_t)(now - obdMs_) <= cfg_.obdStaleMs;
  const bool freshGps = haveGps_ && gpsFix_ && (uint32_t)(now - gpsMs_) <= cfg_.gpsStaleMs;
  if (freshObd || freshGps) {
    const uint16_t speed = freshObd ? obdSpeed_ : gpsSpeed_;
    if (speed >= cfg_.speedOnDmph) moving_ = true;
    else if (speed < cfg_.speedOffDmph) moving_ = false;
    movingKnown_ = true;
    movingKnownMs_ = now;
    out.speedSource = freshObd ? SpeedSource::Obd : SpeedSource::Gps;
    out.speedDmph = speed;
  } else if (movingKnown_ && (uint32_t)(now - movingKnownMs_) > cfg_.gpsHoldMs) {
    movingKnown_ = false;
    moving_ = false;
  }
  const bool visualAllowed = movingKnown_ ? moving_ : true;
  const bool audioAllowed = movingKnown_ && moving_;

  // Mute lasts for the current turn activation only. It also acknowledges a TPMS alarm; neither needs the Pi.
  if (mutePending_) {
    mutePending_ = false;
    if (turn == Turn::Left || turn == Turn::Right) {
      muted_ = true;
      mutedActivation_ = activation;
    }
    if (tpmsActive_) {
      tpmsAcked_ = true;
      tpmsPending_ = false;
    }
  }
  if (muted_ && (turn == Turn::Off || activation != mutedActivation_)) muted_ = false;

  const bool usableLeft = available && !pi_.camFaultLeft;
  const bool usableRight = available && !pi_.camFaultRight;
  const bool occLeft = usableLeft && pi_.occLeft && visualAllowed;
  const bool occRight = usableRight && pi_.occRight && visualAllowed;
  out.dangerLeft = occLeft && turn == Turn::Left;
  out.dangerRight = occRight && turn == Turn::Right;

  auto mode = [&](bool usable, bool occupied, bool danger) {
    if (lampTest_) return LedMode::LampTest;
    if (everAvailable_ && !usable) return LedMode::Fault;
    if (danger) return LedMode::Flash;
    if (occupied) return LedMode::Steady;
    return LedMode::Off;
  };
  out.left = mode(usableLeft, occLeft, out.dangerLeft);
  out.right = mode(usableRight, occRight, out.dangerRight);

  // Buzzer, highest priority first: blind-spot danger, fault, TPMS.
  const bool danger = out.dangerLeft || out.dangerRight;
  if (danger && audioAllowed && !muted_) {
    const uint32_t since = now - lastDangerBeep_;
    const bool due = !everDangerBeep_ || since >= (dangerWas_ ? cfg_.dangerRepeatMs : cfg_.dangerMinGapMs);
    if (due) {
      out.beep = Beep::BsmDanger;
      lastDangerBeep_ = now;
      everDangerBeep_ = true;
    }
  }
  dangerWas_ = danger;
  if (out.beep == Beep::None && faultBeepPending_) {
    out.beep = Beep::Fault;
    faultBeepPending_ = false;
  }
  if (tpmsActive_ && !tpmsAcked_ && !tpmsPending_ && (uint32_t)(now - lastTpmsBeep_) >= cfg_.tpmsRepeatMs) {
    tpmsPending_ = true;
  }
  if (out.beep == Beep::None && tpmsPending_) {
    out.beep = Beep::TpmsLow;
    tpmsPending_ = false;
    lastTpmsBeep_ = now;
  }

  out.level = level_;
  out.bsmAvailable = available;
  out.speedKnown = movingKnown_;
  out.audioAllowed = audioAllowed;
  return out;
}

}  // namespace v2
