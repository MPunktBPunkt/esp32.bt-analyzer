#include "bt/OnchipBt.h"

#include "bt/GattPeerDb.h"
#include "core/DiagLog.h"

#include <esp_bt.h>
#include <esp_timer.h>
#include <nvs_flash.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>

#if CONFIG_IDF_TARGET_ESP32
#include <esp32-hal-bt.h>
#endif

#if defined(CONFIG_BT_BLUEDROID_ENABLED) && CONFIG_BT_BLUEDROID_ENABLED
#include <esp_bt_main.h>
#endif

namespace bt_analyzer {
namespace {

OnchipBt *g_self = nullptr;

bool parseAddrHex(const char *hex, uint8_t out[6]) {
  if (!hex) {
    return false;
  }
  unsigned b[6];
  if (sscanf(hex, "%02x:%02x:%02x:%02x:%02x:%02x", &b[0], &b[1], &b[2], &b[3],
             &b[4], &b[5]) != 6 &&
      sscanf(hex, "%02x%02x%02x%02x%02x%02x", &b[0], &b[1], &b[2], &b[3], &b[4],
             &b[5]) != 6) {
    return false;
  }
  for (int i = 0; i < 6; i++) {
    out[i] = static_cast<uint8_t>(b[i]);
  }
  return true;
}

void addrToStr(const uint8_t addr[6], char *out, size_t n) {
  snprintf(out, n, "%02x:%02x:%02x:%02x:%02x:%02x", addr[0], addr[1], addr[2],
           addr[3], addr[4], addr[5]);
}

void extractAdName(const uint8_t *ad, uint8_t ad_len, char *name, size_t name_n) {
  name[0] = 0;
  size_t i = 0;
  while (i + 1 < ad_len) {
    const uint8_t len = ad[i];
    if (len == 0 || i + len >= ad_len) {
      break;
    }
    const uint8_t type = ad[i + 1];
    if ((type == 0x08 || type == 0x09) && len >= 2) {
      const size_t copy = (len - 1 < name_n - 1) ? (len - 1) : (name_n - 1);
      memcpy(name, &ad[i + 2], copy);
      name[copy] = 0;
      return;
    }
    i += static_cast<size_t>(len) + 1;
  }
}

}  // namespace

int OnchipBt::vhciRecv(uint8_t *data, uint16_t len) {
  if (g_self) {
    g_self->handleControllerPacket(data, len);
  }
  return 0;
}

void OnchipBt::vhciSendAvailable() {}

void OnchipBt::setState(const char *s) {
  strncpy(state_, s ? s : "idle", sizeof(state_) - 1);
  state_[sizeof(state_) - 1] = 0;
}

bool OnchipBt::begin() {
  if (begin_attempted_) {
    return ready_;
  }
  begin_attempted_ = true;
  g_self = this;
  cap_.setRing(&ring_);
  last_err_[0] = 0;

  esp_err_t err = nvs_flash_init();
  if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    nvs_flash_erase();
    err = nvs_flash_init();
  }
  if (err != ESP_OK && err != ESP_ERR_NVS_NOT_INITIALIZED) {
    // Preferences may already have initialized NVS.
    DiagLog::printf("[bt] nvs_flash_init=%s (ok if already init)\n",
                    esp_err_to_name(err));
  }

#if CONFIG_IDF_TARGET_ESP32
  classic_capable_ = true;
  ble_capable_ = true;
#elif CONFIG_IDF_TARGET_ESP32S3 || CONFIG_IDF_TARGET_ESP32C3 || \
    CONFIG_IDF_TARGET_ESP32C6 || CONFIG_IDF_TARGET_ESP32H2
  classic_capable_ = false;
  ble_capable_ = true;
  // S3/C3 have no Classic controller — release that slice only.
  // Do NOT esp_bt_mem_release(BLE/BTDM): that frees the controller we need.
  esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT);
#else
  classic_capable_ = false;
  ble_capable_ = true;
#endif

  DiagLog::printf("[bt] pre-init heap=%u max=%u status=%d\n",
                  static_cast<unsigned>(ESP.getFreeHeap()),
                  static_cast<unsigned>(ESP.getMaxAllocHeap()),
                  static_cast<int>(esp_bt_controller_get_status()));

  esp_bt_controller_status_t st = esp_bt_controller_get_status();
  if (st == ESP_BT_CONTROLLER_STATUS_ENABLED) {
    DiagLog::printf("[bt] controller already enabled\n");
  } else {
#if CONFIG_IDF_TARGET_ESP32
    // Arduino helper sets cfg.mode correctly and waits for INITED.
    if (!btStartMode(BT_MODE_BTDM)) {
      DiagLog::printf("[bt] btStartMode(BTDM) failed heap=%u — try BLE\n",
                      static_cast<unsigned>(ESP.getFreeHeap()));
      if (esp_bt_controller_get_status() != ESP_BT_CONTROLLER_STATUS_IDLE) {
        esp_bt_controller_disable();
        esp_bt_controller_deinit();
      }
      esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT);
      if (!btStartMode(BT_MODE_BLE)) {
        snprintf(last_err_, sizeof(last_err_), "btStart_BLE");
        DiagLog::printf("[bt] btStartMode(BLE) failed heap=%u max=%u\n",
                        static_cast<unsigned>(ESP.getFreeHeap()),
                        static_cast<unsigned>(ESP.getMaxAllocHeap()));
        setState("init_fail");
        return false;
      }
      classic_capable_ = false;
      DiagLog::printf("[bt] BLE-only fallback OK\n");
    }
#else
    if (st != ESP_BT_CONTROLLER_STATUS_IDLE) {
      DiagLog::printf("[bt] controller status=%d — deinit first\n", (int)st);
      esp_bt_controller_disable();
      esp_bt_controller_deinit();
    }
    esp_bt_controller_config_t cfg = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
    err = esp_bt_controller_init(&cfg);
    if (err != ESP_OK) {
      snprintf(last_err_, sizeof(last_err_), "%s", esp_err_to_name(err));
      DiagLog::printf("[bt] controller_init failed: %s heap=%u\n",
                      last_err_, static_cast<unsigned>(ESP.getFreeHeap()));
      setState("init_fail");
      return false;
    }
    err = esp_bt_controller_enable(ESP_BT_MODE_BLE);
    if (err != ESP_OK) {
      snprintf(last_err_, sizeof(last_err_), "%s", esp_err_to_name(err));
      DiagLog::printf("[bt] controller_enable failed: %s\n", last_err_);
      setState("enable_fail");
      return false;
    }
