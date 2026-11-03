/**
 * @file HubClient.cpp
 * @brief Heartbeat JSON build and HTTP register POST.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include "HubClient.h"
#include "IoTypes.h"

#include <HTTPClient.h>
#include <Preferences.h>
#include <WiFi.h>
#include <ArduinoJson.h>

void HubClient::configure(const String& deviceName, const String& hubHost, int hubPort) {
    deviceName_ = deviceName;
    hubHost_ = hubHost;
    hubPort_ = hubPort;
}

static String macNoColon() {
    String mac = WiFi.macAddress();
    mac.replace(":", "");
    mac.toUpperCase();
    return mac;
}

String HubClient::buildHeartbeatJson() const {
    updateIoValues();
#if ARDUINOJSON_VERSION_MAJOR >= 7
    JsonDocument doc;
#else
    DynamicJsonDocument doc(1024);
#endif
    doc["mac"] = macNoColon();
    doc["name"] = deviceName_;
    doc["hwType"] = "esp32";
    doc["chipModel"] = hw_ ? hw_->chipModel() : String(ESP.getChipModel());
    doc["version"] = FW_VERSION;
    doc["ip"] = WiFi.localIP().toString();
    doc["rssi"] = WiFi.RSSI();
    doc["uptime"] = millis() / 1000UL;
    doc["freeHeap"] = hw_ ? hw_->freeHeap() : ESP.getFreeHeap();
    doc["freeSketch"] = hw_ ? hw_->freeSketchSpace() : ESP.getFreeSketchSpace();
    doc["freePsram"] = hw_ ? hw_->freePsram() : ESP.getFreePsram();
    doc["psramSize"] = hw_ ? hw_->psramSize() : ESP.getPsramSize();
    JsonObject ios = doc["ios"].to<JsonObject>();
    for (int i = 0; i < IO_COUNT; i++) {
        JsonObject io = ios[ioTable[i].key].to<JsonObject>();
        io["type"] = ioTable[i].type;
        io["value"] = ioTable[i].value;
        if (ioTable[i].unit.length() > 0) io["unit"] = ioTable[i].unit;
    }
    String out;
    serializeJson(doc, out);
    return out;
}

bool HubClient::sendHeartbeat(String& deviceName,
                              unsigned long& lastSuccessMs,
                              unsigned long& heartbeatIntervalMs,
                              bool& otaPending,
                              String& otaUrl,
                              bool* nameChanged) {
    if (nameChanged) *nameChanged = false;
    deviceName_ = deviceName;
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[HB] Kein WLAN");
        return false;
    }
    String payload = buildHeartbeatJson();
    String url = "http://" + hubHost_ + ":" + String(hubPort_) + "/api/register";
    Serial.println("[HB] -> " + url);
    HTTPClient http;
    http.begin(url);
    http.addHeader(F("Content-Type"), F("application/json"));
    http.setTimeout(8000);
    int code = http.POST(payload);
    bool ok = false;
    if (code == 200) {
        String body = http.getString();
        lastSuccessMs = millis();
        ok = true;
#if ARDUINOJSON_VERSION_MAJOR >= 7
        JsonDocument resp;
#else
        DynamicJsonDocument resp(512);
#endif
        if (deserializeJson(resp, body) == DeserializationError::Ok) {
            if (resp["interval"].is<int>()) {
                unsigned long ni = (unsigned long)(int)resp["interval"] * 1000UL;
                if (ni != heartbeatIntervalMs && ni >= 5000UL) {
                    heartbeatIntervalMs = ni;
                }
            }
            if (!resp["otaUrl"].isNull()) {
                String u = resp["otaUrl"].as<String>();
                if (u.length() > 0) {
                    otaPending = true;
                    otaUrl = u;
                    Serial.println("[HB] OTA: " + u);
                }
            }
            // Hub rename / name sync (iobroker.esp-hub reply.name).
            if (!resp["name"].isNull()) {
                String newName = resp["name"].as<String>();
                newName.trim();
                if (newName.length() > 0 && newName != deviceName) {
                    deviceName = newName;
                    deviceName_ = newName;
                    Preferences prefs;
                    if (prefs.begin("esphub", false)) {
                        prefs.putString("name", deviceName);
                        prefs.end();
                    }
                    Serial.println("[HB] Name: " + deviceName);
                    if (nameChanged) *nameChanged = true;
                }
            }
        }
    } else {
        Serial.printf("[HB] HTTP %d\n", code);
    }
    http.end();
    return ok;
}
