#pragma once

#include <stddef.h>
#include <stdint.h>

namespace bt_analyzer {

/** HCI packet kinds on the wire (USB-HCI / H4). */
enum class HciPacketType : uint8_t {
  Unknown = 0,
  Command = 1,  // host → controller
  Event = 2,    // controller → host
  Acl = 3,
  Sco = 4,
  Iso = 5,
};

enum class HciDirection : uint8_t {
  Unknown = 0,
  HostToController = 1,
  ControllerToHost = 2,
};

inline const char *hciPacketTypeName(HciPacketType t) {
  switch (t) {
  case HciPacketType::Command: return "command";
  case HciPacketType::Event:   return "event";
  case HciPacketType::Acl:     return "acl";
  case HciPacketType::Sco:     return "sco";
  case HciPacketType::Iso:     return "iso";
  default:                     return "unknown";
  }
}

inline const char *hciDirectionName(HciDirection d) {
  switch (d) {
  case HciDirection::HostToController: return "host_to_controller";
  case HciDirection::ControllerToHost: return "controller_to_host";
  default:                             return "unknown";
  }
}

/** Max cached USB endpoints we classify for HCI. */
static constexpr size_t kHciMaxEndpoints = 16;

struct HciEndpointRole {
  uint8_t address = 0;           // bEndpointAddress
  uint8_t interfaceNumber = 0;
  uint8_t attributes = 0;
  uint16_t maxPacketSize = 0;
  uint8_t interval = 0;
  HciPacketType primaryType = HciPacketType::Unknown;
  HciDirection direction = HciDirection::Unknown;
  const char *role = "unknown";  // stable string for JSON
};

struct HciUsbDiscovery {
  bool wirelessControllerIface = false;
  bool primaryControllerProtocol = false;  // protocol 0x01
  uint8_t hciInterfaceNumber = 0xff;
  uint8_t ifaceClass = 0;
  uint8_t ifaceSubclass = 0;
  uint8_t ifaceProtocol = 0;
  uint8_t endpointCount = 0;
  bool hasEventEp = false;
  bool hasCommandAclOut = false;
  bool hasAclIn = false;
  bool hasScoIso = false;
  HciEndpointRole endpoints[kHciMaxEndpoints]{};
};

}  // namespace bt_analyzer
