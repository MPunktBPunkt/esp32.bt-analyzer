#include "usb/UsbHostEnum.h"

#if BT_ANALYZER_ENABLE_USB_HOST

#include "hci/HciUsbMap.h"

#include <EspUsbHost.h>
#include <espusbhost_version.h>

#include <ArduinoJson.h>
#include <hal/usb_dwc_ll.h>

namespace bt_analyzer {
namespace {

EspUsbHost g_usb;

const char *speedName(usb_speed_t speed) {
  switch (speed) {
  case USB_SPEED_LOW:
    return "low";
  case USB_SPEED_FULL:
    return "full";
  case USB_SPEED_HIGH:
    return "high";
  default:
    return "unknown";
  }
}

void jsonEscapeAppend(String &out, const char *s) {
  if (!s) {
    return;
  }
  for (const char *p = s; *p; ++p) {
    const char c = *p;
    if (c == '"' || c == '\\') {
      out += '\\';
      out += c;
    } else if (static_cast<uint8_t>(c) < 0x20) {
      // skip control chars
    } else {
      out += c;
    }
  }
}

String deviceEventJson(const EspUsbHostDeviceInfo &d, const char *event,
                       const String &ifaces_json, const String &eps_json) {
  JsonDocument doc;
  doc["event"] = event;
  doc["address"] = d.address;
  doc["vid"] = d.vid;
  doc["pid"] = d.pid;
  char id[12];
  snprintf(id, sizeof(id), "%04x:%04x", d.vid, d.pid);
  doc["id"] = id;
  doc["manufacturer"] = d.manufacturer ? d.manufacturer : "";
  doc["product"] = d.product ? d.product : "";
  doc["serial"] = d.serial ? d.serial : "";
  doc["speed"] = speedName(d.speed);
  doc["device_class"] = d.deviceClass;
  doc["device_subclass"] = d.deviceSubClass;
  doc["device_protocol"] = d.deviceProtocol;
  doc["configuration_value"] = d.configurationValue;
  doc["configuration_interfaces"] = d.configurationInterfaceCount;
  doc["supported"] = d.supported;
  doc["is_hub"] = d.isHub;

  // Merge pre-built arrays via raw JSON parse (ArduinoJson)
  JsonDocument ifDoc;
  if (!deserializeJson(ifDoc, ifaces_json)) {
    doc["interfaces"] = ifDoc.as<JsonArray>();
  }
  JsonDocument epDoc;
  if (!deserializeJson(epDoc, eps_json)) {
    doc["endpoints"] = epDoc.as<JsonArray>();
  }

  String out;
  serializeJson(doc, out);
  return out;
}

void logConnected(const EspUsbHostDeviceInfo &d, const String &ifaces_json,
                  const String &eps_json) {
  Serial.println();
  Serial.println("=== USB ENUMERATED (BT1) ===");
  Serial.printf("address=%u speed=%s\n", d.address, speedName(d.speed));
  Serial.printf("vid:pid=%04x:%04x\n", d.vid, d.pid);
  Serial.printf("mfr=\"%s\" product=\"%s\" serial=\"%s\"\n",
                d.manufacturer ? d.manufacturer : "",
                d.product ? d.product : "", d.serial ? d.serial : "");
  Serial.printf("device class=0x%02x subclass=0x%02x protocol=0x%02x\n",
                d.deviceClass, d.deviceSubClass, d.deviceProtocol);
  Serial.printf("config value=%u interfaces=%u\n", d.configurationValue,
                d.configurationInterfaceCount);
  Serial.printf("library supported=%s hub=%s\n", d.supported ? "yes" : "no",
                d.isHub ? "yes" : "no");
  Serial.printf("interfaces=%s\n", ifaces_json.c_str());
  Serial.printf("endpoints=%s\n", eps_json.c_str());
  Serial.println("CLAIM: host stack saw USB descriptors (enum). Not HCI. "
                 "Not RF/Air.");
  Serial.println("============================");
  (void)eps_json;
}

}  // namespace

void UsbHostEnum::clearDut() {
  dut_present_ = false;
  dut_vid_ = 0;
  dut_pid_ = 0;
  dut_address_ = 0;
  dut_cfg_ = 0;
  dut_iface_count_ = 0;
  dut_ep_count_ = 0;
  dut_wireless_ctrl_ = false;
  dut_mfr_ = "";
  dut_product_ = "";
  dut_serial_ = "";
  dut_speed_ = "";
  dut_ifaces_json_ = "[]";
  dut_eps_json_ = "[]";
  HciUsbMap::clear(hci_);
}

void UsbHostEnum::cacheDescriptors(uint8_t address) {
  EspUsbHostInterfaceInfo interfaces[ESP_USB_HOST_MAX_INTERFACES];
  const size_t n_if =
      g_usb.getInterfaces(address, interfaces, ESP_USB_HOST_MAX_INTERFACES);
  dut_iface_count_ = static_cast<uint8_t>(n_if);
  dut_wireless_ctrl_ = false;

  JsonDocument ifDoc;
  JsonArray ifArr = ifDoc.to<JsonArray>();
  for (size_t i = 0; i < n_if; i++) {
    JsonObject o = ifArr.add<JsonObject>();
    o["number"] = interfaces[i].number;
    o["class"] = interfaces[i].interfaceClass;
    o["subclass"] = interfaces[i].interfaceSubClass;
    o["protocol"] = interfaces[i].interfaceProtocol;
    o["claimed"] = interfaces[i].claimed;
    if (interfaces[i].interfaceClass == 0xE0 &&
        interfaces[i].interfaceSubClass == 0x01) {
      dut_wireless_ctrl_ = true;
      o["hint"] = "wireless_controller_bt_hci";
    }
  }
  dut_ifaces_json_ = "";
  serializeJson(ifArr, dut_ifaces_json_);

  EspUsbHostEndpointInfo endpoints[ESP_USB_HOST_MAX_ENDPOINTS];
  const size_t n_ep =
      g_usb.getEndpoints(address, endpoints, ESP_USB_HOST_MAX_ENDPOINTS);
  dut_ep_count_ = static_cast<uint8_t>(n_ep);

  JsonDocument epDoc;
  JsonArray epArr = epDoc.to<JsonArray>();
  for (size_t i = 0; i < n_ep; i++) {
    JsonObject o = epArr.add<JsonObject>();
    o["address"] = endpoints[i].address;
    o["interfaceNumber"] = endpoints[i].interfaceNumber;
    o["attributes"] = endpoints[i].attributes;
    o["maxPacketSize"] = endpoints[i].maxPacketSize;
    o["interval"] = endpoints[i].interval;
    const uint8_t xfer = endpoints[i].attributes & 0x03;
    o["transfer"] = (xfer == 1)   ? "iso"
                    : (xfer == 2) ? "bulk"
                    : (xfer == 3) ? "interrupt"
                                  : "control";
    o["dir"] = (endpoints[i].address & 0x80) ? "in" : "out";
  }
  dut_eps_json_ = "";
  serializeJson(epArr, dut_eps_json_);

  HciUsbMap::discover(interfaces, n_if, endpoints, n_ep, hci_);
  if (hci_.wirelessControllerIface) {
    Serial.printf("[hci] BT2 USB-HCI iface=%u proto=0x%02x event=%d "
                  "cmd_acl_out=%d acl_in=%d sco_iso=%d\n",
                  hci_.hciInterfaceNumber, hci_.ifaceProtocol,
                  hci_.hasEventEp ? 1 : 0, hci_.hasCommandAclOut ? 1 : 0,
                  hci_.hasAclIn ? 1 : 0, hci_.hasScoIso ? 1 : 0);
    Serial.println("[hci] CLAIM: descriptor inference only — not packet capture");
  } else {
    Serial.println("[hci] no Wireless Controller (0xE0/0x01) interface");
  }
}

void UsbHostEnum::printNoDeviceHints() const {
  Serial.println("[usb] no device after 10s — check:");
  Serial.println("  - OTG cable / adapter orientation");
  Serial.println("  - self-powered dongle or powered hub (boardSourcesVbus=false)");
  Serial.println("  - Serial is UART/COM, not the OTG connector");
}

bool UsbHostEnum::begin() {
  Serial.println("[usb] EspUsbHost bring-up (BT1 enum)");
  Serial.printf("[usb] EspUsbHost %s\n", ESPUSBHOST_VERSION_STR);
  Serial.printf("[usb] arduino-esp32 %s\n", ESP_ARDUINO_VERSION_STR);
  Serial.printf("[usb] chip %s rev %u\n", ESP.getChipModel(),
                static_cast<unsigned>(ESP.getChipRevision()));
  Serial.println("[usb] Debug: UART/COM — OTG port is for USB DUT only");
  Serial.println("[usb] VBUS: DevKit OTG typically does NOT source 5V");

  clearDut();

  g_usb.onDeviceConnected([this](const EspUsbHostDeviceInfo &d) {
    cacheDescriptors(d.address);
    logConnected(d, dut_ifaces_json_, dut_eps_json_);
    last_event_json_ =
        deviceEventJson(d, "enumerated", dut_ifaces_json_, dut_eps_json_);
    hint_printed_ = false;
    dut_present_ = true;
    dut_vid_ = d.vid;
    dut_pid_ = d.pid;
    dut_address_ = d.address;
    dut_mfr_ = d.manufacturer ? d.manufacturer : "";
    dut_product_ = d.product ? d.product : "";
    dut_serial_ = d.serial ? d.serial : "";
    dut_speed_ = speedName(d.speed);
    dut_cfg_ = d.configurationValue;
    if (d.configurationInterfaceCount > dut_iface_count_) {
      // keep getInterfaces() count when available
    }
  });

  g_usb.onDeviceDisconnected([this](const EspUsbHostDeviceInfo &d) {
    Serial.printf("[usb] REMOVED address=%u %04x:%04x\n", d.address, d.vid,
                  d.pid);
    last_event_json_ =
        deviceEventJson(d, "removed", dut_ifaces_json_, dut_eps_json_);
    clearDut();
  });

  begin_ok_ = g_usb.begin();
  if (begin_ok_) {
    Serial.println("[usb] begin(): ok — waiting for device");
  } else {
    Serial.printf("[usb] begin(): FAILED: %s\n", g_usb.lastErrorName());
    Serial.println("[usb] This is a build/config problem, not cabling.");
  }

  ready_ = true;
  started_ms_ = millis();
  last_report_ms_ = started_ms_;
  return begin_ok_;
}

void UsbHostEnum::loop() {
  if (!begin_ok_) {
    return;
  }
  const uint32_t now = millis();
  if (now - last_report_ms_ < 2000) {
    return;
  }
  last_report_ms_ = now;
  const size_t count = g_usb.deviceCount();
  Serial.printf("[usb] t=%lus devices=%u channels=%u/%u heap=%u\n",
                static_cast<unsigned long>((now - started_ms_) / 1000UL),
                static_cast<unsigned>(count),
                static_cast<unsigned>(g_usb.endpointChannelCount()),
                static_cast<unsigned>(g_usb.maxEndpointChannelCount()),
                static_cast<unsigned>(ESP.getFreeHeap()));

  if (count == 0 && !hint_printed_ && (now - started_ms_) >= 10000) {
    hint_printed_ = true;
    printNoDeviceHints();
  }
}

size_t UsbHostEnum::deviceCount() const {
  if (!begin_ok_) {
    return 0;
  }
  return g_usb.deviceCount();
}

const char *UsbHostEnum::otgState() const {
  if (!begin_ok_) {
    return "disabled";
  }
  if (deviceCount() > 0) {
    return "device_attached";
  }
  return "waiting_for_dut";
}

void UsbHostEnum::appendStatusJson(String &json) const {
  json += ",\"usbHost\":{";
  json += "\"enabled\":true";
  json += ",\"beginOk\":";
  json += begin_ok_ ? "true" : "false";
  json += ",\"library\":\"";
  json += ESPUSBHOST_VERSION_STR;
  json += "\",\"state\":\"";
  json += otgState();
  json += "\"}";

  json += ",\"otg\":{";
  json += "\"mode\":\"host\"";
  json += ",\"state\":\"";
  json += otgState();
  json += "\",\"connected\":";
  json += deviceCount() > 0 ? "true" : "false";
  json += ",\"devices\":";
  json += String(static_cast<unsigned>(deviceCount()));
  json += "}";

  json += ",\"dut\":{";
  json += "\"present\":";
  json += dut_present_ && deviceCount() > 0 ? "true" : "false";
  if (dut_present_ && deviceCount() > 0) {
    char id[12];
    snprintf(id, sizeof(id), "%04x:%04x", dut_vid_, dut_pid_);
    json += ",\"id\":\"";
    json += id;
    json += "\",\"vid\":";
    json += String(dut_vid_);
    json += ",\"pid\":";
    json += String(dut_pid_);
    json += ",\"address\":";
    json += String(dut_address_);
    json += ",\"configurationValue\":";
    json += String(dut_cfg_);
    json += ",\"interfaceCount\":";
    json += String(dut_iface_count_);
    json += ",\"endpointCount\":";
    json += String(dut_ep_count_);
    json += ",\"wirelessController\":";
    json += dut_wireless_ctrl_ ? "true" : "false";
    json += ",\"speed\":\"";
    json += dut_speed_;
    json += "\",\"manufacturer\":\"";
    jsonEscapeAppend(json, dut_mfr_.c_str());
    json += "\",\"product\":\"";
    jsonEscapeAppend(json, dut_product_.c_str());
    json += "\",\"serial\":\"";
    jsonEscapeAppend(json, dut_serial_.c_str());
    json += "\",\"interfaces\":";
    json += dut_ifaces_json_.length() ? dut_ifaces_json_ : "[]";
    json += ",\"endpoints\":";
    json += dut_eps_json_.length() ? dut_eps_json_ : "[]";
  }
  json += "}";

  json += ",\"vbus\":{";
  json += "\"prtpwr\":";
  json += USB_DWC.hprt_reg.prtpwr ? "true" : "false";
  json += ",\"prtlnsts\":";
  json += String(static_cast<unsigned>(USB_DWC.hprt_reg.prtlnsts));
  json += ",\"boardSourcesVbus\":false";
  json += ",\"note\":\"devkit_otg_no_5v_self_powered_dut_or_hub\"";
  json += "}";

  HciUsbMap::appendStatusJson(hci_, json);

  if (last_event_json_.length()) {
    json += ",\"lastUsbEvent\":";
    json += last_event_json_;
  }
}

}  // namespace bt_analyzer

#else  // !BT_ANALYZER_ENABLE_USB_HOST

namespace bt_analyzer {

bool UsbHostEnum::begin() {
  Serial.println("[usb] BT_ANALYZER_ENABLE_USB_HOST=0 — skipped");
  begin_ok_ = false;
  ready_ = true;
  return false;
}

void UsbHostEnum::loop() {}

size_t UsbHostEnum::deviceCount() const { return 0; }

const char *UsbHostEnum::otgState() const { return "disabled"; }

void UsbHostEnum::appendStatusJson(String &json) const {
  json += ",\"usbHost\":{\"enabled\":false,\"beginOk\":false,\"state\":\"disabled\"}";
  json += ",\"otg\":{\"mode\":\"none\",\"state\":\"disabled\",\"connected\":false,\"devices\":0}";
  json += ",\"dut\":{\"present\":false}";
  json += ",\"hci\":{\"transport\":\"usb_hci\",\"detected\":false,\"claim\":\"usb_host_disabled\"}";
}

void UsbHostEnum::clearDut() {}
void UsbHostEnum::cacheDescriptors(uint8_t) {}
void UsbHostEnum::printNoDeviceHints() const {}

}  // namespace bt_analyzer

#endif
