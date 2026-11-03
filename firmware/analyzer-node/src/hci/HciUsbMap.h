#pragma once

#include "hci/HciTypes.h"

#include <EspUsbHost.h>

namespace bt_analyzer {

/**
 * BT2: classify USB interfaces/endpoints as USB-HCI roles.
 *
 * Mapping follows Bluetooth USB transport conventions (Wireless Controller
 * 0xE0/0x01, Primary Controller protocol 0x01):
 *   interrupt IN  → HCI Event
 *   bulk OUT      → HCI Command + ACL (host→controller)
 *   bulk IN       → ACL (controller→host)
 *   isochronous   → SCO/ISO (controller-dependent)
 *
 * Status: INFERENCE from descriptors until BT3 captures packets.
 * Does not own EspUsbHost — caller passes descriptor snapshots.
 */
class HciUsbMap {
public:
  static void clear(HciUsbDiscovery &out);

  static void discover(const EspUsbHostInterfaceInfo *interfaces, size_t n_if,
                       const EspUsbHostEndpointInfo *endpoints, size_t n_ep,
                       HciUsbDiscovery &out);

  static void appendStatusJson(const HciUsbDiscovery &d, String &json);
};

}  // namespace bt_analyzer
