// Host unit test for the burst decoders (no ESP32 needed). From firmware/bringup:
//   python -m ziglang c++ -std=c++17 -O2 -Isrc test/host/test_decode.cpp src/rf_decode.cpp src/eg53ma4.cpp -o test_decode.exe
// (any C++17 compiler works the same way). Exit code 0 = all tests passed.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <vector>

#include "eg53ma4.h"
#include "rf.h"

namespace {

int failures = 0;
#define CHECK(cond, ...)                                    \
  do {                                                      \
    if (!(cond)) {                                          \
      failures++;                                           \
      std::printf("FAIL line %d: ", __LINE__);              \
      std::printf(__VA_ARGS__);                             \
      std::printf("\n");                                    \
    }                                                       \
  } while (0)

using Bits = std::vector<int>;
std::mt19937 rng(1234);

Bits randomBits(int n) {
  Bits b;
  for (int i = 0; i < n; i++) b.push_back(rng() & 1);
  return b;
}

Bits manchester(const Bits& bits) {             // 1 = high-then-low
  Bits c;
  for (int b : bits) {
    c.push_back(b);
    c.push_back(!b);
  }
  return c;
}

Bits diffManchester(const Bits& bits) {         // biphase-mark: transition at every bit start, mid-bit for a 1
  Bits c;
  int level = 0;
  for (int b : bits) {
    level ^= 1;
    c.push_back(level);
    if (b) level ^= 1;
    c.push_back(level);
  }
  return c;
}

rf::Burst toBurst(const Bits& chips, int chipUs, int jitterPct, bool invert = false) {
  rf::Burst burst;
  burst.n = 0;
  burst.firstLevel = (uint8_t)(chips[0] ^ invert);
  std::uniform_int_distribution<int> jitter(-chipUs * jitterPct / 100, chipUs * jitterPct / 100);
  for (size_t i = 0; i < chips.size() && burst.n < rf::kMaxPulses;) {
    size_t k = i;
    while (k < chips.size() && chips[k] == chips[i]) k++;
    burst.us[burst.n++] = (uint16_t)std::max(1, (int)(k - i) * chipUs + jitter(rng));
    i = k;
  }
  return burst;
}

Bits unpack(const uint8_t* bytes, int n) {
  Bits v;
  for (int i = 0; i < n; i++) v.push_back((bytes[i / 8] >> (7 - i % 8)) & 1);
  return v;
}

bool contains(const Bits& hay, const Bits& needle) {
  return std::search(hay.begin(), hay.end(), needle.begin(), needle.end()) != hay.end();
}

Bits complement(Bits b) {
  for (int& x : b) x ^= 1;
  return b;
}

Bits concat(Bits a, const Bits& b) {
  a.insert(a.end(), b.begin(), b.end());
  return a;
}

void testManchester(int chipUs, int jitterPct, bool invert, const char* name) {
  const Bits data = randomBits(64);
  const Bits frame = concat(Bits(48, 0), data);  // GM/Schrader style: all-zero preamble, then data
  rf::Frame f;
  const bool ok = rf::decode(toBurst(manchester(frame), chipUs, jitterPct, invert), f);
  CHECK(ok, "%s: not decoded", name);
  if (!ok) return;
  CHECK(std::abs(f.chipUs - chipUs) * 100 <= chipUs * 5, "%s: chip %u us, expected %d", name, f.chipUs, chipUs);
  const Bits man = unpack(f.man, f.nbits);
  CHECK(contains(man, invert ? complement(data) : data), "%s: data bits not found in the Manchester output", name);
}

void testDiffManchester(int chipUs, int jitterPct, const char* name) {
  const Bits data = randomBits(72);              // Toyota/Pacific style FSK frame
  const Bits frame = concat(Bits(16, 0), data);
  rf::Frame f;
  const bool ok = rf::decode(toBurst(diffManchester(frame), chipUs, jitterPct), f);
  CHECK(ok, "%s: not decoded", name);
  if (!ok) return;
  CHECK(std::abs(f.chipUs - chipUs) * 100 <= chipUs * 5, "%s: chip %u us, expected %d", name, f.chipUs, chipUs);
  const Bits dman = unpack(f.dman, f.ndman);
  CHECK(contains(dman, data), "%s: data bits not found in the DMAN output", name);
}

void testNoiseRejected() {
  std::uniform_int_distribution<int> width(20, 1500);
  int accepted = 0;
  for (int trial = 0; trial < 200; trial++) {
    rf::Burst b;
    b.n = 300;
    b.firstLevel = 0;
    for (int i = 0; i < b.n; i++) b.us[i] = (uint16_t)width(rng);
    rf::Frame f;
    accepted += rf::decode(b, f);
  }
  CHECK(accepted <= 2, "random noise decoded %d/200 times", accepted);
}

void testShortBurstRejected() {
  rf::Frame f;
  CHECK(!rf::decode(toBurst(manchester(randomBits(12)), 100, 5), f), "a 12-bit burst must be rejected");
}

void testSyncViolationThenData() {
  // preamble, then a sync word that breaks Manchester (3 high + 3 low chips), then the data:
  // the longest valid run must be the data, not the preamble
  const Bits data = randomBits(80);
  Bits chips = manchester(Bits(24, 0));
  for (int c : {1, 1, 1, 0, 0, 0}) chips.push_back(c);
  chips = concat(chips, manchester(data));
  rf::Frame f;
  const bool ok = rf::decode(toBurst(chips, 100, 8), f);
  CHECK(ok, "sync frame: not decoded");
  if (ok) CHECK(contains(unpack(f.man, f.nbits), data), "sync frame: data bits not found after the sync word");
}

// ---- GM / Schrader EG53MA4: 120-bit message = hard-coded 0 + 39 sync bits + 10 payload bytes
Bits eg53Message(const uint8_t payload[10], int nbits = 120) {
  Bits bits = {0};
  bits = concat(bits, randomBits(39));
  for (int i = 0; i < 80; i++) bits.push_back((payload[i / 8] >> (7 - i % 8)) & 1);
  bits.resize(nbits);
  return bits;
}

// One or more messages, each starting and ending in carrier-off (the idle gap absorbs those chips),
// separated by gapUs of silence. Durations get +-jitterPct.
rf::Burst eg53Burst(const std::vector<Bits>& messages, int jitterPct, int gapUs = 1000) {
  std::vector<std::pair<int, int>> runs;   // (level, chips or -us for a fixed gap)
  for (size_t m = 0; m < messages.size(); m++) {
    Bits chips = manchester(messages[m]);
    std::vector<std::pair<int, int>> r;
    for (size_t i = 0; i < chips.size();) {
      size_t k = i;
      while (k < chips.size() && chips[k] == chips[i]) k++;
      r.push_back({chips[i], (int)(k - i)});
      i = k;
    }
    if (r.front().first == 0) r.erase(r.begin());
    if (r.back().first == 0) r.pop_back();
    if (m > 0) runs.push_back({0, -gapUs});
    runs.insert(runs.end(), r.begin(), r.end());
  }
  rf::Burst b;
  b.n = 0;
  b.firstLevel = 1;
  std::uniform_int_distribution<int> jitter(-123 * jitterPct / 100, 123 * jitterPct / 100);
  for (auto& run : runs) {
    const int us = run.second < 0 ? -run.second : run.second * 123 + jitter(rng);
    if (b.n < rf::kMaxPulses) b.us[b.n++] = (uint16_t)us;
  }
  return b;
}

void testEg53ma4() {
  uint8_t p[10] = {0x05, 0x8F, 0x20, 0x01, 0x12, 0x34, 0x56, 88, 77, 0};
  unsigned sum = 0;
  for (int i = 0; i < 9; i++) sum += p[i];
  p[9] = (uint8_t)sum;
  eg53ma4::Reading r[4];

  int n = eg53ma4::decode(eg53Burst({eg53Message(p)}, 10), r, 4);
  CHECK(n == 1, "EG53MA4: %d readings, expected 1", n);
  if (n == 1) {
    CHECK(r[0].id == 0x123456, "EG53MA4: id %06X", (unsigned)r[0].id);
    CHECK(r[0].kPa10 == 2200, "EG53MA4: %u x0.1 kPa, expected 2200 (88 x 2.5 kPa)", r[0].kPa10);
    CHECK(r[0].tempF == 77, "EG53MA4: %d F", r[0].tempF);
    CHECK(r[0].flags == 0x058F2001u, "EG53MA4: flags %08X", (unsigned)r[0].flags);
    CHECK(std::abs(eg53ma4::psi(r[0]) - 31.9f) < 0.1f, "EG53MA4: %.2f psi", eg53ma4::psi(r[0]));
  }

  n = eg53ma4::decode(eg53Burst({eg53Message(p), eg53Message(p)}, 10), r, 4);
  CHECK(n == 2, "EG53MA4: two repeats in one burst gave %d readings", n);

  uint8_t bad[10];
  std::copy(p, p + 10, bad);
  bad[9] ^= 0x01;
  CHECK(eg53ma4::decode(eg53Burst({eg53Message(bad)}, 10), r, 4) == 0, "EG53MA4: bad checksum accepted");
  CHECK(eg53ma4::decode(eg53Burst({eg53Message(p, 119)}, 10), r, 4) == 0, "EG53MA4: 119-bit message accepted");

  rf::Frame f;
  CHECK(rf::decode(eg53Burst({eg53Message(p)}, 10), f), "EG53MA4 burst not seen by the generic decoder");
}

}  // namespace

int main() {
  testManchester(123, 10, false, "OOK Manchester 123 us (EG53MA4)");
  testManchester(123, 10, true, "Manchester 123 us inverted");
  testManchester(52, 15, false, "FSK Manchester 52 us, 15% jitter");
  testDiffManchester(52, 15, "FSK differential Manchester 52 us (PMV-C210 timing)");
  testDiffManchester(100, 10, "FSK differential Manchester 100 us (PMV-107J timing)");
  testNoiseRejected();
  testShortBurstRejected();
  testSyncViolationThenData();
  testEg53ma4();
  std::printf(failures ? "%d FAILURE(S)\n" : "all decoder tests passed\n", failures);
  return failures ? 1 : 0;
}
