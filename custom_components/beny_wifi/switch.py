"""Switch entities for Beny Wifi."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DLB, DOMAIN, MODEL, SERIAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switch platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    device_id = config_entry.data[SERIAL]
    device_model = config_entry.data[MODEL]
    dlb = config_entry.data[DLB]

    entities = []

    if dlb:
        entities.extend([
            BenyWifiExtremeModeSwitch(
                coordinator,
                "extreme_mode",
                device_id=device_id,
                device_model=device_model,
            ),
            BenyWifiNightModeSwitch(
                coordinator,
                "night_mode",
                device_id=device_id,
                device_model=device_model,
            ),
        ])

    if entities:
        async_add_entities(entities)


class BenyWifiDlbSwitch(CoordinatorEntity, SwitchEntity):
    """Base class for DLB boolean switches."""

    def __init__(self, coordinator, key, device_id=None, device_model=None):
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.key = key
        self._attr_translation_key = key
        self._device_id = device_id
        self._device_model = device_model
        self._attr_has_entity_name = True
        self.entity_id = f"switch.{device_id}_{key}"
        self._optimistic_state: bool | None = None

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._device_id}_{self.key}"

    def _get_cached_byte(self, field: str) -> int:
        """Read a byte from the coordinator's DLB config cache."""
        if self.coordinator.data:
            return self.coordinator.data.get("dlb_config", {}).get(field, 0x00)
        return 0x00

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=f"Beny Charger {self._device_id}",
            manufacturer="ZJ Beny",
            model=self._device_model,
            serial_number=self._device_id,
        )


class BenyWifiExtremeModeSwitch(BenyWifiDlbSwitch):
    """Switch to enable/disable Extreme Mode.

    In Extreme Mode the charger reduces current as home load rises,
    stopping charging entirely if grid headroom drops below ~10A.
    """

    def __init__(self, coordinator, key, device_id=None, device_model=None):
        """Initialize."""
        super().__init__(coordinator, key, device_id, device_model)
        self._attr_icon = "mdi:lightning-bolt"

    @property
    def is_on(self) -> bool:
        """Return True if Extreme Mode is active."""
        if self._optimistic_state is not None:
            return self._optimistic_state
        return self._get_cached_byte("extreme") == 0x01

    async def async_turn_on(self, **kwargs) -> None:
        """Enable Extreme Mode."""
        device_name = f"Beny Charger {self._device_id}"
        await self.coordinator.async_set_dlb_config(device_name, extreme_mode=True)
        self._optimistic_state = True
        self.async_write_ha_state()
        _LOGGER.info(f"{device_name}: Extreme Mode enabled")

    async def async_turn_off(self, **kwargs) -> None:
        """Disable Extreme Mode."""
        device_name = f"Beny Charger {self._device_id}"
        await self.coordinator.async_set_dlb_config(device_name, extreme_mode=False)
        self._optimistic_state = False
        self.async_write_ha_state()
        _LOGGER.info(f"{device_name}: Extreme Mode disabled")

    def _handle_coordinator_update(self) -> None:
        """Clear optimistic state on coordinator refresh."""
        self._optimistic_state = None
        super()._handle_coordinator_update()


class BenyWifiNightModeSwitch(BenyWifiDlbSwitch):
    """Switch to enable/disable Night Mode (automatic full-speed window).

    Night Mode charges at full speed during a configured hour window.
    The window is configured via the night_start/night_end hours stored
    in the coordinator's DLB config cache. Use the set_dlb_config service
    to adjust the window hours independently.
    """

    def __init__(self, coordinator, key, device_id=None, device_model=None):
        """Initialize."""
        super().__init__(coordinator, key, device_id, device_model)
        self._attr_icon = "mdi:weather-night"

    @property
    def is_on(self) -> bool:
        """Return True if Night Mode is active."""
        if self._optimistic_state is not None:
            return self._optimistic_state
        return self._get_cached_byte("night") == 0x01

    @property
    def extra_state_attributes(self) -> dict:
        """Expose night window hours as state attributes."""
        if self.coordinator.data:
            cfg = self.coordinator.data.get("dlb_config", {})
            return {
                "night_start_hour": cfg.get("night_start"),
                "night_end_hour":   cfg.get("night_end"),
            }
        return {}

    async def async_turn_on(self, **kwargs) -> None:
        """Enable Night Mode."""
        device_name = f"Beny Charger {self._device_id}"
        await self.coordinator.async_set_dlb_config(device_name, night_mode=True)
        self._optimistic_state = True
        self.async_write_ha_state()
        _LOGGER.info(f"{device_name}: Night Mode enabled")

    async def async_turn_off(self, **kwargs) -> None:
        """Disable Night Mode."""
        device_name = f"Beny Charger {self._device_id}"
        await self.coordinator.async_set_dlb_config(device_name, night_mode=False)
        self._optimistic_state = False
        self.async_write_ha_state()
        _LOGGER.info(f"{device_name}: Night Mode disabled")

    def _handle_coordinator_update(self) -> None:
        """Clear optimistic state on coordinator refresh."""
        self._optimistic_state = None
        super()._handle_coordinator_update()