#endif
  }

  // Ring after controller so ESP32 DRAM is free during BTDM bring-up.
  if (!cap_.begin()) {
    setState("ring_fail");
    return false;
  }

  // Controller-only VHCI host — tear down Bluedroid if a sketch linked it.
#if defined(CONFIG_BT_BLUEDROID_ENABLED) && CONFIG_BT_BLUEDROID_ENABLED
  if (esp_bluedroid_get_status() == ESP_BLUEDROID_STATUS_ENABLED) {
    esp_bluedroid_disable();
  }
  if (esp_bluedroid_get_status() == ESP_BLUEDROID_STATUS_INITIALIZED) {
    esp_bluedroid_deinit();
  }
#endif

  static const esp_vhci_host_callback_t cb = {
      .notify_host_send_available = OnchipBt::vhciSendAvailable,
      .notify_host_recv = OnchipBt::vhciRecv,
  };
  err = esp_vhci_host_register_callback(&cb);
  if (err != ESP_OK) {
    Serial.printf("[bt] vhci_register failed: %s\n", esp_err_to_name(err));
    setState("vhci_fail");
    return false;
  }

  cap_.setOpenOk(true);
  ready_ = true;
  gatt_client_.setWriter(&OnchipBt::writeAttBridge, this);
  hogp_.bind(&gatt_client_);
  ftms_.bind(&gatt_client_);
  setState("ready");
  Serial.printf("[bt] on-chip ready ble=%d classic=%d transport=onchip_vhci\n",
                ble_capable_ ? 1 : 0, classic_capable_ ? 1 : 0);

  delay(50);
  hciReset();
  return true;
}

bool OnchipBt::writeAttBridge(void *ctx, const uint8_t *att, uint16_t len) {
  auto *self = static_cast<OnchipBt *>(ctx);
  return self && self->writeAtt(att, len);
}

void OnchipBt::loop() {
  // After HCI Reset: event masks (LE Meta on ESP32 BTDM), then version/addr.
  if (ready_ && reset_done_ && !masks_done_ &&
      (millis() - last_cmd_ms_ > 80)) {
    setEventMasks();
    masks_done_ = true;
    delay(20);
    readLocalVersion();
    delay(20);
    readBdAddr();
  }
  cap_.pollRates();
  pollAppRates();
  thrPump();
  gatt_client_.poll();
  hogp_.poll();
  ftms_.poll();
  // Peer: emit HID / FTMS notifies when CCCD enabled (lab stimulus).
  if (conn_role_ == 1 && le_connected_ && (peer_hid_cccd_ || peer_ftms_cccd_)) {
    const uint32_t now = millis();
    if (now - peer_notify_ms_ >= 500) {
      peer_notify_ms_ = now;
      if (peer_hid_cccd_) {
        // Handle Value Notification report handle 0x0016: mod=0 key='A'(0x04)
        uint8_t ntf[3 + 8] = {0x1b, 0x16, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00,
                              0x00, 0x00, 0x00};
        writeAtt(ntf, 11);
      }
      if (peer_ftms_cccd_) {
        // IBD flags cadence+power, cadence=180, power=150
        uint8_t ntf[3 + 6] = {0x1b, 0x24, 0x00, 0x44, 0x00, 0xb4, 0x00, 0x96, 0x00};
        writeAtt(ntf, 9);
      }
    }
  }
}

void OnchipBt::handleControllerPacket(uint8_t *data, uint16_t len) {
  cap_.onRecv(data, len);
  if (!data || len < 2) {
    return;
  }
  if (data[0] == 0x04) {
    parseEvent(data, len);
  } else if (data[0] == 0x02) {
    parseAclAtt(data, len);
  }
}

void OnchipBt::parseEvent(const uint8_t *h4, uint16_t len) {
  // H4: 04 evt_code plen params...
  if (len < 3) {
    return;
  }
  const uint8_t code = h4[1];
  const uint8_t plen = h4[2];
  if (len < static_cast<uint16_t>(3 + plen)) {
    return;
  }
  const uint8_t *p = h4 + 3;

  if (code == 0x0e && plen >= 4) {
    // Command Complete: Num, OpCode(2), Status, Return...
    const uint16_t opcode = static_cast<uint16_t>(p[1] | (p[2] << 8));
    const uint8_t status = p[3];
    if (opcode == 0x0c03) {  // Reset
      reset_done_ = (status == 0);
      setState(reset_done_ ? "reset_ok" : "reset_fail");
    } else if (opcode == 0x1001 && status == 0 && plen >= 10) {
      // Read Local Version Information return params after status
    } else if (opcode == 0x1009 && status == 0 && plen >= 10) {
      // Read BD_ADDR return is little-endian → store MSB-first for display
      for (int i = 0; i < 6; i++) {
        bd_addr_[i] = p[4 + (5 - i)];
      }
      bd_addr_valid_ = true;
      setState("addr_ok");
    } else if (opcode == 0x200c) {  // LE Set Scan Enable
      if (status == 0) {
        // infer from last intent via le_scanning_ already set
      }
    }
  } else if (code == 0x3e) {
    parseLeMeta(p, plen);
  } else if (code == 0x02 || code == 0x2f) {
    parseInquiryResult(p, plen, code == 0x2f);
  } else if (code == 0x01) {
    classic_inquiry_ = false;
    if (!le_scanning_ && !le_advertising_ && !le_connected_) {
      setState("idle");
    }
  } else if (code == 0x05 && plen >= 4) {
    // Disconnection Complete: status, handle[2], reason
    const uint16_t handle = static_cast<uint16_t>(p[1] | (p[2] << 8));
    if (le_connected_ && handle == conn_handle_) {
      le_connected_ = false;
      conn_handle_ = 0;
      peer_addr_valid_ = false;
      setState("idle");
    }
  }
}

