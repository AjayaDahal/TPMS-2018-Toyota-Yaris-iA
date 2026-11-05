#pragma once
#include <cstdint>

// Edge capture on a demodulated-data pin and a protocol-agnostic Manchester decoder, used to find out
// what a TPMS sensor sends before writing a protocol-specific decoder.
namespace rf {

constexpr int kMaxPulses = 1024;

struct Burst {
  uint16_t n = 0;               // number of pulses
  uint16_t us[kMaxPulses];      // pulse durations (microseconds)
  uint8_t firstLevel = 0;       // logic level of us[0]
};

struct Frame {
  uint16_t chipUs = 0;          // estimated chip (half-bit) length
  uint16_t nbits = 0;           // longest run of chip pairs that each contain a transition
  uint8_t man[64] = {};         // that run decoded as Manchester, MSB first: high-then-low pair = 1
  uint16_t ndman = 0;
  uint8_t dman[64] = {};        // same chips, pairs shifted by one, as differential Manchester: 1 = mid-bit transition
  uint16_t nchips = 0;          // raw chips of the whole burst (1 = high), for offline analysis
  uint8_t chips[128] = {};
};
// The chip stream alone cannot tell Manchester from differential Manchester (Toyota/Pacific-style FSK
// sensors use the latter), and the polarity may be inverted (FSK high/low tone): try all against a CRC.

void attach(int pin);           // capture edges on GDO0 or on the MX-05V input (re-attach to switch)
bool nextBurst(Burst& out);     // pulses separated by gaps shorter than ~2.5 ms
bool decode(const Burst& b, Frame& f);   // false if the burst does not look like 1-2 chip pulses
uint32_t edges();               // total edges seen (noise indicator)
uint32_t dropped();             // edges lost because the ring buffer was full

}  // namespace rf
