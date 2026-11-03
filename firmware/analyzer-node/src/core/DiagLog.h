#pragma once

/**
 * @file DiagLog.h
 * @brief Diagnostic text log: RAM ring, RTC tail, NVS flash snapshots (D-007/D-008).
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include <Arduino.h>

/**
 * @brief Multi-tier diagnostic log for post-mortem without a UART cable.
 *
 * Levels: RAM ring (live) → RTC_NOINIT tail (survives soft reset) → NVS snapshots
 * (survive power loss). Flash/NVS writes only via persist() at Safe Points.
 */
namespace DiagLog {

/**
 * @brief Rescue previous RTC tail, reset RTC ring, allocate RAM ring.
 * @note Call once early in boot before the first printf().
 */
void begin();

/**
 * @brief Append a printf-style line to Serial, RAM ring, and RTC ring.
 * @param fmt  printf format string.
 * @param ...  Format arguments.
 */
void printf(const char* fmt, ...) __attribute__((format(printf, 1, 2)));

/**
 * @brief Previous boot's RTC text (empty after power-on).
 * @return NUL-terminated buffer owned by DiagLog.
 */
const char* previousTail();

/**
 * @brief Bytes currently held in the RAM ring.
 * @return 0 if the ring was not allocated.
 */
size_t ramSize();

/**
 * @brief Copy a slice of the RAM ring (offset 0 = oldest).
 * @param offset  Start offset from oldest byte.
 * @param[out] dst Destination buffer.
 * @param n       Max bytes to copy.
 * @return Bytes copied.
 */
size_t copyRam(size_t offset, char* dst, size_t n);

/**
 * @brief Persist a snapshot to NVS (rate-limited unless forced).
 * @param reason  Short tag (e.g. boot, restart, ckpt).
 * @param force   Ignore rate limit (planned restart / first boot dump).
 * @return true if a snapshot was written.
 * @warning NVS write — Safe Point only (D-008, D-020).
 */
bool persist(const char* reason, bool force = false);

/**
 * @brief Number of valid NVS snapshots (0..kSlots).
 * @return Snapshot count.
 */
uint8_t snapshotCount();

/**
 * @brief Load newest snapshot text from NVS.
 * @param newestIndex 0 = newest.
 * @return Snapshot body or empty string.
 */
String loadSnapshot(uint8_t newestIndex);

/**
 * @brief JSON for GET /api/diag/log (ram excerpt + prevTail + snapshot meta).
 * @return JSON object string.
 */
String buildLogJson();

/**
 * @brief Additive /api/status counters (diagRam, diagPrev, diagSnaps).
 * @param[in,out] json Status JSON being built.
 */
void appendStatusFields(String& json);

}  // namespace DiagLog
