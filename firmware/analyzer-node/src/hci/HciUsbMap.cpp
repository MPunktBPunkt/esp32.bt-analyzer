#include "hci/HciUsbMap.h"

namespace bt_analyzer {

void HciUsbMap::clear(HciUsbDiscovery &out) {
  out = HciUsbDiscovery{};
  out.hciInterfaceNumber = 0xff;
}

void HciUsbMap::discover(const EspUsbHostInterfaceInfo *interfaces, size_t n_if,
                         const EspUsbHostEndpointInfo *endpoints, size_t n_ep,
                         HciUsbDiscovery &out) {
  clear(out);
  if (!interfaces || !endpoints) {
    return;
  }

  for (size_t i = 0; i < n_if; i++) {
    if (interfaces[i].interfaceClass == 0xE0 &&
        interfaces[i].interfaceSubClass == 0x01) {
      out.wirelessControllerIface = true;
      out.hciInterfaceNumber = interfaces[i].number;
      out.ifaceClass = interfaces[i].interfaceClass;
      out.ifaceSubclass = interfaces[i].interfaceSubClass;
      out.ifaceProtocol = interfaces[i].interfaceProtocol;
      out.primaryControllerProtocol = (interfaces[i].interfaceProtocol == 0x01);
      break;
    }
  }

  for (size_t i = 0; i < n_ep && out.endpointCount < kHciMaxEndpoints; i++) {
    const EspUsbHostEndpointInfo &ep = endpoints[i];
    if (out.wirelessControllerIface && out.hciInterfaceNumber != 0xff &&
        ep.interfaceNumber != out.hciInterfaceNumber) {
      continue;
    }

    HciEndpointRole &role = out.endpoints[out.endpointCount++];
    role.address = ep.address;
    role.interfaceNumber = ep.interfaceNumber;
    role.attributes = ep.attributes;
    role.maxPacketSize = ep.maxPacketSize;
    role.interval = ep.interval;

    const uint8_t xfer = ep.attributes & 0x03;
    const bool is_in = (ep.address & 0x80) != 0;

    if (xfer == 3 && is_in) {
      role.primaryType = HciPacketType::Event;
      role.direction = HciDirection::ControllerToHost;
      role.role = "hci_event";
      out.hasEventEp = true;
    } else if (xfer == 2 && !is_in) {
      role.primaryType = HciPacketType::Command;
      role.direction = HciDirection::HostToController;
      role.role = "hci_command_acl_out";
      out.hasCommandAclOut = true;
    } else if (xfer == 2 && is_in) {
      role.primaryType = HciPacketType::Acl;
      role.direction = HciDirection::ControllerToHost;
      role.role = "hci_acl_in";
      out.hasAclIn = true;
    } else if (xfer == 1) {
      role.primaryType = HciPacketType::Sco;
      role.direction =
          is_in ? HciDirection::ControllerToHost : HciDirection::HostToController;
      role.role = is_in ? "hci_sco_iso_in" : "hci_sco_iso_out";
      out.hasScoIso = true;
    } else {
      role.role = "unclassified";
    }
  }
}

void HciUsbMap::appendStatusJson(const HciUsbDiscovery &d, String &json) {
  json += ",\"hci\":{";
  json += "\"transport\":\"usb_hci\"";
  json += ",\"detected\":";
  json += d.wirelessControllerIface ? "true" : "false";
  json += ",\"primaryController\":";
  json += d.primaryControllerProtocol ? "true" : "false";
  json += ",\"claim\":\"descriptor_inference_not_capture\"";
  if (d.wirelessControllerIface) {
    json += ",\"interface\":{";
    json += "\"number\":";
    json += String(d.hciInterfaceNumber);
    json += ",\"class\":";
    json += String(d.ifaceClass);
    json += ",\"subclass\":";
    json += String(d.ifaceSubclass);
    json += ",\"protocol\":";
    json += String(d.ifaceProtocol);
    json += "}";
  }
  json += ",\"capabilities\":{";
  json += "\"event\":";
  json += d.hasEventEp ? "true" : "false";
  json += ",\"command_acl_out\":";
  json += d.hasCommandAclOut ? "true" : "false";
  json += ",\"acl_in\":";
  json += d.hasAclIn ? "true" : "false";
  json += ",\"sco_iso\":";
  json += d.hasScoIso ? "true" : "false";
  json += "}";
  json += ",\"packetTypes\":[\"command\",\"event\",\"acl\",\"sco\",\"iso\"]";
  json += ",\"endpoints\":[";
  for (uint8_t i = 0; i < d.endpointCount; i++) {
    if (i) {
      json += ",";
    }
    const HciEndpointRole &e = d.endpoints[i];
    json += "{";
    json += "\"address\":";
    json += String(e.address);
    json += ",\"interfaceNumber\":";
    json += String(e.interfaceNumber);
    json += ",\"attributes\":";
    json += String(e.attributes);
    json += ",\"maxPacketSize\":";
    json += String(e.maxPacketSize);
    json += ",\"interval\":";
    json += String(e.interval);
    json += ",\"role\":\"";
    json += e.role;
    json += "\",\"type\":\"";
    json += hciPacketTypeName(e.primaryType);
    json += "\",\"dir\":\"";
    json += hciDirectionName(e.direction);
    json += "\"}";
  }
  json += "]";
  json += "}";
}

}  // namespace bt_analyzer
