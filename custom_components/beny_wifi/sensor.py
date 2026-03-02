"""Sensors for Beny Wifi."""

import logging

from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.helpers.entity import DeviceInfo, Entity

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
        self._last_valid_state = None

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

    @property
    def state(self):
        """Return the current state of the sensor with spike filtering."""
        raw_value = self.coordinator.data.get(self.key)
        
        # List of common communication error values
        INVALID_VALUES = [65535, 65534, 999999, -1]
        
        try:
            power = float(raw_value)
            
            # Check for communication error values
            if power in INVALID_VALUES:
                _LOGGER.warning(
                    f"Beny {self._device_id} {self.key}: Communication error value detected: {power}, "
                    f"using last valid value: {self._last_valid_state}"
                )
                return self._last_valid_state if self._last_valid_state is not None else 0
            
            # Define reasonable bounds based on sensor type
            if self.key == "solar_power":
                # Solar power should be 0 to max system capacity (adjust 20 to your system max + buffer)
                min_valid = 0
                max_valid = 30.0  # Adjust this to your solar system capacity + 20% buffer
                
                if not (min_valid <= power <= max_valid):
                    _LOGGER.warning(
                        f"Beny {self._device_id} {self.key}: Spike detected: {power} kW "
                        f"(valid range: {min_valid}-{max_valid} kW), "
                        f"using last valid value: {self._last_valid_state}"
                    )
                    return self._last_valid_state if self._last_valid_state is not None else 0
                    
            elif self.key == "grid_power":
                # Grid power can be negative (export) or positive (import)
                # Adjust these limits based on your grid connection capacity
                min_valid = -30.0  # Max export
                max_valid = 30.0   # Max import
                
                if not (min_valid <= power <= max_valid):
                    _LOGGER.warning(
                        f"Beny {self._device_id} {self.key}: Spike detected: {power} kW "
                        f"(valid range: {min_valid}-{max_valid} kW), "
                        f"using last valid value: {self._last_valid_state}"
                    )
                    return self._last_valid_state if self._last_valid_state is not None else 0
                    
            elif self.key in ["ev_power", "power"]:
                # EV power should be 0 to max charger capacity
                min_valid = 0
                max_valid = 25.0  # Typical max for home EV chargers (adjust if needed)
                
                if not (min_valid <= power <= max_valid):
                    _LOGGER.warning(
                        f"Beny {self._device_id} {self.key}: Spike detected: {power} kW "
                        f"(valid range: {min_valid}-{max_valid} kW), "
                        f"using last valid value: {self._last_valid_state}"
                    )
                    return self._last_valid_state if self._last_valid_state is not None else 0
                    
            elif self.key == "house_power":
                # House power - adjust based on your main breaker capacity
                min_valid = 0
                max_valid = 50.0  # Typical house load (adjust to your needs)
                
                if not (min_valid <= power <= max_valid):
                    _LOGGER.warning(
                        f"Beny {self._device_id} {self.key}: Spike detected: {power} kW "
                        f"(valid range: {min_valid}-{max_valid} kW), "
                        f"using last valid value: {self._last_valid_state}"
                    )
                    return self._last_valid_state if self._last_valid_state is not None else 0
            
            # Value is valid, store it and return it
            self._last_valid_state = power
            return power
            
        except (ValueError, TypeError) as e:
            _LOGGER.error(
                f"Beny {self._device_id} {self.key}: Invalid value received: {raw_value}, error: {e}, "
                f"using last valid value: {self._last_valid_state}"
            )
            return self._last_valid_state if self._last_valid_state is not None else 0

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