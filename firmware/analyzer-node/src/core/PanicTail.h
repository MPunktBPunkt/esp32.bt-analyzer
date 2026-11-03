#pragma once

/**
 * @file PanicTail.h
 * @brief RTC-retained lifecycle breadcrumbs and restart cause.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include <Arduino.h>

/**
 * @brief RTC-retained lifecycle breadcrumbs and planned restart cause (D-009).
 */
class PanicTail {
public:
    enum Code : uint8_t {
        Boot = 1,
        WifiUp = 2,
        HubOk = 3,
        WebUp = 4,
        OtaStart = 5,
        WifiLost = 6,
        WdtFire = 7,
        RestartRequested = 8,
        ResetButton = 9,
    };

    enum RestartCause : uint8_t {
        RestartNone = 0,
        RestartWifiPortalTimeout = 1,
        RestartHubOta = 2,
        RestartWebOta = 3,
        RestartWatchdog = 4,
        RestartWifiReset = 5,
    };

    /** Call once early in boot, before breadcrumbs. */
    static void begin();

    static void breadcrumb(Code code, uint32_t arg = 0);

    /** Record planned restart cause in RTC (no flash). Caller may delay then restart. */
    static void noteRestart(RestartCause cause);

    /** noteRestart + short delay + ESP.restart(). */
    static void requestRestart(RestartCause cause);

    static const char* resetReason();
    static const char* restartCause();  // cause from *previous* boot
    static uint32_t bootGeneration();
    static bool previousValid();

    /** Serial summary of this boot + previous tail. */
    static void logToSerial();

    /** Additive /api/status fields (baseline keys untouched). */
    static void appendStatusFields(String& json);

    /** Full boot/diag JSON for GET /api/diag/boot. */
    static String buildDiagJson();

private:
    PanicTail() = delete;
};
