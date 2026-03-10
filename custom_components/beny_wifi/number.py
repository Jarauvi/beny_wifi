"""Number entities for Beny Wifi."""

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CHARGER_TYPE, CONF_MAX_CURRENT_MAX, CONF_MAX_CURRENT_MIN, DEFAULT_MAX_CURRENT_MAX, DEFAULT_MAX_CURRENT_MIN, DLB, DOMAIN, DLB_MODE, MODEL, SERIAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up number platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    device_id = config_entry.data[SERIAL]
    device_model = config_entry.data[MODEL]
    dlb = config_entry.data[DLB]
    max_current_min = config_entry.data.get(CONF_MAX_CURRENT_MIN, DEFAULT_MAX_CURRENT_MIN)
    max_current_max = config_entry.data.get(CONF_MAX_CURRENT_MAX, DEFAULT_MAX_CURRENT_MAX)

    numbers = [
        BenyWifiMaxCurrentNumber(
            coordinator,
            "max_current_control",
            device_id=device_id,
            device_model=device_model,
            min_value=max_current_min,
            max_value=max_current_max,
        )
    ]

    if dlb:
        numbers.extend([
            BenyWifiHybridCurrentNumber(
                coordinator, "hybrid_current",
                device_id=device_id, device_model=device_model,
            ),
            BenyWifiNightStartNumber(
                coordinator, "night_start_hour",
                device_id=device_id, device_model=device_model,
            ),
            BenyWifiNightEndNumber(
                coordinator, "night_end_hour",
                device_id=device_id, device_model=device_model,
            ),
            BenyWifiAntiOverloadValueNumber(
                coordinator, "anti_overload_value",
                device_id=device_id, device_model=device_model,
            ),
        ])

    async_add_entities(numbers, update_before_add=True)


def _device_info(device_id, device_model) -> DeviceInfo:
    """Shared device info builder."""
    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=f"Beny Charger {device_id}",
        manufacturer="ZJ Beny",
        model=device_model,
        serial_number=device_id,
    )


class BenyWifiMaxCurrentNumber(CoordinatorEntity, NumberEntity):
    """Max Current control number entity."""

    _attr_available = True

    def __init__(self, coordinator, key, device_id=None, device_model=None, min_value=DEFAULT_MAX_CURRENT_MIN, max_value=DEFAULT_MAX_CURRENT_MAX):
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.key = key
        self._attr_translation_key = key
        self._device_id = device_id
        self._device_model = device_model
        self._attr_has_entity_name = True
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_mode = NumberMode.SLIDER
        self._attr_icon = "mdi:current-ac"
        self._local_value = None
        self.entity_id = f"number.{device_id}_max_current_control"

    @property
    def unique_id(self):
        """Return a unique ID for this number entity."""
        return f"{self._device_id}_{self.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    @property
    def native_value(self):
        """Return the current value - prefer local value, fall back to coordinator."""
        if self._local_value is not None:
            return float(self._local_value)

        if self.coordinator.data:
            max_current = self.coordinator.data.get("max_current")
            if max_current is not None:
                try:
                    return float(max_current)
                except (ValueError, TypeError):
                    _LOGGER.warning(f"Invalid max_current value from coordinator: {max_current}")

        return 16.0

    async def async_set_native_value(self, value: float) -> None:
        """Store locally — press Send button to apply."""
        self._local_value = int(value)
        self.async_write_ha_state()
        _LOGGER.info(f"Max current control for {self._device_id} set to {int(value)}A (stored locally)")

    @property
    def should_poll(self) -> bool:
        """No need to poll, coordinator handles updates."""
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return _device_info(self._device_id, self._device_model)


