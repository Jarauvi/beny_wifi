"""Sensors for Beny Wifi."""

import logging

from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CHARGER_TYPE, DLB, DOMAIN, MODEL, SERIAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    device_id = config_entry.data[SERIAL]
    device_model = config_entry.data[MODEL]
    device_type = config_entry.data[CHARGER_TYPE]
    dlb = config_entry.data[DLB]

    sensors = []

    # by default only all 1-phase sensors are included
    if device_type == '1P':
        sensors = [
            BenyWifiChargerStateSensor(coordinator, "charger_state", device_id=device_id, device_model=device_model),
            BenyWifiPowerSensor(coordinator, "power", device_id=device_id, device_model=device_model),
            BenyWifiVoltageSensor(coordinator, "voltage1", device_id=device_id, device_model=device_model),
            BenyWifiCurrentSensor(coordinator, "current1", device_id=device_id, device_model=device_model),
            BenyWifiCurrentSensor(coordinator, "max_current", device_id=device_id, device_model=device_model),
            BenyWifiEnergySensor(coordinator, "total_kwh", device_id=device_id, device_model=device_model),
            BenyWifiTemperatureSensor(coordinator, "temperature", device_id=device_id, device_model=device_model),
            BenyWifiEnergySensor(coordinator, "maximum_session_consumption", icon="mdi:meter-electric", device_id=device_id, device_model=device_model),
            BenyWifiTimerSensor(coordinator, "timer_start", icon="mdi:timer-sand-full", device_id=device_id, device_model=device_model),
            BenyWifiTimerSensor(coordinator, "timer_end", icon="mdi:timer-sand-empty", device_id=device_id, device_model=device_model)
        ]

    # add all three phases if model supports them
    elif device_type == '3P':
        sensors = [
            BenyWifiChargerStateSensor(coordinator, "charger_state", device_id=device_id, device_model=device_model),
            BenyWifiPowerSensor(coordinator, "power", device_id=device_id, device_model=device_model),
            BenyWifiVoltageSensor(coordinator, "voltage1", device_id=device_id, device_model=device_model),
            BenyWifiVoltageSensor(coordinator, "voltage2", device_id=device_id, device_model=device_model),
            BenyWifiVoltageSensor(coordinator, "voltage3", device_id=device_id, device_model=device_model),
            BenyWifiCurrentSensor(coordinator, "current1", device_id=device_id, device_model=device_model),
            BenyWifiCurrentSensor(coordinator, "current2", device_id=device_id, device_model=device_model),
            BenyWifiCurrentSensor(coordinator, "current3", device_id=device_id, device_model=device_model),
            BenyWifiCurrentSensor(coordinator, "max_current", device_id=device_id, device_model=device_model),
            BenyWifiEnergySensor(coordinator, "total_kwh", device_id=device_id, device_model=device_model),
            BenyWifiTemperatureSensor(coordinator, "temperature", device_id=device_id, device_model=device_model),
            BenyWifiEnergySensor(coordinator, "maximum_session_consumption", icon="mdi:meter-electric", device_id=device_id, device_model=device_model),
            BenyWifiTimerSensor(coordinator, "timer_start", icon="mdi:timer-sand-full", device_id=device_id, device_model=device_model),
            BenyWifiTimerSensor(coordinator, "timer_end", icon="mdi:timer-sand-empty", device_id=device_id, device_model=device_model)
        ]

    # TODO: DLB
    if dlb:
        sensors.extend([
            BenyWifiPowerSensor(coordinator, "grid_power", icon="mdi:transmission-tower", device_id=device_id, device_model=device_model),
            BenyWifiPowerSensor(coordinator, "solar_power", icon="mdi:solar-power-variant", device_id=device_id, device_model=device_model),
            BenyWifiPowerSensor(coordinator, "ev_power", icon="mdi:car-electric", device_id=device_id, device_model=device_model),
            BenyWifiPowerSensor(coordinator, "house_power", icon="mdi:home-lightning-bolt", device_id=device_id, device_model=device_model),
        ])

    async_add_entities(sensors)

