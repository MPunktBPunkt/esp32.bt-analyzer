#pragma once

/**
 * @file AppCore.h
 * @brief Central firmware lifecycle: begin() and loop() orchestration.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include "EspHubConfig.h"
#include "HardwareInfo.h"
#include "NetworkWifi.h"
#include "HubClient.h"
#include "WebUi.h"
#include "OtaService.h"
#include "ModuleManager.h"

/**
 * @brief Central lifecycle (D-005); begin()/loop() replace monolithic setup/loop bodies.
 */
class AppCore {
public:
    /**
     * @brief Access the module registry (call add() before begin()).
     * @return Module manager reference.
     */
    ModuleManager& modules() { return modules_; }

    /** @brief Probe hardware, start network/web/hub/modules, send first heartbeat. */
    void begin();
    /** @brief Drive web, modules, heartbeat, OTA, progress/WDT, WiFi maintain. */
    void loop();

private:
    HardwareInfo hw_;
    NetworkWifi net_;
    HubClient hub_;
    WebUi web_;
    OtaService ota_;
    ModuleManager modules_;

    String deviceName_ = DEVICE_NAME;
    String hubHost_ = HUB_HOST;
    int hubPort_ = HUB_PORT;

    unsigned long lastHeartbeat_ = 0;
    unsigned long heartbeatIntervalMs_ = (unsigned long)DEFAULT_INTERVAL_S * 1000UL;
    unsigned long lastSuccess_ = 0;
    bool otaPending_ = false;
    String otaUrl_;
};
