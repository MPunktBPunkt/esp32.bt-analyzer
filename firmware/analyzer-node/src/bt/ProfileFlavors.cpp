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
  if (!cccd_h_ && report_h_) {
    cccd_h_ = static_cast<uint16_t>(report_h_ + 1);
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
  cp_use_indicate_ = false;
  ibd_cccd_cmd_sent_ = false;
  feature_lo_ = 0;
  notifies_ = 0;
  cp_indications_ = 0;
  last_cp_req_ = last_cp_result_ = 0;
  last_power_ = last_cadence_ = 0;
  t0_ = 0;
}

bool FtmsFlavor::subscribeIbd_() {
  if (!gc_ || !cccd_h_) {
    return false;
  }
  ibd_cccd_cmd_sent_ = false;
  // First try Write Request; poll() may retry as Write Command (Varon).
  return gc_->subscribeCccd(cccd_h_, true, false, true);
}

void FtmsFlavor::decodeIbd_(const uint8_t *val, uint16_t val_len) {
  // FTMS Indoor Bike Data — Instantaneous Speed is present when More Data (bit0) is clear
  // (esp32.ergo FtmsCodec / Hammer flags 0x0B54).
  if (!val || val_len < 2) {
    return;
  }
  const uint16_t flags = static_cast<uint16_t>(val[0] | (val[1] << 8));
  uint16_t off = 2;
  if ((flags & 0x0001) == 0) {
    if (off + 2 > val_len) {
      return;
    }
    off = static_cast<uint16_t>(off + 2);  // instantaneous speed
  }
  if (flags & 0x0002) {
    if (off + 2 > val_len) {
      return;
    }
    off = static_cast<uint16_t>(off + 2);  // average speed
  }
  if (flags & 0x0004) {
    if (off + 2 <= val_len) {
      last_cadence_ = static_cast<uint16_t>(val[off] | (val[off + 1] << 8));
      off = static_cast<uint16_t>(off + 2);
    }
  }
  if (flags & 0x0008) {
    if (off + 2 > val_len) {
      return;
    }
    off = static_cast<uint16_t>(off + 2);  // average cadence
  }
  if (flags & 0x0010) {
    if (off + 3 > val_len) {
      return;
    }
    off = static_cast<uint16_t>(off + 3);  // total distance u24
  }
  if (flags & 0x0020) {
    if (off + 2 > val_len) {
      return;
    }
    off = static_cast<uint16_t>(off + 2);  // resistance
  }
  if (flags & 0x0040) {
    if (off + 2 <= val_len) {
      last_power_ = static_cast<uint16_t>(val[off] | (val[off + 1] << 8));
    }
  }
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
  // Never fall back to stub handles 0x25/0x28 — those break real FTMS bikes
  // (TC174 IBD@54 → CCCD@55) when desc discovery was truncated.
  cccd_h_ = gc_->findCccdForValue(ibd_h_);
  cp_cccd_h_ = cp_h_ ? gc_->findCccdForValue(cp_h_) : 0;
  // Hammer Varon: 2AD9 is Notify (0x10), not Indicate — Spec deviation
  // (esp32.ergo FtmsClient::subscribeTo).
  cp_use_indicate_ = cp && (cp->properties & 0x20) != 0 && (cp->properties & 0x10) == 0;
  t0_ = millis();
  if (feat_h_) {
    state_ = 1;
    return gc_->readHandle(feat_h_);
  }
  state_ = 2;
  return subscribeIbd_();
}

void FtmsFlavor::onAttPdu(const uint8_t *att, uint16_t len) {
  if (!att || len < 1) {
    return;
  }
  if (att[0] == 0x0b && state_ == 1 && len >= 5) {
    feature_lo_ = static_cast<uint32_t>(att[1] | (att[2] << 8) | (att[3] << 16) | (att[4] << 24));
    state_ = 2;
    if (!subscribeIbd_()) {
      state_ = 4;
    }
    return;
  }
  if (att[0] == 0x13 && state_ == 2) {
    state_ = 3;
    return;
  }
  if (att[0] == 0x01 && state_ == 2 && len >= 5) {
    // CCCD Write Request failed (Varon: 0x0A on handle 55) — retry Write Command.
    const uint16_t h = static_cast<uint16_t>(att[2] | (att[3] << 8));
    if (h == cccd_h_ && !ibd_cccd_cmd_sent_ && gc_) {
      ibd_cccd_cmd_sent_ = true;
      gc_->subscribeCccd(cccd_h_, true, false, false);
      t0_ = millis();
    }
    return;
  }
  if ((att[0] == 0x1d || att[0] == 0x1b) && len >= 6) {
    // CP response: Indicate (spec) or Notify (Hammer Varon / esp32.ergo)
    const uint16_t h = static_cast<uint16_t>(att[1] | (att[2] << 8));
    if (h == cp_h_) {
      cp_indications_++;
      last_cp_req_ = att[4];
      last_cp_result_ = att[5];
      if (att[0] == 0x1d && gc_) {
        gc_->confirmIndication();
      }
      return;
    }
  }
  if (att[0] == 0x1b && len >= 5) {
    const uint16_t h = static_cast<uint16_t>(att[1] | (att[2] << 8));
    if (h != ibd_h_ || len < 7) {
      return;
    }
    notifies_++;
    decodeIbd_(att + 3, static_cast<uint16_t>(len - 3));
    if (state_ == 2) {
      state_ = 3;  // notify implies CCCD took
    }
  }
}

bool FtmsFlavor::controlPointEnable(bool enable) {
  if (!gc_ || !cp_cccd_h_) {
    return false;
  }
  // Prefer char props; Varon uses Notify. Retry Write Command like esp32.ergo.
  if (!gc_->subscribeCccd(cp_cccd_h_, enable, cp_use_indicate_, true)) {
    return false;
  }
  gc_->subscribeCccd(cp_cccd_h_, enable, cp_use_indicate_, false);
  return true;
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
  if (state_ == 2 && !ibd_cccd_cmd_sent_ && t0_ && (millis() - t0_) > 1200 && gc_ &&
      cccd_h_) {
    // No Write Response yet — esp32.ergo fallback path.
    ibd_cccd_cmd_sent_ = true;
    gc_->subscribeCccd(cccd_h_, true, false, false);
    t0_ = millis();
  }
  if (state_ == 1 || state_ == 2) {
    if (t0_ && (millis() - t0_) > 8000) {
      // Still useful if IBD already arrived; otherwise error.
      state_ = notifies_ > 0 ? 3 : 4;
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
