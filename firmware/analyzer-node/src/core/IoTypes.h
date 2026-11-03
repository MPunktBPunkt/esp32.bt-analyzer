#pragma once

/**
 * @file IoTypes.h
 * @brief Project IO table types provided by the sketch.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include <Arduino.h>

/** @brief One dashboard IO row defined in the sketch IO table. */
struct IoValue {
    String key;   ///< Hub/status key
    String type;  ///< e.g. sensor / output
    float  value; ///< Current value
    String unit;  ///< Optional unit string
};

/** @brief Sketch-provided IO table (may be empty). */
extern IoValue ioTable[];
/** @brief Number of entries in ioTable. */
extern const int IO_COUNT;
/** @brief Sketch hook to refresh ioTable values before status/heartbeat. */
void updateIoValues();
