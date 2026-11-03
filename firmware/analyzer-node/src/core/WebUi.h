#pragma once

/**
 * @file WebUi.h
 * @brief Embedded status/SSE/OTA web server.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include "EspHubConfig.h"
#include "HardwareInfo.h"

class OtaService;
class ModuleManager;

/**
 * @brief Status/OTA SPA (gzip PROGMEM from web/index.html), SSE, APIs.
 */
class WebUi {
public:
    void setHardware(const HardwareInfo* hw) { hw_ = hw; }
    void setOta(OtaService* ota) { ota_ = ota; }
    void setModules(ModuleManager* modules) { modules_ = modules; }

    void begin(const String& deviceName, const String& hubHost, int hubPort,
               unsigned long heartbeatIntervalMs);
    void updateConfig(const String& deviceName, const String& hubHost, int hubPort,
                      unsigned long heartbeatIntervalMs);
    void handleClient();
    void pushSseIfDue(unsigned long nowMs);

    /** @brief Pump the active instance (used as OTA yield). */
    static void pumpActiveClient();

    WebServer& server() { return webServer_; }

    String buildStatusJson() const;

private:
    void registerRoutes();
    void handleRoot();
    void handleStatus();
    void handleEvents();
    void handleOtaPage();
    void handleOtaUpload();
    void handleOtaUploadFinish();
    void handleNotFound();
    void sseSend(const String& data);

    WebServer webServer_{80};
    WiFiClient sseClient_;
    const HardwareInfo* hw_ = nullptr;
    OtaService* ota_ = nullptr;
    ModuleManager* modules_ = nullptr;

    String deviceName_ = DEVICE_NAME;
    String hubHost_ = HUB_HOST;
    int hubPort_ = HUB_PORT;
    unsigned long heartbeatIntervalMs_ = (unsigned long)DEFAULT_INTERVAL_S * 1000UL;
    unsigned long lastSseSend_ = 0;

    static WebUi* active_;
};