void OnchipBt::parseLeMeta(const uint8_t *evt, uint8_t evt_len) {
  if (evt_len < 2) {
    return;
  }
  const uint8_t sub = evt[0];
  if (sub == 0x01) {
    // LE Connection Complete: status, handle[2], role, peer_type, peer[6], ...
    if (evt_len < 19) {
      return;
    }
    const uint8_t status = evt[1];
    if (status == 0) {
      conn_handle_ = static_cast<uint16_t>(evt[2] | (evt[3] << 8));
      conn_role_ = evt[4];
      peer_addr_type_ = evt[5];
      for (int i = 0; i < 6; i++) {
        peer_addr_[i] = evt[6 + (5 - i)];
      }
      peer_addr_valid_ = true;
      le_connected_ = true;
      le_scanning_ = false;
      le_advertising_ = false;
      gatt_name_valid_ = false;
      thr_cccd_enabled_ = false;
      thr_running_ = false;
      att_mtu_ = 23;
      setState(conn_role_ == 1 ? "le_connected_periph" : "le_connected");
    } else {
      le_connected_ = false;
      setState("le_conn_fail");
    }
    return;
  }
  if (sub != 0x02) {
    return;  // Advertising Report
  }
  const uint8_t num = evt[1];
  size_t off = 2;
  for (uint8_t n = 0; n < num && off + 8 <= evt_len; n++) {
    // event_type, addr_type, addr[6], data_len, data, rssi
    const uint8_t addr_type = evt[off + 1];
    const uint8_t *addr = &evt[off + 2];
    const uint8_t dlen = evt[off + 8];
    if (off + 9 + dlen > evt_len) {
      break;
    }
    const uint8_t *ad = &evt[off + 9];
    const int8_t rssi = static_cast<int8_t>(evt[off + 9 + dlen]);
    char name[32];
    extractAdName(ad, dlen, name, sizeof(name));
    // HCI reports address little-endian; store as display big-endian (MSB first)
    uint8_t be[6];
    for (int i = 0; i < 6; i++) {
      be[i] = addr[5 - i];
    }
    upsertDevice(be, addr_type, rssi, name, false, true);
    off += 10 + dlen;
  }
}

void OnchipBt::parseInquiryResult(const uint8_t *params, uint8_t plen,
                                  bool with_rssi) {
  if (plen < 1) {
    return;
  }
  const uint8_t num = params[0];
  size_t off = 1;
  const size_t stride = with_rssi ? 14 : 14;  // addr6 + psrep1 + class3 + clk2 [+rssi]
  // Inquiry Result: BD_ADDR[6], PageScan*, Class[3], ClockOffset[2]
  // Inquiry Result with RSSI: + RSSI
  for (uint8_t n = 0; n < num; n++) {
    const size_t need = with_rssi ? 14 : 13;
    if (off + need > plen) {
      break;
    }
    const uint8_t *addr = &params[off];
    uint8_t be[6];
    for (int i = 0; i < 6; i++) {
      be[i] = addr[5 - i];
    }
    int8_t rssi = 0;
    if (with_rssi) {
      rssi = static_cast<int8_t>(params[off + 13]);
    }
    upsertDevice(be, 0, rssi, "", true, false);
    off += with_rssi ? 14 : 13;
    (void)stride;
  }
}

void OnchipBt::upsertDevice(const uint8_t addr[6], uint8_t addr_type,
                            int8_t rssi, const char *name, bool classic,
                            bool ble) {
  for (size_t i = 0; i < device_count_; i++) {
    if (memcmp(devices_[i].addr, addr, 6) == 0) {
      devices_[i].rssi = rssi;
      devices_[i].addr_type = addr_type;
      devices_[i].last_seen_ms = millis();
      if (classic) {
        devices_[i].classic = true;
      }
      if (ble) {
        devices_[i].ble = true;
      }
      if (name && name[0] && (!devices_[i].name[0] || name[0])) {
        strncpy(devices_[i].name, name, sizeof(devices_[i].name) - 1);
      }
      return;
    }
  }
  if (device_count_ >= kBtMaxDevices) {
    return;
  }
  BtSeenDevice &d = devices_[device_count_++];
  memcpy(d.addr, addr, 6);
  d.addr_type = addr_type;
  d.rssi = rssi;
  d.classic = classic;
  d.ble = ble;
  d.last_seen_ms = millis();
  d.name[0] = 0;
  if (name && name[0]) {
    strncpy(d.name, name, sizeof(d.name) - 1);
  }
}

bool OnchipBt::hciReset() {
  // HCI Reset: opcode 0x0C03, plen 0
  const uint8_t cmd[] = {0x03, 0x0c, 0x00};
  last_cmd_ms_ = millis();
  masks_done_ = false;
  setState("resetting");
  return cap_.writeCommand(cmd, sizeof(cmd));
}

bool OnchipBt::setEventMasks() {
  // HCI_Set_Event_Mask (0x0C01): enable LE Meta Event (bit 61) + common events.
  // Default post-reset mask omits LE Meta on classic ESP32 BTDM.
  const uint8_t ev[] = {0x01, 0x0c, 0x08, 0xff, 0xff, 0xff, 0xff,
                        0xff, 0xff, 0xbf, 0x3d};
  if (!cap_.writeCommand(ev, sizeof(ev))) {
    return false;
  }
  delay(20);
  // HCI_LE_Set_Event_Mask (0x2001): Adv Report + Connection events.
  const uint8_t le[] = {0x01, 0x20, 0x08, 0x1f, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00};
  if (!cap_.writeCommand(le, sizeof(le))) {
    return false;
  }
  delay(20);
  // Write Inquiry Mode (0x0C45) = 1 → Inquiry Result with RSSI (0x2F).
  if (classic_capable_) {
    const uint8_t inq[] = {0x45, 0x0c, 0x01, 0x01};
    cap_.writeCommand(inq, sizeof(inq));
  }
  last_cmd_ms_ = millis();
  return true;
}

bool OnchipBt::readLocalVersion() {
  const uint8_t cmd[] = {0x01, 0x10, 0x00};
  last_cmd_ms_ = millis();
  return cap_.writeCommand(cmd, sizeof(cmd));
}

bool OnchipBt::readBdAddr() {
  const uint8_t cmd[] = {0x09, 0x10, 0x00};
  last_cmd_ms_ = millis();
  return cap_.writeCommand(cmd, sizeof(cmd));
}

