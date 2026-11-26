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

void AlertArbiter::piReport(uint32_t now, uint32_t seq, const PiStatus& status) {
  // The touch screen's mute counter: a change is one press. After a gap (a restarted Pi counts from 0 again) the
  // first report only learns it. Any line counts here, so the mute works even with a frozen vision loop.
  if (havePi_ && (uint32_t)(now - piLineMs_) <= cfg_.piStaleMs && status.mutes != pi_.mutes) mutePressed();
  // Only a moving frame counter refreshes the link: a frozen vision loop goes stale like a silent one.
  if (!havePi_ || seq != piSeq_) piMs_ = now;
  piLineMs_ = now;
  piSeq_ = seq;
  pi_ = status;
  havePi_ = true;
}

void AlertArbiter::piPower(uint32_t now, bool on) {
  if (on && !piPowered_) piPoweredMs_ = now;
  piPowered_ = on;
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
  // Applied in update(), which knows the time (see tpmsClearHoldMs).
  tpmsReq_ = true;
  tpmsReqActive_ = active;
  tpmsReqMask_ = lowWheels;
}

void AlertArbiter::startBeep(AlertOutput& out, Beep b, uint32_t ms, uint32_t now) {
  // Only a higher priority gets here while a pattern plays; the pattern it cuts is played again afterwards.
  if (playing_ == Beep::Fault) faultBeepPending_ = true;
  else if (playing_ == Beep::TpmsLow) tpmsPending_ = true;
  playing_ = b;
  playingUntil_ = now + ms;
  out.beep = b;
  out.beepMs = ms;
}

