#pragma once

/**
 * @file BootContext.h
 * @brief Boot facade that starts PanicTail and Checkpoint.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include "DiagLog.h"
#include "PanicTail.h"
#include "Checkpoint.h"
#include "Recovery.h"

/**
 * @brief Boot-facing facade over DiagLog, PanicTail, Checkpoint, Recovery.
 *
 * Call order: DiagLog → PanicTail → Checkpoint → Recovery, then a forced boot snapshot.
 */
namespace BootContext {
/** @brief Start diagnostic and recovery layers and print the boot summary. */
inline void begin() {
    DiagLog::begin();
    PanicTail::begin();
    PanicTail::logToSerial();
    Checkpoint::begin();
    Checkpoint::logToSerial();
    Recovery::begin();
    DiagLog::persist("boot", true);
}
}  // namespace BootContext
