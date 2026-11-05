#include "bt/ProfileFlavors.h"

#include <string.h>

namespace bt_analyzer {

void HogpFlavor::reset() {
  state_ = 0;
  report_h_ = cccd_h_ = map_h_ = 0;
  map_len_ = 0;
  reports_ = 0;
  output_writes_ = 0;
  last_key_ = last_mod_ = 0;
  t0_ = 0;
}

const char *HogpFlavor::stateName() const {
  switch (state_) {
  case 0:
    return "idle";
  case 1:
    return "read_map";
  case 2:
    return "subscribe";
  case 3:
    return "ready";
  default:
    return "error";
  }
}

bool HogpFlavor::startAfterDiscover() {
  reset();
  if (!gc_ || gc_->state() != GcState::Ready) {
    state_ = 4;
    return false;
  }
  if (!gc_->findServiceUuid(0x1812)) {
    state_ = 4;
    return false;
  }
  const GcChar *rep = gc_->findCharUuid(0x2A4D);
  const GcChar *map = gc_->findCharUuid(0x2A4B);
  // Peer stub uses fixed handles if discovery truncated.
  report_h_ = rep ? rep->value_handle : 0x0016;
  map_h_ = map ? map->value_handle : 0x0014;
  cccd_h_ = gc_->findCccdForValue(report_h_);
  if (!cccd_h_) {
    cccd_h_ = 0x0017;
  }
  t0_ = millis();
  if (map_h_) {
    state_ = 1;
    return gc_->readHandle(map_h_);
  }
  state_ = 2;
  return gc_->subscribeCccd(cccd_h_, true);
}

void HogpFlavor::onAttPdu(const uint8_t *att, uint16_t len) {
  if (!att || len < 1) {
    return;
  }
  if (att[0] == 0x0b && state_ == 1) {
    map_len_ = static_cast<uint16_t>(len > 1 ? len - 1 : 0);
    state_ = 2;
    if (cccd_h_) {
      gc_->subscribeCccd(cccd_h_, true);
    } else {
      state_ = 4;
    }
    return;
  }
  if (att[0] == 0x13 && state_ == 2) {
    state_ = 3;
    return;
  }
  if (att[0] == 0x1b && len >= 5) {
    const uint16_t h = static_cast<uint16_t>(att[1] | (att[2] << 8));
    if (h == report_h_) {
      reports_++;
      // Boot-like: [mod][reserved][keycode…] after handle
      if (len >= 6) {
        last_mod_ = att[3];
        last_key_ = att[5];  // skip reserved
      }
      if (state_ == 2) {
        state_ = 3;  // notify implies CCCD took
      }
    }
  }
}

void HogpFlavor::poll() {
  if (state_ == 1 || state_ == 2) {
    if (t0_ && (millis() - t0_) > 8000) {
      state_ = 4;
    }
  }
}

bool HogpFlavor::writeOutput(const uint8_t *data, uint16_t len) {
  if (state_ != 3 || !gc_ || !report_h_ || !data || len == 0) {
    return false;
  }
  if (!gc_->writeHandle(report_h_, data, len, true)) {
    return false;
  }
  output_writes_++;
  return true;
}

void HogpFlavor::appendStatusJson(String &json) const {
  json += ",\"hogp\":{";
  json += "\"id\":\"hogp_host\"";
  json += ",\"state\":\"";
  json += stateName();
  json += "\",\"claim\":\"STIMULUS_HOGP_over_HCI_not_air\"";
  json += ",\"reportHandle\":";
  json += String(report_h_);
  json += ",\"cccdHandle\":";
  json += String(cccd_h_);
  json += ",\"reportMapLen\":";
  json += String(map_len_);
  json += ",\"reports\":";
  json += String(reports_);
  json += ",\"outputWrites\":";
  json += String(output_writes_);
  json += ",\"lastMod\":";
  json += String(last_mod_);
  json += ",\"lastKey\":";
  json += String(last_key_);
  json += "}";
}

void FtmsFlavor::reset() {
  state_ = 0;
  feat_h_ = ibd_h_ = cccd_h_ = cp_h_ = cp_cccd_h_ = 0;
  feature_lo_ = 0;
  notifies_ = 0;
  cp_indications_ = 0;
  last_cp_req_ = last_cp_result_ = 0;
  last_power_ = last_cadence_ = 0;
  t0_ = 0;
}

const char *FtmsFlavor::stateName() const {
  switch (state_) {
  case 0:
    return "idle";
  case 1:
    return "read_feat";
  case 2:
    return "subscribe";
  case 3:
    return "ready";
  default:
    return "error";
  }
}

bool FtmsFlavor::startAfterDiscover() {
  reset();
  if (!gc_ || gc_->state() != GcState::Ready) {
    state_ = 4;
    return false;
  }
  if (!gc_->findServiceUuid(0x1826)) {
    state_ = 4;
    return false;
  }
  const GcChar *feat = gc_->findCharUuid(0x2ACC);
  const GcChar *ibd = gc_->findCharUuid(0x2AD2);
  const GcChar *cp = gc_->findCharUuid(0x2AD9);
  ibd_h_ = ibd ? ibd->value_handle : 0x0024;
  feat_h_ = feat ? feat->value_handle : 0x0022;
  cp_h_ = cp ? cp->value_handle : 0x0027;
  cccd_h_ = gc_->findCccdForValue(ibd_h_);
  if (!cccd_h_) {
    cccd_h_ = 0x0025;
  }
  cp_cccd_h_ = gc_->findCccdForValue(cp_h_);
  if (!cp_cccd_h_) {
    cp_cccd_h_ = 0x0028;
  }
  t0_ = millis();
  if (feat_h_) {
    state_ = 1;
    return gc_->readHandle(feat_h_);
  }
  state_ = 2;
  return cccd_h_ != 0 && gc_->subscribeCccd(cccd_h_, true);
}

void FtmsFlavor::onAttPdu(const uint8_t *att, uint16_t len) {
  if (!att || len < 1) {
    return;
  }
  if (att[0] == 0x0b && state_ == 1 && len >= 5) {
    feature_lo_ = static_cast<uint32_t>(att[1] | (att[2] << 8) | (att[3] << 16) | (att[4] << 24));
    state_ = 2;
    if (cccd_h_) {
      gc_->subscribeCccd(cccd_h_, true);
    } else {
      state_ = 4;
    }
    return;
  }
  if (att[0] == 0x13 && state_ == 2) {
    state_ = 3;
    return;
  }
  if (att[0] == 0x1d && len >= 6) {
    // Handle Value Indication — Control Point response
    const uint16_t h = static_cast<uint16_t>(att[1] | (att[2] << 8));
    if (h == cp_h_) {
      cp_indications_++;
      // att: 1d | handle | 80 | reqOp | result
      last_cp_req_ = att[4];
      last_cp_result_ = att[5];
      gc_->confirmIndication();
    }
    return;
  }
  if (att[0] == 0x1b && len >= 5) {
    const uint16_t h = static_cast<uint16_t>(att[1] | (att[2] << 8));
    if (h != ibd_h_ || len < 7) {
      return;
    }
    notifies_++;
    const uint16_t flags = static_cast<uint16_t>(att[3] | (att[4] << 8));
    uint16_t off = 5;
    // More Data bit0 unused for our stub; Instantaneous Cadence bit2; Power bit6
    if (flags & 0x0004) {
      if (off + 2 <= len) {
        last_cadence_ = static_cast<uint16_t>(att[off] | (att[off + 1] << 8));
        off = static_cast<uint16_t>(off + 2);
      }
    }
    if (flags & 0x0040) {
      if (off + 2 <= len) {
        last_power_ = static_cast<uint16_t>(att[off] | (att[off + 1] << 8));
      }
    }
    if (state_ == 2) {
      state_ = 3;
    }
  }
}

bool FtmsFlavor::controlPointEnable(bool enable) {
  if (!gc_ || !cp_cccd_h_) {
    return false;
  }
  return gc_->subscribeCccd(cp_cccd_h_, enable, true);
}

bool FtmsFlavor::controlPointWrite(uint8_t opcode, const uint8_t *payload,
                                   uint16_t payload_len) {
  if (!gc_ || !cp_h_ || state_ != 3) {
    return false;
  }
  uint8_t buf[16];
  buf[0] = opcode;
  if (payload && payload_len) {
    if (payload_len > 15) {
      payload_len = 15;
    }
    memcpy(buf + 1, payload, payload_len);
  }
  return gc_->writeHandle(cp_h_, buf, static_cast<uint16_t>(1 + payload_len), true);
}

void FtmsFlavor::poll() {
  if (state_ == 1 || state_ == 2) {
    if (t0_ && (millis() - t0_) > 8000) {
      state_ = 4;
    }
  }
}

void FtmsFlavor::appendStatusJson(String &json) const {
  json += ",\"ftms\":{";
  json += "\"id\":\"ftms_client\"";
  json += ",\"state\":\"";
  json += stateName();
  json += "\",\"claim\":\"STIMULUS_FTMS_over_HCI_not_air\"";
  json += ",\"featureLo\":";
  json += String(feature_lo_);
  json += ",\"ibdHandle\":";
  json += String(ibd_h_);
  json += ",\"cccdHandle\":";
  json += String(cccd_h_);
  json += ",\"cpHandle\":";
  json += String(cp_h_);
  json += ",\"cpCccdHandle\":";
  json += String(cp_cccd_h_);
  json += ",\"notifies\":";
  json += String(notifies_);
  json += ",\"cpIndications\":";
  json += String(cp_indications_);
  json += ",\"lastCpReq\":";
  json += String(last_cp_req_);
  json += ",\"lastCpResult\":";
  json += String(last_cp_result_);
  json += ",\"lastCadence\":";
  json += String(last_cadence_);
  json += ",\"lastPower\":";
  json += String(last_power_);
  json += ",\"note\":\"Success_neq_Wirkung\"";
  json += "}";
}

}  // namespace bt_analyzer