class BenyWifiSensor(CoordinatorEntity):
    """Charger sensor model."""

    def __init__(self, coordinator, key, device_id=None, device_model=None, icon=None):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.key = key
        self._attr_translation_key = key
        self._device_id = device_id
        self._device_model = device_model
        self.entity_id = f"sensor.{device_id}_{key}"
        self._attr_has_entity_name = True
        self._icon = icon

    @property
    def unique_id(self):
        """Return a unique ID for this sensor."""
        return f"{self._device_id}_{self.key}"

    @property
    def state(self):
        """Return the current state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.key)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers = {(DOMAIN, self._device_id)},
            name=f"Beny Charger {self._device_id}",
            manufacturer = "ZJ Beny",
            model = self._device_model,
            serial_number=self._device_id
        )

    @property
    def icon(self):
        """Return corresponding icon."""
        return self._icon

class BenyWifiChargerStateSensor(BenyWifiSensor):
    """Charger state sensor class."""

    def __init__(self, coordinator, key, device_id=None, device_model=None, icon="mdi:ev-station"):
        """Initialize sensor."""
        super().__init__(coordinator, key, device_id, device_model, icon)

class BenyWifiCurrentSensor(BenyWifiSensor):
    """Current sensor class."""

    def __init__(self, coordinator, key, device_id=None, device_model=None, icon="mdi:sine-wave"):
        """Initialize sensor."""
        super().__init__(coordinator, key, device_id, device_model, icon)

    @property
    def unit_of_measurement(self):
        """Sensor unit."""
        return UnitOfElectricCurrent.AMPERE

class BenyWifiVoltageSensor(BenyWifiSensor):
    """Voltage sensor class."""

    def __init__(self, coordinator, key, device_id=None, device_model=None, icon="mdi:flash-triangle"):
        """Initialize sensor."""
        super().__init__(coordinator, key, device_id, device_model, icon)

    @property
    def unit_of_measurement(self):
        """Sensor unit."""
        return UnitOfElectricPotential.VOLT

class BenyWifiPowerSensor(BenyWifiSensor):
    """Power sensor class."""

    def __init__(self, coordinator, key, device_id=None, device_model=None, icon="mdi:ev-plug-type2"):
        """Initialize sensor."""
        super().__init__(coordinator, key, device_id, device_model, icon)

    @property
    def unit_of_measurement(self):
        """Sensor unit."""
        return UnitOfPower.KILO_WATT

    @property
    def available(self) -> bool:
        """Return False once a DLB field has been None for STALE_THRESHOLD consecutive polls.

        For non-DLB power fields, delegates entirely to CoordinatorEntity.available
        which already handles device-unreachable via last_update_success.
        For DLB fields, also checks the per-field stale counter so each can go
        unavailable independently of the overall coordinator state.
        """
        if self.key in ("grid_power", "solar_power", "ev_power", "house_power"):
            return super().available and not self.coordinator.is_field_stale(self.key)
        return super().available

    @property
    def state(self):
        """Return the current state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.key)


class BenyWifiTemperatureSensor(BenyWifiSensor):
    """Temperature sensor class."""

    def __init__(self, coordinator, key, device_id=None, device_model=None, icon="mdi:thermometer"):
        """Initialize sensor."""
        super().__init__(coordinator, key, device_id, device_model, icon)

    @property
    def unit_of_measurement(self):
        """Sensor unit."""
        return self.hass.config.units.temperature_unit

class BenyWifiEnergySensor(BenyWifiSensor):
    """Energy sensor class."""

    def __init__(self, coordinator, key, device_id=None, device_model=None, icon="mdi:power-plug-battery"):
        """Initialize sensor."""
        super().__init__(coordinator, key, device_id, device_model, icon)

    @property
    def unit_of_measurement(self):
        """Sensor unit."""
        return UnitOfEnergy.KILO_WATT_HOUR

class BenyWifiTimerSensor(BenyWifiSensor):
    """Timer sensor class."""

    def __init__(self, coordinator, key, device_id=None, device_model=None, icon="mdi:timer-sand-empty"):
        """Initialize sensor."""
        super().__init__(coordinator, key, device_id, device_model, icon)