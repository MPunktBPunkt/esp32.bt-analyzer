#include "capture/BtacStream.h"

#include "ProjectConfig.h"

#include <string.h>

namespace bt_analyzer {

uint32_t BtacStream::crc32(const uint8_t *data, size_t len) {
  static uint32_t table[256];
  static bool ready = false;
  if (!ready) {
    for (uint32_t i = 0; i < 256; i++) {
      uint32_t c = i;
      for (int b = 0; b < 8; b++) {
        c = (c & 1u) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
      }
      table[i] = c;
    }
    ready = true;
  }
  uint32_t crc = 0xFFFFFFFFu;
  for (size_t i = 0; i < len; i++) {
    crc = table[(crc ^ data[i]) & 0xffu] ^ (crc >> 8);
  }
  return ~crc;
}

void BtacStream::begin() {
  started_ = true;
  port_ = static_cast<uint16_t>(BTAC_PORT);
  // Server starts in loop() once WiFi is up (module begin runs pre-WiFi).
}

void BtacStream::ensureListening() {
  if (!started_ || listening_) {
    return;
  }
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }
  server_.begin(port_);
  server_.setNoDelay(true);
  listening_ = true;
  Serial.printf("[btac] listen :%u\n", static_cast<unsigned>(port_));
}

void BtacStream::acceptIfNeeded() {
  if (!listening_) {
    return;
  }
  if (connected_ && client_.connected()) {
    return;
  }
  if (connected_) {
    client_.stop();
    connected_ = false;
  }
  WiFiClient c = server_.accept();
  if (!c) {
    return;
  }
  client_ = c;
  client_.setNoDelay(true);
  connected_ = true;
  stream_id_++;
  beginClientSession();
  Serial.printf("[btac] client %s stream_id=%u\n",
                client_.remoteIP().toString().c_str(),
                static_cast<unsigned>(stream_id_));
}

void BtacStream::beginClientSession() {
  have_last_seq_ = false;
  seq_gaps_session_ = 0;
  win_bytes_ = 0;
  fwd_bps_ = 0;
  rate_ms_ = millis();
  if (ring_) {
    ring_->beginSession();
  }
}

void BtacStream::pollRates() {
  const uint32_t now = millis();
  if (rate_ms_ == 0) {
    rate_ms_ = now;
    return;
  }
  const uint32_t dt = now - rate_ms_;
  if (dt < 1000) {
    return;
  }
  fwd_bps_ = (win_bytes_ * 1000u) / dt;
  win_bytes_ = 0;
  rate_ms_ = now;
}

bool BtacStream::writeExact(const uint8_t *data, size_t n) {
  size_t off = 0;
  const uint32_t deadline = millis() + 2000;
  while (off < n) {
    if (!connected_ || !client_.connected()) {
      return false;
    }
    const size_t w = client_.write(data + off, n - off);
    if (w == 0) {
      if (static_cast<int32_t>(deadline - millis()) < 0) {
        return false;
      }
      delay(1);
      continue;
    }
    off += w;
  }
  return true;
}

bool BtacStream::writeFrame(const CaptureFrame &f) {
  const uint16_t plen =
      f.length > kCaptureMaxPayload ? kCaptureMaxPayload : f.length;
  // Header
  txbuf_[0] = 'B';
  txbuf_[1] = 'T';
  txbuf_[2] = 'A';
  txbuf_[3] = 'C';
  txbuf_[4] = kVersion;
  txbuf_[5] = 0;  // flags
  txbuf_[6] = static_cast<uint8_t>(stream_id_ & 0xff);
  txbuf_[7] = static_cast<uint8_t>((stream_id_ >> 8) & 0xff);
  txbuf_[8] = static_cast<uint8_t>(f.seq & 0xff);
  txbuf_[9] = static_cast<uint8_t>((f.seq >> 8) & 0xff);
  txbuf_[10] = static_cast<uint8_t>((f.seq >> 16) & 0xff);
  txbuf_[11] = static_cast<uint8_t>((f.seq >> 24) & 0xff);
  for (int i = 0; i < 8; i++) {
    txbuf_[12 + i] = static_cast<uint8_t>((f.ts_us >> (8 * i)) & 0xff);
  }
  txbuf_[20] = static_cast<uint8_t>(f.dir);
  txbuf_[21] = static_cast<uint8_t>(f.type);
  txbuf_[22] = f.usb_endpoint;
  txbuf_[23] = 0;
  txbuf_[24] = static_cast<uint8_t>(plen & 0xff);
  txbuf_[25] = static_cast<uint8_t>((plen >> 8) & 0xff);
  if (plen) {
    memcpy(txbuf_ + kHeaderSize, f.payload, plen);
  }
  const uint32_t crc = crc32(txbuf_, kHeaderSize + plen);
  const size_t crc_off = kHeaderSize + plen;
  txbuf_[crc_off + 0] = static_cast<uint8_t>(crc & 0xff);
  txbuf_[crc_off + 1] = static_cast<uint8_t>((crc >> 8) & 0xff);
  txbuf_[crc_off + 2] = static_cast<uint8_t>((crc >> 16) & 0xff);
  txbuf_[crc_off + 3] = static_cast<uint8_t>((crc >> 24) & 0xff);

  const size_t total = kHeaderSize + plen + 4;
  if (!writeExact(txbuf_, total)) {
    send_fails_++;
    return false;
  }
  bytes_out_ += static_cast<uint32_t>(total);
  win_bytes_ += static_cast<uint32_t>(total);
  forwarded_++;
  return true;
}

void BtacStream::pumpClient() {
  if (!connected_ || !client_.connected() || !ring_) {
    if (connected_ && !client_.connected()) {
      connected_ = false;
    }
    return;
  }
  // Bound work per loop so WiFi/web stay responsive (BT6: drain harder).
  constexpr size_t kMaxPerLoop = 48;
  CaptureFrame f;
  for (size_t i = 0; i < kMaxPerLoop; i++) {
    if (!ring_->dequeue(f)) {
      break;
    }
    if (have_last_seq_ && f.seq > last_seq_ + 1) {
      const uint32_t g = f.seq - last_seq_ - 1;
      seq_gaps_ += g;
      seq_gaps_session_ += g;
    }
    last_seq_ = f.seq;
    have_last_seq_ = true;
    if (!writeFrame(f)) {
      client_.stop();
      connected_ = false;
      Serial.println("[btac] client write fail — closed");
      break;
    }
  }
}

void BtacStream::loop() {
  if (!started_) {
    return;
  }
  ensureListening();
  acceptIfNeeded();
  pumpClient();
  pollRates();
}

void BtacStream::appendStatusJson(String &json) const {
  json += ",\"btac\":{";
  json += "\"port\":";
  json += String(port_);
  json += ",\"version\":";
  json += String(kVersion);
  json += ",\"listening\":";
  json += listening_ ? "true" : "false";
  json += ",\"connected\":";
  json += clientConnected() ? "true" : "false";
  json += ",\"streamId\":";
  json += String(stream_id_);
  json += ",\"forwarded\":";
  json += String(forwarded_);
  json += ",\"bytes\":";
  json += String(bytes_out_);
  json += ",\"sendFails\":";
  json += String(send_fails_);
  json += ",\"seqGaps\":";
  json += String(seq_gaps_);
  json += ",\"seqGapsSession\":";
  json += String(seq_gaps_session_);
  json += ",\"fwdBps\":";
  json += String(fwd_bps_);
  json += "}";
}

}  // namespace bt_analyzer
