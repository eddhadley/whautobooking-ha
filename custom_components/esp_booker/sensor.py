"""Sensor platform for ESP Booker — exposes each booking as a sensor entity."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATUS_PENDING, STATUS_BOOKED, STATUS_FAILED
from .coordinator import ESPBookerCoordinator

logger = logging.getLogger(__name__)

STATUS_ICONS = {
    STATUS_PENDING: "mdi:clock-outline",
    STATUS_BOOKED: "mdi:check-circle",
    STATUS_FAILED: "mdi:alert-circle",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ESP Booker sensors from a config entry."""
    coordinator: ESPBookerCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Summary sensor (always present)
    async_add_entities([ESPBookerSummarySensor(coordinator, entry)])

    # One sensor per booking — dynamically managed
    known_ids: set[str] = set()

    @callback
    def _async_add_new_bookings() -> None:
        """Add sensor entities for any new bookings."""
        new_entities = []
        for booking in coordinator.data or []:
            bid = booking.get("id", "")
            if bid and bid not in known_ids:
                known_ids.add(bid)
                new_entities.append(ESPBookingSensor(coordinator, entry, booking))
        if new_entities:
            async_add_entities(new_entities)

    # Initial population
    _async_add_new_bookings()

    # Re-check on every coordinator update
    coordinator.async_add_listener(_async_add_new_bookings)


class ESPBookerSummarySensor(CoordinatorEntity, SensorEntity):
    """Summary sensor showing total / pending / booked / failed counts."""

    _attr_has_entity_name = True
    _attr_name = "Bookings Summary"
    _attr_icon = "mdi:tennis"

    def __init__(self, coordinator: ESPBookerCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_summary"

    @property
    def native_value(self) -> str:
        bookings = self.coordinator.data or []
        pending = sum(1 for b in bookings if b.get("status") == STATUS_PENDING)
        booked = sum(1 for b in bookings if b.get("status") == STATUS_BOOKED)
        failed = sum(1 for b in bookings if b.get("status") == STATUS_FAILED)
        return f"{pending} pending, {booked} booked, {failed} failed"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        bookings = self.coordinator.data or []
        return {
            "total": len(bookings),
            "pending": sum(1 for b in bookings if b.get("status") == STATUS_PENDING),
            "booked": sum(1 for b in bookings if b.get("status") == STATUS_BOOKED),
            "failed": sum(1 for b in bookings if b.get("status") == STATUS_FAILED),
        }


class ESPBookingSensor(CoordinatorEntity, SensorEntity):
    """Individual booking sensor — state is the booking status."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ESPBookerCoordinator,
        entry: ConfigEntry,
        booking: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._booking_id = booking.get("id", "")
        self._attr_unique_id = f"{entry.entry_id}_{self._booking_id}"
        loc = booking.get("location", "?")
        time = booking.get("time", "?")
        date = booking.get("date", "?")
        self._attr_name = f"{loc} @ {time} on {date}"

    @property
    def _booking(self) -> dict[str, Any] | None:
        for b in self.coordinator.data or []:
            if b.get("id") == self._booking_id:
                return b
        return None

    @property
    def available(self) -> bool:
        return self._booking is not None

    @property
    def native_value(self) -> str | None:
        b = self._booking
        return b["status"] if b else None

    @property
    def icon(self) -> str:
        b = self._booking
        if b:
            return STATUS_ICONS.get(b.get("status", ""), "mdi:help-circle")
        return "mdi:help-circle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        b = self._booking
        if not b:
            return {}
        return {
            "booking_id": b.get("id"),
            "date": b.get("date"),
            "time": b.get("time"),
            "location": b.get("location"),
            "location_desc": b.get("location_desc"),
            "activity": b.get("activity"),
            "activity_desc": b.get("activity_desc"),
            "category": b.get("category"),
            "duration_mins": b.get("duration_mins"),
            "num_people": b.get("num_people"),
            "error_message": b.get("error_message", ""),
            "created_at": b.get("created_at", ""),
            "booked_at": b.get("booked_at", ""),
        }
