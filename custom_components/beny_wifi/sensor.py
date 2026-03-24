"""Sensors for Beny Wifi."""

import logging

from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
    SensorEntity,
)

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CHARGER_TYPE, 
    DLB, 
    DOMAIN, 
    MODEL, 
    SERIAL,
    SECTION_DEVICE,
    SECTION_DLB,
    get_device_id,
    get_config_parameter
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    serial = get_config_parameter(config_entry, SECTION_DEVICE, SERIAL)
    device_model = get_config_parameter(config_entry, SECTION_DEVICE, MODEL)
    device_type = get_config_parameter(config_entry, SECTION_DEVICE, CHARGER_TYPE)
    dlb = get_config_parameter(config_entry, SECTION_DLB, DLB)

    sensors = []

    # by default only all 1-phase sensors are included
    if device_type == '1P':
        sensors = [
            BenyWifiChargerStateSensor(coordinator, "charger_state", device_model=device_model, serial=serial),
            BenyWifiPowerSensor(coordinator, "power", device_model=device_model, serial=serial),
            BenyWifiVoltageSensor(coordinator, "voltage1", device_model=device_model, serial=serial),
            BenyWifiCurrentSensor(coordinator, "current1", device_model=device_model, serial=serial),
            BenyWifiCurrentSensor(coordinator, "max_current", device_model=device_model, serial=serial),
            BenyWifiEnergySensor(coordinator, "total_kwh", device_model=device_model, serial=serial),
            BenyWifiTemperatureSensor(coordinator, "temperature", device_model=device_model, serial=serial),
            BenyWifiEnergySensor(coordinator, "maximum_session_consumption", icon="mdi:meter-electric", device_model=device_model, serial=serial),
            BenyWifiTimerSensor(coordinator, "timer_start", icon="mdi:timer-sand-full", device_model=device_model, serial=serial),
            BenyWifiTimerSensor(coordinator, "timer_end", icon="mdi:timer-sand-empty", device_model=device_model, serial=serial)
        ]

    # add all three phases if model supports them
    elif device_type == '3P':
        sensors = [
            BenyWifiChargerStateSensor(coordinator, "charger_state", device_model=device_model, serial=serial),
            BenyWifiPowerSensor(coordinator, "power", device_model=device_model, serial=serial),
            BenyWifiVoltageSensor(coordinator, "voltage1", device_model=device_model, serial=serial),
            BenyWifiVoltageSensor(coordinator, "voltage2", device_model=device_model, serial=serial),
            BenyWifiVoltageSensor(coordinator, "voltage3", device_model=device_model, serial=serial),
            BenyWifiCurrentSensor(coordinator, "current1", device_model=device_model, serial=serial),
            BenyWifiCurrentSensor(coordinator, "current2", device_model=device_model, serial=serial),
            BenyWifiCurrentSensor(coordinator, "current3", device_model=device_model, serial=serial),
            BenyWifiCurrentSensor(coordinator, "max_current", device_model=device_model, serial=serial),
            BenyWifiEnergySensor(coordinator, "total_kwh", device_model=device_model, serial=serial),
            BenyWifiTemperatureSensor(coordinator, "temperature", device_model=device_model, serial=serial),
            BenyWifiEnergySensor(coordinator, "maximum_session_consumption", icon="mdi:meter-electric", device_model=device_model, serial=serial),
            BenyWifiTimerSensor(coordinator, "timer_start", icon="mdi:timer-sand-full", device_model=device_model, serial=serial),
            BenyWifiTimerSensor(coordinator, "timer_end", icon="mdi:timer-sand-empty", device_model=device_model, serial=serial)
        ]

    # TODO: DLB
    if dlb:
        sensors.extend([
            BenyWifiPowerSensor(coordinator, "grid_power", icon="mdi:transmission-tower", device_model=device_model, serial=serial),
            BenyWifiPowerSensor(coordinator, "solar_power", icon="mdi:solar-power-variant", device_model=device_model, serial=serial),
            BenyWifiPowerSensor(coordinator, "ev_power", icon="mdi:car-electric", device_model=device_model, serial=serial),
            BenyWifiPowerSensor(coordinator, "house_power", icon="mdi:home-lightning-bolt", device_model=device_model, serial=serial),
        ])

    async_add_entities(sensors)

class BenyWifiSensor(CoordinatorEntity, SensorEntity):
    """Charger sensor model."""
    _attr_has_entity_name = True

    def __init__(self, coordinator, key, device_model=None, serial=None, icon=None):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.key = key
        self._attr_translation_key = key
        self._device_model = device_model
        self._serial = serial
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{serial}_{key}"
        self._icon = icon
        self._last_valid_state = None
        self._attr_suggested_object_id = key

    @property
    def native_value(self):
        """Return the current state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.key)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers = {(DOMAIN, self._serial)},
            name = get_device_id(self.hass, self._serial, self._device_model),
            manufacturer = "ZJ Beny",
            model = self._device_model,
            serial_number=self._serial
        )

    @property
    def icon(self):
        """Return corresponding icon."""
        return self._icon

class BenyWifiChargerStateSensor(BenyWifiSensor):
    """Charger state sensor class."""

    def __init__(self, coordinator, key, device_model=None, serial=None, icon="mdi:ev-station"):
        """Initialize sensor."""
        super().__init__(coordinator, key, serial=serial, device_model=device_model, icon=icon)

class BenyWifiCurrentSensor(BenyWifiSensor):
    """Current sensor class."""
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    def __init__(self, coordinator, key, device_model=None, serial=None, icon="mdi:sine-wave"):
        """Initialize sensor."""
        super().__init__(coordinator, key, serial=serial, device_model=device_model, icon=icon)

class BenyWifiVoltageSensor(BenyWifiSensor):
    """Voltage sensor class."""
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    def __init__(self, coordinator, key, device_model=None, serial=None, icon="mdi:flash-triangle"):
        """Initialize sensor."""
        super().__init__(coordinator, key, serial=serial, device_model=device_model, icon=icon)

class BenyWifiPowerSensor(BenyWifiSensor):
    """Power sensor class."""
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT

    def __init__(self, coordinator, key, device_model=None, serial=None, icon="mdi:ev-plug-type2"):
        """Initialize sensor."""
        super().__init__(coordinator, key, serial=serial, device_model=device_model, icon=icon)
            
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


class BenyWifiTemperatureSensor(BenyWifiSensor):
    """Temperature sensor class."""
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, key, device_model=None, serial=None, icon="mdi:thermometer"):
        """Initialize sensor."""
        super().__init__(coordinator, key, serial=serial, device_model=device_model, icon=icon)

class BenyWifiEnergySensor(BenyWifiSensor):
    """Energy sensor class."""
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator, key, device_model=None, serial=None, icon="mdi:power-plug-battery"):
        """Initialize sensor."""
        super().__init__(coordinator, key, serial=serial, device_model=device_model, icon=icon)

class BenyWifiTimerSensor(BenyWifiSensor):
    """Timer sensor class."""

    def __init__(self, coordinator, key, device_model=None, serial=None, icon="mdi:timer-sand-empty"):
        """Initialize sensor."""
        super().__init__(coordinator, key, serial=serial, device_model=device_model, icon=icon)
