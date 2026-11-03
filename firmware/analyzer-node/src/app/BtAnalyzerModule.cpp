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
    while (i < hex.length() && (hex[i] == ' ' || hex[i] == ':' || hex[i] == '-')) {
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

  server.on("/api/usb/last-event", HTTP_GET, [this, srv]() {
    if (!host_) {
      srv->send(503, "application/json", "{\"error\":\"no_host\"}");
      return;
    }
    String body = host_->lastEventJson();
    if (!body.length()) {
      body = "{\"event\":\"none\"}";
    }
    srv->send(200, "application/json", body);
  });

  server.on("/api/usb/status", HTTP_GET, [this, srv]() {
    String json = "{";
    if (host_) {
      String frag;
      host_->appendStatusJson(frag);
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

  server.on("/api/capture/drain", HTTP_GET, [this, srv]() {
    if (!host_) {
      srv->send(503, "text/plain", "no_host\n");
      return;
    }
    size_t max_n = 64;
    if (srv->hasArg("n")) {
      max_n = static_cast<size_t>(srv->arg("n").toInt());
      if (max_n == 0 || max_n > 512) {
        max_n = 64;
      }
    }
    String body = host_->hciCapture().drainJsonl(max_n);
    srv->send(200, "application/x-ndjson", body);
  });

  server.on("/api/capture/inject", HTTP_POST, [this, srv]() {
    if (!host_) {
      srv->send(503, "application/json", "{\"ok\":false,\"error\":\"no_host\"}");
      return;
    }
    // Body: raw hex string, or form field "hex"
    String hex = srv->arg("plain");
    if (!hex.length()) {
      hex = srv->arg("hex");
    }
    if (!hex.length()) {
      hex = srv->arg("plain");  // some clients
    }
    // Esp WebServer: raw body often in arg("plain") when content-type text
    if (!hex.length() && srv->hasArg("plain")) {
      hex = srv->arg("plain");
    }
    uint8_t buf[kCaptureMaxPayload];
    size_t n = parseHex(hex, buf, sizeof(buf));
    if (n == 0) {
      srv->send(400, "application/json",
                "{\"ok\":false,\"error\":\"hex_required\"}");
      return;
    }
    const bool ok = host_->hciCapture().injectRaw(
        HciPacketType::Event, HciDirection::ControllerToHost, 0x81, buf, n);
    srv->send(ok ? 200 : 500, "application/json",
               ok ? "{\"ok\":true}" : "{\"ok\":false,\"error\":\"enqueue\"}");
  });

  server.on("/api/hci/write", HTTP_POST, [this, srv]() {
    if (!host_) {
      srv->send(503, "application/json", "{\"ok\":false,\"error\":\"no_host\"}");
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
    const bool ok = host_->hciCapture().writeHost(buf, n);
    srv->send(ok ? 200 : 500, "application/json",
               ok ? "{\"ok\":true}" : "{\"ok\":false,\"error\":\"write_failed\"}");
  });
}

}  // namespace bt_analyzer
