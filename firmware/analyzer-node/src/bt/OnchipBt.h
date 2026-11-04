#pragma once

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
  /** Classic Write_Local_Name (0x0C13) — deepens BT10 discoverable identity. */
  bool classicSetLocalName(const char *name);

  bool scanning() const { return le_scanning_ || classic_inquiry_; }
  bool advertising() const { return le_advertising_; }
  bool connected() const { return le_connected_; }
  uint16_t connHandle() const { return conn_handle_; }
  bool classicDiscoverable() const { return classic_discoverable_; }
  const char *gattName() const { return gatt_name_; }
  bool gattNameValid() const { return gatt_name_valid_; }
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

  BtSeenDevice devices_[kBtMaxDevices]{};
  size_t device_count_ = 0;

  void setState(const char *s);
  void upsertDevice(const uint8_t addr[6], uint8_t addr_type, int8_t rssi,
                    const char *name, bool classic, bool ble);
  void parseEvent(const uint8_t *h4, uint16_t len);
  void parseLeMeta(const uint8_t *evt, uint8_t evt_len);
  void parseInquiryResult(const uint8_t *params, uint8_t plen, bool with_rssi);
  void parseAclAtt(const uint8_t *h4, uint16_t len);

  static int vhciRecv(uint8_t *data, uint16_t len);
  static void vhciSendAvailable();
};

}  // namespace bt_analyzer
