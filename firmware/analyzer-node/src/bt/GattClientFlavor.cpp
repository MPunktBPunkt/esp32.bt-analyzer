#include "bt/GattClientFlavor.h"

#include <stdio.h>
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

}  // namespace

void GattClientFlavor::reset() {
  state_ = GcState::Idle;
  last_err_[0] = 0;
  svc_n_ = char_n_ = desc_n_ = 0;
  found_cccd_ = 0;
  found_name_handle_ = 0;
  range_start_ = 0x0001;
  range_end_ = 0xffff;
  svc_idx_ = 0;
  // Keep lifetime stimulus counters across runs? Reset per discover for clarity.
  stimulus_tx_ = 0;
  stimulus_rx_ = 0;
}

const char *GattClientFlavor::stateName() const {
  switch (state_) {
  case GcState::Idle:
    return "idle";
  case GcState::Mtu:
    return "mtu";
  case GcState::DiscSvc:
    return "disc_svc";
  case GcState::DiscChar:
    return "disc_char";
  case GcState::DiscDesc:
    return "disc_desc";
  case GcState::Ready:
    return "ready";
  case GcState::Error:
    return "error";
  }
  return "unknown";
}

void GattClientFlavor::setError(const char *e) {
  strncpy(last_err_, e ? e : "error", sizeof(last_err_) - 1);
  last_err_[sizeof(last_err_) - 1] = 0;
  state_ = GcState::Error;
}

bool GattClientFlavor::txAtt(const uint8_t *att, uint16_t len) {
  if (!write_fn_ || !att || !len) {
    return false;
  }
  if (!write_fn_(write_ctx_, att, len)) {
    return false;
  }
  stimulus_tx_++;
  last_tx_ms_ = millis();
  return true;
}

bool GattClientFlavor::sendMtu() {
  uint8_t att[3] = {0x02, 0x00, 0x00};
  putU16(att + 1, want_mtu_);
  return txAtt(att, 3);
}

bool GattClientFlavor::sendDiscServices(uint16_t start) {
  // Read By Group Type Request — Primary Service 0x2800
  uint8_t att[7];
  att[0] = 0x10;
  putU16(att + 1, start);
  putU16(att + 3, 0xffff);
  putU16(att + 5, 0x2800);
  return txAtt(att, 7);
}

bool GattClientFlavor::sendDiscChars(uint16_t start, uint16_t end) {
  // Read By Type Request — Characteristic Declaration 0x2803
  uint8_t att[7];
  att[0] = 0x08;
  putU16(att + 1, start);
  putU16(att + 3, end);
  putU16(att + 5, 0x2803);
  return txAtt(att, 7);
}

bool GattClientFlavor::sendFindInfo(uint16_t start, uint16_t end) {
  uint8_t att[5];
  att[0] = 0x04;
  putU16(att + 1, start);
  putU16(att + 3, end);
  return txAtt(att, 5);
}

bool GattClientFlavor::startDiscover(uint16_t mtu) {
  reset();
  want_mtu_ = mtu >= 23 ? (mtu > 247 ? 247 : mtu) : 23;
  started_ms_ = millis();
  state_ = GcState::Mtu;
  if (!sendMtu()) {
    setError("mtu_tx");
    return false;
  }
  return true;
}

bool GattClientFlavor::readHandle(uint16_t handle) {
  if (handle == 0) {
    return false;
  }
  uint8_t att[3] = {0x0a, 0x00, 0x00};
  putU16(att + 1, handle);
  return txAtt(att, 3);
}

bool GattClientFlavor::writeHandle(uint16_t handle, const uint8_t *value,
                                   uint16_t value_len, bool with_response) {
  if (handle == 0 || !value || value_len == 0 || value_len > 244) {
    return false;
  }
  uint8_t att[3 + 244];
  att[0] = with_response ? 0x12 : 0x52;
  putU16(att + 1, handle);
  memcpy(att + 3, value, value_len);
  return txAtt(att, static_cast<uint16_t>(3 + value_len));
}

bool GattClientFlavor::confirmIndication() {
  uint8_t att[1] = {0x1e};
  return txAtt(att, 1);
}

bool GattClientFlavor::subscribeCccd(uint16_t cccd_handle, bool enable,
                                     bool indicate) {
  if (cccd_handle == 0) {
    return false;
  }
  uint8_t att[5] = {0x12, 0x00, 0x00, 0x00, 0x00};
  putU16(att + 1, cccd_handle);
  if (enable) {
    att[3] = indicate ? 0x02 : 0x01;  // Indicate vs Notify
  }
  att[4] = 0x00;
  return txAtt(att, 5);
}

