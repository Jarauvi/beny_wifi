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
    DLB_MODE,
    DOMAIN,
    REQUEST_TYPE,
    SERIAL,
    SECTION_DEVICE,
    get_config_parameter,
    get_entity_state_by_key
)
from .conversions import convert_schedule, convert_timer, get_hex

_LOGGER = logging.getLogger(__name__)

# Default night mode window used when enabling night mode without prior state
DEFAULT_NIGHT_START = 22  # 10pm
DEFAULT_NIGHT_END = 6     # 6am


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
        self._dlb_config_loaded = False  # set True after first successful read from charger

        # Local cache of DLB config state — populated on first SET and preserved
        # across updates so we never accidentally reset a field we didn't intend to change.
        # Restored from config_entry.options if previously persisted, otherwise defaults.
        persisted = config_entry.options.get("dlb_config", {})
        self._dlb_config: dict = {
            "dlb_enabled":    persisted.get("dlb_enabled",    0x01),   # default: enabled
            "extreme":        persisted.get("extreme",        0x00),
            "dlb_mode":       persisted.get("dlb_mode",       0xff),   # default: DLB Box
            "night":          persisted.get("night",          0x00),
            "night_start":    persisted.get("night_start",    DEFAULT_NIGHT_START),
            "night_end":      persisted.get("night_end",      DEFAULT_NIGHT_END),
            "hybrid_current": persisted.get("hybrid_current", 16),
            "anti_overload":  persisted.get("anti_overload",  0x3f),   # 0x00=off, 1-99=on with that threshold value
            "anti_overload_value": persisted.get("anti_overload_value", 0x3f),  # last non-zero threshold, used on re-enable
        }
        if persisted:
            _LOGGER.debug(f"DLB config restored from config_entry.options: {self._dlb_config}")  # noqa: G004

        # Tracks consecutive polls where a field returned None (sentinel/missing).
        # Once a field hits STALE_THRESHOLD, is_field_stale() returns True so
        # sensors can mark themselves unavailable instead of showing stale data.
        self._stale_counts: dict[str, int] = {}

    # Number of consecutive None polls before a field is considered stale.
    # Set to 6 (3 minutes at 30s polling) to tolerate transient DLB sentinel
    # values during normal charger state transitions without flipping unavailable.
    STALE_THRESHOLD = 6

    def is_field_stale(self, field: str) -> bool:
        """Return True if the field has been missing for STALE_THRESHOLD consecutive polls."""
        return self._stale_counts.get(field, 0) >= self.STALE_THRESHOLD

    def _update_stale_count(self, field: str, value) -> None:
        """Increment stale counter when value is None, reset it when a valid value arrives."""
        if value is None:
            self._stale_counts[field] = self._stale_counts.get(field, 0) + 1
            if self._stale_counts[field] == self.STALE_THRESHOLD:
                _LOGGER.warning(  # noqa: G004
                    f"Field '{field}' has been unavailable for {self.STALE_THRESHOLD} "
                    f"consecutive polls — marking as stale"
                )
        else:
            if self._stale_counts.get(field, 0) >= self.STALE_THRESHOLD:
                _LOGGER.info(f"Field '{field}' has recovered and is available again")  # noqa: G004
            self._stale_counts[field] = 0

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data asynchronously.

        If the entire fetch fails (device unreachable, UDP timeout, etc.) we still
        increment stale counts for all DLB fields so they tip to unavailable after
        STALE_THRESHOLD missed polls, just as they would for per-field sentinel failures.
        """
        try:
            return await self._fetch_data()
        except UpdateFailed:
            if self.config_entry.data.get(DLB):
                for key in ("grid_power", "house_power", "ev_power", "solar_power"):
                    self._update_stale_count(key, None)
            raise

    async def async_read_dlb_config(self) -> bool:
        """Attempt to read current DLB config from charger to populate _dlb_config cache.

        The charger does not support a dedicated config-read command — it responds to
        GET_DLB_CONFIG with a denial packet (message_id=8). This method therefore always
        returns True (marking the attempt as done) so the coordinator stops retrying.

        Config is populated via two other mechanisms instead:
          - Persisted values from config_entry.options (restored in __init__)
          - ACK parsing after every async_set_dlb_config call

        Returns:
            bool: Always True — signals caller not to retry.
        """
        persisted = self.config_entry.options.get("dlb_config", {})
        if persisted:
            _LOGGER.info(  # noqa: G004
                f"DLB config loaded from persisted options: "
                f"extreme={self._dlb_config['extreme']:#04x} "
                f"dlb_mode={self._dlb_config['dlb_mode']:#04x} "
                f"night={self._dlb_config['night']:#04x} "
                f"night_start={self._dlb_config['night_start']} "
                f"night_end={self._dlb_config['night_end']}"
            )
        else:
            _LOGGER.info(
                "No persisted DLB config found — using defaults. "
                "Values will be saved automatically after the first DLB setting change."
            )
        return True

    async def _async_persist_dlb_config(self) -> None:
        """Persist _dlb_config to config_entry.options so it survives HA restarts."""
        options = dict(self.config_entry.options)
        options["dlb_config"] = dict(self._dlb_config)
        self.hass.config_entries.async_update_entry(self.config_entry, options=options)
        _LOGGER.debug(f"DLB config persisted to config_entry.options: {self._dlb_config}")  # noqa: G004

    async def _fetch_data(self):
        """Send UDP request and fetch data asynchronously."""

        # On the first successful fetch, attempt to read DLB config directly from
        # the charger so entities reflect actual state rather than defaults/persisted cache.
        if get_config_parameter(self.config_entry, SECTION_DEVICE, DLB, False) and not self._dlb_config_loaded:
            self._dlb_config_loaded = await self.async_read_dlb_config()

        try:
            # Build the request message
            request = build_message(
                CLIENT_MESSAGE.REQUEST_DATA,
                {"pin": get_config_parameter(self.config_entry, SECTION_DEVICE, CONF_PIN), "request_type": get_hex(REQUEST_TYPE.VALUES.value)}
            ).encode('ascii')

            # Send UDP request asynchronously
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, self._send_udp_request, request)

            # Decode and parse the response
            response = response.decode('ascii')
            
            # Authentication failed
            if "55aa100008" in response:
                raise Exception("Authentication failed, check PIN")
        
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

            # DLB data fetch — isolated so a DLB failure doesn't discard valid charger data
            if get_config_parameter(self.config_entry, SECTION_DEVICE, DLB):
                try:
                    request = build_message(
                        CLIENT_MESSAGE.REQUEST_DLB,
                        {"pin": get_config_parameter(self.config_entry, SECTION_DEVICE, CONF_PIN), "request_type": get_hex(REQUEST_TYPE.DLB.value)}
                    ).encode('ascii')

                    loop = asyncio.get_running_loop()
                    response_dlb = await loop.run_in_executor(None, self._send_udp_request, request)
                    response_dlb = response_dlb.decode('ascii')
                    data_dlb = read_message(response_dlb)

                    if data_dlb is None:
                        _LOGGER.warning("DLB response had invalid checksum — skipping DLB data this cycle")
                        for key in ("grid_power", "house_power", "ev_power", "solar_power"):
                            self._update_stale_count(key, None)
                    else:
                        # Track staleness per field. None means the charger sent a sentinel
                        # (0xFF00+) indicating DLB data is temporarily unavailable.
                        # Only assign valid values so sensors can retain last known state
                        # until is_field_stale() tips them to unavailable after STALE_THRESHOLD.
                        for key in ("grid_power", "house_power", "ev_power", "solar_power"):
                            val = data_dlb.get(key)
                            self._update_stale_count(key, val)
                            if val is not None:
                                data[key] = val

                except Exception as dlb_err:
                    _LOGGER.warning(
                        f"DLB fetch failed (non-fatal): {dlb_err} — DLB sensors will retain last valid value"
                    )
                    for key in ("grid_power", "house_power", "ev_power", "solar_power"):
                        self._update_stale_count(key, None)
                    # Do not re-raise: the primary charger data is still valid


            # Expose current DLB config state so entities can read it
            data['dlb_config'] = dict(self._dlb_config)

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
        state_sensor_value = get_entity_state_by_key(self.hass, self.config_entry, "charger_state", "sensor")

        if state_sensor_value and state_sensor_value.state != CHARGER_STATE.UNPLUGGED.name.lower():
            if command == "start":
                request = build_message(
                    CLIENT_MESSAGE.SEND_CHARGER_COMMAND,
                    {"pin": get_config_parameter(self.config_entry, SECTION_DEVICE, CONF_PIN), "charger_command": get_hex(CHARGER_COMMAND.START.value)}
                ).encode('ascii')
            elif command == "stop":
                request = build_message(
                    CLIENT_MESSAGE.SEND_CHARGER_COMMAND,
                    {"pin": get_config_parameter(self.config_entry, SECTION_DEVICE, CONF_PIN), "charger_command": get_hex(CHARGER_COMMAND.STOP.value)}
                ).encode('ascii')
            else:
                _LOGGER.error(f"Unknown command: {command}")
                return

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._send_udp_request, request)
            _LOGGER.info(f"{device_name}: {command} charging command sent")

    async def async_set_max_monthly_consumption(self, device_name: str, maximum_consumption: int):
        """Set maximum consumption."""

        request = build_message(CLIENT_MESSAGE.SET_MAX_MONTHLY_CONSUMPTION, {"pin": get_config_parameter(self.config_entry, SECTION_DEVICE, CONF_PIN), "maximum_consumption": get_hex(maximum_consumption, 4)}).encode('ascii')
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._send_udp_request, request)

        _LOGGER.info(f"{device_name}: maximum consumption set")

    async def async_set_max_session_consumption(self, device_name: str, maximum_consumption: int):
        """Set maximum consumption."""

        request = build_message(CLIENT_MESSAGE.SET_MAX_SESSION_CONSUMPTION, {"pin": get_config_parameter(self.config_entry, SECTION_DEVICE, CONF_PIN), "maximum_consumption": get_hex(maximum_consumption)}).encode('ascii')
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._send_udp_request, request)

        _LOGGER.info(f"{device_name}: maximum consumption set")

    async def async_set_timer(self, device_name: str, start_time: str, end_time: str):
        """Set charging timer."""

        # check if charger is not unplugged
        state_sensor_value = get_entity_state_by_key(self.hass, self.config_entry, "charger_state", "sensor")

        if state_sensor_value and state_sensor_value.state != CHARGER_STATE.UNPLUGGED.name.lower():
            timer_data = convert_timer(start_time, end_time)
            timer_data['pin'] = get_config_parameter(self.config_entry, SECTION_DEVICE, CONF_PIN)
            request = build_message(CLIENT_MESSAGE.SET_TIMER, timer_data).encode('ascii')
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._send_udp_request, request)

            _LOGGER.info(f"{device_name}: charging timer set")

    async def async_set_schedule(self, device_name: str, weekdays: list[bool], start_time: str, end_time: str):
        """Set charging timer."""
        schedule_data = convert_schedule(reversed(weekdays), start_time, end_time)
        schedule_data['pin'] = get_config_parameter(self.config_entry, SECTION_DEVICE, CONF_PIN)
        request = build_message(CLIENT_MESSAGE.SET_SCHEDULE, schedule_data).encode('ascii')
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._send_udp_request, request)

        _LOGGER.info(f"{device_name}: charging schedule set")

    async def async_reset_timer(self, device_name: str):
        """Reset charging timer."""

        # check if charger is not unplugged
        state_sensor_value = get_entity_state_by_key(self.hass, self.config_entry, "charger_state", "sensor")

        if state_sensor_value and state_sensor_value.state != CHARGER_STATE.UNPLUGGED.name.lower():
            request = build_message(CLIENT_MESSAGE.RESET_TIMER, {"pin": get_config_parameter(self.config_entry, SECTION_DEVICE, CONF_PIN)}).encode('ascii')
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._send_udp_request, request)
            _LOGGER.info(f"{device_name}: charging timer reset")

    async def async_request_weekly_schedule(self, device_name: str):
        """Get set weekly schedule from charger."""

        request = build_message(CLIENT_MESSAGE.REQUEST_SETTINGS, {"pin": get_config_parameter(self.config_entry, SECTION_DEVICE, CONF_PIN)}).encode('ascii')
        loop = asyncio.get_running_loop()
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
        """Set maximum charging current (6A-32A) on the charger."""
        if not (6 <= max_current <= 32):
            raise ValueError("Maximum current must be between 6 and 32 amps")

        request = build_message(
            CLIENT_MESSAGE.SET_MAX_CURRENT,
            {
                "pin": get_config_parameter(self.config_entry, SECTION_DEVICE, CONF_PIN),
                "max_current": format(max_current, "02x"),
            },
        ).encode("ascii")

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._send_udp_request, request)

        _LOGGER.info(f"{device_name}: max current set to {max_current}A")

    async def async_set_dlb_config(
        self,
        device_name: str,
        *,
        dlb_enabled: bool | None = None,
        dlb_mode: DLB_MODE | None = None,
        hybrid_current: int | None = None,
        extreme_mode: bool | None = None,
        night_mode: bool | None = None,
        night_start: int | None = None,
        night_end: int | None = None,
        anti_overload: bool | None = None,
        anti_overload_value: int | None = None,
    ) -> None:
        """Send full DLB config to charger.

        Only the supplied keyword arguments are changed — all others are preserved
        from the local cache so we never accidentally reset a field.

        Args:
            device_name:         Human-readable device label for logging.
            dlb_enabled:         True to enable PV Dynamic Load Balance, False to disable.
            dlb_mode:            DLB_MODE enum value. For HYBRID, also supply hybrid_current.
            hybrid_current:      Current limit in amps (6-32) when dlb_mode=HYBRID.
            extreme_mode:        True to enable Extreme Mode, False to disable.
            night_mode:          True to enable Night Mode, False to disable.
            night_start:         Night mode start hour (0-23, 24h).
            night_end:           Night mode end hour (0-23, 24h).
            anti_overload:       True to enable Anti Overload, False to disable (sets byte to 0x00).
            anti_overload_value: Threshold value (1-99) used when Anti Overload is enabled.
        """
        cfg = self._dlb_config

        # Apply any supplied overrides
        if dlb_enabled is not None:
            cfg["dlb_enabled"] = 0x01 if dlb_enabled else 0x00

        if extreme_mode is not None:
            cfg["extreme"] = 0x01 if extreme_mode else 0x00

        if night_mode is not None:
            cfg["night"] = 0x01 if night_mode else 0x00

        if night_start is not None:
            if not (0 <= night_start <= 23):
                raise ValueError("night_start must be 0-23")
            cfg["night_start"] = night_start

        if night_end is not None:
            if not (0 <= night_end <= 23):
                raise ValueError("night_end must be 0-23")
            cfg["night_end"] = night_end

        if dlb_mode is not None:
            if dlb_mode == DLB_MODE.HYBRID:
                # For hybrid, byte12 carries the actual current limit
                current = hybrid_current if hybrid_current is not None else cfg["hybrid_current"]
                if not (6 <= current <= 32):
                    raise ValueError("hybrid_current must be between 6 and 32 amps")
                cfg["hybrid_current"] = current
                cfg["dlb_mode"] = current  # byte12 = amps value directly
            else:
                cfg["dlb_mode"] = dlb_mode.value

        # Anti Overload: 0x00 = off, 1-99 = on with that threshold value.
        # Updating the value alone (without toggling) stores it ready for next enable.
        # Toggling on uses the stored value; toggling off sends 0x00.
        if anti_overload_value is not None:
            if not (1 <= anti_overload_value <= 99):
                raise ValueError("anti_overload_value must be between 1 and 99")
            cfg["anti_overload_value"] = anti_overload_value
            # If currently enabled, also update the live byte immediately
            if cfg["anti_overload"] != 0x00:
                cfg["anti_overload"] = anti_overload_value

        if anti_overload is not None:
            if anti_overload:
                # Enable: use the stored threshold value (default 63)
                cfg["anti_overload"] = cfg.get("anti_overload_value", 0x3f)
            else:
                cfg["anti_overload"] = 0x00

        # Determine byte12 to send
        dlb_mode_byte = cfg["dlb_mode"]
        # If dlb_mode is stored as an int (hybrid current), use it directly
        # If it's a DLB_MODE enum value use its .value (shouldn't happen but guard anyway)
        if isinstance(dlb_mode_byte, DLB_MODE):
            dlb_mode_byte = dlb_mode_byte.value

        request = build_message(
            CLIENT_MESSAGE.SET_DLB_CONFIG,
            {
                "pin":          get_config_parameter(self.config_entry, SECTION_DEVICE, CONF_PIN),
                "dlb_enabled":  format(cfg["dlb_enabled"],    "02x"),
                "extreme":      format(cfg["extreme"],        "02x"),
                "dlb_mode":     format(dlb_mode_byte,         "02x"),
                "night":        format(cfg["night"],           "02x"),
                "night_start":  format(cfg["night_start"],     "02x"),
                "night_end":    format(cfg["night_end"],       "02x"),
                "anti_overload": format(cfg["anti_overload"],  "02x"),
            },
        ).encode("ascii")

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, self._send_udp_request, request)

        # Parse the ACK — the charger echoes back the full config it applied.
        # This confirms what was stored and keeps _dlb_config in sync,
        # including the anti_overload byte which the user may have set via the Z-Box app.
        try:
            ack = read_message(response.decode("ascii"))
            if ack and ack.get("message_type") == str(SERVER_MESSAGE.SEND_DLB_CONFIG):
                if "dlb_enabled" in ack:
                    cfg["dlb_enabled"] = ack["dlb_enabled"]
                if "anti_overload" in ack:
                    cfg["anti_overload"] = ack["anti_overload"]
                    # If non-zero, also update the stored threshold so re-enable restores it
                    if ack["anti_overload"] != 0x00:
                        cfg["anti_overload_value"] = ack["anti_overload"]
                _LOGGER.debug(f"SET_DLB_CONFIG ACK confirmed by charger: {ack}")  # noqa: G004
        except Exception as ack_err:
            _LOGGER.debug(f"Could not parse SET_DLB_CONFIG ACK (non-fatal): {ack_err}")  # noqa: G004

        await self._async_persist_dlb_config()

        _LOGGER.info(
            f"{device_name}: DLB config set — "
            f"dlb_enabled={cfg['dlb_enabled']:#04x} "
            f"extreme={cfg['extreme']:#04x} dlb_mode={dlb_mode_byte:#04x} "
            f"night={cfg['night']:#04x} "
            f"night_start={cfg['night_start']} night_end={cfg['night_end']}"
        )