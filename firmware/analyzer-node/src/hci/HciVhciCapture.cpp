#include "hci/HciVhciCapture.h"

#include <esp_bt.h>
#include <esp_timer.h>
#include <string.h>

namespace bt_analyzer {

HciPacketType HciVhciCapture::typeFromH4(uint8_t t) {
  switch (t) {
  case 0x01: return HciPacketType::Command;
  case 0x02: return HciPacketType::Acl;
  case 0x03: return HciPacketType::Sco;
  case 0x04: return HciPacketType::Event;
  case 0x05: return HciPacketType::Iso;
  default:   return HciPacketType::Unknown;
  }
}

bool HciVhciCapture::begin() {
  if (!ring_) {
    Serial.println("[vhci] missing ring");
    return false;
  }
  // CaptureFrame ≈1 KiB; PSRAM: 512 for BT5/BT6 headroom. ESP32 D1: keep small.
  const size_t slots =
      (ESP.getPsramSize() > 0) ? 512 : 24;
  if (!ring_->begin(slots)) {
    return false;
  }
  Serial.println("[vhci] capture ring ready");
  return true;
}

void HciVhciCapture::enqueue(HciPacketType type, HciDirection dir,
                             uint8_t endpoint, const uint8_t *data,
                             size_t len) {
  if (!ring_ || !data || len == 0) {
    return;
  }
  CaptureFrame f;
  f.seq = 0;  // CaptureRing assigns on successful enqueue
  f.ts_us = static_cast<uint64_t>(esp_timer_get_time());
  f.dir = dir;
  f.type = type;
  f.usb_endpoint = endpoint;
  f.length = static_cast<uint16_t>(len > kCaptureMaxPayload ? kCaptureMaxPayload
                                                            : len);
  memcpy(f.payload, data, f.length);
  const bool ok = ring_->enqueue(f);
  noteRate(type, dir, f.length, ok);
}

void HciVhciCapture::onRecv(const uint8_t *data, uint16_t len) {
  if (!data || len == 0) {
    return;
  }
  const HciPacketType t = typeFromH4(data[0]);
  enqueue(t, HciDirection::ControllerToHost, 0, data, len);
  rx_++;
}

bool HciVhciCapture::injectRaw(HciPacketType type, HciDirection dir,
                               uint8_t endpoint, const uint8_t *data,
                               size_t len) {
  if (!data && len) {
    return false;
  }
  enqueue(type, dir, endpoint, data, len);
  inject_++;
  return true;
}

bool HciVhciCapture::writeH4(const uint8_t *data, size_t len) {
  if (!open_ok_ || !data || len == 0 || len > 1024) {
    send_fails_++;
    return false;
  }
  // Wait briefly for controller TX credit.
  for (int i = 0; i < 50; i++) {
    if (esp_vhci_host_check_send_available()) {
      break;
    }
    delay(1);
  }
  if (!esp_vhci_host_check_send_available()) {
    send_fails_++;
    return false;
  }
  esp_vhci_host_send_packet(const_cast<uint8_t *>(data),
                            static_cast<uint16_t>(len));
  enqueue(typeFromH4(data[0]), HciDirection::HostToController, 0, data, len);
  tx_++;
  return true;
}

bool HciVhciCapture::writeCommand(const uint8_t *cmd, size_t len) {
  if (!cmd || len == 0 || len + 1 > 256) {
    return false;
  }
  uint8_t buf[256];
  buf[0] = 0x01;
  memcpy(buf + 1, cmd, len);
  return writeH4(buf, len + 1);
}

void HciVhciCapture::noteRate(HciPacketType type, HciDirection dir,
                              uint16_t length, bool enqueued) {
  if (!enqueued) {
    return;
  }
  win_pkts_++;
  if (type != HciPacketType::Acl) {
    return;
  }
  if (dir == HciDirection::HostToController) {
    win_acl_tx_ += length;
  } else if (dir == HciDirection::ControllerToHost) {
    win_acl_rx_ += length;
  }
}

void HciVhciCapture::pollRates() {
  const uint32_t now = millis();
  if (rate_ms_ == 0) {
    rate_ms_ = now;
    return;
  }
  const uint32_t dt = now - rate_ms_;
  if (dt < 1000) {
    return;
  }
  acl_tx_bps_ = (win_acl_tx_ * 1000u) / dt;
  acl_rx_bps_ = (win_acl_rx_ * 1000u) / dt;
  pkt_ps_ = (win_pkts_ * 1000u) / dt;
  win_acl_tx_ = win_acl_rx_ = win_pkts_ = 0;
  rate_ms_ = now;
}

void HciVhciCapture::appendStatusJson(String &json) const {
  json += ",\"hciCapture\":{";
  json += "\"transport\":\"onchip_vhci\"";
  json += ",\"armed\":";
  json += open_ok_ ? "true" : "false";
  json += ",\"openOk\":";
  json += open_ok_ ? "true" : "false";
  json += ",\"eventCapture\":\"vhci\"";
  json += ",\"rx\":";
  json += String(rx_);
  json += ",\"tx\":";
  json += String(tx_);
  json += ",\"aclIn\":";
  json += String(rx_);  // UI compat
  json += ",\"cmdOut\":";
  json += String(tx_);
  json += ",\"inject\":";
  json += String(inject_);
  json += ",\"sendFails\":";
  json += String(send_fails_);
  json += ",\"aclTxBps\":";
  json += String(acl_tx_bps_);
  json += ",\"aclRxBps\":";
  json += String(acl_rx_bps_);
  json += ",\"pktPs\":";
  json += String(pkt_ps_);
  json += "}";
}

String HciVhciCapture::drainJsonl(size_t max_frames) {
  String out;
  if (!ring_) {
    return out;
  }
  CaptureFrame f;
  size_t n = 0;
  while (n < max_frames && ring_->dequeue(f)) {
    out += "{\"seq\":";
    out += String(f.seq);
    out += ",\"ts_us\":";
    char ts[32];
    snprintf(ts, sizeof(ts), "%llu", static_cast<unsigned long long>(f.ts_us));
    out += ts;
    out += ",\"dir\":\"";
    out += hciDirectionName(f.dir);
    out += "\",\"transport\":\"onchip_vhci\",\"type\":\"";
    out += hciPacketTypeName(f.type);
    out += "\",\"endpoint\":";
    out += String(f.usb_endpoint);
    out += ",\"length\":";
    out += String(f.length);
    out += ",\"payload_hex\":\"";
    for (uint16_t i = 0; i < f.length; i++) {
      char hx[3];
      snprintf(hx, sizeof(hx), "%02x", f.payload[i]);
      out += hx;
    }
    out += "\"}\n";
    n++;
  }
  return out;
}

}  // namespace bt_analyzer
