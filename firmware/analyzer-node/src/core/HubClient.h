#pragma once

/**
 * @file HubClient.h
 * @brief ESP-Hub register/heartbeat client.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include <Arduino.h>
#include "EspHubConfig.h"
#include "HardwareInfo.h"

/**
 * @brief ESP-Hub HTTP register/heartbeat client (POST /api/register).
 */
class HubClient {
public:
    void setHardware(const HardwareInfo* hw) { hw_ = hw; }
    void configure(const String& deviceName, const String& hubHost, int hubPort);

    /**
     * @brief POST /api/register; updates timing/OTA/name from the Hub reply.
     * @param[in,out] deviceName  Local name; replaced when Hub sends a new name.
     * @param[out] nameChanged    Set true when deviceName was updated (persist/UI).
     * @return true on HTTP 200.
     */
    bool sendHeartbeat(String& deviceName,
                       unsigned long& lastSuccessMs,
                       unsigned long& heartbeatIntervalMs,
                       bool& otaPending,
                       String& otaUrl,
                       bool* nameChanged = nullptr);

    String buildHeartbeatJson() const;

private:
    String deviceName_ = DEVICE_NAME;
    String hubHost_ = HUB_HOST;
    int hubPort_ = HUB_PORT;
    const HardwareInfo* hw_ = nullptr;
};
