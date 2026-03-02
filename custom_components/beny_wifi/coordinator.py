"""Coordinator."""
import asyncio
from datetime import timedelta
import logging
import socket
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow

from .communication import SERVER_MESSAGE, build_message, read_message
from .const import (
    CHARGER_COMMAND,
    CHARGER_STATE,
    CLIENT_MESSAGE,
    CONF_PIN,
    DLB,
    DOMAIN,
    REQUEST_TYPE,
    SERIAL,
)
from .conversions import convert_schedule, convert_timer, get_hex

_LOGGER = logging.getLogger(__name__)


class BenyWifiUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Beny Wifi update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry,
        ip_address,
        port,
        scan_interval,
    ) -> None:
        """Initialize Beny Wifi update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

        self.config_entry = config_entry
        self.ip_address = ip_address
        self.port = port
        self.hass = hass

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data asynchronously."""
        return await self._fetch_data()

    async def _fetch_data(self):
        """Send UDP request and fetch data asynchronously."""
        try:
            # Build the request message
            request = build_message(
                CLIENT_MESSAGE.REQUEST_DATA,
                {"pin": self.config_entry.data[CONF_PIN], "request_type": get_hex(REQUEST_TYPE.VALUES.value)}
            ).encode('ascii')

            # Send UDP request asynchronously
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self._send_udp_request, request)

            # Decode and parse the response
            response = response.decode('ascii')
            data = read_message(response)

            if data is None:
                raise UpdateFailed("Error fetching data: checksum not valid")

            if data['message_type'] == "SERVER_MESSAGE.ACCESS_DENIED":
                raise UpdateFailed("Device denied request. Please reconfigure integration if your pin has changed")

            # Set unset state to both start and end time if timer is not set at all
            if data['timer_state'] == 'UNSET':
                start = "not_set"
                end = "not_set"
            # if timer has START_TIME or START_END_TIME value
            elif data['timer_state'] != 'END_TIME':
                # Convert timer values to timestamps
                now = utcnow()
                start = now.replace(
                    hour=data['timer_start_h'], minute=data['timer_start_min'], second=0, microsecond=0
                )

                # If start is before current time, move it to the next day
                if start < now:
                    start += timedelta(days=1)

                if data['timer_state'] == 'START_END_TIME':
                    end = now.replace(
                        hour=data['timer_end_h'], minute=data['timer_end_min'], second=0, microsecond=0
                    )

                    # If end is before current time, move it to the next day
                    if end < now:
                        end += timedelta(days=1)

                    # If end is also before start, move end to the next day of start
                    if end <= start:
                        end += timedelta(days=1)
                else:
                    # timer end is not set
                    end = "not_set"
            else:
                start = "not_set"

                # Convert timer value to timestamp
                now = utcnow()
                end = now.replace(
                    hour=data['timer_end_h'], minute=data['timer_end_min'], second=0, microsecond=0
                )

            data['timer_start'] = start
            data['timer_end'] = end

            data['charger_state'] = data['state'].lower()

            data['power'] = float(data['power']) / 10
            data['total_kwh'] = float(data['total_kwh'])
            data['temperature'] = int(data['temperature'] - 100)

            # ORIGINAL v0.7.0 DLB HANDLING - UNCHANGED
            if self.config_entry.data[DLB]:
                # Build the dlb request message
                request = build_message(
                    CLIENT_MESSAGE.REQUEST_DLB,
                    {"pin": self.config_entry.data[CONF_PIN], "request_type": get_hex(REQUEST_TYPE.DLB.value)}
                ).encode('ascii')

                # Send UDP request asynchronously
                loop = asyncio.get_event_loop()
                response_dlb = await loop.run_in_executor(None, self._send_udp_request, request)
                response_dlb = response_dlb.decode('ascii')
                data_dlb = read_message(response_dlb)

                data['grid_power'] = float(data_dlb['grid_power']) / 10
                data['house_power'] = float(data_dlb['house_power']) / 10
                data['ev_power'] = float(data_dlb['ev_power']) / 10
                data['solar_power'] = float(data_dlb['solar_power']) / 10

            return data

        except Exception as err:
            _LOGGER.error(f"Failed to fetch data: {err}")
            raise UpdateFailed(f"Error fetching data: {err}")

    def _send_udp_request(self, request, retries=2, timeout=8):
        """Send UDP request synchronously in a separate thread, with retries."""
        for attempt in range(retries):
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(timeout)
                sock.sendto(request, (self.ip_address, self.port))

                response, addr = sock.recvfrom(1024)
                return response
            except socket.timeout:
                _LOGGER.warning(
                    f"UDP request timed out (attempt {attempt + 1}/{retries}). Retrying..."
                )
                if attempt == retries - 1:
                    _LOGGER.error(f"UDP request failed after {retries} attempts due to timeout.")
                    raise UpdateFailed(f"Error sending UDP request: timed out after {retries} attempts")
            except Exception as err:
                _LOGGER.error(f"UDP request failed: {err}")
                raise UpdateFailed(f"Error sending UDP request: {err}")
            finally:
                if sock:
                    sock.close()
        raise UpdateFailed("Unknown error after retries in _send_udp_request")

    async def async_toggle_charging(self, device_name: str, command: str):
        """Start or stop charging service."""

        # check if charger is unplugged
        state_sensor_id = f"sensor.{self.config_entry.data[SERIAL]}_charger_state"
        state_sensor_value = self.hass.states.get(state_sensor_id)

        if state_sensor_value and state_sensor_value.state != CHARGER_STATE.UNPLUGGED.name.lower():
            if command == "start":
                request = build_message(
                    CLIENT_MESSAGE.SEND_CHARGER_COMMAND,
                    {"pin": self.config_entry.data[CONF_PIN], "charger_command": get_hex(CHARGER_COMMAND.START.value)}
                ).encode('ascii')
            elif command == "stop":
                request = build_message(
                    CLIENT_MESSAGE.SEND_CHARGER_COMMAND,
                    {"pin": self.config_entry.data[CONF_PIN], "charger_command": get_hex(CHARGER_COMMAND.STOP.value)}
                ).encode('ascii')
            else:
                _LOGGER.error(f"Unknown command: {command}")
                return

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_udp_request, request)
            _LOGGER.info(f"{device_name}: {command} charging command sent")

    async def async_set_max_monthly_consumption(self, device_name: str, maximum_consumption: int):
        """Set maximum consumption."""

        request = build_message(CLIENT_MESSAGE.SET_MAX_MONTHLY_CONSUMPTION, {"pin": self.config_entry.data[CONF_PIN], "maximum_consumption": get_hex(maximum_consumption, 4)}).encode('ascii')
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_udp_request, request)

        _LOGGER.info(f"{device_name}: maximum consumption set")

    async def async_set_max_session_consumption(self, device_name: str, maximum_consumption: int):
        """Set maximum consumption."""

        request = build_message(CLIENT_MESSAGE.SET_MAX_SESSION_CONSUMPTION, {"pin": self.config_entry.data[CONF_PIN], "maximum_consumption": get_hex(maximum_consumption)}).encode('ascii')
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_udp_request, request)

        _LOGGER.info(f"{device_name}: maximum consumption set")

    async def async_set_timer(self, device_name: str, start_time: str, end_time: str):
        """Set charging timer."""

        # check if charger is not unplugged
        state_sensor_id = f"sensor.{self.config_entry.data[SERIAL]}_charger_state"
        state_sensor_value = self.hass.states.get(state_sensor_id)

        if state_sensor_value and state_sensor_value.state != CHARGER_STATE.UNPLUGGED.name.lower():
            timer_data = convert_timer(start_time, end_time)
            timer_data['pin'] = self.config_entry.data[CONF_PIN]
            request = build_message(CLIENT_MESSAGE.SET_TIMER, timer_data).encode('ascii')
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_udp_request, request)

            _LOGGER.info(f"{device_name}: charging timer set")

    async def async_set_schedule(self, device_name: str, weekdays: list[bool], start_time: str, end_time: str):
        """Set charging timer."""
        schedule_data = convert_schedule(reversed(weekdays), start_time, end_time)
        schedule_data['pin'] = self.config_entry.data[CONF_PIN]
        request = build_message(CLIENT_MESSAGE.SET_SCHEDULE, schedule_data).encode('ascii')
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_udp_request, request)

        _LOGGER.info(f"{device_name}: charging schedule set")

    async def async_reset_timer(self, device_name: str):
        """Reset charging timer."""

        # check if charger is not unplugged
        state_sensor_id = f"sensor.{self.config_entry.data[SERIAL]}_charger_state"
        state_sensor_value = self.hass.states.get(state_sensor_id)

        if state_sensor_value and state_sensor_value.state != CHARGER_STATE.UNPLUGGED.name.lower():
            request = build_message(CLIENT_MESSAGE.RESET_TIMER, {"pin": self.config_entry.data[CONF_PIN]}).encode('ascii')
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_udp_request, request)
            _LOGGER.info(f"{device_name}: charging timer reset")

    async def async_request_weekly_schedule(self, device_name: str):
        """Get set weekly schedule from charger."""

        request = build_message(CLIENT_MESSAGE.REQUEST_SETTINGS, {"pin": self.config_entry.data[CONF_PIN]}).encode('ascii')
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self._send_udp_request, request)
        # Decode and parse the response
        response = response.decode('ascii')
        data = read_message(response, SERVER_MESSAGE.SEND_SETTINGS)
        data['start_time'] = f"{data['timer_start_h']}:{data['timer_start_min']}"
        data['end_time'] = f"{data['timer_end_h']}:{data['timer_end_min']}"
        _LOGGER.info(f"{device_name}: requested weekly schedule")
        return {
            "result": {
                "schedule": data["schedule"],
                "weekdays": data["weekdays"],
                "start_time": data["start_time"],
                "end_time": data["end_time"]
            }
        }

    async def async_set_max_current(self, device_name: str, max_current: int):
        """Set maximum charging current (6A–32A) on the charger."""
        if not (6 <= max_current <= 32):
            raise ValueError("Maximum current must be between 6 and 32 amps")

        request = build_message(
            CLIENT_MESSAGE.SET_MAX_CURRENT,
            {
                "pin": self.config_entry.data[CONF_PIN],
                "max_current": format(max_current, "02x"),
            },
        ).encode("ascii")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_udp_request, request)

        _LOGGER.info(f"{device_name}: max current set to {max_current}A")