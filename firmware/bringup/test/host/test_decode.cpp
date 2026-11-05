// Host unit test for the burst decoder (no ESP32 needed). From firmware/bringup:
//   python -m ziglang c++ -std=c++17 -O2 -Isrc test/host/test_decode.cpp src/rf_decode.cpp -o test_decode.exe
// (any C++17 compiler works the same way). Exit code 0 = all tests passed.
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <vector>

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
  std::printf(failures ? "%d FAILURE(S)\n" : "all decoder tests passed\n", failures);
  return failures ? 1 : 0;
}
