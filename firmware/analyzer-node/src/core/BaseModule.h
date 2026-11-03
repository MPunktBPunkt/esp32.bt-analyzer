#pragma once

/**
 * @file BaseModule.h
 * @brief Application module contract for project-specific logic (D-016).
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include <Arduino.h>
#include <WebServer.h>

/**
 * @brief Interface for optional application modules hosted by AppCore.
 *
 * Core firmware without registered modules behaves like the baseline.
 */
class BaseModule {
public:
    virtual ~BaseModule() = default;

    /** @brief Stable module id for logs/status. */
    virtual const char* name() const = 0;

    /** @brief One-shot init after WiFi/web are up (may be empty). */
    virtual void begin() {}

    /** @brief Called every AppCore::loop(). */
    virtual void loop() {}

    /**
     * @brief Append additive JSON fields into the status object (leading commas OK).
     * @param[in,out] json Status JSON buffer before the closing brace / ios field.
     */
    virtual void appendStatusJson(String& json) { (void)json; }

    /**
     * @brief Optional metrics blob for diagnostics.
     * @param[in,out] json Target JSON fragment.
     */
    virtual void appendMetrics(String& json) { (void)json; }

    /**
     * @brief Handle a text command; return true if consumed.
     * @param cmd       Command name.
     * @param arg       Optional argument.
     * @param[out] response Filled on success/failure when handled.
     * @return true if this module handled the command.
     */
    virtual bool handleCommand(const String& cmd, const String& arg, String& response) {
        (void)cmd;
        (void)arg;
        (void)response;
        return false;
    }

    /**
     * @brief Register extra HTTP routes on the device web server.
     * @param server  Live WebServer instance.
     */
    virtual void registerRoutes(WebServer& server) { (void)server; }

    /**
     * @brief Optional self-test hook.
     * @param[out] report Human-readable result.
     * @return true if the test passed.
     */
    virtual bool selfTest(String& report) {
        report = "ok";
        return true;
    }
};
