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
    CHECK(right > 3200 && right <= 3200 + 150 + 5, "right reported %ld ms after its lamp (want <= 155)",
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
  {  // hazards pressed during a right turn signal, the left lamp joining at any point of the right's flash:
     // never a left turn (that would be a danger beep for the left lane)
    int asLeft = 0, missed = 0;
    for (uint32_t join = 3000; join < 3666; join += 37) {
      BlinkerDetector d;
      Lamp r = blink(1000, 9000, 333, 333);
      Lamp l = [r, join](uint32_t t) { return t >= join && r(t); };
      Trace tr = run(d, 10000, l, r);
      asLeft += tr.any(0, 10000, Turn::Left);
      missed += !tr.any(join, join + 1000, Turn::Hazard);
    }
    CHECK(asLeft == 0 && missed == 0, "hazards during a right turn: %d of 18 press times read as left, %d missed",
          asLeft, missed);
  }
  {  // ... or the body control module restarting both lamps when the hazard button is pressed
    int bad = 0;
    for (uint32_t press = 3000; press < 3666; press += 37) {
      BlinkerDetector d;
      Lamp before = blink(1000, press, 333, 333), after = blink(press, 9000, 333, 333);
      Lamp r = [before, after](uint32_t t) { return before(t) || after(t); };
      Trace tr = run(d, 10000, after, r);
      bad += tr.any(0, 10000, Turn::Left) || !tr.any(press, press + 1000, Turn::Hazard);
    }
    CHECK(bad == 0, "hazards restarting both lamps: %d of 18 press times went wrong", bad);
  }
  {  // left straight to right at any point of a left flash: never hazard, right within the 150 ms window
    int bad = 0;
    for (uint32_t sw = 3000; sw < 3330; sw += 29) {
      BlinkerDetector d;
      Trace tr = run(d, 9000, blink(1000, sw, 333, 333), blink(sw, sw + 4000, 333, 333));
      const long right = tr.firstAfter(sw, Turn::Right);
      bad += tr.any(0, 9000, Turn::Hazard) || right < 0 || right > (long)sw + 155;
    }
    CHECK(bad == 0, "left -> right: %d of 12 switch points read as hazard or were late", bad);
  }
  {  // hazards with 100-150 ms of skew between the sides, either side first: never a single side
    int bad = 0;
    for (uint32_t skew = 100; skew <= 150; skew += 10) {
      for (int leftFirst = 0; leftFirst < 2; leftFirst++) {
        BlinkerDetector d;
        Lamp a = blink(1000, 4000, 333, 333), b = blink(1000, 4000, 333, 333, skew);
        Trace tr = leftFirst ? run(d, 6000, a, b) : run(d, 6000, b, a);
        bad += tr.any(0, 6000, Turn::Left) || tr.any(0, 6000, Turn::Right) || !tr.any(1000, 4000, Turn::Hazard);
      }
    }
    CHECK(bad == 0, "skewed hazards: %d of 12 showed a single side or were missed", bad);
  }
  {  // hazards starting right at the millis() wrap (49.7 days), 40 ms of skew: the two edges straddle it
    BlinkerDetector d;
    const uint32_t base = 0xFFFFFFFFu - 1019u;  // the left edge at t = 1000 is 20 ms before the wrap
    Lamp a = blink(1000, 4000, 333, 333), b = blink(1000, 4000, 333, 333, 40);
    bool single = false, hazard = false;
    for (uint32_t t = 0; t < 6000; t++) {
      d.update(base + t, a(t), b(t));
      single |= d.state() == Turn::Left || d.state() == Turn::Right;
      hazard |= d.state() == Turn::Hazard;
    }
    CHECK(!single && hazard, "hazards across the millis() wrap: single side %d, hazard %d", single, hazard);
  }
  {  // ... and a 20 ms spike on the other side just after the wrap, during a left flash, is not a hazard
    BlinkerDetector d;
    const uint32_t base = 0xFFFFFFFFu - 2019u;  // the left flash at t = 2000 starts 20 ms before the wrap
    Lamp left = blink(1334, 6000, 333, 333);
    Lamp spike = [](uint32_t t) { return t >= 2040 && t < 2060; };
    bool hazard = false, dropped = false;
    for (uint32_t t = 0; t < 6000; t++) {
      d.update(base + t, left(t), spike(t));
      hazard |= d.state() == Turn::Hazard;
      dropped |= t >= 1600 && t < 6000 && d.state() != Turn::Left;
    }
    CHECK(!hazard && !dropped, "spike across the wrap: hazard %d, left dropped %d", hazard, dropped);
  }
  {  // a lamp input stuck lit (failed opto, shorted input, wrong wire): flagged as a fault, then treated as dark,
     // so a real right turn reads as right (not hazard); the fault clears 2 s after the input goes dark
    BlinkerDetector d;
    Lamp stuck = [](uint32_t t) { return t >= 1000 && t < 12000; };
    Trace tr = run(d, 16000, stuck, blink(5000, 9000, 333, 333));
    CHECK(tr.all(2600, 5000, Turn::Off), "a stuck input must not read as a turn");
    const long right = tr.firstAfter(5000, Turn::Right);
    CHECK(right > 5000 && right <= 5000 + 155 && !tr.any(2600, 16000, Turn::Hazard),
          "right turn with the left input stuck: right at %ld", right);
    BlinkerDetector e;
    run(e, 12000, stuck, never());
    CHECK(e.faultMask() == 0x1, "stuck left input must be flagged (mask %u)", (unsigned)e.faultMask());
    for (uint32_t t = 12000; t < 14100; t++) e.update(t, false, false);
    CHECK(e.faultMask() == 0, "the fault must clear 2 s after the input goes dark");
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
  {  // ESP32 started with the engine already running, Pi rail still off
    PiPowerSequencer p;
    uint32_t on = 0;
    for (uint32_t t = 0; t < 3000; t += 10) {
      p.update(t, 14000, false, 0);
      if (!on && !p.inhibit()) on = t;
    }
    CHECK(on >= 1000 && on <= 1020, "running engine release at %u ms", (unsigned)on);
  }
  {  // the ESP32 is reset or reflashed while the Pi runs (rail up): the Pi is never cut, in any of the holds
    const uint16_t acc[] = {14200, 12400, 14200};
    const int16_t temp[] = {25, 25, 65};
    for (int i = 0; i < 3; i++) {
      PiPowerSequencer p;
      bool cut = false;
      for (uint32_t t = 0; t < 20000; t += 10) {
        p.update(t, acc[i], i == 2, temp[i], true);
        cut |= p.inhibit();
      }
      CHECK(!cut, "a running Pi was cut after an ESP32 reset (case %d)", i);
    }
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
  uint32_t seq = 0;
  bool frozen = false;       // the Pi's vision loop is stuck: reports keep coming, the frame counter doesn't move
  uint8_t blinkerFault = 0;  // BlinkerDetector::faultMask()
  std::vector<Beep> beeps;
  AlertOutput last;
  void step(uint32_t ms, Turn turn, uint32_t act, const PiStatus* pi, int speedDmph) {
    for (uint32_t i = 0; i < ms; i += 10, t += 10) {
      if (pi && t % 50 == 0) a.piReport(t, frozen ? seq : ++seq, *pi);
      if (speedDmph >= 0 && t % 1000 == 0) a.gpsSpeed(t, true, (uint16_t)speedDmph);
      if (obd != -1 && t % 200 == 0) a.obdSpeed(t, obd >= 0, (uint16_t)(obd >= 0 ? obd : 0));
      last = a.update(t, turn, act, blinkerFault);
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
    r.step(AlertConfig().dangerBeepMs + 100, Turn::Left, 1, &s, 600);
    CHECK(r.count(Beep::TpmsLow) == 1, "TPMS beep expected once the danger pattern has played");
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
    r.step(AlertConfig().tpmsClearHoldMs + 1000, Turn::Off, 0, nullptr, -1);
    r.a.tpmsAlarm(true, 0x1);
    r.step(100, Turn::Off, 0, nullptr, -1);
    CHECK(r.count(Beep::TpmsLow) == 3, "a new alarm after it stayed clear must sound again");
  }
  {  // a camera that fails while running: fault pattern on that side and one fault beep
    AlertRun r;
    PiStatus s = ready();
    r.step(3000, Turn::Off, 0, &s, 600);
    s.camFaultLeft = true;
    r.step(3000, Turn::Off, 0, &s, 600);
    CHECK(r.last.left == LedMode::Fault && r.last.right == LedMode::Off && r.count(Beep::Fault) == 1,
          "camera fault: left %s, %d fault beeps", ledModeName(r.last.left), r.count(Beep::Fault));
  }
  {  // ... also when the camera is faulted from the first report
    AlertRun r;
    PiStatus s = ready();
    s.camFaultRight = true;
    r.step(4000, Turn::Off, 0, &s, 600);
    CHECK(r.last.right == LedMode::Fault && r.count(Beep::Fault) == 1, "camera faulted from the start: %d beeps",
          r.count(Beep::Fault));
  }
  {  // a flapping Pi link (1.2 s gap every 4 s) beeps once, not at every gap; 30 s healthy re-arms it
    AlertRun r;
    PiStatus s = ready();
    r.step(3000, Turn::Off, 0, &s, 600);
    for (int i = 0; i < 15; i++) {
      r.step(2800, Turn::Off, 0, &s, 600);
      r.step(1200, Turn::Off, 0, nullptr, 600);
    }
    CHECK(r.count(Beep::Fault) == 1, "flapping link: %d fault beeps in 60 s", r.count(Beep::Fault));
    r.step(31000, Turn::Off, 0, &s, 600);
    r.step(2000, Turn::Off, 0, nullptr, 600);
    CHECK(r.count(Beep::Fault) == 2, "a fault after 30 s healthy must beep again (%d)", r.count(Beep::Fault));
  }
  {  // beep priority holds over time: a TPMS beep 1 ms after a danger beep waits for it to finish ...
    AlertArbiter a;
    PiStatus s = ready(true, false);
    uint32_t dangerAt = 0, tpmsAt = 0;
    for (uint32_t t = 0; t < 4000; t++) {
      if (t % 50 == 0) a.piReport(t, t, s);
      if (t % 1000 == 0) a.gpsSpeed(t, true, 600);
      if (t == 2001) a.tpmsAlarm(true);
      AlertOutput o = a.update(t, t >= 2000 ? Turn::Left : Turn::Off, t >= 2000 ? 1 : 0);
      if (o.beep == Beep::BsmDanger && !dangerAt) dangerAt = t;
      if (o.beep == Beep::TpmsLow && !tpmsAt) tpmsAt = t;
    }
    CHECK(dangerAt == 2000 && tpmsAt >= 2000 + AlertConfig().dangerBeepMs,
          "TPMS beep at %u cut the danger beep at %u", (unsigned)tpmsAt, (unsigned)dangerAt);
  }
  {  // ... and a danger beep that cuts a TPMS beep has the TPMS beep played again afterwards
    AlertArbiter a;
    PiStatus s = ready(true, false);
    std::vector<uint32_t> tpms;
    uint32_t dangerAt = 0;
    for (uint32_t t = 0; t < 4000; t++) {
      if (t % 50 == 0) a.piReport(t, t, s);
      if (t % 1000 == 0) a.gpsSpeed(t, true, 600);
      if (t == 2000) a.tpmsAlarm(true);
      AlertOutput o = a.update(t, t >= 2001 ? Turn::Left : Turn::Off, t >= 2001 ? 1 : 0);
      if (o.beep == Beep::BsmDanger && !dangerAt) dangerAt = t;
      if (o.beep == Beep::TpmsLow) tpms.push_back(t);
    }
    CHECK(dangerAt == 2001 && tpms.size() == 2 && tpms.back() >= 2001 + AlertConfig().dangerBeepMs,
          "TPMS cut by a danger beep: %zu TPMS beeps, danger at %u", tpms.size(), (unsigned)dangerAt);
  }
  {  // a tyre hovering at the threshold after acknowledge: one re-raise, not one per crossing; a flapping
     // alarm flag doesn't re-raise either; a new alarm after it stayed clear for a minute does
    AlertRun r;
    r.a.tpmsAlarm(true, 0x1);
    r.step(100, Turn::Off, 0, nullptr, -1);
    r.a.mutePressed();
    r.step(100, Turn::Off, 0, nullptr, -1);
    for (int i = 0; i < 12; i++) {
      r.a.tpmsAlarm(true, i % 2 ? 0x1 : 0x3);
      r.step(5000, Turn::Off, 0, nullptr, -1);
    }
    CHECK(r.count(Beep::TpmsLow) == 2, "flapping second tyre: %d TPMS beeps (want 2)", r.count(Beep::TpmsLow));
    for (int i = 0; i < 12; i++) {
      r.a.tpmsAlarm(i % 2 == 1);
      r.step(5000, Turn::Off, 0, nullptr, -1);
    }
    CHECK(r.count(Beep::TpmsLow) == 2, "flapping alarm flag: %d TPMS beeps (want 2)", r.count(Beep::TpmsLow));
    r.a.tpmsAlarm(false);
    r.step(61000, Turn::Off, 0, nullptr, -1);
    r.a.tpmsAlarm(true, 0x1);
    r.step(100, Turn::Off, 0, nullptr, -1);
    CHECK(r.count(Beep::TpmsLow) == 3, "a new alarm after a 1 min clear must sound (%d)", r.count(Beep::TpmsLow));
  }
  {  // LED level 0 from the Pi can't make a danger flash or a fault invisible
    AlertRun r;
    PiStatus s = ready(true, false);
    s.ledLevel = 0;
    r.step(3000, Turn::Left, 1, &s, 600);
    CHECK(r.last.left == LedMode::Flash && r.last.level >= AlertConfig().minLedLevel, "level %u",
          (unsigned)r.last.level);
  }
  {  // a Pi that is powered but never becomes ready (dead SD card): fault on both sides and one beep after 90 s
    AlertRun r;
    r.a.piPower(0, true);
    r.step(80000, Turn::Off, 0, nullptr, 600);
    CHECK(r.last.left == LedMode::Off && r.beeps.empty(), "still booting at 80 s must be quiet");
    r.step(20000, Turn::Off, 0, nullptr, 600);
    CHECK(r.last.left == LedMode::Fault && r.last.right == LedMode::Fault && r.count(Beep::Fault) == 1,
          "Pi never ready: %s, %d fault beeps", ledModeName(r.last.left), r.count(Beep::Fault));
    AlertRun ok;
    ok.a.piPower(0, true);
    PiStatus s = ready();
    ok.step(60000, Turn::Off, 0, nullptr, 600);
    ok.step(60000, Turn::Off, 0, &s, 600);
    CHECK(ok.last.left == LedMode::Off && ok.count(Beep::Fault) == 0, "a Pi ready after 60 s is no fault");
  }
  {  // the vision loop freezes while its reporting thread keeps saying "ready": stale after 1 s, one fault beep
    AlertRun r;
    PiStatus s = ready(true, false);
    r.step(3000, Turn::Off, 0, &s, 600);
    r.frozen = true;
    r.step(3000, Turn::Off, 0, &s, 600);
    CHECK(r.last.left == LedMode::Fault && !r.last.bsmAvailable && r.count(Beep::Fault) == 1,
          "frozen vision: %s, %d fault beeps", ledModeName(r.last.left), r.count(Beep::Fault));
    r.frozen = false;
    r.step(500, Turn::Off, 0, &s, 600);
    CHECK(r.last.left == LedMode::Steady && r.last.bsmAvailable, "must recover when the frame counter moves");
  }
  {  // a stuck blinker input: fault on that side, one fault beep, no danger beeps (hazard vs turn is unknown)
    AlertRun r;
    PiStatus s = ready(false, true);
    r.step(3000, Turn::Off, 0, &s, 600);
    r.blinkerFault = 0x1;
    r.step(5000, Turn::Right, 1, &s, 600);
    CHECK(r.last.left == LedMode::Fault && r.last.right == LedMode::Flash && r.count(Beep::BsmDanger) == 0 &&
              r.count(Beep::Fault) == 1,
          "blinker fault: left %s, right %s, %d danger, %d fault beeps", ledModeName(r.last.left),
          ledModeName(r.last.right), r.count(Beep::BsmDanger), r.count(Beep::Fault));
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
  {  // an overlong line cut short by the next '$' is counted as dropped too
    link::LineReader r;
    std::vector<std::string> lines;
    feedAll(r, std::string(200, 'A') + good + "\n", lines);
    CHECK(lines.size() == 1 && lines[0] == good && r.dropped() == 1, "overlong then $: %zu lines, %u dropped",
          lines.size(), (unsigned)r.dropped());
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
  uint32_t lagNext = 0;       // the Bluetooth link holds the next speed reply this long (the ELM327 itself is done)
  std::string banner = "ELM327 v1.5";  // clones print other names
  bool noSp6 = false;         // clone: answers "?" to ATSPA6, so the first request searches the protocols ...
  bool car29 = false;         // the car answers on 29-bit IDs (protocol 7): protocol 6 fails, a search finds it
  bool forced6 = false;       // ATSP6 received: protocol 6 without automatic search
  uint32_t searchMs = 2500;   // ... for this long ("SEARCHING..." first)
  bool protocolKnown = false;
  bool echo = true, spaces = true;
  std::string rx;
  struct Out {
    uint32_t at;
    std::string text;
    uint32_t lag = 0;
    bool found = false;       // the protocol search succeeded with this reply
  };
  std::vector<Out> out;       // what the ELM327 is still producing (it is busy while this isn't empty)
  std::vector<Out> wire;      // produced, in transit over the Bluetooth link: delivered in order
  uint32_t wireFree = 0;
  void say(uint32_t at, const std::string& text, uint32_t lag = 0, bool found = false) {
    out.push_back({at, text, lag, found});
  }

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
        protocolKnown = false;
        say(now + 800, e + "\r\r" + banner + "\r\r>");
      } else if (cmd == "ATSPA6" && noSp6) {
        say(now + 5, e + "?\r\r>");
      } else if (cmd == "ATSP6") {   // protocol 6 forced, no automatic search
        forced6 = true;
        protocolKnown = true;
        say(now + 5, e + "OK\r\r>");
      } else if (cmd == "ATE0" || cmd == "ATS0" || cmd == "ATH0" || cmd == "ATSPA6") {
        if (cmd == "ATE0") echo = false;
        if (cmd == "ATS0" && !ignoreS0) spaces = false;
        if (cmd == "ATSPA6") protocolKnown = !car29;  // 6 first; a 29-bit car needs the automatic search
        say(now + 5, e + "OK\r\r>");
      } else if (cmd == "010D1" && noCountDigit) {
        say(now + 5, e + "?\r\r>");
      } else if (cmd == "010D1" || cmd == "010D") {
        if (!carAwake || (forced6 && car29)) {   // engine computer silent, or not on the forced protocol
          say(now + 200, e + "SEARCHING...\rNO DATA\r\r>");
          continue;
        }
        char b[16];
        std::snprintf(b, sizeof b, spaces ? "41 0D %02X" : "410D%02X", kmh & 0xFF);
        if (!protocolKnown) {
          say(now + 5, e + "SEARCHING...\r");
          say(now + searchMs, std::string(b) + "\r\r>", 0, true);
          continue;
        }
        const uint32_t delay = slowNext ? slowNext : (cmd == "010D1" ? 30 : 230);  // plain: waits out the timer
        slowNext = 0;
        say(now + delay, e + b + "\r\r>", lagNext);
        lagNext = 0;
      } else {
        say(now + 5, e + "?\r\r>");
      }
    }
  }
  void tick(uint32_t now, obd::ElmClient& c) {
    while (!out.empty() && out.front().at <= now) {
      const Out o = out.front();
      out.erase(out.begin());
      if (o.found) protocolKnown = true;
      wireFree = std::max(o.at + o.lag, wireFree);
      wire.push_back({wireFree, o.text});
    }
    while (!wire.empty() && wire.front().at <= now) {
      const std::string text = wire.front().text;
      wire.erase(wire.begin());
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
  std::vector<uint8_t> values;
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
        values.push_back(k);
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
    const std::vector<std::string> start = {"ATZ", "ATE0", "ATS0", "ATH0", "ATSPA6", "010D1"};
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
  {  // key in ACC, engine computer silent: NO DATA is not a dongle failure (no resets); speeds once it answers
    ElmRun r;
    r.f.carAwake = false;
    r.c.connected(0, true);
    r.run(5000);
    CHECK(r.speeds == 0 && r.c.resets() == 1 && r.c.noData() >= 10 && r.c.failures() == 0,
          "NO DATA: %d speeds, %u resets, %u NO DATA, %u failures", r.speeds, (unsigned)r.c.resets(),
          (unsigned)r.c.noData(), (unsigned)r.c.failures());
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
  {  // a reply the Bluetooth link holds up past the timeout is not credited to the next request
    ElmRun r;
    r.c.connected(0, true);
    r.run(2000);
    r.f.kmh = 61;
    r.f.lagNext = 1100;
    const size_t n = r.sent.size();
    while (r.sent.size() == n) r.run(1);
    r.f.kmh = 30;
    r.values.clear();
    r.run(4000);
    const long stale = (long)std::count(r.values.begin(), r.values.end(), (uint8_t)61);
    CHECK(stale == 0 && !r.values.empty() && r.values.back() == 30, "late reply credited %ld times", stale);
  }
  {  // a clone with its own banner (no "ELM327" in it) is used like any other
    ElmRun r;
    r.f.banner = "OBDII to RS232 Interpreter";
    r.c.connected(0, true);
    r.run(4000);
    CHECK(r.speeds > 5 && r.c.resets() == 1, "odd banner: %d speeds, %u resets", r.speeds, (unsigned)r.c.resets());
  }
  {  // a clone that rejects ATSPA6 searches the protocols on the first request (2.5 s): the client waits for it
    ElmRun r;
    r.f.noSp6 = true;
    r.c.connected(0, true);
    r.run(8000);
    CHECK(r.speeds > 5 && r.c.resets() == 1, "protocol search: %d speeds, %u resets", r.speeds,
          (unsigned)r.c.resets());
  }
  {  // a car on 29-bit CAN IDs: protocol 6 doesn't answer, the automatic search (ATSPA6) finds protocol 7
    ElmRun r;
    r.f.car29 = true;
    r.c.connected(0, true);
    r.run(8000);
    CHECK(r.speeds > 5 && r.c.resets() == 1, "29-bit car: %d speeds, %u resets", r.speeds, (unsigned)r.c.resets());
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