bool OnchipBt::leScanStart(bool active) {
  if (!ble_capable_ || !cap_.openOk()) {
    return false;
  }
  if (le_advertising_) {
    leAdvertiseStop();
    delay(20);
  }
  // LE Set Scan Parameters: opcode 0x200B
  const uint8_t params[] = {
      0x0b, 0x20, 0x07,
      static_cast<uint8_t>(active ? 0x01 : 0x00),  // LE_Scan_Type
      0x10, 0x00,                                  // Interval
      0x10, 0x00,                                  // Window
      0x00,                                        // Own_Address_Type
      0x00,                                        // Filter_Policy
  };
  if (!cap_.writeCommand(params, sizeof(params))) {
    return false;
  }
  delay(30);
  // LE Set Scan Enable: opcode 0x200C, enable=1, filter_dup=0
  const uint8_t en[] = {0x0c, 0x20, 0x02, 0x01, 0x00};
  if (!cap_.writeCommand(en, sizeof(en))) {
    return false;
  }
  le_scanning_ = true;
  setState("le_scanning");
  last_cmd_ms_ = millis();
  return true;
}

bool OnchipBt::leScanStop() {
  const uint8_t en[] = {0x0c, 0x20, 0x02, 0x00, 0x00};
  const bool ok = cap_.writeCommand(en, sizeof(en));
  le_scanning_ = false;
  if (!classic_inquiry_ && !le_advertising_) {
    setState("idle");
  }
  return ok;
}

bool OnchipBt::leAdvertiseStart(const char *name) {
  if (!ble_capable_ || !cap_.openOk()) {
    return false;
  }
  if (name && name[0]) {
    strncpy(adv_name_, name, sizeof(adv_name_) - 1);
    adv_name_[sizeof(adv_name_) - 1] = 0;
  }
  if (le_scanning_) {
    leScanStop();
    delay(20);
  }

  // LE Set Advertising Parameters (0x2006), ADV_IND, ~100 ms, all channels.
  const uint8_t par[] = {
      0x06, 0x20, 0x0f, 0xa0, 0x00, 0xa0, 0x00, 0x00, 0x00, 0x00,
      0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x07, 0x00,
  };
  if (!cap_.writeCommand(par, sizeof(par))) {
    return false;
  }
  delay(20);

  // LE Set Advertising Data (0x2008): significant_len + 31-octet payload (Core Spec).
  const size_t name_len = strnlen(adv_name_, sizeof(adv_name_) - 1);
  const size_t name_ad = 1 + name_len;  // type + name
  // Flags AD (3) + name AD (1 + type+name) must fit in 31.
  if (3 + 1 + name_ad > 31) {
    return false;
  }
  const uint8_t significant = static_cast<uint8_t>(3 + 1 + name_ad);
  uint8_t adv[3 + 1 + 31];
  memset(adv, 0, sizeof(adv));
  adv[0] = 0x08;
  adv[1] = 0x20;
  adv[2] = 32;  // plen = 1 + 31
  adv[3] = significant;
  adv[4] = 0x02;
  adv[5] = 0x01;
  adv[6] = 0x06;  // LE General Discoverable, BR/EDR Not Supported
  adv[7] = static_cast<uint8_t>(name_ad);
  adv[8] = 0x09;  // Complete Local Name
  memcpy(&adv[9], adv_name_, name_len);
  if (!cap_.writeCommand(adv, sizeof(adv))) {
    return false;
  }
  delay(20);

  // LE Set Advertise Enable (0x200A) = 1
  const uint8_t en[] = {0x0a, 0x20, 0x01, 0x01};
  if (!cap_.writeCommand(en, sizeof(en))) {
    return false;
  }
  le_advertising_ = true;
  setState("le_advertising");
  last_cmd_ms_ = millis();
  return true;
}

bool OnchipBt::leAdvertiseStop() {
  const uint8_t en[] = {0x0a, 0x20, 0x01, 0x00};
  const bool ok = cap_.writeCommand(en, sizeof(en));
  le_advertising_ = false;
  if (!le_scanning_ && !classic_inquiry_) {
    setState("idle");
  }
  return ok;
}

bool OnchipBt::classicInquiryStart() {
  if (!classic_capable_ || !cap_.openOk()) {
    return false;
  }
  // HCI_Inquiry: opcode 0x0401, LAP=0x9E8B33, length=8*1.28s, num=0
  const uint8_t cmd[] = {0x01, 0x04, 0x05, 0x33, 0x8b, 0x9e, 0x08, 0x00};
  if (!cap_.writeCommand(cmd, sizeof(cmd))) {
    return false;
  }
  classic_inquiry_ = true;
  setState("classic_inquiry");
  last_cmd_ms_ = millis();
  return true;
}

bool OnchipBt::classicInquiryCancel() {
  const uint8_t cmd[] = {0x02, 0x04, 0x00};
  const bool ok = cap_.writeCommand(cmd, sizeof(cmd));
  classic_inquiry_ = false;
  if (!le_scanning_ && !le_advertising_ && !le_connected_) {
    setState("idle");
  }
  return ok;
}

bool OnchipBt::classicDiscoverableStart() {
  if (!classic_capable_ || !cap_.openOk()) {
    return false;
  }
  classicSetLocalName(classic_name_);
  delay(30);
  // Write_Scan_Enable (0x0C1A) = 0x03 inquiry + page scan
  const uint8_t cmd[] = {0x1a, 0x0c, 0x01, 0x03};
  if (!cap_.writeCommand(cmd, sizeof(cmd))) {
    return false;
  }
  classic_discoverable_ = true;
  setState("classic_discoverable");
  last_cmd_ms_ = millis();
  return true;
}

bool OnchipBt::classicDiscoverableStop() {
  if (!classic_capable_) {
    return false;
  }
  const uint8_t cmd[] = {0x1a, 0x0c, 0x01, 0x00};
  const bool ok = cap_.writeCommand(cmd, sizeof(cmd));
  classic_discoverable_ = false;
  if (!classic_inquiry_ && !le_scanning_ && !le_advertising_ && !le_connected_) {
    setState("idle");
  }
  return ok;
}

