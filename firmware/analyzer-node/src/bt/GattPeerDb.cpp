#include "bt/GattPeerDb.h"

#include <stddef.h>
#include <string.h>

namespace bt_analyzer {
namespace {

void putU16(uint8_t *p, uint16_t v) {
  p[0] = static_cast<uint8_t>(v & 0xff);
  p[1] = static_cast<uint8_t>((v >> 8) & 0xff);
}

uint16_t getU16(const uint8_t *p) {
  return static_cast<uint16_t>(p[0] | (p[1] << 8));
}

// GAP 0x1800 @ 0x0001-0x0004 (BT16 thr value/CCCD)
// HID 0x1812 @ 0x0010-0x0018
// FTMS 0x1826 @ 0x0020-0x0028
constexpr uint16_t kGapStart = 0x0001, kGapEnd = 0x0004;
constexpr uint16_t kHidStart = 0x0010, kHidEnd = 0x0018;
constexpr uint16_t kFtmsStart = 0x0020, kFtmsEnd = 0x0028;

static const uint8_t kReportMap[] = {
    0x05, 0x01, 0x09, 0x06, 0xA1, 0x01, 0x85, 0x01, 0x05, 0x07, 0x19, 0xE0,
    0x29, 0xE7, 0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x08, 0x81, 0x02,
    0x95, 0x01, 0x75, 0x08, 0x81, 0x01, 0x95, 0x06, 0x75, 0x08, 0x15, 0x00,
    0x25, 0x65, 0x05, 0x07, 0x19, 0x00, 0x29, 0x65, 0x81, 0x00, 0xC0,
};

static const uint8_t kHidInfo[] = {0x11, 0x01, 0x00, 0x02};
// FTMS features: cadence + power present (simplified LE uint32 + uint32)
static const uint8_t kFtmsFeat[] = {0x14, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};

struct SvcPage {
  uint16_t start;
  uint16_t end;
  uint16_t uuid;
};

static const SvcPage kSvcs[] = {
    {kGapStart, kGapEnd, 0x1800},
    {kHidStart, kHidEnd, 0x1812},
    {kFtmsStart, kFtmsEnd, 0x1826},
};

struct CharDecl {
  uint16_t decl;
  uint8_t props;
  uint16_t value;
  uint16_t uuid;
  uint16_t svc_start;
  uint16_t svc_end;
};

static const CharDecl kChars[] = {
    {0x0002, 0x1e, 0x0003, 0x2A00, kGapStart, kGapEnd},
    {0x0011, 0x02, 0x0012, 0x2A4A, kHidStart, kHidEnd},  // HID Info Read
    {0x0013, 0x02, 0x0014, 0x2A4B, kHidStart, kHidEnd},  // Report Map Read
    {0x0015, 0x12, 0x0016, 0x2A4D, kHidStart, kHidEnd},  // Report Notify|Read
    {0x0021, 0x02, 0x0022, 0x2ACC, kFtmsStart, kFtmsEnd},  // Feature Read
    {0x0023, 0x10, 0x0024, 0x2AD2, kFtmsStart, kFtmsEnd},  // IBD Notify
    {0x0026, 0x28, 0x0027, 0x2AD9, kFtmsStart, kFtmsEnd},  // CP Write|Indicate
};

struct InfoRow {
  uint16_t h;
  uint16_t u;
};

static const InfoRow kInfo[] = {
    {0x0001, 0x2800}, {0x0002, 0x2803}, {0x0003, 0x2A00}, {0x0004, 0x2902},
    {0x0010, 0x2800}, {0x0011, 0x2803}, {0x0012, 0x2A4A}, {0x0013, 0x2803},
    {0x0014, 0x2A4B}, {0x0015, 0x2803}, {0x0016, 0x2A4D}, {0x0017, 0x2902},
    {0x0018, 0x2908}, {0x0020, 0x2800}, {0x0021, 0x2803}, {0x0022, 0x2ACC},
    {0x0023, 0x2803}, {0x0024, 0x2AD2}, {0x0025, 0x2902}, {0x0026, 0x2803},
    {0x0027, 0x2AD9}, {0x0028, 0x2902},
};

}  // namespace

const uint8_t *gattPeerReportMap(size_t *len) {
  if (len) {
    *len = sizeof(kReportMap);
  }
  return kReportMap;
}

const uint8_t *gattPeerHidInfo(size_t *len) {
  if (len) {
    *len = sizeof(kHidInfo);
  }
  return kHidInfo;
}

const uint8_t *gattPeerFtmsFeature(size_t *len) {
  if (len) {
    *len = sizeof(kFtmsFeat);
  }
  return kFtmsFeat;
}

bool gattPeerHandleRequest(uint8_t conn_role, const char *adv_name,
                           bool (*write_att)(void *, const uint8_t *, uint16_t),
                           void *ctx, const uint8_t *att, uint16_t att_len,
                           bool *hid_cccd_on, bool *ftms_cccd_on) {
  if (conn_role != 1 || !write_att || !att || att_len < 1) {
    return false;
  }
  auto reply = [&](const uint8_t *p, uint16_t n) -> bool {
    return write_att(ctx, p, n);
  };

  if (att[0] == 0x10 && att_len >= 7) {
    const uint16_t start = getU16(att + 1);
    const uint16_t uuid = getU16(att + 5);
    if (uuid != 0x2800) {
      uint8_t err[5] = {0x01, att[0], att[1], att[2], 0x06};
      return reply(err, 5);
    }
    for (const auto &s : kSvcs) {
      if (s.start >= start) {
        uint8_t rsp[8] = {0x11, 0x06};
        putU16(rsp + 2, s.start);
        putU16(rsp + 4, s.end);
        putU16(rsp + 6, s.uuid);
        return reply(rsp, 8);
      }
    }
    uint8_t err[5] = {0x01, 0x10, att[1], att[2], 0x0A};
    return reply(err, 5);
  }

  if (att[0] == 0x08 && att_len >= 7) {
    const uint16_t start = getU16(att + 1);
    const uint16_t end = getU16(att + 3);
    const uint16_t uuid = getU16(att + 5);
    if (uuid == 0x2803) {
      // Pack as many 7-byte char decls as fit (~3 under MTU 23).
      uint8_t rsp[2 + 7 * 3];
      rsp[0] = 0x09;
      rsp[1] = 0x07;
      uint16_t n = 2;
      for (const auto &c : kChars) {
        if (c.decl < start || c.decl > end) {
          continue;
        }
        if (n + 7 > sizeof(rsp)) {
          break;
        }
        putU16(rsp + n, c.decl);
        rsp[n + 2] = c.props;
        putU16(rsp + n + 3, c.value);
        putU16(rsp + n + 5, c.uuid);
        n = static_cast<uint16_t>(n + 7);
      }
      if (n == 2) {
        uint8_t err[5] = {0x01, 0x08, att[1], att[2], 0x0A};
        return reply(err, 5);
      }
      return reply(rsp, n);
    }
    if (uuid == 0x2A00) {
      return false;  // legacy OnchipBt name path
    }
    uint8_t err[5] = {0x01, 0x08, att[1], att[2], 0x0A};
    return reply(err, 5);
  }

  if (att[0] == 0x04 && att_len >= 5) {
    const uint16_t start = getU16(att + 1);
    const uint16_t end = getU16(att + 3);
    uint8_t rsp[2 + 4 * 8];
    rsp[0] = 0x05;
    rsp[1] = 0x01;
    uint16_t n = 2;
    for (const auto &r : kInfo) {
      if (r.h < start || r.h > end) {
        continue;
      }
      if (n + 4 > sizeof(rsp)) {
        break;
      }
      putU16(rsp + n, r.h);
      putU16(rsp + n + 2, r.u);
      n = static_cast<uint16_t>(n + 4);
    }
    if (n == 2) {
      uint8_t err[5] = {0x01, 0x04, att[1], att[2], 0x0A};
      return reply(err, 5);
    }
    return reply(rsp, n);
  }

  if (att[0] == 0x0A && att_len >= 3) {
    const uint16_t handle = getU16(att + 1);
    if (handle == 0x0003) {
      const char *name = adv_name && adv_name[0] ? adv_name : "bt-peer";
      const size_t nlen = strnlen(name, 20);
      uint8_t rsp[1 + 20];
      rsp[0] = 0x0b;
      memcpy(rsp + 1, name, nlen);
      return reply(rsp, static_cast<uint16_t>(1 + nlen));
    }
    if (handle == 0x0004 || handle == 0x0017 || handle == 0x0025 || handle == 0x0028) {
      uint8_t rsp[3] = {0x0b, 0x00, 0x00};
      return reply(rsp, 3);
    }
    if (handle == 0x0012) {
      size_t n = 0;
      const uint8_t *p = gattPeerHidInfo(&n);
      uint8_t rsp[1 + 8];
      rsp[0] = 0x0b;
      memcpy(rsp + 1, p, n);
      return reply(rsp, static_cast<uint16_t>(1 + n));
    }
    if (handle == 0x0014) {
      size_t n = 0;
      const uint8_t *p = gattPeerReportMap(&n);
      uint8_t rsp[1 + 64];
      rsp[0] = 0x0b;
      memcpy(rsp + 1, p, n);
      return reply(rsp, static_cast<uint16_t>(1 + n));
    }
    if (handle == 0x0016) {
      uint8_t rsp[9] = {0x0b, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
      return reply(rsp, 9);
    }
    if (handle == 0x0018) {
      uint8_t rsp[3] = {0x0b, 0x01, 0x01};  // report id 1, input
      return reply(rsp, 3);
    }
    if (handle == 0x0022) {
      size_t n = 0;
      const uint8_t *p = gattPeerFtmsFeature(&n);
      uint8_t rsp[1 + 8];
      rsp[0] = 0x0b;
      memcpy(rsp + 1, p, n);
      return reply(rsp, static_cast<uint16_t>(1 + n));
    }
    if (handle == 0x0024) {
      // flags cadence+power, cadence=180(=90rpm*2), power=150
      uint8_t rsp[8] = {0x0b, 0x44, 0x00, 0xb4, 0x00, 0x96, 0x00};
      return reply(rsp, 7);
    }
    if (handle == 0x0027) {
      uint8_t rsp[2] = {0x0b, 0x00};
      return reply(rsp, 2);
    }
    uint8_t err[5] = {0x01, 0x0A, att[1], att[2], 0x0A};
    return reply(err, 5);
  }

  // Write Request — CCCD / Control Point (leave 0x0003/0x0004 to BT16 thr path)
  if ((att[0] == 0x12 || att[0] == 0x52) && att_len >= 5) {
    const uint16_t handle = getU16(att + 1);
    if (handle == 0x0003 || handle == 0x0004) {
      return false;
    }
    if (handle == 0x0017 || handle == 0x0025 || handle == 0x0028) {
      const bool on = (att[3] & 0x01) != 0 || (att[3] & 0x02) != 0;
      if (handle == 0x0017 && hid_cccd_on) {
        *hid_cccd_on = on;
      }
      if (handle == 0x0025 && ftms_cccd_on) {
        *ftms_cccd_on = on;
      }
      if (att[0] == 0x12) {
        uint8_t rsp[1] = {0x13};
        return reply(rsp, 1);
      }
      return true;
    }
    if (handle == 0x0027) {
      // Control Point write → Indicate Success (0x80 result 0x01)
      if (att[0] == 0x12) {
        uint8_t wr[1] = {0x13};
        reply(wr, 1);
      }
      uint8_t ind[5] = {0x1d, 0x27, 0x00, 0x80, 0x01};
      return reply(ind, 5);
    }
  }

  return false;
}

}  // namespace bt_analyzer
