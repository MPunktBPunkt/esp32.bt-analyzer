// Host test for firmware/analyzer-node/src/agent/H4Framer.h
//   c++ -std=c++17 -I ../../firmware/analyzer-node/src test_h4_framer.cpp && ./a.out

#include "agent/H4Framer.h"

#include <cstdio>
#include <cstdlib>
#include <vector>

using bt_analyzer::H4Framer;
using Framer = H4Framer<64>;

static int failures = 0;

#define CHECK(cond)                                              \
  do {                                                           \
    if (!(cond)) {                                               \
      std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #cond); \
      failures++;                                                \
    }                                                            \
  } while (0)

static std::vector<std::vector<uint8_t>> feed(Framer &f,
                                              const std::vector<uint8_t> &in,
                                              bool *error) {
  std::vector<std::vector<uint8_t>> out;
  *error = false;
  for (uint8_t b : in) {
    switch (f.push(b)) {
    case Framer::Result::Packet:
      out.emplace_back(f.data(), f.data() + f.size());
      f.reset();
      break;
    case Framer::Result::Error:
      *error = true;
      return out;
    case Framer::Result::NeedMore:
      break;
    }
  }
  return out;
}

int main() {
  Framer f;
  bool err = false;

  // HCI_Reset: command with zero-length payload.
  auto p = feed(f, {0x01, 0x03, 0x0c, 0x00}, &err);
  CHECK(!err && p.size() == 1 && p[0].size() == 4);

  // Command + ACL back to back, ACL length little-endian 0x0005.
  f.reset();
  p = feed(f, {0x01, 0x01, 0x10, 0x00, 0x02, 0x40, 0x20, 0x05, 0x00, 1, 2, 3, 4, 5},
           &err);
  CHECK(!err && p.size() == 2);
  CHECK(p.size() == 2 && p[1].size() == 10 && p[1][9] == 5);

  // Event: Command Complete with 4-byte payload, split across pushes.
  f.reset();
  p = feed(f, {0x04, 0x0e}, &err);
  CHECK(!err && p.empty());
  p = feed(f, {0x04, 0x01, 0x03, 0x0c, 0x00}, &err);
  CHECK(!err && p.size() == 1 && p[0].size() == 7);

  // SCO 1-byte length; ISO 14-bit length masks the flag bits.
  f.reset();
  p = feed(f, {0x03, 0x01, 0x00, 0x02, 0xaa, 0xbb}, &err);
  CHECK(!err && p.size() == 1 && p[0].size() == 6);
  f.reset();
  p = feed(f, {0x05, 0x01, 0x00, 0x01, 0xc0, 0x7f}, &err);
  CHECK(!err && p.size() == 1 && p[0].size() == 6);

  // Unknown type and oversize payload are errors.
  f.reset();
  feed(f, {0x07}, &err);
  CHECK(err);
  f.reset();
  feed(f, {0x02, 0x40, 0x20, 0xff, 0x00}, &err);
  CHECK(err);

  if (failures == 0) {
    std::printf("h4 framer: all checks passed\n");
  }
  return failures == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