bool OnchipBt::leConnect(const char *addr_hex, uint8_t addr_type) {
  uint8_t be[6];
  if (!parseAddrHex(addr_hex, be)) {
    return false;
  }
  // LE Create Connection: opcode 0x200D, plen 25
  // Peer_Address is little-endian on air.
  uint8_t cmd[28];
  cmd[0] = 0x0d;
  cmd[1] = 0x20;
  cmd[2] = 0x19;
  cmd[3] = 0x10;
  cmd[4] = 0x00;  // Scan_Interval
  cmd[5] = 0x10;
  cmd[6] = 0x00;  // Scan_Window
  cmd[7] = 0x00;  // Initiator_Filter_Policy
  cmd[8] = addr_type;
  for (int i = 0; i < 6; i++) {
    cmd[9 + i] = be[5 - i];
  }
  cmd[15] = 0x00;  // Own_Address_Type
  cmd[16] = 0x18;
  cmd[17] = 0x00;  // Conn_Interval_Min
  cmd[18] = 0x28;
  cmd[19] = 0x00;  // Conn_Interval_Max
  cmd[20] = 0x00;
  cmd[21] = 0x00;  // Conn_Latency
  cmd[22] = 0x48;
  cmd[23] = 0x00;  // Supervision_Timeout
  cmd[24] = 0x00;
  cmd[25] = 0x00;  // Min_CE_Len
  cmd[26] = 0x00;
  cmd[27] = 0x00;  // Max_CE_Len
  if (le_scanning_) {
    leScanStop();
    delay(20);
  }
  if (le_advertising_) {
    leAdvertiseStop();
    delay(20);
  }
  setState("le_connecting");
  last_cmd_ms_ = millis();
  return cap_.writeCommand(cmd, sizeof(cmd));
}

bool OnchipBt::leDisconnect() {
  if (!le_connected_ || !cap_.openOk()) {
    return false;
  }
  // HCI Disconnect (0x0406): handle, reason=0x13 (Remote User Terminated)
  const uint8_t cmd[] = {
      0x06, 0x04, 0x03,
      static_cast<uint8_t>(conn_handle_ & 0xff),
      static_cast<uint8_t>((conn_handle_ >> 8) & 0xff),
      0x13,
  };
  setState("le_disconnecting");
  last_cmd_ms_ = millis();
  return cap_.writeCommand(cmd, sizeof(cmd));
}

bool OnchipBt::classicSetLocalName(const char *name) {
  if (!classic_capable_ || !cap_.openOk()) {
    return false;
  }
  if (name && name[0]) {
    strncpy(classic_name_, name, sizeof(classic_name_) - 1);
    classic_name_[sizeof(classic_name_) - 1] = 0;
  }
  const size_t n = strnlen(classic_name_, sizeof(classic_name_) - 1);
  // Write_Local_Name (0x0C13): Core Spec pads to 248; keep stack small — heap buffer.
  uint8_t *cmd = static_cast<uint8_t *>(calloc(1, 3 + 248));
  if (!cmd) {
    return false;
  }
  cmd[0] = 0x13;
  cmd[1] = 0x0c;
  cmd[2] = 248;
  memcpy(&cmd[3], classic_name_, n);
  last_cmd_ms_ = millis();
  const bool ok = cap_.writeCommand(cmd, 3 + 248);
  free(cmd);
  return ok;
}

bool OnchipBt::gattClientDiscover(uint16_t mtu) {
  if (!le_connected_ || conn_role_ != 0) {
    return false;
  }
  setState("gatt_discover");
  return gatt_client_.startDiscover(mtu);
}

bool OnchipBt::gattClientRead(uint16_t handle) {
  if (!le_connected_ || conn_role_ != 0) {
    return false;
  }
  return gatt_client_.readHandle(handle);
}

bool OnchipBt::gattClientSubscribe(uint16_t cccd_handle, bool enable) {
  if (!le_connected_ || conn_role_ != 0) {
    return false;
  }
  return gatt_client_.subscribeCccd(cccd_handle, enable);
}

bool OnchipBt::hogpStart() {
  if (!le_connected_ || conn_role_ != 0) {
    return false;
  }
  setState("hogp");
  return hogp_.startAfterDiscover();
}

bool OnchipBt::ftmsStart() {
  if (!le_connected_ || conn_role_ != 0) {
    return false;
  }
  setState("ftms");
  return ftms_.startAfterDiscover();
}

bool OnchipBt::gattReadDeviceName() {
  if (!le_connected_ || !cap_.openOk()) {
    return false;
  }
  gatt_name_valid_ = false;
  gatt_name_[0] = 0;
  // H4 ACL + L2CAP(ATT) Read By Type Request for UUID 0x2A00.
  // handle | PB=0 BC=0, ACL len=11, L2CAP len=7 CID=0x0004, ATT 0x08 ...
  uint8_t h4[1 + 4 + 11];
  h4[0] = 0x02;
  const uint16_t hdr = static_cast<uint16_t>(conn_handle_ & 0x0FFFu);
  h4[1] = static_cast<uint8_t>(hdr & 0xff);
  h4[2] = static_cast<uint8_t>((hdr >> 8) & 0xff);
  h4[3] = 11;
  h4[4] = 0;  // ACL data length
  h4[5] = 7;
  h4[6] = 0;  // L2CAP length
  h4[7] = 0x04;
  h4[8] = 0x00;  // CID ATT
  h4[9] = 0x08;  // ATT Read By Type Request
  h4[10] = 0x01;
  h4[11] = 0x00;  // starting handle
  h4[12] = 0xff;
  h4[13] = 0xff;  // ending handle
  h4[14] = 0x00;
  h4[15] = 0x2a;  // UUID 0x2A00 LE
  setState("gatt_read_name");
  last_cmd_ms_ = millis();
  return cap_.writeH4(h4, sizeof(h4));
}

bool OnchipBt::writeAtt(const uint8_t *att, uint16_t att_len) {
  if (!le_connected_ || !cap_.openOk() || !att || att_len == 0 || att_len > 512) {
    return false;
  }
  uint8_t h4[1 + 4 + 4 + 512];
  const uint16_t l2 = att_len;
  const uint16_t alen = static_cast<uint16_t>(4 + l2);
  h4[0] = 0x02;
  const uint16_t hdr = static_cast<uint16_t>(conn_handle_ & 0x0FFFu);
  h4[1] = static_cast<uint8_t>(hdr & 0xff);
  h4[2] = static_cast<uint8_t>((hdr >> 8) & 0xff);
  h4[3] = static_cast<uint8_t>(alen & 0xff);
  h4[4] = static_cast<uint8_t>((alen >> 8) & 0xff);
  h4[5] = static_cast<uint8_t>(l2 & 0xff);
  h4[6] = static_cast<uint8_t>((l2 >> 8) & 0xff);
  h4[7] = 0x04;
  h4[8] = 0x00;
  memcpy(h4 + 9, att, att_len);
  return cap_.writeH4(h4, static_cast<size_t>(9 + att_len));
}

