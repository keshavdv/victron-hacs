"""Button platform for victron_ble."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .profiles.inverter.button import async_setup_entry as async_setup_inverter_button_entry


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up button entities."""
    await async_setup_inverter_button_entry(hass, entry, async_add_entities)
    # await async_setup_charger_button_entry(hass, entry, async_add_entities)
    # await async_setup_mppt_button_entry(hass, entry, async_add_entities)
