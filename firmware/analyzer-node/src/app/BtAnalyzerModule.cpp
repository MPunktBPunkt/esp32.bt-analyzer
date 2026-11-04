#include "app/BtAnalyzerModule.h"

#include "capture/CaptureFrame.h"
#include "hci/HciTypes.h"

#include <stdlib.h>
#include <string.h>

namespace bt_analyzer {
namespace {

int hexNibble(char c) {
  if (c >= '0' && c <= '9') {
    return c - '0';
  }
  if (c >= 'a' && c <= 'f') {
    return c - 'a' + 10;
  }
  if (c >= 'A' && c <= 'F') {
    return c - 'A' + 10;
  }
  return -1;
}

size_t parseHex(const String &hex, uint8_t *out, size_t max_out) {
  size_t n = 0;
  for (size_t i = 0; i + 1 < hex.length() && n < max_out;) {
    while (i < hex.length() &&
           (hex[i] == ' ' || hex[i] == ':' || hex[i] == '-')) {
      i++;
    }
    if (i + 1 >= hex.length()) {
      break;
    }
    const int hi = hexNibble(hex[i]);
    const int lo = hexNibble(hex[i + 1]);
    if (hi < 0 || lo < 0) {
      break;
    }
    out[n++] = static_cast<uint8_t>((hi << 4) | lo);
    i += 2;
  }
  return n;
}

}  // namespace

void BtAnalyzerModule::registerRoutes(WebServer &server) {
  WebServer *srv = &server;

  server.on("/api/bt/status", HTTP_GET, [this, srv]() {
    String json = "{";
    if (onchip_) {
      String frag;
      onchip_->appendStatusJson(frag);
      if (frag.startsWith(",")) {
        frag.remove(0, 1);
      }
      json += frag;
    } else {
      json += "\"error\":\"no_onchip\"";
    }
    json += "}";
    srv->send(200, "application/json", json);
  });

  server.on("/api/bt/devices", HTTP_GET, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "application/json", "{\"error\":\"no_onchip\"}");
      return;
    }
    srv->send(200, "application/json", onchip_->devicesJson());
  });

  server.on("/api/bt/scan/start", HTTP_POST, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "application/json", "{\"ok\":false,\"error\":\"no_onchip\"}");
      return;
    }
    onchip_->clearDevices();
    const bool ok = onchip_->leScanStart(true);
    srv->send(ok ? 200 : 500, "application/json",
              ok ? "{\"ok\":true,\"mode\":\"le\"}"
                 : "{\"ok\":false,\"error\":\"le_scan_failed\"}");
  });

  server.on("/api/bt/scan/stop", HTTP_POST, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "application/json", "{\"ok\":false,\"error\":\"no_onchip\"}");
      return;
    }
    const bool ok = onchip_->leScanStop();
    srv->send(ok ? 200 : 500, "application/json",
              ok ? "{\"ok\":true}" : "{\"ok\":false}");
  });

  server.on("/api/bt/advertise/start", HTTP_POST, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "application/json", "{\"ok\":false,\"error\":\"no_onchip\"}");
      return;
    }
    String name = srv->arg("name");
    if (!name.length()) {
      name = "bt-peer";
    }
    if (name.length() > 24) {
      name = name.substring(0, 24);
    }
    const bool ok = onchip_->leAdvertiseStart(name.c_str());
    srv->send(ok ? 200 : 500, "application/json",
              ok ? "{\"ok\":true,\"mode\":\"le_adv\",\"role\":\"peripheral\"}"
                 : "{\"ok\":false,\"error\":\"advertise_failed\"}");
  });

  server.on("/api/bt/advertise/stop", HTTP_POST, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "application/json", "{\"ok\":false,\"error\":\"no_onchip\"}");
      return;
    }
    const bool ok = onchip_->leAdvertiseStop();
    srv->send(ok ? 200 : 500, "application/json",
              ok ? "{\"ok\":true}" : "{\"ok\":false}");
  });

  server.on("/api/bt/inquiry/start", HTTP_POST, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "application/json", "{\"ok\":false,\"error\":\"no_onchip\"}");
      return;
    }
    if (!onchip_->classicCapable()) {
      srv->send(400, "application/json",
                "{\"ok\":false,\"error\":\"classic_not_available\"}");
      return;
    }
    onchip_->clearDevices();
    const bool ok = onchip_->classicInquiryStart();
    srv->send(ok ? 200 : 500, "application/json",
              ok ? "{\"ok\":true,\"mode\":\"classic\"}"
                 : "{\"ok\":false,\"error\":\"inquiry_failed\"}");
  });

  server.on("/api/bt/inquiry/stop", HTTP_POST, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "application/json", "{\"ok\":false,\"error\":\"no_onchip\"}");
      return;
    }
    const bool ok = onchip_->classicInquiryCancel();
    srv->send(ok ? 200 : 500, "application/json",
              ok ? "{\"ok\":true}" : "{\"ok\":false}");
  });

  server.on("/api/bt/connect", HTTP_POST, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "application/json", "{\"ok\":false,\"error\":\"no_onchip\"}");
      return;
    }
    String addr = srv->arg("addr");
    uint8_t at = static_cast<uint8_t>(srv->arg("addrType").toInt());
    if (!addr.length()) {
      srv->send(400, "application/json",
                "{\"ok\":false,\"error\":\"addr_required\"}");
      return;
    }
    const bool ok = onchip_->leConnect(addr.c_str(), at);
    srv->send(ok ? 200 : 500, "application/json",
              ok ? "{\"ok\":true,\"mode\":\"le_connect\"}"
                 : "{\"ok\":false,\"error\":\"connect_failed\"}");
  });

  server.on("/api/bt/disconnect", HTTP_POST, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "application/json", "{\"ok\":false,\"error\":\"no_onchip\"}");
      return;
    }
    const bool ok = onchip_->leDisconnect();
    srv->send(ok ? 200 : 500, "application/json",
              ok ? "{\"ok\":true}" : "{\"ok\":false,\"error\":\"disconnect_failed\"}");
  });

  server.on("/api/bt/gatt/read-name", HTTP_POST, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "application/json", "{\"ok\":false,\"error\":\"no_onchip\"}");
      return;
    }
    if (!onchip_->connected()) {
      srv->send(400, "application/json",
                "{\"ok\":false,\"error\":\"not_connected\",\"claim\":\"L2_ATT\"}");
      return;
    }
    const bool ok = onchip_->gattReadDeviceName();
    srv->send(ok ? 200 : 500, "application/json",
              ok ? "{\"ok\":true,\"mode\":\"att_read_by_type_2a00\",\"claim\":\"L2_over_HCI_not_air\"}"
                 : "{\"ok\":false,\"error\":\"gatt_write_failed\"}");
  });

  server.on("/api/bt/classic/name", HTTP_POST, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "application/json", "{\"ok\":false,\"error\":\"no_onchip\"}");
      return;
    }
    if (!onchip_->classicCapable()) {
      srv->send(400, "application/json",
                "{\"ok\":false,\"error\":\"classic_not_available\"}");
      return;
    }
    String name = srv->arg("name");
    if (!name.length()) {
      name = "bt-classic-87";
    }
    if (name.length() > 24) {
      name = name.substring(0, 24);
    }
    const bool ok = onchip_->classicSetLocalName(name.c_str());
    srv->send(ok ? 200 : 500, "application/json",
              ok ? "{\"ok\":true,\"mode\":\"classic_local_name\"}"
                 : "{\"ok\":false,\"error\":\"name_failed\"}");
  });

  server.on("/api/bt/discoverable/start", HTTP_POST, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "application/json", "{\"ok\":false,\"error\":\"no_onchip\"}");
      return;
    }
    if (!onchip_->classicCapable()) {
      srv->send(400, "application/json",
                "{\"ok\":false,\"error\":\"classic_not_available\"}");
      return;
    }
    String name = srv->arg("name");
    if (name.length()) {
      if (name.length() > 24) {
        name = name.substring(0, 24);
      }
      onchip_->classicSetLocalName(name.c_str());
    }
    const bool ok = onchip_->classicDiscoverableStart();
    srv->send(ok ? 200 : 500, "application/json",
              ok ? "{\"ok\":true,\"mode\":\"classic_discoverable\"}"
                 : "{\"ok\":false,\"error\":\"discoverable_failed\"}");
  });

  server.on("/api/bt/discoverable/stop", HTTP_POST, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "application/json", "{\"ok\":false,\"error\":\"no_onchip\"}");
      return;
    }
    const bool ok = onchip_->classicDiscoverableStop();
    srv->send(ok ? 200 : 500, "application/json",
              ok ? "{\"ok\":true}" : "{\"ok\":false}");
  });

  server.on("/api/bt/reset", HTTP_POST, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "application/json", "{\"ok\":false}");
      return;
    }
    const bool ok = onchip_->hciReset();
    srv->send(ok ? 200 : 500, "application/json",
              ok ? "{\"ok\":true}" : "{\"ok\":false}");
  });

