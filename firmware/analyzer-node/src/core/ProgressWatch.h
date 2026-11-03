#pragma once

/**
 * @file ProgressWatch.h
 * @brief Progress-based stall detection running parallel to the legacy time WDT (D-010).
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include <Arduino.h>
#include "EspHubConfig.h"

#ifndef PROGRESS_TIMEOUT_S
#define PROGRESS_TIMEOUT_S WATCHDOG_TIMEOUT_S
#endif

/**
 * @brief Tracks forward progress on Idle / Heartbeat / OTA channels.
 *
 * M7 rule: evaluate() may log and expose stall state, but must not replace the
 * legacy lastSuccess watchdog — kept after M11 until Field-Evidence (D-010).
 */
class ProgressWatch {
public:
    enum Channel : uint8_t {
        Idle = 0,
        Heartbeat = 1,
        Ota = 2,
        ChannelCount = 3,
    };

    /** @brief Initialize channel timestamps to now. */
    static void begin();

    /**
     * @brief Record progress on a channel.
     * @param channel  Idle, Heartbeat, or Ota.
     */
    static void note(Channel channel);

    /**
     * @brief Evaluate stalls; log transitions; never restarts the device (M7).
     * @param nowMs  Current millis().
     */
    static void evaluate(unsigned long nowMs);

    /**
     * @brief Whether the given channel has not progressed within PROGRESS_TIMEOUT_S.
     * @param channel  Channel to inspect.
     * @param nowMs    Current millis().
     * @return true if stalled (and progress watch is enabled).
     */
    static bool stalled(Channel channel, unsigned long nowMs);

    /** @brief Snake_case channel name. */
    static const char* name(Channel channel);

    /**
     * @brief Additive status fields: progIdleAge, progHbAge, progOtaAge, progStalled.
     * @param[in,out] json Status JSON being built.
     */
    static void appendStatusFields(String& json);

private:
    ProgressWatch() = delete;
};
