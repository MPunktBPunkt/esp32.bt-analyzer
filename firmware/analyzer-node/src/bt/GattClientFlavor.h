#pragma once

#include <Arduino.h>
#include <stdint.h>

namespace bt_analyzer {

/** Bounded GATT Client Flavor (BT18) — thin ATT over VHCI, not a full stack. */
static constexpr size_t kGcMaxServices = 8;
static constexpr size_t kGcMaxChars = 24;
static constexpr size_t kGcMaxDescs = 32;

struct GcService {
  uint16_t start = 0;
  uint16_t end = 0;
  uint16_t uuid16 = 0;
};

struct GcChar {
  uint16_t decl_handle = 0;
  uint16_t value_handle = 0;
  uint8_t properties = 0;
  uint16_t uuid16 = 0;
};

struct GcDesc {
  uint16_t handle = 0;
  uint16_t uuid16 = 0;
};

enum class GcState : uint8_t {
  Idle = 0,
  Mtu,
  DiscSvc,
  DiscChar,
  DiscDesc,
  Ready,
  Error,
};

/**
 * Central-side GATT Client FSM.
 * TX path goes through OnchipBt::writeAtt (caller-provided).
 * All TX counted as STIMULUS.
 */
class GattClientFlavor {
public:
  using WriteAttFn = bool (*)(void *ctx, const uint8_t *att, uint16_t len);

  void setWriter(WriteAttFn fn, void *ctx) {
    write_fn_ = fn;
    write_ctx_ = ctx;
  }

  void reset();
  bool startDiscover(uint16_t mtu);
  bool readHandle(uint16_t handle);
  bool writeHandle(uint16_t handle, const uint8_t *value, uint16_t value_len,
                   bool with_response = true);
  /** ATT Handle Value Confirmation (0x1E) after Indication. */
  bool confirmIndication();
  /** enable CCCD notify (bit0) and/or indicate (bit1). */
  bool subscribeCccd(uint16_t cccd_handle, bool enable, bool indicate = false);

  /** Feed ATT PDU from ACL (central RX). */
  void onAttPdu(const uint8_t *att, uint16_t len);

  void poll();  // timeouts / continue discovery ranges

  GcState state() const { return state_; }
  const char *stateName() const;
  uint32_t stimulusTx() const { return stimulus_tx_; }
  uint32_t stimulusRx() const { return stimulus_rx_; }
  uint8_t serviceCount() const { return svc_n_; }
  uint8_t charCount() const { return char_n_; }
  uint8_t descCount() const { return desc_n_; }
  const GcService *serviceAt(size_t i) const {
    return i < svc_n_ ? &svcs_[i] : nullptr;
  }
  const GcChar *charAt(size_t i) const {
    return i < char_n_ ? &chars_[i] : nullptr;
  }
  const GcDesc *descAt(size_t i) const {
    return i < desc_n_ ? &descs_[i] : nullptr;
  }
  uint16_t foundCccd() const { return found_cccd_; }
  uint16_t foundNameHandle() const { return found_name_handle_; }
  const char *lastError() const { return last_err_; }

  const GcChar *findCharUuid(uint16_t uuid16) const;
  const GcService *findServiceUuid(uint16_t uuid16) const;
  /** First CCCD handle strictly after value_handle within +8. */
  uint16_t findCccdForValue(uint16_t value_handle) const;

  void appendStatusJson(String &json) const;

private:
  WriteAttFn write_fn_ = nullptr;
  void *write_ctx_ = nullptr;
  GcState state_ = GcState::Idle;
  char last_err_[24]{};
  uint16_t want_mtu_ = 23;
  uint16_t range_start_ = 0x0001;
  uint16_t range_end_ = 0xffff;
  uint16_t char_range_end_ = 0xffff;
  size_t svc_idx_ = 0;
  uint32_t stimulus_tx_ = 0;
  uint32_t stimulus_rx_ = 0;
  uint32_t started_ms_ = 0;
  uint32_t last_tx_ms_ = 0;

  GcService svcs_[kGcMaxServices]{};
  uint8_t svc_n_ = 0;
  GcChar chars_[kGcMaxChars]{};
  uint8_t char_n_ = 0;
  GcDesc descs_[kGcMaxDescs]{};
  uint8_t desc_n_ = 0;
  uint16_t found_cccd_ = 0;
  uint16_t found_name_handle_ = 0;

  bool txAtt(const uint8_t *att, uint16_t len);
  bool sendMtu();
  bool sendDiscServices(uint16_t start);
  bool sendDiscChars(uint16_t start, uint16_t end);
  bool sendFindInfo(uint16_t start, uint16_t end);
  void setError(const char *e);
  void advanceAfterServices();
  void advanceAfterChars();
};

}  // namespace bt_analyzer