bool OnchipBt::attExchangeMtu(uint16_t mtu) {
  if (!le_connected_) {
    return false;
  }
  if (mtu < 23) {
    mtu = 23;
  }
  if (mtu > 247) {
    mtu = 247;
  }
  uint8_t att[3];
  att[0] = 0x02;  // Exchange MTU Request
  att[1] = static_cast<uint8_t>(mtu & 0xff);
  att[2] = static_cast<uint8_t>((mtu >> 8) & 0xff);
  setState("att_mtu_req");
  return writeAtt(att, 3);
}

bool OnchipBt::throughputStart(const char *mode, uint16_t payload_len,
                               uint16_t mtu, uint16_t pace_ms) {
  if (!le_connected_) {
    return false;
  }
  thr_notify_ = !(mode && strcasecmp(mode, "write") == 0);
  if (payload_len < 12) {
    payload_len = 12;
  }
  if (payload_len > 200) {
    payload_len = 200;
  }
  thr_payload_ = payload_len;
  thr_pace_ms_ = pace_ms;
  thr_seq_tx_ = 0;
  thr_have_rx_ = false;
  app_seq_gaps_ = 0;
  app_reorder_ = 0;
  app_tx_packets_ = 0;
  app_rx_packets_ = 0;
  thr_app_tx_ = thr_app_rx_ = 0;
  win_app_tx_ = win_app_rx_ = 0;
  app_tx_bps_ = app_rx_bps_ = 0;
  app_rate_ms_ = millis();
  thr_last_send_ms_ = 0;
  // Peripheral must wait for CCCD write from central — never pre-enable.
  thr_cccd_enabled_ = false;
  acl_reasm_handle_ = 0xffff;
  acl_reasm_len_ = 0;
  acl_reasm_need_ = 0;
  if (mtu >= 23) {
    attExchangeMtu(mtu);
  }
  if (thr_notify_ && conn_role_ == 0) {
    // Central: enable CCCD on handle 0x0004
    uint8_t cccd[5] = {0x12, 0x04, 0x00, 0x01, 0x00};  // Write Request
    writeAtt(cccd, 5);
  }
  thr_running_ = true;
  setState(thr_notify_ ? "thr_notify" : "thr_write");
  return true;
}

void OnchipBt::throughputStop() {
  thr_running_ = false;
  setState(le_connected_ ? (conn_role_ == 1 ? "le_connected_periph" : "le_connected")
                         : "idle");
}

void OnchipBt::pollAppRates() {
  const uint32_t now = millis();
  if (app_rate_ms_ == 0) {
    app_rate_ms_ = now;
    return;
  }
  const uint32_t dt = now - app_rate_ms_;
  if (dt < 1000) {
    return;
  }
  app_tx_bps_ = (win_app_tx_ * 1000u) / dt;
  app_rx_bps_ = (win_app_rx_ * 1000u) / dt;
  win_app_tx_ = win_app_rx_ = 0;
  app_rate_ms_ = now;
}

bool OnchipBt::sendThrPayload() {
  // Value = [seq:u32 LE][ts_us:u64 LE][pad…]
  uint8_t att[3 + 200];
  uint16_t att_len = 0;
  if (thr_notify_) {
    if (conn_role_ != 1 || !thr_cccd_enabled_) {
      return false;
    }
    att[0] = 0x1b;  // Handle Value Notification
    att[1] = 0x03;
    att[2] = 0x00;  // handle 0x0003
    att_len = 3;
  } else {
    if (conn_role_ != 0) {
      return false;
    }
    att[0] = 0x52;  // Write Command
    att[1] = 0x03;
    att[2] = 0x00;
    att_len = 3;
  }
  const uint32_t seq = thr_seq_tx_++;
  const uint64_t ts = static_cast<uint64_t>(esp_timer_get_time());
  for (int i = 0; i < 4; i++) {
    att[att_len++] = static_cast<uint8_t>((seq >> (8 * i)) & 0xff);
  }
  for (int i = 0; i < 8; i++) {
    att[att_len++] = static_cast<uint8_t>((ts >> (8 * i)) & 0xff);
  }
  while (att_len < static_cast<uint16_t>(3 + thr_payload_) && att_len < sizeof(att)) {
    att[att_len++] = 0xa5;
  }
  // Clamp to ATT MTU (opcode+handle+value ≤ mtu)
  const uint16_t max_att = att_mtu_ > 3 ? static_cast<uint16_t>(att_mtu_) : 23;
  if (att_len > max_att) {
    att_len = max_att;
  }
  if (!writeAtt(att, att_len)) {
    return false;
  }
  const uint16_t app = static_cast<uint16_t>(att_len > 3 ? att_len - 3 : 0);
  thr_app_tx_ += app;
  win_app_tx_ += app;
  app_tx_packets_++;
  return true;
}

void OnchipBt::thrPump() {
  if (!thr_running_ || !le_connected_) {
    return;
  }
  const uint32_t now = millis();
  // Pace ATT flood: larger payloads need more airtime; keep WiFi/BTAC alive.
  uint32_t min_gap_ms = thr_pace_ms_;
  if (min_gap_ms == 0) {
    min_gap_ms = thr_payload_ >= 100 ? 12u : 8u;
  }
  if (now - thr_last_send_ms_ < min_gap_ms) {
    return;
  }
  if (thr_notify_ && conn_role_ == 1 && thr_cccd_enabled_) {
    if (sendThrPayload()) {
      thr_last_send_ms_ = now;
    }
  } else if (!thr_notify_ && conn_role_ == 0) {
    if (sendThrPayload()) {
      thr_last_send_ms_ = now;
    }
  }
}