class BenyWifiHybridCurrentNumber(CoordinatorEntity, NumberEntity):
    """Current limit for Hybrid DLB mode (1–32 A).

    Adjusting this while already in Hybrid mode immediately resends the config.
    Adjusting it in any other mode stores the value ready for the next switch.
    """

    def __init__(self, coordinator, key, device_id=None, device_model=None):
        """Initialize."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.key = key
        self._attr_translation_key = key
        self._device_id = device_id
        self._device_model = device_model
        self._attr_has_entity_name = True
        self._attr_icon = "mdi:current-ac"
        self._attr_native_min_value = 1
        self._attr_native_max_value = 32
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_mode = NumberMode.SLIDER
        self.entity_id = f"number.{device_id}_{key}"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._device_id}_{self.key}"

    @property
    def native_value(self) -> float:
        """Return current hybrid current limit from coordinator cache."""
        return float(self.coordinator._dlb_config.get("hybrid_current", 16))

    async def async_set_native_value(self, value: float) -> None:
        """Update hybrid current; resend to charger if currently in Hybrid mode."""
        current = int(value)
        device_name = f"Beny Charger {self._device_id}"

        self.coordinator._dlb_config["hybrid_current"] = current

        raw = self.coordinator._dlb_config.get("dlb_mode")
        if raw is not None and 1 <= raw <= 32:
            await self.coordinator.async_set_dlb_config(
                device_name,
                dlb_mode=DLB_MODE.HYBRID,
                hybrid_current=current,
            )
            _LOGGER.info(f"{device_name}: Hybrid current updated to {current}A (sent to charger)")
        else:
            self.async_write_ha_state()
            _LOGGER.info(f"{device_name}: Hybrid current stored as {current}A (applies on next Hybrid mode switch)")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return _device_info(self._device_id, self._device_model)


class BenyWifiNightStartNumber(CoordinatorEntity, NumberEntity):
    """Night Mode start hour (0–23, whole hours only).

    Uses sunset-down icon: the window begins when the sun goes down.
    """

    def __init__(self, coordinator, key, device_id=None, device_model=None):
        """Initialize."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.key = key
        self._attr_translation_key = key
        self._device_id = device_id
        self._device_model = device_model
        self._attr_has_entity_name = True
        self._attr_icon = "mdi:weather-sunset-down"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 23
        self._attr_native_step = 1
        self._attr_mode = NumberMode.BOX
        self.entity_id = f"number.{device_id}_{key}"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._device_id}_{self.key}"

    @property
    def native_value(self) -> float:
        """Return current night start hour from coordinator cache."""
        return float(self.coordinator._dlb_config.get("night_start", 22))

    async def async_set_native_value(self, value: float) -> None:
        """Update night start hour and resend config to charger."""
        hour = int(value)
        device_name = f"Beny Charger {self._device_id}"
        await self.coordinator.async_set_dlb_config(device_name, night_start=hour)
        _LOGGER.info(f"{device_name}: Night Mode start hour set to {hour:02d}:00")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return _device_info(self._device_id, self._device_model)


class BenyWifiNightEndNumber(CoordinatorEntity, NumberEntity):
    """Night Mode end hour (0–23, whole hours only).

    Uses sunrise icon: the window ends when the sun comes up.
    """

    def __init__(self, coordinator, key, device_id=None, device_model=None):
        """Initialize."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.key = key
        self._attr_translation_key = key
        self._device_id = device_id
        self._device_model = device_model
        self._attr_has_entity_name = True
        self._attr_icon = "mdi:weather-sunset-up"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 23
        self._attr_native_step = 1
        self._attr_mode = NumberMode.BOX
        self.entity_id = f"number.{device_id}_{key}"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._device_id}_{self.key}"

    @property
    def native_value(self) -> float:
        """Return current night end hour from coordinator cache."""
        return float(self.coordinator._dlb_config.get("night_end", 6))

    async def async_set_native_value(self, value: float) -> None:
        """Update night end hour and resend config to charger."""
        hour = int(value)
        device_name = f"Beny Charger {self._device_id}"
        await self.coordinator.async_set_dlb_config(device_name, night_end=hour)
        _LOGGER.info(f"{device_name}: Night Mode end hour set to {hour:02d}:00")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return _device_info(self._device_id, self._device_model)

class BenyWifiAntiOverloadValueNumber(CoordinatorEntity, NumberEntity):
    """Threshold value for Anti Overload Mode (1–99).

    This sets the grid-draw limit used when Anti Overload is enabled.
    Adjusting it while Anti Overload is ON immediately resends the config.
    Adjusting it while OFF stores the value ready for the next enable.
    """

    def __init__(self, coordinator, key, device_id=None, device_model=None):
        """Initialize."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.key = key
        self._attr_translation_key = key
        self._device_id = device_id
        self._device_model = device_model
        self._attr_has_entity_name = True
        self._attr_icon = "mdi:transmission-tower-off"
        self._attr_native_min_value = 1
        self._attr_native_max_value = 99
        self._attr_native_step = 1
        self._attr_mode = NumberMode.BOX
        self.entity_id = f"number.{device_id}_{key}"

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._device_id}_{self.key}"

    @property
    def native_value(self) -> float:
        """Return the stored threshold value (always the non-zero value, even when disabled)."""
        return float(self.coordinator._dlb_config.get("anti_overload_value", 0x3f))

    async def async_set_native_value(self, value: float) -> None:
        """Update Anti Overload threshold; resend to charger if currently enabled."""
        threshold = int(value)
        device_name = f"Beny Charger {self._device_id}"
        await self.coordinator.async_set_dlb_config(
            device_name, anti_overload_value=threshold
        )
        _LOGGER.info(
            f"{device_name}: Anti Overload threshold set to {threshold}"
            + (" (sent to charger)" if self.coordinator._dlb_config.get("anti_overload", 0) != 0 else " (stored, applies on next enable)")
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return _device_info(self._device_id, self._device_model)