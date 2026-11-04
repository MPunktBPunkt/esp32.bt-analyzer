#pragma once

#include "capture/CaptureFrame.h"
#include "capture/CaptureRing.h"

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <WiFiServer.h>

namespace bt_analyzer {

/**
 * BTAC v1 TCP capture stream (Gate BT4).
 *
 * ESP listens; Debian connects and receives framed HCI captures.
 * While a client is connected the stream owns ring dequeues
 * (/api/capture/drain returns 409 btac_owns_ring).
 *
 * Wire (little-endian):
 *   magic[4]="BTAC" | ver:u8 | flags:u8 | stream_id:u16 | seq:u32 | ts_us:u64
 *   | dir:u8 | type:u8 | endpoint:u8 | reserved:u8 | length:u16
 *   | payload[length] | crc32:u32 (IEEE over header+payload)
 */
class BtacStream {
public:
  static constexpr uint16_t kDefaultPort = 9753;
  static constexpr uint8_t kVersion = 1;
  static constexpr size_t kHeaderSize = 26;

  void setRing(CaptureRing *ring) { ring_ = ring; }
  void setPort(uint16_t port) { port_ = port; }

  void begin();
  void loop();

  bool listening() const { return listening_; }
  bool clientConnected() const { return connected_; }
  uint16_t port() const { return port_; }
  uint16_t streamId() const { return stream_id_; }
  uint32_t forwarded() const { return forwarded_; }
  uint32_t bytesOut() const { return bytes_out_; }
  uint32_t sendFails() const { return send_fails_; }
  uint32_t seqGaps() const { return seq_gaps_; }
  uint32_t seqGapsSession() const { return seq_gaps_session_; }
  uint32_t fwdBps() const { return fwd_bps_; }

  void appendStatusJson(String &json) const;

  static uint32_t crc32(const uint8_t *data, size_t len);

private:
  CaptureRing *ring_ = nullptr;
  WiFiServer server_{};
  WiFiClient client_;
  uint16_t port_ = kDefaultPort;
  bool started_ = false;
  bool listening_ = false;
  bool connected_ = false;
  uint16_t stream_id_ = 0;
  uint32_t forwarded_ = 0;
  uint32_t bytes_out_ = 0;
  uint32_t send_fails_ = 0;
  uint32_t seq_gaps_ = 0;
  uint32_t seq_gaps_session_ = 0;
  uint32_t last_seq_ = 0;
  bool have_last_seq_ = false;
  uint32_t win_bytes_ = 0;
  uint32_t fwd_bps_ = 0;
  uint32_t rate_ms_ = 0;
  uint8_t txbuf_[kHeaderSize + kCaptureMaxPayload + 4]{};

  void ensureListening();
  void acceptIfNeeded();
  void beginClientSession();
  void pumpClient();
  void pollRates();
  bool writeFrame(const CaptureFrame &f);
  bool writeExact(const uint8_t *data, size_t n);
};

}  // namespace bt_analyzer
