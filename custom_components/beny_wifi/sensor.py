"""Sensors for Beny Wifi."""

from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import (
    DLB_CHARGERS,
    DOMAIN,
    MODEL,
    SERIAL,
    SINGLE_PHASE_CHARGERS,
    THREE_PHASE_CHARGERS,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    device_id = config_entry.data[SERIAL]
    device_model = config_entry.data[MODEL]

    sensors = []

    # by default only all 1-phase sensors are included
    if device_model in SINGLE_PHASE_CHARGERS:
        sensors = [
            BenyWifiChargerStateSensor(coordinator, "charger_state", device_id=device_id, device_model=device_model),
            BenyWifiPowerSensor(coordinator, "power", device_id=device_id, device_model=device_model),
            BenyWifiVoltageSensor(coordinator, "voltage1", device_id=device_id, device_model=device_model),
            BenyWifiCurrentSensor(coordinator, "current1", device_id=device_id, device_model=device_model),
            BenyWifiCurrentSensor(coordinator, "max_current", device_id=device_id, device_model=device_model),
            BenyWifiEnergySensor(coordinator, "total_kwh", device_id=device_id, device_model=device_model),
            BenyWifiEnergySensor(coordinator, "maximum_session_consumption", icon="mdi:meter-electric", device_id=device_id, device_model=device_model),
            BenyWifiTimerSensor(coordinator, "timer_start", icon="mdi:timer-sand-full", device_id=device_id, device_model=device_model),
            BenyWifiTimerSensor(coordinator, "timer_end", icon="mdi:timer-sand-empty", device_id=device_id, device_model=device_model)
        ]

    # add all three phases if model supports them
    elif device_model in THREE_PHASE_CHARGERS:
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
            BenyWifiEnergySensor(coordinator, "maximum_session_consumption", icon="mdi:meter-electric", device_id=device_id, device_model=device_model),
            BenyWifiTimerSensor(coordinator, "timer_start", icon="mdi:timer-sand-full", device_id=device_id, device_model=device_model),
            BenyWifiTimerSensor(coordinator, "timer_end", icon="mdi:timer-sand-empty", device_id=device_id, device_model=device_model)
        ]

    # TODO: DLB
    if device_model in DLB_CHARGERS:
        # sensors.insert([])
        pass

    async_add_entities(sensors)

class BenyWifiSensor(Entity):
    """Charger sensor model."""

    def __init__(self, coordinator, key, device_id=None, device_model=None, icon=None):
        """Initialize the sensor."""
        self.coordinator = coordinator
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
        return self.coordinator.data.get(self.key)

    async def async_update(self):
        """Update the sensor."""
        await self.coordinator.async_request_refresh()

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
