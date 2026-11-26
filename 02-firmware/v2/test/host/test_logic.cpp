// Host unit tests for the v2 safety logic (no ESP32 needed). From 02-firmware/v2:
//   python -m ziglang c++ -std=c++17 -O2 -Wall -Wextra -Isrc/logic test/host/test_logic.cpp
//       src/logic/blinker.cpp src/logic/pi_power.cpp src/logic/alerts.cpp src/logic/link.cpp src/logic/obd.cpp
//       -o test_logic.exe
// (any C++17 compiler works the same way). Exit code 0 = all tests passed.
#include <algorithm>
#include <cctype>
#include <cstdio>
#include <cstring>
#include <functional>
#include <string>
#include <vector>

#include "alerts.h"
#include "blinker.h"
#include "link.h"
#include "obd.h"
#include "pi_power.h"

using namespace v2;

namespace {

int failures = 0, checks = 0;
#define CHECK(cond, ...)                         \
  do {                                           \
    checks++;                                    \
    if (!(cond)) {                               \
      failures++;                                \
      std::printf("FAIL line %d: ", __LINE__);   \
      std::printf(__VA_ARGS__);                  \
      std::printf("\n");                         \
    }                                            \
  } while (0)

// ------------------------------------------------------------------------------------------- blinker helpers
using Lamp = std::function<bool(uint32_t)>;  // lamp state at time t (ms)

Lamp blink(uint32_t start, uint32_t stop, uint32_t onMs, uint32_t offMs, uint32_t phase = 0) {
  return [=](uint32_t t) {
    if (t < start + phase || t >= stop) return false;
    return (t - start - phase) % (onMs + offMs) < onMs;
  };
}
Lamp never() { return [](uint32_t) { return false; }; }

struct Trace {
  std::vector<Turn> states;  // one per ms
  Turn at(uint32_t t) const { return states[t]; }
  bool any(uint32_t from, uint32_t to, Turn s) const {
    for (uint32_t t = from; t < to && t < states.size(); t++)
      if (states[t] == s) return true;
    return false;
  }
  bool all(uint32_t from, uint32_t to, Turn s) const {
    for (uint32_t t = from; t < to && t < states.size(); t++)
      if (states[t] != s) return false;
    return true;
  }
  long firstAfter(uint32_t from, Turn s) const {
    for (uint32_t t = from; t < states.size(); t++)
      if (states[t] == s) return (long)t;
    return -1;
  }
};

Trace run(BlinkerDetector& d, uint32_t ms, const Lamp& left, const Lamp& right) {
  Trace tr;
  for (uint32_t t = 0; t < ms; t++) {
    d.update(t, left(t), right(t));
    tr.states.push_back(d.state());
  }
  return tr;
}

void testBlinker() {
  {
    BlinkerDetector d;
    Trace tr = run(d, 2000, never(), never());
    CHECK(tr.all(0, 2000, Turn::Off), "idle must stay off");
  }
  {  // 90 flashes/min (333 ms on / 333 ms off) from 1000 to 4000 ms
    BlinkerDetector d;
    Trace tr = run(d, 7000, blink(1000, 4000, 333, 333), never());
    long first = tr.firstAfter(1000, Turn::Left);
    CHECK(first > 1000 && first <= 1000 + 50 + 150 + 5, "left reported %ld ms after the lamp (want <= 205)",
          first - 1000);
    CHECK(tr.all((uint32_t)first, 4000, Turn::Left), "left must not drop out in the off phases");
    long off = tr.firstAfter(4000, Turn::Off);  // last flash ends at 1000 + 4*666 + 333 = 3997
    CHECK(off > 3997 && off <= 3997 + 25 + 50 + 900 + 5, "left released %ld ms after the last flash", off - 3997);
    CHECK(!tr.any(0, 7000, Turn::Right) && !tr.any(0, 7000, Turn::Hazard), "no right / hazard on a left turn");
    CHECK(d.activation() == 1, "one activation, got %u", (unsigned)d.activation());
  }
  {  // right side, slow flasher: 60/min (500 / 500)
    BlinkerDetector d;
    Trace tr = run(d, 6000, never(), blink(500, 3500, 500, 500));
    long first = tr.firstAfter(500, Turn::Right);
    CHECK(first > 0 && tr.all((uint32_t)first, 3500, Turn::Right), "slow flasher must hold right");
  }
  {  // bulb-out hyper-flash: about 2.7 Hz
    BlinkerDetector d;
    Trace tr = run(d, 5000, blink(500, 3500, 185, 185), never());
    long first = tr.firstAfter(500, Turn::Left);
    CHECK(first > 0 && tr.all((uint32_t)first, 3500, Turn::Left), "hyper-flash must hold left");
  }
  {  // hazards, both sides in sync: never a single side, so no false danger beep at hazard onset
    BlinkerDetector d;
    Trace tr = run(d, 6000, blink(1000, 4000, 333, 333), blink(1000, 4000, 333, 333));
    CHECK(!tr.any(0, 6000, Turn::Left) && !tr.any(0, 6000, Turn::Right), "hazard showed as a single side");
    long first = tr.firstAfter(1000, Turn::Hazard);
    CHECK(first > 1000 && tr.all((uint32_t)first, 4000, Turn::Hazard), "hazard must be steady");
  }
  {  // hazards with an 80 ms skew between the sides
    BlinkerDetector d;
    Trace tr = run(d, 6000, blink(1000, 4000, 333, 333), blink(1000, 4000, 333, 333, 80));
    CHECK(!tr.any(0, 6000, Turn::Left) && !tr.any(0, 6000, Turn::Right), "skewed hazard showed as a single side");
    CHECK(tr.any(1000, 4000, Turn::Hazard), "skewed hazard not detected");
  }
  {  // hazards switched off while the left signal keeps going: left again after a fresh flash, never right
    BlinkerDetector d;
    Trace tr = run(d, 8000, blink(1000, 7000, 333, 333), blink(1000, 4000, 333, 333));
    CHECK(tr.any(1000, 4000, Turn::Hazard) && !tr.any(0, 8000, Turn::Right), "hazard -> left went through right");
    long left = tr.firstAfter(4000, Turn::Left);
    CHECK(left > 4000 && left < 5400 && tr.all((uint32_t)left, 7000, Turn::Left), "left after hazard at %ld", left);
  }
  {  // lane change: left, then right straight away
    BlinkerDetector d;
    Trace tr = run(d, 8000, blink(1000, 3000, 333, 333), blink(3200, 5200, 333, 333));
    CHECK(tr.any(1000, 3000, Turn::Left), "left phase missing");
    long right = tr.firstAfter(3200, Turn::Right);
    CHECK(right > 3200 && right <= 3200 + 50 + 5, "right reported %ld ms after its lamp (left still held)",
          right - 3200);
    CHECK(!tr.any(0, 8000, Turn::Hazard), "lane change mistaken for hazard");
    CHECK(d.activation() == 2, "two activations, got %u", (unsigned)d.activation());
  }
  {  // lamp PWM-driven by the BCM (5 ms on / 5 ms off) inside each 333 ms flash
    BlinkerDetector d;
    Lamp flash = blink(1000, 4000, 333, 333);
    Lamp pwm = [flash](uint32_t t) { return flash(t) && (t % 10) < 5; };
    Trace tr = run(d, 6000, pwm, never());
    long first = tr.firstAfter(1000, Turn::Left);
    CHECK(first > 0 && tr.all((uint32_t)first, 4000, Turn::Left), "PWM lamp drive must read as a steady flash");
  }
  {  // spikes (20 ms every 1.5 s) must be ignored
    BlinkerDetector d;
    Lamp spikes = [](uint32_t t) { return t > 500 && (t % 1500) < 20; };
    Trace tr = run(d, 8000, spikes, spikes);
    CHECK(tr.all(0, 8000, Turn::Off), "spikes produced a turn");
  }
  {  // one-touch lane-change signal (3 flashes), twice, gives two activations
    BlinkerDetector d;
    run(d, 7000, [](uint32_t t) { return blink(500, 2500, 333, 333)(t) || blink(4500, 6500, 333, 333)(t); },
        never());
    CHECK(d.activation() == 2, "expected 2 activations, got %u", (unsigned)d.activation());
  }
}

// ------------------------------------------------------------------------------------------- Pi power
void testPiPower() {
  {
    PiPowerSequencer p;
    for (uint32_t t = 0; t < 2000; t += 10) p.update(t, 0, false, 0);
    CHECK(p.state() == PiPowerState::NoAcc && p.inhibit(), "no ACC must hold the Pi off");
  }
  {  // key in ACC, engine never started: release after 15 s
    PiPowerSequencer p;
    uint32_t on = 0;
    for (uint32_t t = 0; t < 20000; t += 10) {
      p.update(t, 12400, false, 0);
      if (!on && !p.inhibit()) on = t;
    }
    CHECK(on >= 15000 && on <= 15020, "ACC-only release at %u ms (want 15000)", (unsigned)on);
  }
  {  // key straight to START: 0.5 s ACC, 1.5 s crank (ACC dropped), then the engine runs at 14.2 V
    PiPowerSequencer p;
    bool onBeforeRun = false;
    uint32_t on = 0;
    for (uint32_t t = 0; t < 6000; t += 10) {
      uint16_t mv = t < 500 ? 12400 : (t < 2000 ? 0 : 14200);
      p.update(t, mv, false, 0);
      if (!p.inhibit() && t < 2000) onBeforeRun = true;
      if (!on && !p.inhibit()) on = t;
    }
    CHECK(!onBeforeRun, "the Pi must not start before or during the crank");
    CHECK(on >= 3000 && on <= 3020, "engine-running release at %u ms (want ~3000)", (unsigned)on);
  }
  {  // ESP32 restarted with the engine already running
    PiPowerSequencer p;
    uint32_t on = 0;
    for (uint32_t t = 0; t < 3000; t += 10) {
      p.update(t, 14000, false, 0);
      if (!on && !p.inhibit()) on = t;
    }
    CHECK(on >= 1000 && on <= 1020, "running engine release at %u ms", (unsigned)on);
  }
  {  // short dip (100 ms) while on is ignored, a 300 ms loss restarts the sequence
    PiPowerSequencer p;
    for (uint32_t t = 0; t < 2000; t += 10) p.update(t, 14000, false, 0);
    CHECK(p.state() == PiPowerState::On, "should be on");
    for (uint32_t t = 2000; t < 2100; t += 10) p.update(t, 6000, false, 0);
    for (uint32_t t = 2100; t < 2500; t += 10) p.update(t, 14000, false, 0);
    CHECK(p.state() == PiPowerState::On, "a 100 ms dip must not restart the Pi");
    for (uint32_t t = 2500; t < 2800; t += 10) p.update(t, 6000, false, 0);
    CHECK(p.state() == PiPowerState::NoAcc, "a 300 ms loss is a real ACC loss");
  }
  {  // hysteresis: 8.5 V never turns a dead ACC on
    PiPowerSequencer p;
    for (uint32_t t = 0; t < 5000; t += 10) p.update(t, 8500, false, 0);
    CHECK(p.state() == PiPowerState::NoAcc, "8.5 V must not count as ACC present");
  }
  {  // hot car: wait until 55 C ...
    PiPowerSequencer p;
    uint32_t on = 0;
    for (uint32_t t = 0; t < 400000; t += 100) {
      int16_t temp = t < 180000 ? 70 : 54;
      p.update(t, 14000, true, temp);
      if (!on && !p.inhibit()) on = t;
    }
    CHECK(on >= 180000 && on <= 180100, "hot hold released at %u ms (want 180000)", (unsigned)on);
  }
  {  // ... but never longer than 10 minutes
    PiPowerSequencer p;
    uint32_t on = 0;
    for (uint32_t t = 0; t < 700000; t += 100) {
      p.update(t, 14000, true, 80);
      if (!on && !p.inhibit()) on = t;
    }
    CHECK(on >= 601000 && on <= 601200, "hot hold cap at %u ms (want ~601000)", (unsigned)on);
  }
  {  // a missing or failed temperature sensor never holds the Pi off
    PiPowerSequencer p;
    uint32_t on = 0;
    for (uint32_t t = 0; t < 3000; t += 10) {
      p.update(t, 14000, false, 120);
      if (!on && !p.inhibit()) on = t;
    }
    CHECK(on > 0 && on <= 1020, "invalid temperature must be ignored (on at %u)", (unsigned)on);
  }
}

// ------------------------------------------------------------------------------------------- alerts
PiStatus ready(bool occL = false, bool occR = false) {
  PiStatus s;
  s.ready = true;
  s.occLeft = occL;
  s.occRight = occR;
  s.ledLevel = 200;
  return s;
}

struct AlertRun {
  AlertArbiter a;
  uint32_t t = 0;
  int obd = -1;  // OBD-II speed reported every 200 ms: >= 0 valid deci-mph, -1 not reporting, -2 "NO DATA"
  std::vector<Beep> beeps;
  AlertOutput last;
  void step(uint32_t ms, Turn turn, uint32_t act, const PiStatus* pi, int speedDmph) {
    for (uint32_t i = 0; i < ms; i += 10, t += 10) {
      if (pi && t % 50 == 0) a.piReport(t, *pi);
      if (speedDmph >= 0 && t % 1000 == 0) a.gpsSpeed(t, true, (uint16_t)speedDmph);
      if (obd != -1 && t % 200 == 0) a.obdSpeed(t, obd >= 0, (uint16_t)(obd >= 0 ? obd : 0));
      last = a.update(t, turn, act);
      if (last.beep != Beep::None) beeps.push_back(last.beep);
    }
  }
  int count(Beep b) const {
    int n = 0;
    for (Beep x : beeps) n += x == b;
    return n;
  }
};

void testAlerts() {
  {  // Pi still booting: nothing at all
    AlertRun r;
    r.step(5000, Turn::Left, 1, nullptr, 600);
    CHECK(r.last.left == LedMode::Off && r.last.right == LedMode::Off && r.beeps.empty() && !r.last.bsmAvailable,
          "booting Pi must give no LEDs and no beeps");
  }
  {  // lamp test once when the Pi is first ready
    AlertRun r;
    PiStatus s = ready();
    r.step(500, Turn::Off, 0, &s, 600);
    CHECK(r.last.left == LedMode::LampTest && r.last.right == LedMode::LampTest, "lamp test expected");
    r.step(1000, Turn::Off, 0, &s, 600);
    CHECK(r.last.left == LedMode::Off && r.last.right == LedMode::Off, "lamp test must end after 1 s");
  }
  {  // occupied left at 60 mph: steady, no beep; signalling left: flash + danger beep, repeated every 3 s
    AlertRun r;
    PiStatus s = ready(true, false);
    r.step(2000, Turn::Off, 0, &s, 600);
    CHECK(r.last.left == LedMode::Steady && r.last.right == LedMode::Off && r.beeps.empty(), "steady left expected");
    CHECK(r.last.level == 200, "LED level must follow the Pi");
    r.step(7000, Turn::Left, 1, &s, 600);
    CHECK(r.last.left == LedMode::Flash && r.last.dangerLeft, "left danger must flash");
    CHECK(r.count(Beep::BsmDanger) == 3, "danger beeps at 0, 3 and 6 s: got %d", r.count(Beep::BsmDanger));
  }
  {  // signalling right with the left lane occupied: no danger
    AlertRun r;
    PiStatus s = ready(true, false);
    r.step(3000, Turn::Right, 1, &s, 600);
    CHECK(r.last.left == LedMode::Steady && !r.last.dangerLeft && !r.last.dangerRight && r.beeps.empty(),
          "the other side must not alarm");
  }
  {  // hazards never beep
    AlertRun r;
    PiStatus s = ready(true, true);
    r.step(5000, Turn::Hazard, 1, &s, 600);
    CHECK(r.count(Beep::BsmDanger) == 0 && r.last.left == LedMode::Steady, "hazard must stay quiet");
  }
  {  // slow (5 mph): nothing; hysteresis: 10 mph after 15 mph still counts as moving
    AlertRun r;
    PiStatus s = ready(true, false);
    r.step(3000, Turn::Left, 1, &s, 50);
    CHECK(r.last.left == LedMode::Off && r.beeps.empty(), "5 mph must be silent and dark");
    AlertRun h;
    h.step(2000, Turn::Off, 0, &s, 150);
    h.step(3000, Turn::Left, 1, &s, 100);
    CHECK(h.last.left == LedMode::Flash && h.count(Beep::BsmDanger) >= 1, "10 mph after 15 mph must still alert");
  }
  {  // GPS lost: hold 10 s, then LEDs only (no buzzer)
    AlertRun r;
    PiStatus s = ready(true, false);
    r.step(2000, Turn::Off, 0, &s, 600);
    r.step(5000, Turn::Off, 0, &s, -1);
    CHECK(r.last.speedKnown && r.last.audioAllowed, "speed must be held through a short GPS gap");
    r.step(10000, Turn::Off, 0, &s, -1);
    CHECK(!r.last.speedKnown && !r.last.audioAllowed, "speed must become unknown after the hold");
    CHECK(r.last.speedSource == SpeedSource::None && r.last.speedDmph == -1, "no fresh speed must report none / -1");
    size_t before = r.beeps.size();
    r.step(3000, Turn::Left, 1, &s, -1);
    CHECK(r.last.left == LedMode::Flash && r.beeps.size() == before, "unknown speed: flash but no buzzer");
  }
  {  // OBD speed alone (no GPS fix: a garage exit or a cold GPS) enables the buzzer and is reported as the source
    AlertRun r;
    r.obd = 300;
    PiStatus s = ready(true, false);
    r.step(2000, Turn::Off, 0, &s, -1);
    r.step(1000, Turn::Left, 1, &s, -1);
    CHECK(r.last.speedSource == SpeedSource::Obd && r.last.speedDmph == 300 && r.count(Beep::BsmDanger) == 1,
          "OBD speed alone must enable the buzzer (source %s, %d beeps)", speedSourceName(r.last.speedSource),
          r.count(Beep::BsmDanger));
  }
  {  // the car's own speed wins over a wandering GPS: 5 mph by OBD, 60 mph by GPS -> dark and quiet
    AlertRun r;
    r.obd = 50;
    PiStatus s = ready(true, false);
    r.step(2000, Turn::Off, 0, &s, 600);
    r.step(3000, Turn::Left, 1, &s, 600);
    CHECK(r.last.speedSource == SpeedSource::Obd && r.last.left == LedMode::Off && r.beeps.empty(),
          "OBD must win over GPS");
  }
  {  // the dongle goes silent: GPS takes over after 1 s; a "NO DATA" (invalid) report hands over at once
    AlertRun r;
    r.obd = 50;
    PiStatus s = ready(true, false);
    r.step(2000, Turn::Off, 0, &s, 600);
    r.obd = -1;
    r.step(1500, Turn::Left, 1, &s, 600);
    CHECK(r.last.speedSource == SpeedSource::Gps && r.last.left == LedMode::Flash && r.count(Beep::BsmDanger) >= 1,
          "a silent dongle must hand over to the GPS");
    AlertRun v;
    v.obd = 50;
    v.step(2000, Turn::Off, 0, &s, 600);
    v.obd = -2;
    v.step(10, Turn::Off, 0, &s, 600);
    CHECK(v.last.speedSource == SpeedSource::Gps, "an invalid OBD report must hand over at once");
  }
  {  // mute: silences the rest of this activation only
    AlertRun r;
    PiStatus s = ready(true, false);
    r.step(2000, Turn::Off, 0, &s, 600);
    r.step(500, Turn::Left, 1, &s, 600);
    CHECK(r.count(Beep::BsmDanger) == 1, "first danger beep expected");
    r.a.mutePressed();
    r.step(7000, Turn::Left, 1, &s, 600);
    CHECK(r.count(Beep::BsmDanger) == 1, "muted activation must not repeat (got %d)", r.count(Beep::BsmDanger));
    CHECK(r.last.left == LedMode::Flash, "mute must not hide the LED");
    r.step(1500, Turn::Off, 1, &s, 600);
    r.step(500, Turn::Left, 2, &s, 600);
    CHECK(r.count(Beep::BsmDanger) == 2, "a new activation must beep again");
  }
  {  // flickering detection must not machine-gun the buzzer
    AlertRun r;
    PiStatus occ = ready(true, false), clear = ready(false, false);
    r.step(2000, Turn::Off, 0, &clear, 600);
    for (int i = 0; i < 20; i++) {
      r.step(100, Turn::Left, 1, &occ, 600);
      r.step(100, Turn::Left, 1, &clear, 600);
    }
    CHECK(r.count(Beep::BsmDanger) <= 5, "flicker gave %d beeps in 4 s", r.count(Beep::BsmDanger));
  }
  {  // Pi link lost after being ready: fault LEDs and exactly one fault beep
    AlertRun r;
    PiStatus s = ready();
    r.step(3000, Turn::Off, 0, &s, 600);
    r.step(5000, Turn::Off, 0, nullptr, 600);
    CHECK(r.last.left == LedMode::Fault && r.last.right == LedMode::Fault && !r.last.bsmAvailable, "fault expected");
    CHECK(r.count(Beep::Fault) == 1, "one fault beep, got %d", r.count(Beep::Fault));
    r.step(2000, Turn::Off, 0, &s, 600);
    CHECK(r.last.left == LedMode::Off && r.last.bsmAvailable, "must recover when the Pi is back");
  }
  {  // one faulted camera: that side shows the fault, the other keeps working
    AlertRun r;
    PiStatus s = ready(false, true);
    s.camFaultLeft = true;
    r.step(3000, Turn::Off, 0, &s, 600);
    CHECK(r.last.left == LedMode::Fault && r.last.right == LedMode::Steady, "per-side camera fault");
  }
  {  // TPMS alarm: one beep now, repeat after 10 min, a blind-spot beep takes priority
    AlertRun r;
    PiStatus s = ready(true, false);
    r.step(2000, Turn::Off, 0, &s, 600);
    r.a.tpmsAlarm(true);
    r.step(10, Turn::Left, 1, &s, 600);
    CHECK(r.count(Beep::BsmDanger) == 1 && r.count(Beep::TpmsLow) == 0, "danger first");
    r.step(100, Turn::Left, 1, &s, 600);
    CHECK(r.count(Beep::TpmsLow) == 1, "deferred TPMS beep expected");
    r.step(60000, Turn::Off, 0, &s, 600);
    CHECK(r.count(Beep::TpmsLow) == 1, "TPMS must not repeat within 10 min");
  }
  {  // no acknowledge: a reminder every 10 min
    AlertRun r;
    r.a.tpmsAlarm(true);
    r.step(1300000, Turn::Off, 0, nullptr, -1);
    CHECK(r.count(Beep::TpmsLow) == 3, "TPMS reminders at 0, 10 and 20 min: got %d", r.count(Beep::TpmsLow));
  }
  {  // the pod button acknowledges a TPMS alarm with the Pi down; another low tyre or a new alarm sounds again
    AlertRun r;
    r.a.tpmsAlarm(true, 0x1);
    r.step(100, Turn::Off, 0, nullptr, -1);
    CHECK(r.count(Beep::TpmsLow) == 1, "TPMS beep expected with the Pi down");
    r.a.mutePressed();
    r.step(700000, Turn::Off, 0, nullptr, -1);
    CHECK(r.count(Beep::TpmsLow) == 1, "acknowledged TPMS alarm repeated (%d beeps)", r.count(Beep::TpmsLow));
    r.a.tpmsAlarm(true, 0x1);
    r.step(100, Turn::Off, 0, nullptr, -1);
    CHECK(r.count(Beep::TpmsLow) == 1, "the same low tyre must stay acknowledged");
    r.a.tpmsAlarm(true, 0x3);
    r.step(100, Turn::Off, 0, nullptr, -1);
    CHECK(r.count(Beep::TpmsLow) == 2, "a second low tyre must sound again");
    r.a.tpmsAlarm(false);
    r.a.tpmsAlarm(true, 0x1);
    r.step(100, Turn::Off, 0, nullptr, -1);
    CHECK(r.count(Beep::TpmsLow) == 3, "a new alarm after it cleared must sound again");
  }
}

// ------------------------------------------------------------------------------------------- link
std::string withChecksum(const std::string& body) {
  char buf[8];
  std::snprintf(buf, sizeof buf, "*%02X", link::checksum(body.data() + 1, body.data() + body.size()));
  return body + buf;
}

bool feedAll(link::LineReader& r, const std::string& bytes, std::vector<std::string>& lines) {
  bool any = false;
  for (char c : bytes) {
    if (r.feed(c)) {
      lines.push_back(r.line());
      any = true;
    }
  }
  return any;
}

void testLink() {
  uint32_t seq = 0;
  PiStatus s;
  std::string good = withChecksum("$BSM,42,1,1,0,0,1,128");
  CHECK(link::parseBsm(good.c_str(), seq, s), "valid BSM rejected: %s", good.c_str());
  CHECK(seq == 42 && s.ready && s.occLeft && !s.occRight && !s.camFaultLeft && s.camFaultRight && s.ledLevel == 128,
        "BSM fields wrong");

  std::string lower = good;
  for (char& c : lower) c = (char)std::tolower((unsigned char)c);
  lower = good.substr(0, good.size() - 2) + lower.substr(lower.size() - 2);
  CHECK(link::parseBsm(lower.c_str(), seq, s), "lower-case checksum must be accepted");

  std::string corrupt = good;
  corrupt[8] = corrupt[8] == '1' ? '0' : '1';  // the "ready" flag
  CHECK(!link::parseBsm(corrupt.c_str(), seq, s), "corrupted line accepted");
  CHECK(!link::parseBsm(withChecksum("$BSM,1,1,1,0,0,1").c_str(), seq, s), "missing field accepted");
  CHECK(!link::parseBsm(withChecksum("$BSM,1,1,1,0,0,1,300").c_str(), seq, s), "level 300 accepted");
  CHECK(!link::parseBsm(withChecksum("$BSM,1,2,1,0,0,1,10").c_str(), seq, s), "flag 2 accepted");
  CHECK(!link::parseBsm(withChecksum("$BSM,x,1,1,0,0,1,10").c_str(), seq, s), "non-numeric seq accepted");
  CHECK(!link::parseBsm(withChecksum("$ESP,1,1,1,0,0,1,10").c_str(), seq, s), "wrong type accepted");
  CHECK(!link::parseBsm((good + "Z").c_str(), seq, s), "trailing garbage accepted");
  CHECK(!link::parseBsm("BSM,1,1,1,0,0,1,10*00", seq, s), "missing $ accepted");

  {  // the reader resyncs on '$', handles CR/LF and drops overlong lines
    link::LineReader r;
    std::vector<std::string> lines;
    feedAll(r, "noise\x01\xff" + good + "\r\n" + std::string(200, 'A') + "\n" + good + "\n", lines);
    CHECK(lines.size() == 2 && lines[0] == good && lines[1] == good, "reader returned %zu lines", lines.size());
    CHECK(r.dropped() == 1, "one overlong line must be counted, got %u", (unsigned)r.dropped());
  }
  {  // formatted lines carry valid checksums and the expected fields
    char buf[96];
    int n = link::formatEsp(buf, sizeof buf, 7, Turn::Right, -1, 14120, true, 3, true, SpeedSource::Obd);
    std::string line(buf, n > 0 ? (size_t)n - 1 : 0);
    link::Frame f;
    CHECK(n > 0 && buf[n - 1] == '\n' && link::split(line.c_str(), f), "ESP line invalid: %s", buf);
    CHECK(f.count == 9 && f.is(0, "ESP") && f.is(2, "R") && f.is(3, "-1") && f.is(4, "14120") && f.is(8, "O"),
          "ESP fields: %s", buf);
    n = link::formatTpm(buf, sizeof buf, 2, 0x1A2B3C, 2205, -4, -87, 12);
    line.assign(buf, n > 0 ? (size_t)n - 1 : 0);
    CHECK(n > 0 && link::split(line.c_str(), f) && f.is(2, "1A2B3C") && f.is(4, "-4") && f.is(5, "-87"),
          "TPM line: %s", buf);
    CHECK(link::formatEsp(buf, 10, 7, Turn::Left, 600, 14000, true, 0, true, SpeedSource::Gps) == 0,
          "overflow must return 0");
  }
}

// ------------------------------------------------------------------------------------------- OBD-II (ELM327)
// A simulated ELM327 that behaves as its datasheet describes: echo and spaces on after a reset, a '>' prompt after
// every answer, and "STOPPED" when a command arrives while it is still busy (that command is lost). Switches model
// the car and common clone quirks.
struct FakeElm {
  bool carAwake = true;       // false: the engine computer doesn't answer (key in ACC) -> NO DATA after 200 ms
  int kmh = 60;
  bool noCountDigit = false;  // clone: answers "?" to "010D1"
  bool ignoreS0 = false;      // clone: keeps the spaces
  bool hung = false;          // swallows everything
  uint32_t slowNext = 0;      // delay of the next speed reply in ms (0 = normal)
  bool echo = true, spaces = true;
  std::string rx;
  struct Out {
    uint32_t at;
    std::string text;
  };
  std::vector<Out> out;
  void say(uint32_t at, const std::string& text) { out.push_back({at, text}); }

