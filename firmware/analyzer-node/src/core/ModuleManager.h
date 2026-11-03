#pragma once

/**
 * @file ModuleManager.h
 * @brief Registry and lifecycle fan-out for BaseModule instances.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include "BaseModule.h"

/**
 * @brief Holds up to kMaxModules application modules.
 */
class ModuleManager {
public:
    static constexpr uint8_t kMaxModules = 6;

    /**
     * @brief Register a module before AppCore::begin() completes web setup.
     * @param module  Non-owning pointer; must outlive the firmware run.
     * @return true if registered.
     */
    bool add(BaseModule* module);

    /** @brief Call begin() on all modules (after core services are up). */
    void beginAll();

    /** @brief Call loop() on all modules. */
    void loopAll();

    /** @brief Let modules register HTTP routes. */
    void registerRoutes(WebServer& server);

    /** @brief Append each module's status fields. */
    void appendStatusJson(String& json) const;

    /** @brief Number of registered modules. */
    uint8_t count() const { return count_; }

    BaseModule* at(uint8_t i) const {
        return (i < count_) ? modules_[i] : nullptr;
    }

private:
    BaseModule* modules_[kMaxModules] = {};
    uint8_t count_ = 0;
};
