"""Home Assistant config flow ."""
import asyncio
import logging
import socket

import voluptuous as vol
from homeassistant.data_entry_flow import section
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.device_registry import async_get as async_get_device_registry

from .communication import build_message, read_message
from .const import (
    CHARGER_TYPE,
    CLIENT_MESSAGE,
    CONF_ANTI_OVERLOAD,
    CONF_ANTI_OVERLOAD_VALUE,
    CONF_MAX_CURRENT_MAX,
    CONF_MAX_CURRENT_MIN,
    CONF_PIN,
    CONF_SERIAL,
    DEFAULT_ANTI_OVERLOAD,
    DEFAULT_ANTI_OVERLOAD_VALUE,
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
    SECTION_DEVICE,
    SECTION_CONNECTION,
    SECTION_CURRENT_LIMITS,
    SECTION_DLB,
    CONF_NUMERIC_PIN,
    get_config_parameter
)
from .conversions import convert_pin_to_hex, convert_serial_to_hex, get_hex

_LOGGER = logging.getLogger(__name__)

class BenyWifiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for beny-wifi."""

    VERSION = 3
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Handle user initialized config flow."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""

        self._errors = {}

        if user_input is not None:
            if not user_input[SECTION_DEVICE][CONF_PIN].isdigit():
                self._errors["base"] = "pin_not_numeric"

            if len(user_input[SECTION_DEVICE][CONF_PIN]) != 6:
                self._errors["base"] = "pin_length_invalid"

            if not user_input[SECTION_DEVICE][CONF_SERIAL].isdigit():
                self._errors["base"] = "serial_not_numeric"

            if len(user_input[SECTION_DEVICE][CONF_SERIAL]) != 9:
                self._errors["base"] = "serial_length_invalid"

            if IP_ADDRESS not in user_input[SECTION_CONNECTION]:
                user_input[SECTION_CONNECTION][IP_ADDRESS] = None

            user_input[SECTION_DEVICE][CONF_NUMERIC_PIN] = user_input[SECTION_DEVICE][CONF_PIN]
            user_input[SECTION_DEVICE][CONF_PIN] = convert_pin_to_hex(user_input[SECTION_DEVICE][CONF_PIN])
            
            if "base" not in self._errors or self._errors["base"] is None:
                dev_data = await self._poll_devices(user_input[SECTION_DEVICE][CONF_SERIAL], user_input[SECTION_DEVICE][CONF_PIN], user_input[SECTION_CONNECTION][IP_ADDRESS], user_input[SECTION_CONNECTION][PORT])
                if dev_data is not None:
                    
                    # changed to native way to handle unique instance and abort
                    serial = dev_data["serial_number"]
                    await self.async_set_unique_id(serial)
                    self._abort_if_unique_id_configured(
                        description_placeholders={"serial": str(serial)}
                    )
                    
                    user_input[SECTION_CONNECTION][IP_ADDRESS] = dev_data["ip_address"]
                    user_input[SECTION_CONNECTION][PORT] = dev_data["port"]
                    user_input[SECTION_DEVICE][MODEL] = dev_data.get("model", "Charger")
                    user_input[SECTION_DEVICE][SERIAL] = dev_data["serial_number"]

                    if user_input[SECTION_DEVICE][MODEL] in SINGLE_PHASE_CHARGERS:
                        user_input[SECTION_DEVICE][CHARGER_TYPE] = '1P'

                    elif user_input[SECTION_DEVICE][MODEL] in THREE_PHASE_CHARGERS:
                        user_input[SECTION_DEVICE][CHARGER_TYPE] = '3P'

                    # DLB is a separate physical module — only enable if the model
                    # supports it AND the user confirmed they have the module installed.
                    if user_input[SECTION_DEVICE][MODEL] in DLB_CHARGERS and user_input.get(SECTION_DLB, {}).get(DLB, False):
                        user_input[SECTION_DLB][DLB] = True
                    else:
                        user_input[SECTION_DLB][DLB] = False

                    pin_is_valid = await self.hass.async_add_executor_job(self._pin_is_valid, user_input[SECTION_CONNECTION][IP_ADDRESS], user_input[SECTION_CONNECTION][PORT], user_input[SECTION_DEVICE][CONF_PIN])
                    if not pin_is_valid:
                        self._errors["base"] = "wrong_pin"
                    else:
                        return self.async_create_entry(title=user_input[SECTION_DEVICE][MODEL], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(SECTION_CONNECTION): section(
                        vol.Schema({
                            vol.Required(PORT, default=self._get_previous_user_input(user_input, SECTION_CONNECTION, PORT, DEFAULT_PORT)): int,
                            vol.Optional(IP_ADDRESS, default=self._get_previous_user_input(user_input, SECTION_CONNECTION, IP_ADDRESS, "")): str,
                            vol.Optional(SCAN_INTERVAL, default=self._get_previous_user_input(user_input, SECTION_CONNECTION, SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): int,
                        }), 
                        {"collapsed": False}
                    ),
                    vol.Required(SECTION_DEVICE): section(
                        vol.Schema({
                            vol.Required(CONF_SERIAL, default=self._get_previous_user_input(user_input, SECTION_DEVICE, CONF_SERIAL, "")): str,
                            vol.Required(CONF_PIN, default=self._get_previous_user_input(user_input, SECTION_DEVICE, CONF_NUMERIC_PIN, "")): str,
                        }), 
                        {"collapsed": False}
                    ),
                    vol.Required(SECTION_CURRENT_LIMITS): section(
                        vol.Schema({
                            vol.Optional(CONF_MAX_CURRENT_MIN, default=self._get_previous_user_input(user_input, SECTION_CURRENT_LIMITS, CONF_MAX_CURRENT_MIN, DEFAULT_MAX_CURRENT_MIN)): vol.All(int, vol.Range(min=6, max=32)),
                            vol.Optional(CONF_MAX_CURRENT_MAX, default=self._get_previous_user_input(user_input, SECTION_CURRENT_LIMITS, CONF_MAX_CURRENT_MAX, DEFAULT_MAX_CURRENT_MAX)): vol.All(int, vol.Range(min=6, max=32)),                    
                        }), 
                        {"collapsed": False}
                    ),
                    vol.Required(SECTION_DLB): section(
                        vol.Schema({
                            vol.Optional(DLB, default=self._get_previous_user_input(user_input, SECTION_DLB, DLB, False)): bool,
                            vol.Optional(CONF_ANTI_OVERLOAD, default=self._get_previous_user_input(user_input, SECTION_DLB, CONF_ANTI_OVERLOAD, DEFAULT_ANTI_OVERLOAD)): bool,
                            vol.Optional(CONF_ANTI_OVERLOAD_VALUE, default=self._get_previous_user_input(user_input, SECTION_DLB, CONF_ANTI_OVERLOAD_VALUE, DEFAULT_ANTI_OVERLOAD_VALUE)): vol.All(int, vol.Range(min=1, max=99)),
                        }),
                        {"collapsed": True}
                    ),
                }
            ),
            errors=self._errors
        )
        
    def _get_previous_user_input(self, user_input, section, key, default, existing_config=None):
        if user_input:
            if section in user_input:
                if key in user_input[section]:
                    return user_input[section][key]

        if existing_config:
            return get_config_parameter(existing_config, section, key, default)
        
        return default

    async def async_step_reconfigure(self, user_input = None):
        """Reconfigure integration."""

        existing_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        existing_data = existing_entry.data if existing_entry else {}

        self._errors = {}

        if user_input is not None:

            if not user_input[SECTION_DEVICE][CONF_PIN].isdigit():
                self._errors["base"] = "pin_not_numeric"

            if len(user_input[SECTION_DEVICE][CONF_PIN]) != 6:
                self._errors["base"] = "pin_length_invalid"

            user_input[SECTION_DEVICE][CONF_NUMERIC_PIN] = user_input[SECTION_DEVICE][CONF_PIN]
            user_input[SECTION_DEVICE][CONF_PIN] = convert_pin_to_hex(user_input[SECTION_DEVICE][CONF_PIN])

            if "base" not in self._errors or self._errors["base"] is None:
                # Re-evaluate DLB: only allowed if model supports it AND user ticked the box
                model = get_config_parameter(existing_data, SECTION_DEVICE, MODEL, "")
                if model not in DLB_CHARGERS:
                    user_input[SECTION_DLB][DLB] = False
                    
                pin_is_valid = await self.hass.async_add_executor_job(self._pin_is_valid, user_input[SECTION_CONNECTION][IP_ADDRESS], user_input[SECTION_CONNECTION][PORT], user_input[SECTION_DEVICE][CONF_PIN])
                if not pin_is_valid:
                    self._errors["base"] = "wrong_pin"
                else:
                    return self.async_update_reload_and_abort(self._get_reconfigure_entry(), data_updates=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(SECTION_CONNECTION): section(
                        vol.Schema({
                            vol.Required(PORT, default=self._get_previous_user_input(user_input, SECTION_CONNECTION, PORT, DEFAULT_PORT, existing_entry)): int,
                            vol.Optional(IP_ADDRESS, default=self._get_previous_user_input(user_input, SECTION_CONNECTION, IP_ADDRESS, "", existing_entry)): str,
                            vol.Optional(SCAN_INTERVAL, default=self._get_previous_user_input(user_input, SECTION_CONNECTION, SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, existing_entry)): int,
                        }), 
                        {"collapsed": False}
                    ),
                    vol.Required(SECTION_DEVICE): section(
                        vol.Schema({
                            vol.Required(CONF_PIN, default=self._get_previous_user_input(user_input, SECTION_DEVICE, CONF_NUMERIC_PIN, "", existing_entry)): str,
                        }), 
                        {"collapsed": False}
                    ),
                    vol.Required(SECTION_CURRENT_LIMITS): section(
                        vol.Schema({
                            vol.Optional(CONF_MAX_CURRENT_MIN, default=self._get_previous_user_input(user_input, SECTION_CURRENT_LIMITS, CONF_MAX_CURRENT_MIN, DEFAULT_MAX_CURRENT_MIN, existing_entry)): vol.All(int, vol.Range(min=6, max=32)),
                            vol.Optional(CONF_MAX_CURRENT_MAX, default=self._get_previous_user_input(user_input, SECTION_CURRENT_LIMITS, CONF_MAX_CURRENT_MAX, DEFAULT_MAX_CURRENT_MAX, existing_entry)): vol.All(int, vol.Range(min=6, max=32)),                    
                        }), 
                        {"collapsed": False}
                    ),
                    vol.Required(SECTION_DLB): section(
                        vol.Schema({
                            vol.Optional(DLB, default=self._get_previous_user_input(user_input, SECTION_DLB, DLB, self._get_previous_user_input(None, SECTION_DEVICE, DLB, False, existing_entry), existing_entry)): bool,
                            vol.Optional(CONF_ANTI_OVERLOAD, default=self._get_previous_user_input(user_input, SECTION_DLB, CONF_ANTI_OVERLOAD, DEFAULT_ANTI_OVERLOAD, existing_entry)): bool,
                            vol.Optional(CONF_ANTI_OVERLOAD_VALUE, default=self._get_previous_user_input(user_input, SECTION_DLB, CONF_ANTI_OVERLOAD_VALUE, DEFAULT_ANTI_OVERLOAD_VALUE, existing_entry)): vol.All(int, vol.Range(min=1, max=99)),
                        }),
                        {"collapsed": True}
                    ),
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

                        # Guard: read_message returns None on invalid checksum
                        if data is None:
                            _LOGGER.warning(
                                f"Received broadcast response from {addr} but checksum was invalid — ignoring"  # noqa: G004
                            )
                            continue

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
                _LOGGER.exception(f"Exception receiving device handshake data by broadcast 255.255.255.255:{dev_data['port']}. Cause: {ex}")  # noqa: G004, TRY401
                return None

            if dev_data['ip_address'] is None:
                # If user supplied an IP manually, attempt a direct unicast handshake
                # before giving up. OCPP variants and some firewalled devices do not
                # respond to UDP broadcasts but may respond to a direct packet.
                if ip:
                    _LOGGER.info(
                        f"Broadcast returned no IP; attempting direct unicast handshake to {ip}:{port}"  # noqa: G004
                    )
                    direct_data = _try_direct_handshake(ip, port, pin, serial)
                    if direct_data is not None:
                        dev_data.update(direct_data)
                    else:
                        self._errors["base"] = "cannot_communicate"
                        _LOGGER.warning(
                            f"Direct unicast handshake to {ip}:{port} also failed. "  # noqa: G004
                            "The device did not respond to local UDP. If this is an OCPP model "
                            "(model name ends in -P) it may not support local UDP polling."
                        )
                        return None
                else:
                    self._errors["base"] = "cannot_resolve_ip"
                    _LOGGER.exception("Cannot resolve device IP, you can try to set it manually")  # noqa: G004, TRY401
                    return None

            # Brief pause to allow the charger to finish processing the handshake
            # before we send the model request — some firmware versions need this.
            import time
            time.sleep(0.5)

            data = self._send_model_request(dev_data['ip_address'], dev_data['port'], dev_data['pin'], "55aa10")
            if not data:
                data = self._send_model_request(dev_data['ip_address'], dev_data['port'], dev_data['pin'], "55aa04")

            if not data:
                self._errors["base"] = "cannot_communicate"
                return None

            dev_data["model"] = data.get("model", "Charger")

            return dev_data

        def _try_direct_handshake(ip, port, pin, serial):
            """Attempt a unicast POLL_DEVICES packet to a known IP.

            Some devices (notably OCPP variants that are also reachable via LAN)
            do not respond to broadcasts but will reply to a direct unicast packet.
            Returns a partial dev_data dict on success, or None on failure.
            """
            request = build_message(
                CLIENT_MESSAGE.POLL_DEVICES,
                {"pin": pin, "serial": convert_serial_to_hex(serial)}
            ).encode('ascii')

            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(5)
                sock.sendto(request, (ip, port))
                _LOGGER.debug(f"Direct unicast handshake to {ip}:{port}")  # noqa: G004

                response, _ = sock.recvfrom(1024)
                sock.close()

                data = read_message(response.decode('ascii'))
                if data is None:
                    _LOGGER.warning(f"Direct unicast response from {ip} had invalid checksum")  # noqa: G004
                    return None

                if data.get('message_type') == "SERVER_MESSAGE.ACCESS_DENIED":
                    return None

                return {
                    "serial_number": data.get('serial', serial),
                    "ip_address": ip,
                    "port": port,
                }
            except Exception as ex:  # noqa: BLE001
                _LOGGER.debug(f"Direct unicast handshake to {ip}:{port} failed: {ex}")  # noqa: G004
                return None

        return await asyncio.to_thread(sync_socket_communication)

    def _send_model_request(self, ip, port, pin, header_prefix, retries=3, timeout=5):
        """Send a model request to the charger and return parsed response, or None on failure.

        Retries up to `retries` times with a short delay between attempts to handle
        chargers that are slow to respond after the initial handshake broadcast.
        The socket sendto is inside the try block so any send-side errors are also caught.
        """
        request = b""  # Initialize so it's always available in exception logging
        for attempt in range(1, retries + 1):
            response = b""
            data = None
            try:
                request = build_message(
                    CLIENT_MESSAGE.REQUEST_DATA,
                    {"pin": pin, "request_type": get_hex(REQUEST_TYPE.MODEL.value)},
                    header_prefix=header_prefix
                ).encode("ascii")

                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(timeout)
                try:
                    sock.sendto(request, (ip, port))
                    response, _ = sock.recvfrom(1024)
                    data = read_message(response.decode("ascii"))
                    return data
                finally:
                    sock.close()

            except Exception as ex:
                _LOGGER.warning(  # noqa: G004
                    f"Model request attempt {attempt}/{retries} failed for {ip}:{port} "
                    f"(prefix={header_prefix}). Cause: {ex}. "
                    f"Request hex: {request}. Response hex: {response}. Translated: {data}"
                )
                if attempt < retries:
                    import time
                    time.sleep(0.5)

        self._errors["base"] = "cannot_communicate"
        _LOGGER.error(  # noqa: G004
            f"All {retries} model request attempts failed for {ip}:{port} (prefix={header_prefix})"
        )
        return None
        
    def _pin_is_valid(self, ip, port, pin):
        request = b"" # Initialize
        response = b"" # Initialize
        data = None    # Initialize
        try:
            request = build_message(
                CLIENT_MESSAGE.REQUEST_DATA,
                {"pin": pin, "request_type": get_hex(REQUEST_TYPE.VALUES.value)}
            ).encode('ascii')
        except Exception as ex:
            self._errors["base"] = "cannot_connect"
            _LOGGER.exception(f"Exception sending model request to {ip}:{port}. Cause: {ex}. Request: {request}")  # noqa: G004, TRY401

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        sock.sendto(request, (ip, port))

        try:
            response, _ = sock.recvfrom(1024)
            response = response.decode("ascii")
            if "55aa100008" in response:
                return False
            else:
                return True
        except Exception as ex:
            self._errors["base"] = "cannot_communicate"
            _LOGGER.exception(f"Exception receiving model data from {ip}:{port}. Cause: {ex}. Request hex: {request}. Response hex: {response}. Translated response: {data}")  # noqa: G004, TRY401
            return None
        finally:
            sock.close()