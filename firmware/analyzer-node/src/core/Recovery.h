#pragma once

/**
 * @file Recovery.h
 * @brief Explicit recovery layer: reasons, escalation, history (D-011).
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include <Arduino.h>

/**
 * @brief Single entry point for planned device restarts.
 *
 * Replaces scattered PanicTail::requestRestart / ESP.restart call sites.
 * Records reason + level into an RTC history ring and then delegates to PanicTail.
 */
class Recovery {
public:
    enum Reason : uint8_t {
        None = 0,
        WifiPortalTimeout = 1,
        HubOta = 2,
        WebOta = 3,
        LegacyWatchdog = 4,
        WifiReset = 5,
    };

    enum Level : uint8_t {
        Soft = 0,       ///< Planned / user-driven (OTA, WiFi reset)
        Degraded = 1,   ///< Recoverable infra failure (portal timeout)
        Hard = 2,       ///< Forced health restart (legacy WDT)
    };

    /** @brief Load RTC history and log the previous recovery, if any. */
    static void begin();

    /**
     * @brief Record recovery and restart the device.
     * @param reason  Why recovery was requested.
     * @param detail  Optional short detail for DiagLog (may be nullptr).
     */
    static void requestRestart(Reason reason, const char* detail = nullptr);

    /** @brief Snake_case reason name. */
    static const char* reasonName(Reason reason);

    /** @brief Escalation level for a reason. */
    static Level levelFor(Reason reason);

    /** @brief Snake_case level name. */
    static const char* levelName(Level level);

    /** @brief Hard recoveries counted in the current RTC generation window. */
    static uint8_t hardCount();

    /** @brief Total recoveries retained in the RTC history ring. */
    static uint8_t historyCount();

    /** @brief Additive /api/status fields. */
    static void appendStatusFields(String& json);

    /** @brief Nested object for /api/diag/boot. */
    static void appendDiagFields(String& json);

    /** @brief Standalone JSON for GET /api/diag/recovery. */
    static String buildDiagJson();

private:
    Recovery() = delete;
};
