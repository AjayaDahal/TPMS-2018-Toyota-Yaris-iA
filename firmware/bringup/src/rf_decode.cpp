// Protocol-agnostic burst decoder (no ESP32 dependencies, so it can be unit-tested on a PC).
#include <algorithm>
#include <cstdlib>
#include <cstring>

#include "rf.h"

namespace rf {

constexpr int kMinBurstPulses = 40;

bool decode(const Burst& b, Frame& f) {
  f = Frame();
  const int n = b.n;
  if (n < kMinBurstPulses) return false;

  // Chip length: the shortest common pulse. Take the 25th percentile and average its neighbourhood.
  static uint16_t sorted[kMaxPulses];
  memcpy(sorted, b.us, n * sizeof(uint16_t));
  std::sort(sorted, sorted + n);
  const uint32_t t0 = sorted[n / 4];
  if (t0 < 20) return false;
  uint32_t sum = 0, cnt = 0;
  for (int i = 0; i < n; i++) {
    if (sorted[i] * 100u >= t0 * 65u && sorted[i] * 100u <= t0 * 135u) {
      sum += sorted[i];
      cnt++;
    }
  }
  if (cnt == 0) return false;
  const uint32_t T = sum / cnt;

  // Manchester pulses are 1 or 2 chips long (sync words may use 3-4); expand the burst into chips.
  static uint8_t chips[kMaxPulses * 4];
  int nc = 0, good = 0;
  uint8_t level = b.firstLevel;
  for (int i = 0; i < n; i++, level ^= 1) {
    const uint32_t k = (b.us[i] + T / 2) / T;
    const int32_t err = (int32_t)b.us[i] - (int32_t)(k * T);
    if (k >= 1 && k <= 2 && std::abs(err) * 100 < (int32_t)T * 35) good++;
    const uint32_t kk = std::min<uint32_t>(std::max<uint32_t>(k, 1), 4);
    for (uint32_t j = 0; j < kk && nc < (int)sizeof(chips); j++) chips[nc++] = level;
  }
  if (good * 100 < n * 70) return false;   // not Manchester-like (noise, or another line code)

  f.nchips = (uint16_t)std::min<int>(nc, sizeof(f.chips) * 8);
  for (int i = 0; i < f.nchips; i++) {
    if (chips[i]) f.chips[i / 8] |= 0x80 >> (i % 8);
  }

  // Longest run of chip pairs with a transition in the middle, trying both pair alignments.
  int bestStart = 0, bestLen = 0;
  for (int phase = 0; phase < 2; phase++) {
    int start = phase, len = 0;
    for (int i = phase; i + 1 < nc; i += 2) {
      if (chips[i] != chips[i + 1]) {
        if (len == 0) start = i;
        if (++len > bestLen) {
          bestLen = len;
          bestStart = start;
        }
      } else {
        len = 0;
      }
    }
  }
  if (bestLen < 24) return false;
  f.chipUs = (uint16_t)T;
  f.nbits = (uint16_t)std::min<int>(bestLen, sizeof(f.man) * 8);
  for (int k = 0; k < f.nbits; k++) {
    if (chips[bestStart + 2 * k]) f.man[k / 8] |= 0x80 >> (k % 8);
  }
  // Differential Manchester uses the other pair alignment: the guaranteed transitions are the bit
  // boundaries and a mid-bit transition encodes the data. Start one chip before the run so its first and
  // last bits are kept.
  const int first = bestStart >= 1 ? bestStart - 1 : bestStart + 1;
  const int end = std::min(nc, bestStart + 2 * bestLen + 1);   // one chip past the run
  for (int i = first; i + 1 < end && f.ndman < (int)sizeof(f.dman) * 8; i += 2, f.ndman++) {
    if (chips[i] != chips[i + 1]) f.dman[f.ndman / 8] |= 0x80 >> (f.ndman % 8);
  }
  return true;
}

}  // namespace rf