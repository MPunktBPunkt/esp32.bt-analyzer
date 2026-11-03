/**
 * @file DiagSaved.cpp
 * @brief NVS persistence for the boot diagnostic snapshot.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include "DiagSaved.h"
#include "EspHubConfig.h"
#include "PanicTail.h"
#include "Checkpoint.h"

#include <Preferences.h>

namespace {

constexpr const char* kNvsNs = "ehdiag";
constexpr const char* kKeySnap = "snap";
constexpr size_t kMaxSnapBytes = 2048;

void appendHwFields(String& j, const HardwareInfo* hw) {
    if (!hw || !hw->probed()) return;
    j += ",\"chip\":\"";
    j += hw->chipModel();
    j += "\",\"flashKb\":";
    j += String(hw->flashSizeKb());
    j += ",\"psramSize\":";
    j += String((uint32_t)hw->psramSize());
    j += ",\"hasPsram\":";
    j += hw->hasPsram() ? "true" : "false";
}

void appendMeta(String& j, bool truncated) {
    j += "\"saved\":true";
    if (truncated) j += ",\"truncated\":true";
    j += ",\"fw\":\"";
    j += FW_VERSION;
    j += "\",\"bootGen\":";
    j += String(PanicTail::bootGeneration());
    j += ",\"resetReason\":\"";
    j += PanicTail::resetReason();
    j += "\",\"restartCause\":\"";
    j += PanicTail::restartCause();
    j += "\"";
}

/** @brief Full snapshot including live diag object. */
String buildFullSnapshot(const HardwareInfo* hw) {
    String j = "{";
    appendMeta(j, false);
    appendHwFields(j, hw);
    j += ",\"diag\":";
    j += PanicTail::buildDiagJson();
    j += "}";
    return j;
}

/**
 * @brief Compact but still valid JSON when the full diag blob exceeds NVS budget.
 *
 * Drops nested panic breadcrumbs; keeps reset/checkpoint last-open summary.
 */
String buildCompactSnapshot(const HardwareInfo* hw) {
    String j = "{";
    appendMeta(j, true);
    appendHwFields(j, hw);
    j += ",\"diag\":{";
    j += "\"resetReason\":\"";
    j += PanicTail::resetReason();
    j += "\",\"restartCause\":\"";
    j += PanicTail::restartCause();
    j += "\",\"bootGen\":";
    j += String(PanicTail::bootGeneration());
    if (Checkpoint::hasLastCrash()) {
        j += ",\"ckptLastOpen\":{\"phase\":\"";
        j += Checkpoint::name(Checkpoint::lastCrashPhase());
        j += "\",\"arg\":";
        j += String(Checkpoint::lastCrashArg());
        j += "}";
    } else {
        j += ",\"ckptLastOpen\":null";
    }
    j += ",\"note\":\"compact_snapshot\"";
    j += "}}";
    return j;
}

/** @brief Minimal always-valid fallback if even compact is somehow huge. */
String buildMinimalSnapshot() {
    String j = "{";
    appendMeta(j, true);
    j += ",\"error\":\"snapshot_budget\"";
    j += "}";
    return j;
}

String buildSnapshot(const HardwareInfo* hw) {
    String full = buildFullSnapshot(hw);
    if (full.length() <= kMaxSnapBytes) return full;

    Serial.printf("[DIAG] full snapshot %u > %u, using compact\n",
                  (unsigned)full.length(), (unsigned)kMaxSnapBytes);
    String compact = buildCompactSnapshot(hw);
    if (compact.length() <= kMaxSnapBytes) return compact;

    Serial.printf("[DIAG] compact snapshot %u > %u, using minimal\n",
                  (unsigned)compact.length(), (unsigned)kMaxSnapBytes);
    return buildMinimalSnapshot();
}

}  // namespace

void DiagSaved::persistBootSnapshot(const HardwareInfo* hw) {
    String snap = buildSnapshot(hw);
    // buildSnapshot() always returns syntactically valid JSON within budget.
    Preferences prefs;
    if (!prefs.begin(kNvsNs, false)) {
        Serial.println("[DIAG] NVS begin FAIL");
        return;
    }
    const size_t n = prefs.putString(kKeySnap, snap);
    prefs.end();
    Serial.printf("[DIAG] saved snapshot %u bytes\n", (unsigned)n);
}

String DiagSaved::loadJson() {
    Preferences prefs;
    if (!prefs.begin(kNvsNs, true)) {
        return String(F("{\"saved\":false,\"error\":\"nvs\"}"));
    }
    String snap = prefs.getString(kKeySnap, "");
    prefs.end();
    if (snap.length() == 0) {
        return String(F("{\"saved\":false}"));
    }
    return snap;
}

bool DiagSaved::hasSaved() {
    Preferences prefs;
    if (!prefs.begin(kNvsNs, true)) return false;
    const String snap = prefs.getString(kKeySnap, "");
    prefs.end();
    return snap.length() > 0;
}

void DiagSaved::clear() {
    Preferences prefs;
    if (!prefs.begin(kNvsNs, false)) return;
    prefs.remove(kKeySnap);
    prefs.end();
    Serial.println("[DIAG] snapshot cleared");
}
