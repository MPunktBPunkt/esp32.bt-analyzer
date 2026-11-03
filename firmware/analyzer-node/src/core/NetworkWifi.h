#pragma once

/**
 * @file NetworkWifi.h
 * @brief WiFiManager portal, NVS hub settings, BOOT reset gesture.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include <Arduino.h>
#include <Preferences.h>
#include <WiFiManager.h>
#include "EspHubConfig.h"

/**
 * @brief WiFiManager portal, NVS name/hub settings, and BOOT reset gesture.
 */
class NetworkWifi {
public:
    void checkResetButton();
    void begin(String& deviceName, String& hubHost, int& hubPort);
    void maintain();  // reconnect helper (baseline: delay+reconnect)

    WiFiManager& manager() { return wifiManager_; }

private:
    Preferences prefs_;
    WiFiManager wifiManager_;
};
