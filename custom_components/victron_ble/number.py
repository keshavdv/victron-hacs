"""Number platform for victron_ble."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .profiles.inverter.number import async_setup_entry as async_setup_inverter_number_entry


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up number entities."""
    await async_setup_inverter_number_entry(hass, entry, async_add_entities)
    # await async_setup_charger_number_entry(hass, entry, async_add_entities)
    # await async_setup_mppt_number_entry(hass, entry, async_add_entities)
