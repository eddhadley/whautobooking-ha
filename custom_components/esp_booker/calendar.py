"""Calendar platform for ESP Booker — shows bookings on the HA calendar."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ESPBookerCoordinator

logger = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ESP Booker calendar entity."""
    coordinator: ESPBookerCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([ESPBookerCalendar(coordinator, entry)])


class ESPBookerCalendar(CoordinatorEntity, CalendarEntity):
    """Calendar entity that displays all planned/booked slots."""

    _attr_has_entity_name = True
    _attr_name = "Court Bookings"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: ESPBookerCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_calendar"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event (used for the entity state)."""
        events = self._build_events()
        now = dt_util.now()
        future = [e for e in events if e.end > now]
        return future[0] if future else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return events within a date range (used by the calendar card)."""
        events = self._build_events()
        return [e for e in events if e.end >= start_date and e.start <= end_date]

    def _build_events(self) -> list[CalendarEvent]:
        """Convert bookings to CalendarEvent objects."""
        events: list[CalendarEvent] = []
        for b in self.coordinator.data or []:
            ev = _booking_to_event(b)
            if ev:
                events.append(ev)
        events.sort(key=lambda e: e.start)
        return events


def _booking_to_event(booking: dict[str, Any]) -> CalendarEvent | None:
    """Convert a booking dict to a CalendarEvent."""
    date_str = booking.get("date", "")
    time_str = booking.get("time", "")
    if not date_str or not time_str:
        return None

    try:
        # date_str is dd/MM/yy
        start_naive = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%y %H:%M")
        start = start_naive.replace(tzinfo=dt_util.get_default_time_zone())
    except ValueError:
        return None

    duration = int(booking.get("duration_mins", 60))
    end = start + timedelta(minutes=duration)
    status = booking.get("status", "pending")
    location = booking.get("location_desc", booking.get("location", "?"))
    activity = booking.get("activity_desc", booking.get("activity", "?"))

    status_emoji = {"pending": "\u23f3", "booked": "\u2705", "failed": "\u274c"}.get(
        status, "\u2753"
    )

    return CalendarEvent(
        summary=f"{status_emoji} {activity} – {location}",
        description=f"Status: {status}\nCourt: {location}\nPeople: {booking.get('num_people', 1)}",
        start=start,
        end=end,
    )