AlertOutput AlertArbiter::update(uint32_t now, Turn turn, uint32_t activation, uint8_t blinkerFault) {
  AlertOutput out;

  // TPMS alarm changes. A tyre not seen low before in this alarm re-raises it; an alarm that clears and comes back
  // within tpmsClearHoldMs is the same alarm (a tyre hovering at the threshold doesn't beep at every crossing).
  if (tpmsReq_) {
    tpmsReq_ = false;
    if (tpmsReqActive_) {
      const bool newAlarm =
          !tpmsActive_ && (!tpmsEverActive_ || (uint32_t)(now - tpmsClearMs_) >= cfg_.tpmsClearHoldMs);
      if (newAlarm) tpmsSeen_ = 0;
      if (newAlarm || (tpmsReqMask_ & ~tpmsSeen_) != 0) {
        tpmsPending_ = true;
        tpmsAcked_ = false;
        tpmsRemindersLeft_ = cfg_.tpmsReminders;
      }
      tpmsSeen_ |= tpmsReqMask_;
      tpmsActive_ = tpmsEverActive_ = true;
    } else if (tpmsActive_) {
      tpmsActive_ = false;
      tpmsPending_ = false;
      tpmsClearMs_ = now;
    }
  }

  // Pi availability: lamp test the first time it is ready.
  const bool available = havePi_ && pi_.ready && (uint32_t)(now - piMs_) <= cfg_.piStaleMs;
  if (available) level_ = pi_.ledLevel;
  if (available && !everAvailable_) {
    everAvailable_ = true;
    lampTest_ = true;
    lampTestStart_ = now;
  }
  if (lampTest_ && (uint32_t)(now - lampTestStart_) >= cfg_.lampTestMs) lampTest_ = false;
  // A Pi that is powered but never becomes ready (dead SD card, crashed app) must not stay silent either.
  const bool bootOverdue =
      piPowered_ && !everAvailable_ && (uint32_t)(now - piPoweredMs_) >= cfg_.piBootTimeoutMs;
  const bool expectPi = everAvailable_ || bootOverdue;

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

  // Mute (the touch screen) lasts for the current turn activation only. It also acknowledges a TPMS alarm; neither
  // needs the Pi.
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
  const bool faultLeft = (blinkerFault & 0x1) || (expectPi && !usableLeft);
  const bool faultRight = (blinkerFault & 0x2) || (expectPi && !usableRight);
  const bool occLeft = usableLeft && pi_.occLeft && visualAllowed;
  const bool occRight = usableRight && pi_.occRight && visualAllowed;
  out.dangerLeft = occLeft && turn == Turn::Left;
  out.dangerRight = occRight && turn == Turn::Right;

  auto mode = [&](bool fault, bool occupied, bool danger) {
    if (lampTest_) return LedMode::LampTest;
    if (fault) return LedMode::Fault;
    if (danger) return LedMode::Flash;
    if (occupied) return LedMode::Steady;
    return LedMode::Off;
  };
  out.left = mode(faultLeft, occLeft, out.dangerLeft);
  out.right = mode(faultRight, occRight, out.dangerRight);

  // One fault beep when a side becomes faulted; another only after faultRearmMs without any fault.
  const uint8_t faults = (uint8_t)((faultLeft ? 1 : 0) | (faultRight ? 2 : 0));
  if ((faults & ~faultsWas_) != 0 && (!everFaultBeep_ || faultRearmed_)) {
    faultBeepPending_ = true;
    everFaultBeep_ = true;
    faultRearmed_ = false;
  }
  if (faults == 0) {
    if (faultsWas_ != 0) healthySince_ = now;
    else if (everFaultBeep_ && (uint32_t)(now - healthySince_) >= cfg_.faultRearmMs) faultRearmed_ = true;
  }
  faultsWas_ = faults;

  // Buzzer, highest priority first: blind-spot danger, fault, TPMS. A pattern plays for its full length.
  if (playing_ != Beep::None && (int32_t)(playingUntil_ - now) <= 0) playing_ = Beep::None;
  const bool danger = out.dangerLeft || out.dangerRight;
  // Danger episodes mute themselves: one starts with a new turn activation, or when the danger comes back after
  // dangerRearmMs without it (so a flickering detection stays one episode). It beeps at once (dangerMinGapMs after
  // any earlier beep), repeats every dangerRepeatMs and goes quiet dangerAutoMuteMs after it started.
  if (danger) {
    if (!dangerEpisode_ || activation != episodeActivation_ || (uint32_t)(now - dangerLastMs_) >= cfg_.dangerRearmMs) {
      dangerEpisode_ = true;
      episodeBeeped_ = false;
      episodeStart_ = now;
      episodeActivation_ = activation;
    }
    dangerLastMs_ = now;
  }
  const bool autoMuted = (uint32_t)(now - episodeStart_) >= cfg_.dangerAutoMuteMs;
  if (danger && audioAllowed && !muted_ && !autoMuted && blinkerFault == 0) {
    const uint32_t since = now - lastDangerBeep_;
    const bool due = episodeBeeped_ ? since >= cfg_.dangerRepeatMs : (!everDangerBeep_ || since >= cfg_.dangerMinGapMs);
    if (due && playing_ != Beep::BsmDanger) {
      startBeep(out, Beep::BsmDanger, cfg_.dangerBeepMs, now);
      lastDangerBeep_ = now;
      everDangerBeep_ = true;
      episodeBeeped_ = true;
    }
  }
  if (out.beep == Beep::None && faultBeepPending_ && playing_ != Beep::BsmDanger && playing_ != Beep::Fault) {
    faultBeepPending_ = false;
    startBeep(out, Beep::Fault, cfg_.faultBeepMs, now);
  }
  if (tpmsActive_ && !tpmsAcked_ && !tpmsPending_ && tpmsRemindersLeft_ > 0 &&
      (uint32_t)(now - lastTpmsBeep_) >= cfg_.tpmsRepeatMs) {
    tpmsPending_ = true;
    tpmsRemindersLeft_--;
  }
  if (out.beep == Beep::None && tpmsPending_ && playing_ == Beep::None) {
    tpmsPending_ = false;
    lastTpmsBeep_ = now;
    startBeep(out, Beep::TpmsLow, cfg_.tpmsBeepMs, now);
  }

  out.level = level_ < cfg_.minLedLevel ? cfg_.minLedLevel : level_;
  out.bsmAvailable = available;
  out.speedKnown = movingKnown_;
  out.audioAllowed = audioAllowed;
  return out;
}

}  // namespace v2
