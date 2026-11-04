#pragma once

#include "bt/GattClientFlavor.h"
#include "bt/ProfileFlavors.h"
#include "capture/CaptureRing.h"
#include "hci/HciVhciCapture.h"

#include <Arduino.h>

namespace bt_analyzer {

static constexpr size_t kBtMaxDevices = 32;

struct BtSeenDevice {
  uint8_t addr[6]{};
  uint8_t addr_type = 0;  // 0=public, 1=random (BLE); Classic uses 0
  int8_t rssi = 0;
  char name[32]{};
  bool classic = false;
  bool ble = true;
  uint32_t last_seen_ms = 0;
};

/**
 * On-chip Bluetooth controller + thin VHCI host (no NimBLE/Bluedroid).
 * S3: BLE only. ESP32: Classic + BLE when CONFIG allows.
 */
class OnchipBt {
public:
  bool begin();
  void loop();

  bool ready() const { return ready_; }
  bool classicCapable() const { return classic_capable_; }
  bool bleCapable() const { return ble_capable_; }

  CaptureRing &ring() { return ring_; }
  HciVhciCapture &capture() { return cap_; }

  bool hciReset();
  bool setEventMasks();
  bool readLocalVersion();
  bool readBdAddr();
  bool leScanStart(bool active = true);
  bool leScanStop();
  /** GAP Peripheral: connectable undirected advertise with Complete Local Name. */
  bool leAdvertiseStart(const char *name = nullptr);
  bool leAdvertiseStop();
  bool classicInquiryStart();
  bool classicInquiryCancel();
  /** Classic discoverable (inquiry+page scan). ESP32 only. */
  bool classicDiscoverableStart();
  bool classicDiscoverableStop();
  /** addr_hex: "aa:bb:cc:dd:ee:ff", addr_type 0/1 for BLE */
  bool leConnect(const char *addr_hex, uint8_t addr_type = 0);
  bool leDisconnect();
  /**
   * L2 probe only: ATT Read By Type (UUID 0x2A00 Device Name) over HCI ACL.
   * Not a full GATT stack; not Air FACT.
   */
  bool gattReadDeviceName();
  /** BT18 GATT Client Flavor — discover services/chars/CCCD (STIMULUS). */
  bool gattClientDiscover(uint16_t mtu = 23);
  bool gattClientRead(uint16_t handle);
  bool gattClientSubscribe(uint16_t cccd_handle, bool enable);
  bool hogpStart();
  bool ftmsStart();
  /**
   * Peer peripheral fault injection (lab only).
   * mode: off|normal|slow|burst|gap|drop — drop = disconnect after N notifies.
   */
  bool peerFaultSet(const char *mode, uint16_t after_n = 8);
  const char *peerFaultMode() const;
  GattClientFlavor &gattClient() { return gatt_client_; }
  HogpFlavor &hogp() { return hogp_; }
  FtmsFlavor &ftms() { return ftms_; }
  /** Classic Write_Local_Name (0x0C13) — deepens BT10 discoverable identity. */
  bool classicSetLocalName(const char *name);

  /**
   * BT16 thin L2 throughput: ATT Notify (peripheral) or Write CMD (central).
   * payload_len = app bytes after [seq:u32][ts_us:u64] header (min 12).
   * pace_ms: min gap between ATT sends (0 = auto 8/12 by payload).
   */
  bool throughputStart(const char *mode, uint16_t payload_len, uint16_t mtu,
                       uint16_t pace_ms = 0);
  void throughputStop();
  bool throughputRunning() const { return thr_running_; }

  /** Exchange MTU Request (central) / respond as peripheral. */
  bool attExchangeMtu(uint16_t mtu);

  bool scanning() const { return le_scanning_ || classic_inquiry_; }
  bool advertising() const { return le_advertising_; }
  bool connected() const { return le_connected_; }
  uint16_t connHandle() const { return conn_handle_; }
  bool classicDiscoverable() const { return classic_discoverable_; }
  const char *gattName() const { return gatt_name_; }
  bool gattNameValid() const { return gatt_name_valid_; }
  uint16_t attMtu() const { return att_mtu_; }
  uint32_t appTxBps() const { return app_tx_bps_; }
  uint32_t appRxBps() const { return app_rx_bps_; }
  uint32_t appTxPackets() const { return app_tx_packets_; }
  uint32_t appRxPackets() const { return app_rx_packets_; }
  uint32_t appSeqGaps() const { return app_seq_gaps_; }
  uint32_t appReorder() const { return app_reorder_; }
  /** @deprecated use appSeqGaps() */
  uint32_t thrLoss() const { return app_seq_gaps_; }
  uint32_t thrReorder() const { return app_reorder_; }
  size_t deviceCount() const { return device_count_; }
  const BtSeenDevice *deviceAt(size_t i) const {
    return i < device_count_ ? &devices_[i] : nullptr;
  }

