#pragma once

/**
 * @file UiPages.h
 * @brief Embedded Web-UI (gzip PROGMEM).
 *
 * Edit web/index.html (+ index_esp32_min.html), then run: python3 tools/pack_ui.py
 * Generated: UiPagesGz.h / UiPagesGzEsp32.h
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#if defined(BT_ANALYZER_BOARD_ESP32) && BT_ANALYZER_BOARD_ESP32
#include "UiPagesGzEsp32.h"
#else
#include "UiPagesGz.h"
#endif