void OnchipBt::parseAclAtt(const uint8_t *h4, uint16_t len) {
  // H4 02 | handle+PB+BC[2] | acl_len[2] | data...
  if (len < 5 || h4[0] != 0x02) {
    return;
  }
  const uint16_t handle_full = static_cast<uint16_t>(h4[1] | (h4[2] << 8));
  const uint16_t handle = static_cast<uint16_t>(handle_full & 0x0FFFu);
  const uint8_t pb = static_cast<uint8_t>((handle_full >> 12) & 0x3u);
  const uint16_t acl_len = static_cast<uint16_t>(h4[3] | (h4[4] << 8));
  if (static_cast<uint16_t>(5 + acl_len) > len || acl_len == 0) {
    return;
  }
  const uint8_t *data = h4 + 5;

  // PB=1 → continuation fragment; PB=2/0 → start of L2CAP.
  if (pb == 1) {
    if (acl_reasm_handle_ != handle || acl_reasm_need_ == 0) {
      return;
    }
    const uint16_t space = static_cast<uint16_t>(sizeof(acl_reasm_buf_) - acl_reasm_len_);
    const uint16_t copy = acl_len < space ? acl_len : space;
    memcpy(acl_reasm_buf_ + acl_reasm_len_, data, copy);
    acl_reasm_len_ = static_cast<uint16_t>(acl_reasm_len_ + copy);
    if (acl_reasm_len_ >= acl_reasm_need_) {
      feedAclAtt(acl_reasm_buf_, acl_reasm_need_, true);
      acl_reasm_handle_ = 0xffff;
      acl_reasm_len_ = 0;
      acl_reasm_need_ = 0;
    }
    return;
  }

  if (acl_len < 4) {
    return;
  }
  const uint16_t l2_len = static_cast<uint16_t>(data[0] | (data[1] << 8));
  const uint16_t need = static_cast<uint16_t>(4 + l2_len);
  if (need <= acl_len) {
    feedAclAtt(data, need, true);
    return;
  }
  // Start reassembly
  if (need > sizeof(acl_reasm_buf_)) {
    return;
  }
  memcpy(acl_reasm_buf_, data, acl_len);
  acl_reasm_handle_ = handle;
  acl_reasm_len_ = acl_len;
  acl_reasm_need_ = need;
}

void OnchipBt::feedAclAtt(const uint8_t *l2cap, uint16_t len, bool has_l2cap_hdr) {
  if (!l2cap || len < 5) {
    return;
  }
  const uint8_t *att;
  uint16_t att_len;
  if (has_l2cap_hdr) {
    const uint16_t cid = static_cast<uint16_t>(l2cap[2] | (l2cap[3] << 8));
    if (cid != 0x0004) {
      return;
    }
    const uint16_t l2_len = static_cast<uint16_t>(l2cap[0] | (l2cap[1] << 8));
    if (static_cast<uint16_t>(4 + l2_len) > len || l2_len < 1) {
      return;
    }
    att = l2cap + 4;
    att_len = l2_len;
  } else {
    att = l2cap;
    att_len = len;
  }

  auto noteThrRx = [&](const uint8_t *val, uint16_t vlen) {
    if (!thr_running_ || vlen < 12) {
      return;
    }
    uint32_t seq = 0;
    for (int i = 0; i < 4; i++) {
      seq |= static_cast<uint32_t>(val[i]) << (8 * i);
    }
    thr_app_rx_ += vlen;
    win_app_rx_ += vlen;
    app_rx_packets_++;
    if (!thr_have_rx_) {
      thr_expect_rx_ = seq + 1;
      thr_have_rx_ = true;
    } else if (seq < thr_expect_rx_) {
      app_reorder_++;
    } else if (seq > thr_expect_rx_) {
      app_seq_gaps_ += (seq - thr_expect_rx_);
      thr_expect_rx_ = seq + 1;
    } else {
      thr_expect_rx_ = seq + 1;
    }
  };

  // Exchange MTU Request (peripheral answers)
  if (att[0] == 0x02 && att_len >= 3 && conn_role_ == 1) {
    uint16_t client_mtu = static_cast<uint16_t>(att[1] | (att[2] << 8));
    if (client_mtu < 23) {
      client_mtu = 23;
    }
    if (client_mtu > 247) {
      client_mtu = 247;
    }
    att_mtu_ = client_mtu;
    uint8_t rsp[3] = {0x03, att[1], att[2]};
    writeAtt(rsp, 3);
    return;
  }
  if (att[0] == 0x03 && att_len >= 3) {
    att_mtu_ = static_cast<uint16_t>(att[1] | (att[2] << 8));
    if (att_mtu_ < 23) {
      att_mtu_ = 23;
    }
    if (conn_role_ == 0) {
      gatt_client_.onAttPdu(att, att_len);
    }
    return;
  }

  // GATT Client / HOGP / FTMS (central)
  if (conn_role_ == 0) {
    const GcState gst = gatt_client_.state();
    if (gst != GcState::Idle && gst != GcState::Error &&
        (att[0] == 0x01 || att[0] == 0x05 || att[0] == 0x09 || att[0] == 0x0b ||
         att[0] == 0x11 || att[0] == 0x13 || att[0] == 0x1b || att[0] == 0x1d)) {
      gatt_client_.onAttPdu(att, att_len);
      hogp_.onAttPdu(att, att_len);
      ftms_.onAttPdu(att, att_len);
      if (att[0] == 0x0b && att_len >= 2 && gatt_client_.foundNameHandle() != 0) {
        // only treat as name if reading name handle — heuristic: small ASCII
        bool ascii = true;
        for (uint16_t i = 1; i < att_len && i < 20; i++) {
          if (att[i] < 0x20 || att[i] > 0x7e) {
            ascii = false;
            break;
          }
        }
        if (ascii) {
          const size_t copy =
              (att_len - 1) < sizeof(gatt_name_) - 1 ? (att_len - 1) : sizeof(gatt_name_) - 1;
          memcpy(gatt_name_, att + 1, copy);
          gatt_name_[copy] = 0;
          gatt_name_valid_ = true;
        }
      }
      if (att[0] != 0x1b) {
        return;
      }
      // notifications also feed thr path below
    }
  }

  // Peripheral GATT DB (GAP + HID + FTMS)
  if (conn_role_ == 1 &&
      gattPeerHandleRequest(conn_role_, adv_name_, &OnchipBt::writeAttBridge, this, att,
                            att_len, &peer_hid_cccd_, &peer_ftms_cccd_)) {
    return;
  }

  // CCCD write → enable notifications (handle 0x0004)
  if ((att[0] == 0x12 || att[0] == 0x52) && att_len >= 5 && conn_role_ == 1) {
    const uint16_t handle = static_cast<uint16_t>(att[1] | (att[2] << 8));
    if (handle == 0x0004) {
      thr_cccd_enabled_ = (att[3] & 0x01) != 0;
      if (att[0] == 0x12) {
        uint8_t rsp[1] = {0x13};  // Write Response
        writeAtt(rsp, 1);
      }
      return;
    }
    if (handle == 0x0003 && att[0] == 0x52) {
      noteThrRx(att + 3, static_cast<uint16_t>(att_len - 3));
      return;
    }
  }

  // Notification on central
  if (att[0] == 0x1b && att_len >= 15) {
    noteThrRx(att + 3, static_cast<uint16_t>(att_len - 3));
    return;
  }

  // Peripheral stub: answer Read By Type 0x2A00 with adv_name_ (thin GATT).
  if (att[0] == 0x08 && att_len >= 7 && le_connected_ && conn_role_ == 1) {
    const uint16_t uuid = static_cast<uint16_t>(att[5] | (att[6] << 8));
    if (uuid == 0x2A00) {
      const size_t nlen = strnlen(adv_name_, sizeof(adv_name_) - 1);
      const uint8_t pair = static_cast<uint8_t>(2 + nlen);
      uint8_t rsp[2 + 32];
      rsp[0] = 0x09;
      rsp[1] = pair;
      rsp[2] = 0x03;
      rsp[3] = 0x00;
      memcpy(&rsp[4], adv_name_, nlen);
      writeAtt(rsp, static_cast<uint16_t>(2 + pair));
      return;
    }
  }
  // Read By Type Response (0x09): length, handle[2], value...
  if (att[0] == 0x09 && att_len >= 4) {
    const uint8_t pair_len = att[1];
    if (pair_len >= 3 && att_len >= static_cast<uint16_t>(2 + pair_len)) {
      const uint8_t *val = att + 4;
      const size_t vlen = pair_len - 2;
      const size_t copy = vlen < sizeof(gatt_name_) - 1 ? vlen : sizeof(gatt_name_) - 1;
      memcpy(gatt_name_, val, copy);
      gatt_name_[copy] = 0;
      gatt_name_valid_ = true;
      setState("gatt_name_ok");
    }
  } else if (att[0] == 0x01 && att_len >= 5) {
    setState("gatt_err");
  }
}

