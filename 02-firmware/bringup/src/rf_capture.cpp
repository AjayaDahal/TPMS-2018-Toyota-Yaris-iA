// Edge capture on the demodulated-data pin (GDO0 or the MX-05V input) into bursts of pulse widths.
#include <Arduino.h>

#include "rf.h"

#include <algorithm>

#include "esp_timer.h"
#include "soc/gpio_reg.h"

namespace rf {
namespace {

constexpr uint32_t kRing = 4096;        // power of two
constexpr uint32_t kGapUs = 2500;       // a quiet period longer than this ends a burst
// RF-01 squelch hang time: the gate stays open this long after the last RSSI reading above the threshold. In Manchester
// OOK the RSSI can read at the noise floor on every "off" chip, so the hold outlasts a whole frame (EG53MA4: 120 bits
// of 246 us, ~30 ms): a frame that opens the gate in its preamble then passes intact however its RSSI readings fall.
// Simulated worst case (RSSI following the chips, readings every 0.5-1 ms): ~98 % of frames intact, against 2-5 % with
// the first gate's 5 ms hold and 2 ms readings.
constexpr uint32_t kGateHoldUs = 40000;
constexpr uint16_t kGlitchUs = 15;      // shorter pulses are folded into their neighbours
constexpr int kMinBurst = 40;           // shorter bursts are treated as noise

volatile uint16_t ring[kRing];          // bit 15: level of the pulse that just ended, bits 0-14: duration
volatile uint32_t head = 0, tail = 0, nEdges = 0, nDropped = 0;
volatile uint32_t lastEdgeUs = 0;
volatile uint32_t lastLevel = 0;        // input level after the last recorded edge
volatile uint32_t inReg = GPIO_IN_REG;  // GPIO_IN1_REG for GPIO32..39
volatile uint32_t inShift = 0;
volatile bool useGate = false;
volatile bool gateOpen = false;
volatile uint32_t lastGateHighUs = 0;
int attachedPin = -1;

Burst cur;
bool inBurst = false, mergeNext = false;

void IRAM_ATTR onEdge() {
  const uint32_t now = (uint32_t)esp_timer_get_time();
  if (useGate && !gateOpen && (uint32_t)(now - lastGateHighUs) > kGateHoldUs) {
    return;  // RF-01: ignore idle noise without touching lastEdgeUs so active bursts close cleanly
  }
  const uint32_t level = (*(volatile uint32_t*)inReg >> inShift) & 1;
  // A glitch shorter than the interrupt latency (the CC1101's asynchronous output has ~38 ns ones) is over by the
  // time the level is read: no edge, so the pulse/gap alternation stays intact and the time adds to the next edge.
  if (level == lastLevel) return;
  lastLevel = level;
  const uint32_t d = now - lastEdgeUs;
  lastEdgeUs = now;
  nEdges++;
  const uint32_t ended = level ^ 1;
  const uint32_t h = head, next = (h + 1) & (kRing - 1);
  if (next == tail) {
    nDropped++;
    return;
  }
  ring[h] = (uint16_t)((d > 0x7FFF ? 0x7FFF : d) | (ended << 15));
  head = next;
}

bool finish(Burst& out) {
  const bool ok = inBurst && cur.n >= kMinBurst;
  if (ok) out = cur;
  inBurst = false;
  mergeNext = false;
  cur.n = 0;
  return ok;
}

}  // namespace

void attach(int pin) {
  detach();
  pinMode(pin, INPUT);
  inReg = pin >= 32 ? GPIO_IN1_REG : GPIO_IN_REG;
  inShift = pin >= 32 ? pin - 32 : pin;
  head = tail = 0;
  inBurst = mergeNext = false;
  cur.n = 0;
  lastLevel = (uint32_t)digitalRead(pin);
  const uint32_t nowUs = (uint32_t)esp_timer_get_time();
  lastEdgeUs = nowUs;
  useGate = false;
  gateOpen = false;
  lastGateHighUs = nowUs - kGateHoldUs - 1;
  attachedPin = pin;
  attachInterrupt(digitalPinToInterrupt(pin), onEdge, CHANGE);
}

void setGate(bool open) {
  useGate = true;
  gateOpen = open;
  if (open) lastGateHighUs = (uint32_t)esp_timer_get_time();
}

void clearGate() {
  useGate = false;
  gateOpen = false;
}

void detach() {
  if (attachedPin >= 0) detachInterrupt(digitalPinToInterrupt(attachedPin));
  attachedPin = -1;
}

bool nextBurst(Burst& out) {
  while (tail != head) {
    const uint16_t e = ring[tail];
    tail = (tail + 1) & (kRing - 1);
    const uint16_t d = e & 0x7FFF;
    const uint8_t level = e >> 15;
    if (d >= kGapUs) {                     // a long quiet pulse closes the burst before it
      if (finish(out)) return true;
      continue;
    }
    if (!inBurst) {
      inBurst = true;
      cur.n = 0;
      cur.firstLevel = level;
    }
    if (cur.n > 0 && (d < kGlitchUs || mergeNext)) {
      // a glitch splits one pulse into three: fold the glitch and the pulse after it into the previous one
      cur.us[cur.n - 1] = (uint16_t)std::min<uint32_t>(0x7FFF, cur.us[cur.n - 1] + d);
      mergeNext = !mergeNext;
      continue;
    }
    if (cur.n < kMaxPulses) cur.us[cur.n++] = d;
  }
  if (inBurst) {
    // Sample lastEdgeUs before esp_timer_get_time() and verify no new edge arrived in the ring;
    // evaluating now before lastEdgeUs allows onEdge() to advance lastEdgeUs > now and wrap unsigned.
    const uint32_t last = lastEdgeUs;
    const uint32_t now = (uint32_t)esp_timer_get_time();
    if (tail == head && (int32_t)(now - last) > (int32_t)kGapUs) return finish(out);
  }
  return false;
}

uint32_t edges() { return nEdges; }
uint32_t dropped() { return nDropped; }

}  // namespace rf
