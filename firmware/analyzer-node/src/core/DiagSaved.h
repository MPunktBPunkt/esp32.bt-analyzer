#pragma once

/**
 * @file DiagSaved.h
 * @brief Persisted boot/checkpoint diagnostic snapshot for GET /api/diag/saved.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include <Arduino.h>
#include "HardwareInfo.h"

/**
 * @brief NVS-backed diagnostic snapshot separated from live /api/status (D-012, D-013).
 *
 * Captured once at a boot Safe Point after PanicTail/Checkpoint/HardwareInfo are ready.
 * No writes from the hot loop.
 */
class DiagSaved {
public:
    /**
     * @brief Persist the current boot diagnostic view to NVS (Safe Point only).
     * @param hw  Probed hardware capabilities included in the snapshot; may be nullptr.
     */
    static void persistBootSnapshot(const HardwareInfo* hw);

    /**
     * @brief Load the last persisted snapshot JSON from NVS.
     * @return JSON object string, or `{"saved":false}` when none exists.
     */
    static String loadJson();

    /**
     * @brief Whether an NVS snapshot is present.
     * @return true if a non-empty snapshot was stored.
     */
    static bool hasSaved();

    /**
     * @brief Clear the persisted snapshot (manual / test).
     */
    static void clear();

private:
    DiagSaved() = delete;
};
