#pragma once

/**
 * @file ProjectConfig.h
 * @brief bt-analyzer device/hub configuration.
 *
 * Base repository (keep when syncing):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub  (esp-hub-base v1.10.5)
 *
 * No WiFi secrets in source — use WiFiManager portal / NVS.
 */

#ifndef DEVICE_NAME
#define DEVICE_NAME            "bt-analyzer"
#endif
#ifndef FW_VERSION
#define FW_VERSION             "0.1.1"
#endif

#ifndef ESPHUB_ENABLE_EXAMPLE_MODULE
#define ESPHUB_ENABLE_EXAMPLE_MODULE 0
#endif
#ifndef HUB_HOST
#define HUB_HOST               "192.168.178.113"
#endif
#ifndef HUB_PORT
#define HUB_PORT               8093
#endif
#ifndef WIFI_AP_NAME
#define WIFI_AP_NAME           "BT-Analyzer-Setup"
#endif
#ifndef WIFI_PORTAL_TIMEOUT_S
#define WIFI_PORTAL_TIMEOUT_S  180
#endif
#ifndef DEFAULT_INTERVAL_S
#define DEFAULT_INTERVAL_S     30
#endif
#ifndef WATCHDOG_TIMEOUT_S
#define WATCHDOG_TIMEOUT_S     300
#endif
#ifndef PROGRESS_TIMEOUT_S
#define PROGRESS_TIMEOUT_S     WATCHDOG_TIMEOUT_S
#endif
#ifndef RESET_BUTTON_PIN
#define RESET_BUTTON_PIN       0
#endif
#ifndef RESET_HOLD_SEC
#define RESET_HOLD_SEC         3
#endif

/* Debian control plane (reserved for BT4+; unused in BT0). */
#ifndef CONTROLLER_HOST_DEFAULT
#define CONTROLLER_HOST_DEFAULT "192.168.178.187"
#endif
#ifndef CONTROLLER_PORT_DEFAULT
#define CONTROLLER_PORT_DEFAULT 9750
#endif
