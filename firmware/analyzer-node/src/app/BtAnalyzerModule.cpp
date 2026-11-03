#include "app/BtAnalyzerModule.h"

namespace bt_analyzer {

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
}

}  // namespace bt_analyzer