#if BT_ANALYZER_ENABLE_USB_HOST
  server.on("/api/usb/last-event", HTTP_GET, [this, srv]() {
    if (!usb_) {
      srv->send(503, "application/json", "{\"error\":\"no_host\"}");
      return;
    }
    String body = usb_->lastEventJson();
    if (!body.length()) {
      body = "{\"event\":\"none\"}";
    }
    srv->send(200, "application/json", body);
  });

  server.on("/api/usb/status", HTTP_GET, [this, srv]() {
    String json = "{";
    if (usb_) {
      String frag;
      usb_->appendStatusJson(frag);
      if (frag.startsWith(",")) {
        frag.remove(0, 1);
      }
      json += frag;
    } else {
      json += "\"error\":\"no_host\"";
    }
    json += "}";
    srv->send(200, "application/json", json);
  });
#endif

  server.on("/api/capture/drain", HTTP_GET, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "text/plain", "no_onchip\n");
      return;
    }
    size_t max_n = 64;
    if (srv->hasArg("n")) {
      max_n = static_cast<size_t>(srv->arg("n").toInt());
      if (max_n == 0 || max_n > 512) {
        max_n = 64;
      }
    }
    String body = onchip_->capture().drainJsonl(max_n);
    srv->send(200, "application/x-ndjson", body);
  });

  server.on("/api/capture/inject", HTTP_POST, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "application/json", "{\"ok\":false,\"error\":\"no_onchip\"}");
      return;
    }
    String hex = srv->arg("plain");
    if (!hex.length()) {
      hex = srv->arg("hex");
    }
    uint8_t buf[kCaptureMaxPayload];
    size_t n = parseHex(hex, buf, sizeof(buf));
    if (n == 0) {
      srv->send(400, "application/json",
                "{\"ok\":false,\"error\":\"hex_required\"}");
      return;
    }
    const bool ok = onchip_->capture().injectRaw(
        HciPacketType::Event, HciDirection::ControllerToHost, 0, buf, n);
    srv->send(ok ? 200 : 500, "application/json",
              ok ? "{\"ok\":true}" : "{\"ok\":false,\"error\":\"enqueue\"}");
  });

  server.on("/api/hci/write", HTTP_POST, [this, srv]() {
    if (!onchip_) {
      srv->send(503, "application/json", "{\"ok\":false,\"error\":\"no_onchip\"}");
      return;
    }
    String hex = srv->arg("hex");
    if (!hex.length()) {
      hex = srv->arg("plain");
    }
    uint8_t buf[kCaptureMaxPayload];
    size_t n = parseHex(hex, buf, sizeof(buf));
    if (n == 0) {
      srv->send(400, "application/json",
                "{\"ok\":false,\"error\":\"hex_required\"}");
      return;
    }
    // Accept either raw HCI command (no type) or full H4 (leading 01/…).
    bool ok = false;
    if (n >= 1 && (buf[0] == 0x01 || buf[0] == 0x02 || buf[0] == 0x03)) {
      ok = onchip_->capture().writeH4(buf, n);
    } else {
      ok = onchip_->capture().writeCommand(buf, n);
    }
    srv->send(ok ? 200 : 500, "application/json",
              ok ? "{\"ok\":true}" : "{\"ok\":false,\"error\":\"write_failed\"}");
  });
}

}  // namespace bt_analyzer
