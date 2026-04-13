"""Local JSON storage for planned bookings, replacing Azure Table Storage."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    STATUS_PENDING,
    STATUS_BOOKED,
    STATUS_FAILED,
    DEFAULT_ADVANCE_DAYS,
)

logger = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}_bookings"
STORAGE_VERSION = 1


class BookingStore:
    """Manage planned bookings in HA's local JSON storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = {"bookings": []}

    async def async_load(self) -> None:
        """Load bookings from disk."""
        stored = await self._store.async_load()
        if stored and "bookings" in stored:
            self._data = stored
        else:
            self._data = {"bookings": []}

    async def _async_save(self) -> None:
        """Persist bookings to disk."""
        await self._store.async_save(self._data)

    @property
    def bookings(self) -> list[dict[str, Any]]:
        return self._data["bookings"]

    async def async_add_booking(self, booking: dict[str, Any]) -> dict[str, Any]:
        """Add a new planned booking. Returns the booking with generated id."""
        booking.setdefault("id", uuid.uuid4().hex[:12])
        booking.setdefault("status", STATUS_PENDING)
        booking.setdefault("error_message", "")
        booking.setdefault("created_at", datetime.utcnow().isoformat())
        self._data["bookings"].append(booking)
        await self._async_save()
        logger.info("Added booking: %s @ %s on %s", booking.get("activity"), booking.get("time"), booking.get("date"))
        return booking

    async def async_remove_booking(self, booking_id: str) -> bool:
        """Remove a booking by id. Returns True if found and removed."""
        original_len = len(self._data["bookings"])
        self._data["bookings"] = [
            b for b in self._data["bookings"] if b.get("id") != booking_id
        ]
        if len(self._data["bookings"]) < original_len:
            await self._async_save()
            logger.info("Removed booking %s", booking_id)
            return True
        return False

    async def async_mark_booked(self, booking_id: str) -> None:
        """Mark a booking as successfully booked."""
        for b in self._data["bookings"]:
            if b.get("id") == booking_id:
                b["status"] = STATUS_BOOKED
                b["error_message"] = ""
                b["booked_at"] = datetime.utcnow().isoformat()
                break
        await self._async_save()
        logger.info("Marked booking %s as booked", booking_id)

    async def async_mark_failed(self, booking_id: str, error: str) -> None:
        """Mark a booking as failed."""
        for b in self._data["bookings"]:
            if b.get("id") == booking_id:
                b["status"] = STATUS_FAILED
                b["error_message"] = error[:1000]
                break
        await self._async_save()
        logger.warning("Marked booking %s as failed: %s", booking_id, error)

    async def async_reset_to_pending(self, booking_id: str) -> None:
        """Reset a failed booking back to pending for retry."""
        for b in self._data["bookings"]:
            if b.get("id") == booking_id:
                b["status"] = STATUS_PENDING
                b["error_message"] = ""
                break
        await self._async_save()
        logger.info("Reset booking %s to pending", booking_id)

    def get_pending_for_date(self, date_str: str) -> list[dict[str, Any]]:
        """Return all pending bookings for a given date (dd/MM/yy)."""
        return [
            b
            for b in self._data["bookings"]
            if b.get("date") == date_str and b.get("status") == STATUS_PENDING
        ]

    def get_all(self) -> list[dict[str, Any]]:
        """Return all bookings."""
        return list(self._data["bookings"])

    def get_by_id(self, booking_id: str) -> dict[str, Any] | None:
        """Return a single booking by id."""
        for b in self._data["bookings"]:
            if b.get("id") == booking_id:
                return b
        return None

    @staticmethod
    def target_date(advance_days: int = DEFAULT_ADVANCE_DAYS) -> str:
        """Return the booking date N days from now in dd/MM/yy format."""
        target = datetime.utcnow() + timedelta(days=advance_days)
        return target.strftime("%d/%m/%y")
