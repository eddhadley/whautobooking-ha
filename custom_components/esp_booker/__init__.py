"""ESP Booker – Home Assistant custom integration.

Automatically books padel courts (or other activities) at West Hants Club
via ESP Elite Live, N days in advance.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.event import async_track_time_change

from .const import (
    DOMAIN,
    CONF_BOOK_HOUR,
    CONF_BOOK_MINUTE,
    CONF_ADVANCE_DAYS,
    DEFAULT_BOOK_HOUR,
    DEFAULT_BOOK_MINUTE,
    DEFAULT_ADVANCE_DAYS,
    DEFAULT_CATEGORY,
    DEFAULT_GROUP,
    DEFAULT_GROUP_DESC,
    DEFAULT_ACTIVITY,
    DEFAULT_ACTIVITY_DESC,
    DEFAULT_ACTIVITY_TYPE,
    DEFAULT_LOCATION_TYPE,
    DEFAULT_EXPORT_ID,
    DEFAULT_DURATION_MINS,
    DEFAULT_NUM_PEOPLE,
    STATUS_PENDING,
)
from .coordinator import ESPBookerCoordinator
from .store import BookingStore

logger = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ESP Booker from a config entry."""
    store = BookingStore(hass)
    await store.async_load()

    coordinator = ESPBookerCoordinator(hass, entry, store)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "store": store,
    }

    # ── Schedule daily auto-booking ──────────────────────────────────
    book_hour = entry.data.get(CONF_BOOK_HOUR, DEFAULT_BOOK_HOUR)
    book_minute = entry.data.get(CONF_BOOK_MINUTE, DEFAULT_BOOK_MINUTE)
    advance_days = entry.data.get(CONF_ADVANCE_DAYS, DEFAULT_ADVANCE_DAYS)

    async def _daily_auto_book(_now) -> None:
        """Triggered at the configured time each day."""
        target_date = BookingStore.target_date(advance_days)
        logger.info("Daily auto-booker triggered for %s", target_date)
        await coordinator.async_run_bookings_for_date(target_date)

    unsub = async_track_time_change(
        hass, _daily_auto_book, hour=book_hour, minute=book_minute, second=0
    )
    hass.data[DOMAIN][entry.entry_id]["unsub_timer"] = unsub

    # ── Register services ────────────────────────────────────────────
    _register_services(hass)

    # ── Register Lovelace card resource ──────────────────────────────
    await _register_frontend_card(hass)

    # ── Forward to platforms ─────────────────────────────────────────
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data[DOMAIN].pop(entry.entry_id, {})
    unsub = data.get("unsub_timer")
    if unsub:
        unsub()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _register_services(hass: HomeAssistant) -> None:
    """Register integration services (idempotent)."""

    if hass.services.has_service(DOMAIN, "add_booking"):
        return  # Already registered

    async def _handle_add_booking(call: ServiceCall) -> None:
        """Handle esp_booker.add_booking service call."""
        # Use the first configured entry
        entry_id = next(iter(hass.data[DOMAIN]))
        store: BookingStore = hass.data[DOMAIN][entry_id]["store"]
        coordinator: ESPBookerCoordinator = hass.data[DOMAIN][entry_id]["coordinator"]

        booking = {
            "date": call.data["date"],
            "time": call.data["time"],
            "location": call.data.get("court", "PADEL02"),
            "location_desc": f"Padel {call.data.get('court', 'PADEL02')[-2:]}",
            "location_type": call.data.get("location_type", DEFAULT_LOCATION_TYPE),
            "category": call.data.get("category", DEFAULT_CATEGORY),
            "group": call.data.get("group", DEFAULT_GROUP),
            "group_desc": call.data.get("group_desc", DEFAULT_GROUP_DESC),
            "activity": call.data.get("activity", DEFAULT_ACTIVITY),
            "activity_desc": call.data.get("activity_desc", DEFAULT_ACTIVITY_DESC),
            "activity_type": call.data.get("activity_type", DEFAULT_ACTIVITY_TYPE),
            "export_id": call.data.get("export_id", DEFAULT_EXPORT_ID),
            "duration_mins": call.data.get("duration_mins", DEFAULT_DURATION_MINS),
            "num_people": call.data.get("num_people", DEFAULT_NUM_PEOPLE),
            "status": STATUS_PENDING,
        }
        await store.async_add_booking(booking)
        await coordinator.async_request_refresh()

    async def _handle_remove_booking(call: ServiceCall) -> None:
        """Handle esp_booker.remove_booking service call."""
        entry_id = next(iter(hass.data[DOMAIN]))
        store: BookingStore = hass.data[DOMAIN][entry_id]["store"]
        coordinator: ESPBookerCoordinator = hass.data[DOMAIN][entry_id]["coordinator"]

        await store.async_remove_booking(call.data["booking_id"])
        await coordinator.async_request_refresh()

    async def _handle_retry_booking(call: ServiceCall) -> None:
        """Handle esp_booker.retry_booking service call."""
        entry_id = next(iter(hass.data[DOMAIN]))
        store: BookingStore = hass.data[DOMAIN][entry_id]["store"]
        coordinator: ESPBookerCoordinator = hass.data[DOMAIN][entry_id]["coordinator"]

        await store.async_reset_to_pending(call.data["booking_id"])
        await coordinator.async_request_refresh()

    async def _handle_book_now(call: ServiceCall) -> None:
        """Handle esp_booker.book_now — trigger booking run immediately."""
        entry_id = next(iter(hass.data[DOMAIN]))
        coordinator: ESPBookerCoordinator = hass.data[DOMAIN][entry_id]["coordinator"]

        target_date = call.data.get(
            "date",
            BookingStore.target_date(
                hass.data[DOMAIN][entry_id]["coordinator"].advance_days
            ),
        )
        await coordinator.async_run_bookings_for_date(target_date)

    hass.services.async_register(DOMAIN, "add_booking", _handle_add_booking)
    hass.services.async_register(DOMAIN, "remove_booking", _handle_remove_booking)
    hass.services.async_register(DOMAIN, "retry_booking", _handle_retry_booking)
    hass.services.async_register(DOMAIN, "book_now", _handle_book_now)


async def _register_frontend_card(hass: HomeAssistant) -> None:
    """Serve the Lovelace card JS directly from the integration."""
    from homeassistant.components.http import StaticPathConfig

    url = "/esp_booker/esp-booker-card.js"
    path = str(Path(__file__).parent / "www" / "esp-booker-card.js")

    await hass.http.async_register_static_paths(
        [StaticPathConfig(url, path, cache_headers=False)]
    )
    logger.info("ESP Booker card JS registered at %s", url)
