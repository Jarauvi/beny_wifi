"""Home Assistant config flow ."""
import asyncio
import logging
import socket

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.device_registry import async_get as async_get_device_registry

from .communication import build_message, read_message
from .const import (
    CHARGER_TYPE,
    CLIENT_MESSAGE,
    CONF_MAX_CURRENT_MAX,
    CONF_MAX_CURRENT_MIN,
    CONF_PIN,
    CONF_SERIAL,
    DEFAULT_MAX_CURRENT_MAX,
    DEFAULT_MAX_CURRENT_MIN,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DLB,
    DLB_CHARGERS,
    DOMAIN,
    IP_ADDRESS,
    MODEL,
    PORT,
    REQUEST_TYPE,
    SCAN_INTERVAL,
    SERIAL,
    SINGLE_PHASE_CHARGERS,
    THREE_PHASE_CHARGERS,
)
from .conversions import convert_pin_to_hex, convert_serial_to_hex, get_hex

_LOGGER = logging.getLogger(__name__)

class BenyWifiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for beny-wifi."""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return BenyWifiOptionsFlow()

    VERSION = 2
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

                        if user_input[MODEL] in SINGLE_PHASE_CHARGERS:
                            user_input[CHARGER_TYPE] = '1P'

                        elif user_input[MODEL] in THREE_PHASE_CHARGERS:
                            user_input[CHARGER_TYPE] = '3P'

                        # DLB is a separate physical module — only enable if the model
                        # supports it AND the user confirmed they have the module installed.
                        if user_input[MODEL] in DLB_CHARGERS and user_input.get(DLB, False):
                            user_input[DLB] = True
                        else:
                            user_input[DLB] = False

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
                    vol.Optional(CONF_MAX_CURRENT_MIN, default=DEFAULT_MAX_CURRENT_MIN): vol.All(int, vol.Range(min=6, max=32)),
                    vol.Optional(CONF_MAX_CURRENT_MAX, default=DEFAULT_MAX_CURRENT_MAX): vol.All(int, vol.Range(min=6, max=32)),
                    vol.Optional(DLB, default=False): bool,
                }
            ),
            errors=self._errors
        )

    async def async_step_reconfigure(self, user_input = None):
        """Reconfigure integration."""

        existing_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        existing_data = existing_entry.data if existing_entry else {}

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

            user_input[CONF_PIN] = convert_pin_to_hex(user_input[CONF_PIN])

            if "base" not in self._errors or self._errors["base"] is None:
                # Re-evaluate DLB: only allowed if model supports it AND user ticked the box
                model = existing_data.get(MODEL, "")
                if model not in DLB_CHARGERS:
                    user_input[DLB] = False

                return self.async_update_reload_and_abort(self._get_reconfigure_entry(), data_updates=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(PORT, default=int(existing_data.get(PORT))): int,
                    vol.Optional(IP_ADDRESS, default=str(existing_data.get(IP_ADDRESS))): str,
                    vol.Required(CONF_SERIAL, default=str(existing_data.get(CONF_SERIAL))): str,
                    vol.Required(CONF_PIN, default=str(int(existing_data.get(CONF_PIN), 16)).zfill(6)): str,
                    vol.Optional(SCAN_INTERVAL, default=int(existing_data.get(SCAN_INTERVAL))): int,
                    vol.Optional(CONF_MAX_CURRENT_MIN, default=int(existing_data.get(CONF_MAX_CURRENT_MIN, DEFAULT_MAX_CURRENT_MIN))): vol.All(int, vol.Range(min=6, max=32)),
                    vol.Optional(CONF_MAX_CURRENT_MAX, default=int(existing_data.get(CONF_MAX_CURRENT_MAX, DEFAULT_MAX_CURRENT_MAX))): vol.All(int, vol.Range(min=6, max=32)),
                    vol.Optional(DLB, default=bool(existing_data.get(DLB, False))): bool,
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
                "port": port,
                "pin": pin,
                "serial_number": serial
            }

            request = build_message(
                CLIENT_MESSAGE.POLL_DEVICES,
                {"pin": dev_data["pin"], "serial": convert_serial_to_hex(dev_data["serial_number"])}
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
                        if not port:
                            dev_data['port'] = data.get('port', None)
                        else:
                            dev_data['port'] = port
                        break

                    except TimeoutError:
                        break

            except Exception as ex:  # noqa: BLE001
                self._errors["base"] = "cannot_communicate"
                _LOGGER.exception(f"Exception receiving device handshake data by broadcast 255.255.255.255:{dev_data["port"]}. Cause: {ex}")  # noqa: G004, TRY401
                return None

            if dev_data['ip_address'] is None:
                self._errors["base"] = "cannot_resolve_ip"
                _LOGGER.exception("Cannot resolve device IP, you can try to set it manually")  # noqa: G004, TRY401
                return None

            data = self._send_model_request(dev_data['ip_address'], dev_data['port'], dev_data['pin'], "55aa10")
            if not data:
                data = self._send_model_request(dev_data['ip_address'], dev_data['port'], dev_data['pin'], "55aa04")

            if not data:
                self._errors["base"] = "cannot_communicate"
                return None

            dev_data["model"] = data.get("model", "Charger")

            return dev_data

        return await asyncio.to_thread(sync_socket_communication)

    def _send_model_request(self, ip, port, pin, header_prefix):
        try:
            request = build_message(
                CLIENT_MESSAGE.REQUEST_DATA,
                {"pin": pin, "request_type": get_hex(REQUEST_TYPE.MODEL.value)},
                header_prefix=header_prefix
            ).encode("ascii")
        except Exception as ex:
            self._errors["base"] = "cannot_connect"
            _LOGGER.exception(f"Exception sending model request to {ip}:{port}. Cause: {ex}. Request: {request}")  # noqa: G004, TRY401

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        sock.sendto(request, (ip, port))

        try:
            response, _ = sock.recvfrom(1024)
            sock.close()
            data = read_message(response.decode("ascii"))
            return data
        except Exception as ex:
            self._errors["base"] = "cannot_communicate"
            _LOGGER.exception(f"Exception receiving model data from {ip}:{port}. Cause: {ex}. Request hex: {request}. Response hex: {response}. Translated response: {data}")  # noqa: G004, TRY401
            return None
        
class BenyWifiOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for integration."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
    
        existing_data = self.config_entry.data
        existing_options = self.config_entry.options

        self._errors = {}
        
        if user_input is not None:

            if not user_input[CONF_PIN].isdigit():
                self._errors["base"] = "pin_not_numeric"

            if len(user_input[CONF_PIN]) != 6:
                self._errors["base"] = "pin_length_invalid"

            user_input[CONF_PIN] = convert_pin_to_hex(user_input[CONF_PIN])
            
            if "base" not in self._errors or self._errors["base"] is None:
                # Re-evaluate DLB: only allowed if model supports it AND user ticked the box
                model = existing_data.get(MODEL, "")
                if model not in DLB_CHARGERS:
                    user_input[DLB] = False

                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        PORT,
                        default=existing_options.get(PORT, existing_data.get(PORT)),
                    ): int,

                    vol.Optional(
                        IP_ADDRESS,
                        default=existing_options.get(IP_ADDRESS, existing_data.get(IP_ADDRESS)),
                    ): str,

                    vol.Required(
                        CONF_PIN,
                        default=str(int(existing_data.get(CONF_PIN), 16)).zfill(6),
                    ): str,

                    vol.Optional(
                        SCAN_INTERVAL,
                        default=existing_options.get(
                            SCAN_INTERVAL, existing_data.get(SCAN_INTERVAL)
                        ),
                    ): int,

                    vol.Optional(
                        CONF_MAX_CURRENT_MIN,
                        default=existing_options.get(
                            CONF_MAX_CURRENT_MIN,
                            existing_data.get(CONF_MAX_CURRENT_MIN, DEFAULT_MAX_CURRENT_MIN),
                        ),
                    ): vol.All(int, vol.Range(min=6, max=32)),

                    vol.Optional(
                        CONF_MAX_CURRENT_MAX,
                        default=existing_options.get(
                            CONF_MAX_CURRENT_MAX,
                            existing_data.get(CONF_MAX_CURRENT_MAX, DEFAULT_MAX_CURRENT_MAX),
                        ),
                    ): vol.All(int, vol.Range(min=6, max=32)),

                    vol.Optional(
                        DLB,
                        default=existing_options.get(
                            DLB, existing_data.get(DLB, False)
                        ),
                    ): bool,
                }
            ),
        )