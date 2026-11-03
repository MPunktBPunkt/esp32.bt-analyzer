/**
 * @file WebUi.cpp
 * @brief Web routes, status JSON, SSE, and upload OTA handlers.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include "WebUi.h"
#include "IoTypes.h"
#include "Checkpoint.h"
#include "CpuLoad.h"
#include "DiagLog.h"
#include "DiagSaved.h"
#include "ModuleManager.h"
#include "OtaService.h"
#include "PanicTail.h"
#include "ProgressWatch.h"
#include "Recovery.h"
#include "UiPages.h"

#include <Update.h>
#include <WiFi.h>

WebUi* WebUi::active_ = nullptr;

// ── helpers ──────────────────────────────────────────────────────

static String macNoColon() {
    String mac = WiFi.macAddress();
    mac.replace(":", "");
    mac.toUpperCase();
    return mac;
}

static String fmtUptime(unsigned long s) {
    if (s < 60) return String(s) + "s";
    if (s < 3600) return String(s / 60) + "min " + String(s % 60) + "s";
    return String(s / 3600) + "h " + String((s % 3600) / 60) + "min";
}

void WebUi::begin(const String& deviceName, const String& hubHost, int hubPort,
                  unsigned long heartbeatIntervalMs) {
    active_ = this;
    updateConfig(deviceName, hubHost, hubPort, heartbeatIntervalMs);
    registerRoutes();
    if (modules_) modules_->registerRoutes(webServer_);
    webServer_.begin();
    Serial.println("[WEB] http://" + WiFi.localIP().toString() + "/");
}

void WebUi::pumpActiveClient() {
    if (active_) active_->handleClient();
}

void WebUi::updateConfig(const String& deviceName, const String& hubHost, int hubPort,
                         unsigned long heartbeatIntervalMs) {
    deviceName_ = deviceName;
    hubHost_ = hubHost;
    hubPort_ = hubPort;
    heartbeatIntervalMs_ = heartbeatIntervalMs;
}

void WebUi::registerRoutes() {
    webServer_.on("/", HTTP_GET, [this]() { handleRoot(); });
    webServer_.on("/events", HTTP_GET, [this]() { handleEvents(); });
    webServer_.on("/api/status", HTTP_GET, [this]() { handleStatus(); });
    webServer_.on("/api/diag/boot", HTTP_GET, [this]() {
        webServer_.sendHeader(F("Access-Control-Allow-Origin"), F("*"));
        webServer_.send(200, F("application/json"), PanicTail::buildDiagJson());
    });
    webServer_.on("/api/diag/saved", HTTP_GET, [this]() {
        webServer_.sendHeader(F("Access-Control-Allow-Origin"), F("*"));
        webServer_.send(200, F("application/json"), DiagSaved::loadJson());
    });
    webServer_.on("/api/diag/log", HTTP_GET, [this]() {
        webServer_.sendHeader(F("Access-Control-Allow-Origin"), F("*"));
        webServer_.send(200, F("application/json"), DiagLog::buildLogJson());
    });
    webServer_.on("/api/diag/recovery", HTTP_GET, [this]() {
        webServer_.sendHeader(F("Access-Control-Allow-Origin"), F("*"));
        webServer_.send(200, F("application/json"), Recovery::buildDiagJson());
    });
    webServer_.on("/ota", HTTP_GET, [this]() { handleOtaPage(); });
    webServer_.on("/ota-upload", HTTP_POST,
                  [this]() { handleOtaUploadFinish(); },
                  [this]() { handleOtaUpload(); });
    webServer_.onNotFound([this]() { handleNotFound(); });
}

void WebUi::handleClient() { webServer_.handleClient(); }

void WebUi::pushSseIfDue(unsigned long nowMs) {
    if (nowMs - lastSseSend_ >= 4000UL) {
        lastSseSend_ = nowMs;
        if (sseClient_ && sseClient_.connected()) sseSend(buildStatusJson());
    }
}

String WebUi::buildStatusJson() const {
    updateIoValues();
    String ios = "{";
    for (int i = 0; i < IO_COUNT; i++) {
        if (i > 0) ios += ",";
        ios += "\"" + ioTable[i].key + "\":{\"v\":" + String(ioTable[i].value, 2)
             + ",\"u\":\"" + ioTable[i].unit + "\",\"t\":\"" + ioTable[i].type + "\"}";
    }
    ios += "}";
    const String chip = hw_ ? hw_->chipModel() : String(ESP.getChipModel());
    const uint32_t heap = hw_ ? hw_->freeHeap() : ESP.getFreeHeap();
    const size_t psramFree = hw_ ? hw_->freePsram() : ESP.getFreePsram();
    const size_t psramSize = hw_ ? hw_->psramSize() : ESP.getPsramSize();
    const uint32_t sketch = hw_ ? hw_->freeSketchSpace() : ESP.getFreeSketchSpace();
    String j = "{";
    j += "\"name\":\"" + deviceName_ + "\"";
    j += ",\"version\":\"" FW_VERSION "\"";
    j += ",\"chip\":\"" + chip + "\"";
    j += ",\"mac\":\"" + macNoColon() + "\"";
    j += ",\"ip\":\"" + WiFi.localIP().toString() + "\"";
    j += ",\"rssi\":" + String(WiFi.RSSI());
    j += ",\"uptime\":\"" + fmtUptime(millis() / 1000UL) + "\"";
    j += ",\"heap\":" + String(heap);
    j += ",\"psram\":" + String(psramFree);
    j += ",\"psramSize\":" + String(psramSize);
    j += ",\"sketch\":" + String(sketch);
    j += ",\"hub\":\"" + hubHost_ + ":" + String(hubPort_) + "\"";
    j += ",\"interval\":" + String(heartbeatIntervalMs_ / 1000);
    if (hw_) hw_->appendStatusFields(j);
    PanicTail::appendStatusFields(j);
    Checkpoint::appendStatusFields(j);
    DiagLog::appendStatusFields(j);
    ProgressWatch::appendStatusFields(j);
    Recovery::appendStatusFields(j);
    CpuLoad::appendStatusFields(j);
    if (ota_) ota_->appendStatusFields(j);
    if (modules_) modules_->appendStatusJson(j);
    j += ",\"ios\":" + ios + "}";
    return j;
}

void WebUi::sseSend(const String& data) {
    if (!sseClient_ || !sseClient_.connected()) return;
    sseClient_.print("data: ");
    sseClient_.print(data);
    sseClient_.print("\n\n");
    sseClient_.flush();
}

void WebUi::handleRoot() {
    webServer_.sendHeader(F("Content-Encoding"), F("gzip"));
    webServer_.sendHeader(F("Cache-Control"), F("no-store"));
    webServer_.send_P(200, "text/html", (PGM_P)PAGE_MAIN_GZ, PAGE_MAIN_GZ_LEN);
}

void WebUi::handleStatus() {
    webServer_.sendHeader(F("Access-Control-Allow-Origin"), F("*"));
    webServer_.send(200, F("application/json"), buildStatusJson());
}

void WebUi::handleEvents() {
    if (sseClient_ && sseClient_.connected()) sseClient_.stop();
    sseClient_ = webServer_.client();
    sseClient_.print(F("HTTP/1.1 200 OK\r\n"
                       "Content-Type: text/event-stream\r\n"
                       "Cache-Control: no-cache\r\n"
                       "Connection: keep-alive\r\n"
                       "Access-Control-Allow-Origin: *\r\n"
                       "\r\n"));
    sseClient_.flush();
    sseSend(buildStatusJson());
    Serial.println("[SSE] Client: " + sseClient_.remoteIP().toString());
}

void WebUi::handleOtaPage() {
    // Same SPA as / — client opens the OTA tab from the path.
    handleRoot();
}

void WebUi::handleOtaUpload() {
    HTTPUpload& upload = webServer_.upload();
    if (!ota_) return;
    if (upload.status == UPLOAD_FILE_START) {
        ota_->webBegin(upload.filename.c_str());
    } else if (upload.status == UPLOAD_FILE_WRITE) {
        ota_->webWrite(upload.buf, upload.currentSize);
    } else if (upload.status == UPLOAD_FILE_END) {
        const bool ok = !Update.hasError();
        ota_->webFinish(ok);
        if (ok) Serial.printf("\n[WEB-OTA] OK %u Bytes\n", upload.totalSize);
    }
}

void WebUi::handleOtaUploadFinish() {
    if (!ota_ || ota_->state() == OtaService::Failed || Update.hasError()) {
        webServer_.send(500, F("text/plain"), F("OTA fehlgeschlagen!"));
        return;
    }
    webServer_.send(200, F("text/plain"), F("OK - Neustart..."));
    Recovery::requestRestart(Recovery::WebOta, "web_upload_ok");
}

void WebUi::handleNotFound() {
    webServer_.sendHeader(F("Location"), F("/"), true);
    webServer_.send(302, F("text/plain"), F(""));
}