void OnchipBt::appendStatusJson(String &json) const {
  json += ",\"onchip\":{";
  json += "\"transport\":\"onchip_vhci\"";
  json += ",\"ready\":";
  json += ready_ ? "true" : "false";
  json += ",\"ble\":";
  json += ble_capable_ ? "true" : "false";
  json += ",\"classic\":";
  json += classic_capable_ ? "true" : "false";
  json += ",\"state\":\"";
  json += state_;
  json += "\",\"leScanning\":";
  json += le_scanning_ ? "true" : "false";
  json += ",\"leAdvertising\":";
  json += le_advertising_ ? "true" : "false";
  json += ",\"advName\":\"";
  json += adv_name_;
  json += "\",\"classicInquiry\":";
  json += classic_inquiry_ ? "true" : "false";
  json += ",\"classicDiscoverable\":";
  json += classic_discoverable_ ? "true" : "false";
  json += ",\"leConnected\":";
  json += le_connected_ ? "true" : "false";
  json += ",\"connHandle\":";
  json += String(conn_handle_);
  json += ",\"devices\":";
  json += String(device_count_);
  json += ",\"bdAddr\":";
  if (bd_addr_valid_) {
    char a[24];
    addrToStr(bd_addr_, a, sizeof(a));
    json += "\"";
    json += a;
    json += "\"";
  } else {
    json += "null";
  }
  json += ",\"peerAddr\":";
  if (peer_addr_valid_) {
    char a[24];
    addrToStr(peer_addr_, a, sizeof(a));
    json += "\"";
    json += a;
    json += "\"";
  } else {
    json += "null";
  }
  json += ",\"gattName\":";
  if (gatt_name_valid_) {
    json += "\"";
    json += gatt_name_;
    json += "\"";
  } else {
    json += "null";
  }
  json += ",\"classicName\":\"";
  json += classic_name_;
  json += "\",\"attMtu\":";
  json += String(att_mtu_);
  json += ",\"thrRunning\":";
  json += thr_running_ ? "true" : "false";
  json += ",\"thrMode\":\"";
  json += thr_notify_ ? "notify" : "write";
  json += "\",\"appTxBps\":";
  json += String(app_tx_bps_);
  json += ",\"appRxBps\":";
  json += String(app_rx_bps_);
  json += ",\"appTxBytes\":";
  json += String(thr_app_tx_);
  json += ",\"appRxBytes\":";
  json += String(thr_app_rx_);
  json += ",\"appTxPackets\":";
  json += String(app_tx_packets_);
  json += ",\"appRxPackets\":";
  json += String(app_rx_packets_);
  json += ",\"appSeqGaps\":";
  json += String(app_seq_gaps_);
  json += ",\"appReorder\":";
  json += String(app_reorder_);
  json += ",\"thrLoss\":";
  json += String(app_seq_gaps_);  // compat alias
  json += ",\"thrReorder\":";
  json += String(app_reorder_);
  json += ",\"l2Claim\":\"att_over_hci_acl_not_air\"";
  json += ",\"hci\":{\"detected\":";
  json += ready_ ? "true" : "false";
  json += ",\"claim\":\"onchip_controller_vhci\"}";
  if (last_err_[0]) {
    json += ",\"lastErr\":\"";
    json += last_err_;
    json += "\"";
  }
  json += "}";

  gatt_client_.appendStatusJson(json);
  hogp_.appendStatusJson(json);
  ftms_.appendStatusJson(json);
  ring_.appendStatusJson(json);
  cap_.appendStatusJson(json);
}

String OnchipBt::devicesJson() const {
  String out = "{\"devices\":[";
  for (size_t i = 0; i < device_count_; i++) {
    if (i) {
      out += ",";
    }
    const BtSeenDevice &d = devices_[i];
    char a[24];
    addrToStr(d.addr, a, sizeof(a));
    out += "{\"addr\":\"";
    out += a;
    out += "\",\"addrType\":";
    out += String(d.addr_type);
    out += ",\"rssi\":";
    out += String(d.rssi);
    out += ",\"classic\":";
    out += d.classic ? "true" : "false";
    out += ",\"ble\":";
    out += d.ble ? "true" : "false";
    out += ",\"name\":\"";
    for (const char *p = d.name; *p; ++p) {
      if (*p == '"' || *p == '\\') {
        out += '\\';
      }
      if (static_cast<uint8_t>(*p) >= 0x20) {
        out += *p;
      }
    }
    out += "\"}";
  }
  out += "]}";
  return out;
}

}  // namespace bt_analyzer
