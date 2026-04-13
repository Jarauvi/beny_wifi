"""Binary sensors for Beny Wifi."""
import logging
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MODEL,
    SERIAL,
    SECTION_DEVICE,
    get_device_id,
    get_config_parameter,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up binary_sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    serial = get_config_parameter(config_entry, SECTION_DEVICE, SERIAL)
    device_model = get_config_parameter(config_entry, SECTION_DEVICE, MODEL)

    # Define diagnostic binary sensors
    sensors = [
        BenyWifiBinarySensor(coordinator, "emergency_stop_fault", BinarySensorDeviceClass.SAFETY, serial, device_model),
        BenyWifiBinarySensor(coordinator, "high_temperature_fault", BinarySensorDeviceClass.PROBLEM, serial, device_model),
        BenyWifiBinarySensor(coordinator, "leakage_fault", BinarySensorDeviceClass.SAFETY, serial, device_model),
        BenyWifiBinarySensor(coordinator, "overload_fault", BinarySensorDeviceClass.PROBLEM, serial, device_model),
    ]

    async_add_entities(sensors)

class BenyWifiBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor representing a specific charger fault or state."""

    def __init__(self, coordinator, key, device_class, serial, device_model):
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.key = key
        self._attr_translation_key = key
        self._attr_device_class = device_class
        self._attr_unique_id = f"{serial}_{key}"
        self._serial = serial
        self._device_model = device_model
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if self.coordinator.data is None:
            return False
        return self.coordinator.data.get(self.key, False)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial)},
            name=get_device_id(self.hass, self._serial, self._device_model),
            manufacturer="ZJ Beny",
            model=self._device_model,
            serial_number=self._serial,
        )