void GattClientFlavor::advanceAfterServices() {
  if (svc_n_ == 0) {
    setError("no_services");
    return;
  }
  svc_idx_ = 0;
  state_ = GcState::DiscChar;
  char_range_end_ = svcs_[0].end;
  sendDiscChars(svcs_[0].start, svcs_[0].end);
}

void GattClientFlavor::advanceAfterChars() {
  // Find descriptors in each service range (CCCD etc.)
  svc_idx_ = 0;
  state_ = GcState::DiscDesc;
  sendFindInfo(svcs_[0].start, svcs_[0].end);
}

void GattClientFlavor::onAttPdu(const uint8_t *att, uint16_t len) {
  if (!att || len < 1) {
    return;
  }
  stimulus_rx_++;

  if (att[0] == 0x01 && len >= 5) {
    // Error Response — Attribute Not Found (0x0A) ends a discovery page.
    const uint8_t err = att[4];
    const uint16_t h = getU16(att + 1);
    (void)h;
    if (err == 0x0A) {
      if (state_ == GcState::DiscSvc) {
        advanceAfterServices();
        return;
      }
      if (state_ == GcState::DiscChar) {
        svc_idx_++;
        if (svc_idx_ < svc_n_) {
          sendDiscChars(svcs_[svc_idx_].start, svcs_[svc_idx_].end);
        } else {
          advanceAfterChars();
        }
        return;
      }
      if (state_ == GcState::DiscDesc) {
        svc_idx_++;
        if (svc_idx_ < svc_n_) {
          sendFindInfo(svcs_[svc_idx_].start, svcs_[svc_idx_].end);
        } else {
          state_ = GcState::Ready;
        }
        return;
      }
    }
    char buf[20];
    snprintf(buf, sizeof(buf), "att_err_%02x", err);
    setError(buf);
    return;
  }

  if (att[0] == 0x03 && len >= 3) {
    // Exchange MTU Response
    if (state_ == GcState::Mtu) {
      state_ = GcState::DiscSvc;
      sendDiscServices(0x0001);
    }
    return;
  }

  if (att[0] == 0x11 && len >= 2 && state_ == GcState::DiscSvc) {
    // Read By Group Type Response
    const uint8_t elen = att[1];
    if (elen < 6) {
      setError("svc_elen");
      return;
    }
    uint16_t last_end = 0;
    for (uint16_t off = 2; off + elen <= len; off = static_cast<uint16_t>(off + elen)) {
      if (svc_n_ >= kGcMaxServices) {
        break;
      }
      GcService &s = svcs_[svc_n_++];
      s.start = getU16(att + off);
      s.end = getU16(att + off + 2);
      s.uuid16 = (elen >= 6) ? getU16(att + off + 4) : 0;
      last_end = s.end;
    }
    if (last_end != 0 && last_end < 0xffff) {
      sendDiscServices(static_cast<uint16_t>(last_end + 1));
    } else {
      advanceAfterServices();
    }
    return;
  }

  if (att[0] == 0x09 && len >= 2 && state_ == GcState::DiscChar) {
    const uint8_t elen = att[1];
    if (elen < 7) {
      setError("char_elen");
      return;
    }
    uint16_t last_decl = 0;
    for (uint16_t off = 2; off + elen <= len; off = static_cast<uint16_t>(off + elen)) {
      if (char_n_ >= kGcMaxChars) {
        break;
      }
      GcChar &c = chars_[char_n_++];
      c.decl_handle = getU16(att + off);
      c.properties = att[off + 2];
      c.value_handle = getU16(att + off + 3);
      c.uuid16 = getU16(att + off + 5);
      last_decl = c.decl_handle;
      if (c.uuid16 == 0x2A00) {
        found_name_handle_ = c.value_handle;
      }
    }
    if (last_decl && last_decl < char_range_end_) {
      sendDiscChars(static_cast<uint16_t>(last_decl + 1), char_range_end_);
    } else {
      svc_idx_++;
      if (svc_idx_ < svc_n_) {
        char_range_end_ = svcs_[svc_idx_].end;
        sendDiscChars(svcs_[svc_idx_].start, svcs_[svc_idx_].end);
      } else {
        advanceAfterChars();
      }
    }
    return;
  }

  if (att[0] == 0x05 && len >= 2 && state_ == GcState::DiscDesc) {
    // Find Information Response: format 1 = 16-bit UUIDs
    const uint8_t fmt = att[1];
    if (fmt != 0x01) {
      // Skip 128-bit for MVP
      svc_idx_++;
      if (svc_idx_ < svc_n_) {
        sendFindInfo(svcs_[svc_idx_].start, svcs_[svc_idx_].end);
      } else {
        state_ = GcState::Ready;
      }
      return;
    }
    uint16_t last_h = 0;
    for (uint16_t off = 2; off + 4 <= len; off = static_cast<uint16_t>(off + 4)) {
      if (desc_n_ >= kGcMaxDescs) {
        break;
      }
      GcDesc &d = descs_[desc_n_++];
      d.handle = getU16(att + off);
      d.uuid16 = getU16(att + off + 2);
      last_h = d.handle;
      if (d.uuid16 == 0x2902 && found_cccd_ == 0) {
        found_cccd_ = d.handle;
      }
    }
    const uint16_t end = svcs_[svc_idx_].end;
    if (last_h && last_h < end) {
      sendFindInfo(static_cast<uint16_t>(last_h + 1), end);
    } else {
      svc_idx_++;
      if (svc_idx_ < svc_n_) {
        sendFindInfo(svcs_[svc_idx_].start, svcs_[svc_idx_].end);
      } else {
        state_ = GcState::Ready;
      }
    }
    return;
  }

  if (att[0] == 0x0b && len >= 2) {
    // Read Response — Device Name value for lab
    // handled via status gattName by OnchipBt if needed
    return;
  }

  if (att[0] == 0x13) {
    // Write Response (CCCD)
    return;
  }
}

