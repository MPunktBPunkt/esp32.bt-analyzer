/**
 * @file NetworkWifi.cpp
 * @brief WiFi setup, reconnect maintain, and portal reset.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include "NetworkWifi.h"
#include "PanicTail.h"
#include "Recovery.h"

void NetworkWifi::checkResetButton() {
    pinMode(RESET_BUTTON_PIN, INPUT_PULLUP);
    if (digitalRead(RESET_BUTTON_PIN) == HIGH) return;
    Serial.println("[RESET] Halte " + String(RESET_HOLD_SEC) + "s...");
    unsigned long t = millis();
    while (digitalRead(RESET_BUTTON_PIN) == LOW) {
        if (millis() - t > (unsigned long)RESET_HOLD_SEC * 1000UL) {
            Serial.println("[RESET] Geloescht! Neustart...");
            PanicTail::breadcrumb(PanicTail::ResetButton);
            wifiManager_.resetSettings();
            prefs_.begin("esphub", false);
            prefs_.clear();
            prefs_.end();
            Recovery::requestRestart(Recovery::WifiReset, "boot_button");
        }
        delay(100);
    }
}

void NetworkWifi::begin(String& deviceName, String& hubHost, int& hubPort) {
    prefs_.begin("esphub", false);
    String sName = prefs_.getString("name", deviceName);
    String sHost = prefs_.getString("hub_host", hubHost);
    int    sPort = prefs_.getInt("hub_port", hubPort);
    prefs_.end();
    deviceName = sName;
    hubHost = sHost;
    hubPort = sPort;

    WiFiManagerParameter pName("name", "Geraetename", deviceName.c_str(), 32);
    WiFiManagerParameter pHost("hub_host", "ESP-Hub IP", hubHost.c_str(), 40);
    WiFiManagerParameter pPort("hub_port", "Port", String(hubPort).c_str(), 6);
    wifiManager_.addParameter(&pName);
    wifiManager_.addParameter(&pHost);
    wifiManager_.addParameter(&pPort);
    wifiManager_.setConfigPortalTimeout(WIFI_PORTAL_TIMEOUT_S);
    wifiManager_.setAPCallback([](WiFiManager*) {
        Serial.println("[WiFi] Portal: " WIFI_AP_NAME);
    });
    if (!wifiManager_.autoConnect(WIFI_AP_NAME)) {
        Recovery::requestRestart(Recovery::WifiPortalTimeout, "autoConnect_fail");
    }

    prefs_.begin("esphub", false);
    prefs_.putString("name", String(pName.getValue()));
    prefs_.putString("hub_host", String(pHost.getValue()));
    prefs_.putInt("hub_port", String(pPort.getValue()).toInt());
    prefs_.end();
    deviceName = String(pName.getValue());
    hubHost = String(pHost.getValue());
    hubPort = String(pPort.getValue()).toInt();
    Serial.println("[WiFi] IP: " + WiFi.localIP().toString() +
                   " Name: " + deviceName + " Hub: " + hubHost + ":" + String(hubPort));
}

void NetworkWifi::maintain() {
    if (WiFi.status() != WL_CONNECTED) {
        PanicTail::breadcrumb(PanicTail::WifiLost);
        delay(5000);
        if (WiFi.status() != WL_CONNECTED) WiFi.reconnect();
    }
}