  void receive(uint32_t now, const std::string& bytes) {
    for (char c : bytes) {
      if (hung) continue;
      if (c != '\r') {
        rx += c;
        continue;
      }
      const std::string cmd = rx;
      rx.clear();
      if (!out.empty()) {
        out.clear();
        say(now + 2, "STOPPED\r\r>");
        continue;
      }
      const std::string e = echo ? cmd + "\r" : "";
      if (cmd == "ATZ") {
        echo = spaces = true;
        say(now + 800, e + "\r\rELM327 v1.5\r\r>");
      } else if (cmd == "ATE0" || cmd == "ATS0" || cmd == "ATH0" || cmd == "ATSP6") {
        if (cmd == "ATE0") echo = false;
        if (cmd == "ATS0" && !ignoreS0) spaces = false;
        say(now + 5, e + "OK\r\r>");
      } else if (cmd == "010D1" && noCountDigit) {
        say(now + 5, e + "?\r\r>");
      } else if (cmd == "010D1" || cmd == "010D") {
        if (!carAwake) {
          say(now + 200, e + "SEARCHING...\rNO DATA\r\r>");
          continue;
        }
        char b[16];
        std::snprintf(b, sizeof b, spaces ? "41 0D %02X" : "410D%02X", kmh & 0xFF);
        const uint32_t delay = slowNext ? slowNext : (cmd == "010D1" ? 30 : 230);  // plain: waits out the timer
        slowNext = 0;
        say(now + delay, e + b + "\r\r>");
      } else {
        say(now + 5, e + "?\r\r>");
      }
    }
  }
  void tick(uint32_t now, obd::ElmClient& c) {
    while (!out.empty() && out.front().at <= now) {
      const std::string text = out.front().text;
      out.erase(out.begin());
      for (char ch : text) c.feed(now, ch);
    }
  }
};

struct ElmRun {
  obd::ElmClient c;
  FakeElm f;
  uint32_t t = 0;
  int speeds = 0;
  uint8_t kmh = 0;
  uint32_t firstAt = 0, lastAt = 0;
  std::vector<std::string> sent;
  void run(uint32_t ms) {
    for (uint32_t end = t + ms; t < end; t++) {
      if (const char* cmd = c.poll(t)) {
        sent.push_back(cmd);
        f.receive(t, std::string(cmd) + "\r");
      }
      f.tick(t, c);
      uint8_t k;
      uint32_t at;
      if (c.takeSpeed(k, at)) {
        if (!speeds) firstAt = at;
        speeds++;
        kmh = k;
        lastAt = at;
      }
    }
  }
  int count(const char* cmd) const { return (int)std::count(sent.begin(), sent.end(), std::string(cmd)); }
};

void testObd() {
  // km/h -> deci-mph around the speed gate: on at 12.0 mph (19.3 km/h), off below 8.0 mph (12.9 km/h)
  CHECK(obd::kmhToDmph(0) == 0 && obd::kmhToDmph(12) == 75 && obd::kmhToDmph(13) == 81 &&
            obd::kmhToDmph(19) == 118 && obd::kmhToDmph(20) == 124 && obd::kmhToDmph(100) == 621 &&
            obd::kmhToDmph(255) == 1584,
        "km/h -> deci-mph conversion");

  uint8_t k = 0;
  CHECK(obd::parseSpeedLine("410D3C", k) && k == 60, "plain reply");
  CHECK(obd::parseSpeedLine("41 0D 3C", k) && k == 60, "reply with spaces");
  CHECK(obd::parseSpeedLine("410d3c", k) && k == 60, "lower-case reply");
  CHECK(obd::parseSpeedLine("7E803410D00", k) && k == 0, "reply with an 11-bit header");
  CHECK(obd::parseSpeedLine("7E8 03 41 0D FF", k) && k == 255, "header and spaces");
  for (const char* bad : {"NO DATA", "SEARCHING...", "STOPPED", "?", "", "410C1AF8", "410D", "410D3", "410D3C00",
                          "410D3G", "7E804410D3C", "7E8 03 41 0C 3C", "CAN ERROR", "BUFFER FULL"}) {
    CHECK(!obd::parseSpeedLine(bad, k), "accepted \"%s\"", bad);
  }

  {  // a normal dongle: reset, setup, then speed requests at 5 Hz
    ElmRun r;
    r.c.connected(0, true);
    r.run(3000);
    const std::vector<std::string> start = {"ATZ", "ATE0", "ATS0", "ATH0", "ATSP6", "010D1"};
    CHECK(r.sent.size() >= start.size() && std::equal(start.begin(), start.end(), r.sent.begin()),
          "setup sequence");
    CHECK(r.speeds > 0 && r.kmh == 60 && r.firstAt <= 1000, "first speed at %u ms (want <= 1000)",
          (unsigned)r.firstAt);
    const int before = r.speeds;
    r.run(10000);
    CHECK(r.speeds - before >= 48 && r.speeds - before <= 51, "%d replies in 10 s (want ~50)", r.speeds - before);
    CHECK(r.c.failures() == 0 && r.c.resets() == 1, "%u failures, %u resets", (unsigned)r.c.failures(),
          (unsigned)r.c.resets());
  }
  {  // a clone without the response-count digit is polled with plain "010D"; spaces left on don't matter
    ElmRun r;
    r.f.noCountDigit = true;
    r.f.ignoreS0 = true;
    r.c.connected(0, true);
    r.run(3000);
    CHECK(r.count("010D1") == 1 && r.count("010D") > 5 && r.speeds > 5 && r.c.failures() == 0,
          "plain 010D fallback: %d polls, %d speeds", r.count("010D"), r.speeds);
  }
  {  // key in ACC, engine computer silent: NO DATA, a reset after 3 failures; recovers once it answers
    ElmRun r;
    r.f.carAwake = false;
    r.c.connected(0, true);
    r.run(5000);
    CHECK(r.speeds == 0 && r.c.resets() >= 2, "NO DATA: %d speeds, %u resets", r.speeds, (unsigned)r.c.resets());
    r.f.carAwake = true;
    const uint32_t woke = r.t;
    r.run(3000);
    CHECK(r.speeds > 0 && r.firstAt - woke <= 2000, "first speed %u ms after the car answered",
          (unsigned)(r.firstAt - woke));
  }
  {  // a hung dongle: timeouts, resets, no stale speed; recovers when it answers again
    ElmRun r;
    r.c.connected(0, true);
    r.run(2000);
    const int s0 = r.speeds;
    const uint32_t r0 = r.c.resets();
    r.f.hung = true;
    r.run(6000);
    CHECK(r.speeds == s0 && r.c.resets() > r0, "hung: %d new speeds, %u resets", r.speeds - s0,
          (unsigned)r.c.resets());
    r.f.hung = false;
    const uint32_t back = r.t;
    r.run(8000);
    CHECK(r.speeds > s0 && r.lastAt > back, "no recovery after the hang");
  }
  {  // one slow reply: the next request interrupts it ("STOPPED") and the client resyncs without a reset
    ElmRun r;
    r.c.connected(0, true);
    r.run(2000);
    const uint32_t r0 = r.c.resets();
    r.f.slowNext = 1500;
    r.run(4000);
    CHECK(r.c.resets() == r0 && r.c.failures() == 2 && r.lastAt > 5000, "resync: %u resets, %u failures",
          (unsigned)(r.c.resets() - r0), (unsigned)r.c.failures());
  }
  {  // link dropped: nothing is sent; reconnecting starts over with ATZ
    ElmRun r;
    r.c.connected(0, true);
    r.run(2000);
    r.c.connected(r.t, false);
    const size_t n = r.sent.size();
    r.run(5000);
    CHECK(r.sent.size() == n && r.c.state() == obd::ElmState::Disconnected, "sent while disconnected");
    r.c.connected(r.t, true);
    const uint32_t back = r.t;
    r.run(2000);
    CHECK(r.sent.size() > n && r.sent[n] == "ATZ" && r.lastAt > back, "reconnect must start with ATZ");
  }
  {  // noise and an overlong line between replies are ignored
    ElmRun r;
    r.c.connected(0, true);
    r.run(2000);
    for (char ch : std::string("\x01\xff") + std::string(200, 'A') + "\r") r.c.feed(r.t, ch);
    const int s0 = r.speeds;
    r.run(1000);
    CHECK(r.speeds > s0 && r.kmh == 60, "junk stopped the replies");
  }
}

}  // namespace

int main() {
  testBlinker();
  testPiPower();
  testAlerts();
  testLink();
  testObd();
  if (failures) {
    std::printf("%d of %d checks FAILED\n", failures, checks);
    return 1;
  }
  std::printf("all %d v2 logic checks passed\n", checks);
  return 0;
}
