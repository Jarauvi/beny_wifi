"""Home Assistant config flow ."""
import asyncio
import logging
import socket

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.device_registry import async_get as async_get_device_registry

from .communication import build_message, read_message
from .const import (
    CLIENT_MESSAGE,
    CONF_PIN,
    CONF_SERIAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    IP_ADDRESS,
    MODEL,
    PORT,
    REQUEST_TYPE,
    SCAN_INTERVAL,
    SERIAL,
)
from .conversions import convert_pin_to_hex, convert_serial_to_hex, get_hex

_LOGGER = logging.getLogger(__name__)

class BenyWifiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for beny-wifi."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Handle user initialized config flow."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""

        self._errors = {}

        if user_input is not None:
            if not user_input[CONF_PIN].isdigit():
                self._errors["base"] = "pin_not_numeric"

            if len(user_input[CONF_PIN]) != 6:
                self._errors["base"] = "pin_length_invalid"

            if not user_input[CONF_SERIAL].isdigit():
                self._errors["base"] = "serial_not_numeric"

            if len(user_input[CONF_SERIAL]) != 9:
                self._errors["base"] = "serial_length_invalid"

            if IP_ADDRESS not in user_input:
                user_input[IP_ADDRESS] = None

            user_input[CONF_PIN] = convert_pin_to_hex(user_input[CONF_PIN])

            if "base" not in self._errors or self._errors["base"] is None:

                dev_data = await self._poll_devices(user_input[CONF_SERIAL], user_input[CONF_PIN], user_input[IP_ADDRESS], user_input[PORT])
                if dev_data is not None:

                    if not await self._device_exists(dev_data["serial_number"]):
                        user_input[IP_ADDRESS] = dev_data["ip_address"]
                        user_input[PORT] = dev_data["port"]
                        user_input[MODEL] = dev_data.get("model", "Charger")
                        user_input[SERIAL] = dev_data["serial_number"]
                        return self.async_create_entry(title="Beny Wifi", data=user_input)

                    self._errors["base"] = "device_already_configured"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(PORT, default=DEFAULT_PORT): int,
                    vol.Optional(IP_ADDRESS): str,
                    vol.Required(CONF_SERIAL): str,
                    vol.Required(CONF_PIN): str,
                    vol.Optional(SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
                }
            ),
            errors=self._errors
        )

    async def _device_exists(self, serial_number: str) -> bool:
        """Check if a device with the given serial number already exists."""
        device_registry = async_get_device_registry(self.hass)
        return any(device.serial_number == serial_number for device in device_registry.devices.values())

    async def _poll_devices(self, serial, pin, ip, port) -> dict | None:
        """Check is device andswers to broadcast."""
        def sync_socket_communication():
            dev_data = {
                "ip_address": ip,
                "pin": pin,
                "serial": convert_serial_to_hex(serial)
            }

            request = build_message(
                CLIENT_MESSAGE.POLL_DEVICES,
                {"pin": dev_data["pin"], "serial": dev_data["serial"]}
            ).encode('ascii')

            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(5)

                sock.bind(('0.0.0.0', 0))
                sock.sendto(request, ('255.255.255.255', port))
                _LOGGER.debug(f"Broadcast request to {'255.255.255.255'}:{port}")  # noqa: G004

                while True:
                    try:
                        response, addr = sock.recvfrom(1024)
                        sock.close()

                        response = response.decode('ascii')
                        data = read_message(response)

                        if data['message_type'] == "SERVER_MESSAGE.ACCESS_DENIED":
                            self._errors["base"] = "access_denied"
                            _LOGGER.exception("Device denied request. Please reconfigure integration if your pin has changed")  # noqa: G004, TRY401
                            return None

                        dev_data['serial_number'] = data.get('serial', '12345678')
                        dev_data['ip_address'] = data.get('ip', None)
                        dev_data['port'] = data.get('port', None)
                        break

                    except TimeoutError:
                        _LOGGER.warning("UDP broadcast timed out, no response received")
                        break

            except Exception as ex:  # noqa: BLE001
                self._errors["base"] = "cannot_communicate"
                _LOGGER.exception(f"Exception receiving device handshake data by broadcast {'255.255.255.255'}:{port}. Cause: {ex}")  # noqa: G004, TRY401
                return None

            if dev_data['ip_address'] is None:
                self._errors["base"] = "cannot_communicate"
                _LOGGER.exception("Device IP not known")  # noqa: G004, TRY401
                return None

            try:
                request = build_message(CLIENT_MESSAGE.REQUEST_DATA, {"pin": dev_data["pin"], "request_type": get_hex(REQUEST_TYPE.MODEL.value)}).encode('ascii')
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(5)
                sock.sendto(request, (dev_data['ip_address'], dev_data['port']))
                _LOGGER.debug(f"Sent model request to {dev_data['ip_address']}:{dev_data['port']}")  # noqa: G004
            except Exception as ex:  # noqa: BLE001
                self._errors["base"] = "cannot_connect"
                _LOGGER.exception(f"Exception sending model request to {dev_data['ip_address']}:{dev_data['port']}. Cause: {ex}. Request: {request}")  # noqa: G004, TRY401
                return None

            try:
                response, addr = sock.recvfrom(1024)
                _LOGGER.debug(f"Model message received from {dev_data['ip_address']}:{dev_data['port']}")  # noqa: G004
                sock.close()
                response = response.decode('ascii')
                data = read_message(response)
                _LOGGER.debug(f"Model message data: {data}")  # noqa: G004
                dev_data['model'] = data.get("model", "Charger")
            except Exception as ex:  # noqa: BLE001
                self._errors["base"] = "cannot_communicate"
                _LOGGER.exception(f"Exception receiving model data from {dev_data['ip_address']}:{dev_data['port']}. Cause: {ex}. Request hex: {request}. Response hex: {response}. Translated response: {data}")  # noqa: G004, TRY401
                return None

            return dev_data  # noqa: TRY300

        return await asyncio.to_thread(sync_socket_communication)
