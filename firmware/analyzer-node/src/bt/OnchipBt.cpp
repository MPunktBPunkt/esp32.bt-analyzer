#include "bt/OnchipBt.h"

#include "core/DiagLog.h"

#include <esp_bt.h>
#include <nvs_flash.h>
#include <string.h>
#include <stdio.h>

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
  setState("ready");
  Serial.printf("[bt] on-chip ready ble=%d classic=%d transport=onchip_vhci\n",
                ble_capable_ ? 1 : 0, classic_capable_ ? 1 : 0);

  delay(50);
  hciReset();
  return true;
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
}

void OnchipBt::handleControllerPacket(uint8_t *data, uint16_t len) {
  cap_.onRecv(data, len);
  if (data && len >= 2 && data[0] == 0x04) {
    parseEvent(data, len);
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
      peer_addr_type_ = evt[5];
      for (int i = 0; i < 6; i++) {
        peer_addr_[i] = evt[6 + (5 - i)];
      }
      peer_addr_valid_ = true;
      le_connected_ = true;
      le_scanning_ = false;
      le_advertising_ = false;
      setState("le_connected");
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
  json += ",\"hci\":{\"detected\":";
  json += ready_ ? "true" : "false";
  json += ",\"claim\":\"onchip_controller_vhci\"}";
  if (last_err_[0]) {
    json += ",\"lastErr\":\"";
    json += last_err_;
    json += "\"";
  }
  json += "}";

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
