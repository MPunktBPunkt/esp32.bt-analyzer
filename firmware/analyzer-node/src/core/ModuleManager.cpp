/**
 * @file ModuleManager.cpp
 * @brief ModuleManager registration and fan-out.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include "ModuleManager.h"
#include "DiagLog.h"

bool ModuleManager::add(BaseModule* module) {
    if (!module || count_ >= kMaxModules) return false;
    modules_[count_++] = module;
    // May run before DiagLog::begin() — use Serial only here.
    Serial.printf("[MOD] register %s\n", module->name());
    return true;
}

void ModuleManager::beginAll() {
    for (uint8_t i = 0; i < count_; i++) {
        DiagLog::printf("[MOD] begin %s\n", modules_[i]->name());
        modules_[i]->begin();
    }
}

void ModuleManager::loopAll() {
    for (uint8_t i = 0; i < count_; i++) modules_[i]->loop();
}

void ModuleManager::registerRoutes(WebServer& server) {
    for (uint8_t i = 0; i < count_; i++) modules_[i]->registerRoutes(server);
}

void ModuleManager::appendStatusJson(String& json) const {
    if (count_ == 0) return;
    json += ",\"modules\":[";
    for (uint8_t i = 0; i < count_; i++) {
        if (i) json += ",";
        json += "\"";
        json += modules_[i]->name();
        json += "\"";
    }
    json += "]";
    for (uint8_t i = 0; i < count_; i++) modules_[i]->appendStatusJson(json);
}