void GattClientFlavor::poll() {
  if (state_ == GcState::Idle || state_ == GcState::Ready || state_ == GcState::Error) {
    return;
  }
  const uint32_t now = millis();
  if (started_ms_ && (now - started_ms_) > 15000) {
    setError("timeout");
    return;
  }
  // If MTU response never arrives, proceed to discovery anyway.
  if (state_ == GcState::Mtu && (now - last_tx_ms_) > 800) {
    state_ = GcState::DiscSvc;
    sendDiscServices(0x0001);
  }
}

const GcChar *GattClientFlavor::findCharUuid(uint16_t uuid16) const {
  for (uint8_t i = 0; i < char_n_; i++) {
    if (chars_[i].uuid16 == uuid16) {
      return &chars_[i];
    }
  }
  return nullptr;
}

const GcService *GattClientFlavor::findServiceUuid(uint16_t uuid16) const {
  for (uint8_t i = 0; i < svc_n_; i++) {
    if (svcs_[i].uuid16 == uuid16) {
      return &svcs_[i];
    }
  }
  return nullptr;
}

uint16_t GattClientFlavor::findCccdForValue(uint16_t value_handle) const {
  uint16_t best = 0;
  for (uint8_t i = 0; i < desc_n_; i++) {
    if (descs_[i].uuid16 != 0x2902) {
      continue;
    }
    if (descs_[i].handle > value_handle && descs_[i].handle <= value_handle + 8) {
      if (best == 0 || descs_[i].handle < best) {
        best = descs_[i].handle;
      }
    }
  }
  return best;
}

void GattClientFlavor::appendStatusJson(String &json) const {
  json += ",\"flavor\":{";
  json += "\"id\":\"gatt_client\"";
  json += ",\"state\":\"";
  json += stateName();
  json += "\",\"claim\":\"STIMULUS_L2_over_HCI_not_air\"";
  json += ",\"stimulusTx\":";
  json += String(stimulus_tx_);
  json += ",\"stimulusRx\":";
  json += String(stimulus_rx_);
  json += ",\"services\":";
  json += String(svc_n_);
  json += ",\"characteristics\":";
  json += String(char_n_);
  json += ",\"descriptors\":";
  json += String(desc_n_);
  json += ",\"cccdHandle\":";
  json += String(found_cccd_);
  json += ",\"nameHandle\":";
  json += String(found_name_handle_);
  if (last_err_[0]) {
    json += ",\"lastErr\":\"";
    json += last_err_;
    json += "\"";
  }
  json += ",\"svc\":[";
  for (uint8_t i = 0; i < svc_n_; i++) {
    if (i) {
      json += ",";
    }
    json += "{\"start\":";
    json += String(svcs_[i].start);
    json += ",\"end\":";
    json += String(svcs_[i].end);
    json += ",\"uuid\":\"0x";
    char hx[8];
    snprintf(hx, sizeof(hx), "%04X", svcs_[i].uuid16);
    json += hx;
    json += "\"}";
  }
  json += "],\"chr\":[";
  for (uint8_t i = 0; i < char_n_; i++) {
    if (i) {
      json += ",";
    }
    json += "{\"decl\":";
    json += String(chars_[i].decl_handle);
    json += ",\"value\":";
    json += String(chars_[i].value_handle);
    json += ",\"props\":";
    json += String(chars_[i].properties);
    json += ",\"uuid\":\"0x";
    char hx[8];
    snprintf(hx, sizeof(hx), "%04X", chars_[i].uuid16);
    json += hx;
    json += "\"}";
  }
  json += "]}";
}

}  // namespace bt_analyzer