  void clearDevices() { device_count_ = 0; }

  void appendStatusJson(String &json) const;
  String devicesJson() const;

  /** Called from VHCI recv callback (static bridge). */
  void handleControllerPacket(uint8_t *data, uint16_t len);

private:
  CaptureRing ring_;
  HciVhciCapture cap_;
  GattClientFlavor gatt_client_{};
  HogpFlavor hogp_{};
  FtmsFlavor ftms_{};
  bool peer_hid_cccd_ = false;
  bool peer_ftms_cccd_ = false;
  uint32_t peer_notify_ms_ = 0;
  uint8_t peer_fault_mode_ = 0;  // 0 off/normal 1 slow 2 burst 3 gap 4 drop
  uint16_t peer_fault_after_n_ = 8;
  uint16_t peer_fault_count_ = 0;
  bool peer_fault_gap_skip_ = false;

  bool ready_ = false;
  bool begin_attempted_ = false;
  bool ble_capable_ = false;
  bool classic_capable_ = false;
  bool le_scanning_ = false;
  bool le_advertising_ = false;
  bool le_connected_ = false;
  bool classic_inquiry_ = false;
  bool classic_discoverable_ = false;
  bool reset_done_ = false;
  bool masks_done_ = false;
  uint16_t conn_handle_ = 0;
  uint8_t conn_role_ = 0xff;  // 0=master/central, 1=slave/peripheral
  uint8_t peer_addr_[6]{};
  uint8_t peer_addr_type_ = 0;
  bool peer_addr_valid_ = false;
  uint8_t bd_addr_[6]{};
  bool bd_addr_valid_ = false;
  char state_[24] = "idle";
  char last_err_[24]{};
  char adv_name_[28] = "bt-peer";
  char classic_name_[28] = "bt-classic-87";
  char gatt_name_[32]{};
  bool gatt_name_valid_ = false;
  uint32_t last_cmd_ms_ = 0;

  uint16_t att_mtu_ = 23;
  bool thr_running_ = false;
  bool thr_notify_ = true;  // false = write_cmd
  bool thr_cccd_enabled_ = false;
  uint16_t thr_payload_ = 20;
  uint32_t thr_seq_tx_ = 0;
  uint32_t thr_expect_rx_ = 0;
  bool thr_have_rx_ = false;
  uint32_t app_seq_gaps_ = 0;
  uint32_t app_reorder_ = 0;
  uint32_t app_tx_packets_ = 0;
  uint32_t app_rx_packets_ = 0;
  uint32_t thr_app_tx_ = 0;
  uint32_t thr_app_rx_ = 0;
  uint32_t win_app_tx_ = 0;
  uint32_t win_app_rx_ = 0;
  uint32_t app_tx_bps_ = 0;
  uint32_t app_rx_bps_ = 0;
  uint32_t app_rate_ms_ = 0;
  uint32_t thr_last_send_ms_ = 0;
  uint16_t thr_pace_ms_ = 0;  // 0 = auto

  // HCI ACL reassembly for ATT (PB continuation fragments).
  uint16_t acl_reasm_handle_ = 0xffff;
  uint16_t acl_reasm_len_ = 0;
  uint16_t acl_reasm_need_ = 0;
  uint8_t acl_reasm_buf_[512]{};

  BtSeenDevice devices_[kBtMaxDevices]{};
  size_t device_count_ = 0;

  void setState(const char *s);
  void upsertDevice(const uint8_t addr[6], uint8_t addr_type, int8_t rssi,
                    const char *name, bool classic, bool ble);
  void parseEvent(const uint8_t *h4, uint16_t len);
  void parseLeMeta(const uint8_t *evt, uint8_t evt_len);
  void parseInquiryResult(const uint8_t *params, uint8_t plen, bool with_rssi);
  void parseAclAtt(const uint8_t *h4, uint16_t len);
  void feedAclAtt(const uint8_t *l2cap_or_att, uint16_t len, bool has_l2cap_hdr);
  void pollAppRates();
  void thrPump();
  bool writeAtt(const uint8_t *att, uint16_t att_len);
  bool sendThrPayload();
  static bool writeAttBridge(void *ctx, const uint8_t *att, uint16_t len);

  static int vhciRecv(uint8_t *data, uint16_t len);
  static void vhciSendAvailable();
};

}  // namespace bt_analyzer
