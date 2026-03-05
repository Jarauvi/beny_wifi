"""Select entities for Beny Wifi DLB mode control."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DLB, DOMAIN, DLB_MODE, DLB_MODE_OPTIONS, MODEL, SERIAL

_LOGGER = logging.getLogger(__name__)

# Reverse map: label → DLB_MODE
_LABEL_TO_MODE = DLB_MODE_OPTIONS
# Forward map: DLB_MODE → label
_MODE_TO_LABEL = {v: k for k, v in DLB_MODE_OPTIONS.items()}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up select platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    device_id = config_entry.data[SERIAL]
    device_model = config_entry.data[MODEL]
    dlb = config_entry.data[DLB]

    entities = []

    if dlb:
        entities.append(
            BenyWifiDlbModeSelect(
                coordinator, "dlb_mode",
                device_id=device_id, device_model=device_model,
            )
        )

    if entities:
        async_add_entities(entities)


class BenyWifiDlbModeSelect(CoordinatorEntity, SelectEntity):
    """Select entity to choose the primary DLB operating mode."""

    def __init__(self, coordinator, key, device_id=None, device_model=None):
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.key = key
        self._attr_translation_key = key
        self._device_id = device_id
        self._device_model = device_model
        self._attr_has_entity_name = True
        self._attr_icon = "mdi:solar-power"
        self._attr_options = list(DLB_MODE_OPTIONS.keys())
        self.entity_id = f"select.{device_id}_{key}"

        # Optimistic label — set on user action, cleared on coordinator refresh
        self._optimistic_label: str | None = None

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._device_id}_{self.key}"

    @property
    def current_option(self) -> str:
        """Return the currently selected option.

        Priority:
          1. Optimistic label (set immediately when user makes a selection,
             so the UI snaps to the new value without waiting for a poll).
          2. Coordinator's _dlb_config cache (authoritative after any command).
          3. Safe default.
        """
        if self._optimistic_label is not None:
            return self._optimistic_label

        raw = self.coordinator._dlb_config.get("dlb_mode")
        if raw is not None:
            if raw == DLB_MODE.PURE_PV.value:
                return _MODE_TO_LABEL[DLB_MODE.PURE_PV]
            elif raw == DLB_MODE.FULL_SPEED.value:
                return _MODE_TO_LABEL[DLB_MODE.FULL_SPEED]
            elif raw == DLB_MODE.DLB_BOX.value:
                return _MODE_TO_LABEL[DLB_MODE.DLB_BOX]
            elif 1 <= raw <= 32:
                return _MODE_TO_LABEL[DLB_MODE.HYBRID]

        return _MODE_TO_LABEL[DLB_MODE.DLB_BOX]

    def _handle_coordinator_update(self) -> None:
        """Clear optimistic state when the coordinator delivers fresh data."""
        self._optimistic_label = None
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Handle user selecting a new DLB mode."""
        mode = _LABEL_TO_MODE.get(option)
        if mode is None:
            _LOGGER.error(f"Unknown DLB mode option: {option}")
            return

        device_name = f"Beny Charger {self._device_id}"
        await self.coordinator.async_set_dlb_config(device_name, dlb_mode=mode)

        # Snap the UI immediately — don't wait for next coordinator poll
        self._optimistic_label = option
        self.async_write_ha_state()

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