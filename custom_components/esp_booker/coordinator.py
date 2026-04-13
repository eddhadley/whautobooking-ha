"""Data coordinator for ESP Booker — schedules the daily auto-booking run."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    CONF_CLUB_ID,
    CONF_ADVANCE_DAYS,
    DEFAULT_ADVANCE_DAYS,
)
from .esp_client import ESPBookingClient, BookingError
from .store import BookingStore

logger = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=30)


class ESPBookerCoordinator(DataUpdateCoordinator):
    """Coordinator that refreshes booking state for sensor entities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, store: BookingStore) -> None:
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.entry = entry
        self.store = store

    @property
    def club_id(self) -> str:
        return self.entry.data[CONF_CLUB_ID]

    @property
    def username(self) -> str:
        return self.entry.data[CONF_USERNAME]

    @property
    def password(self) -> str:
        return self.entry.data[CONF_PASSWORD]

    @property
    def advance_days(self) -> int:
        return self.entry.data.get(CONF_ADVANCE_DAYS, DEFAULT_ADVANCE_DAYS)

    async def _async_update_data(self) -> list[dict]:
        """Return current bookings list (sensors read from this)."""
        return self.store.get_all()

    async def async_run_bookings_for_date(self, target_date: str) -> dict:
        """Execute the booking flow for all pending bookings on target_date.

        Returns a summary dict: {"attempted": N, "booked": N, "failed": N}.
        """
        pending = self.store.get_pending_for_date(target_date)
        if not pending:
            logger.info("No pending bookings for %s", target_date)
            return {"attempted": 0, "booked": 0, "failed": 0}

        logger.info("Found %d pending booking(s) for %s", len(pending), target_date)
        booked = 0
        failed = 0

        for b in pending:
            bid = b["id"]
            desc = f"{b.get('activity_desc', '?')} on {b.get('location', '?')} @ {b.get('time', '?')} on {target_date}"
            logger.info("Attempting: %s", desc)

            client = ESPBookingClient(self.club_id, self.username, self.password)
            try:
                success = await self.hass.async_add_executor_job(
                    client.book,
                    b.get("category", "Padel"),
                    b.get("group", "V_Padel"),
                    b.get("group_desc", "Book Padel Courts"),
                    b.get("activity", "PADEL60"),
                    b.get("activity_desc", "Padel 60 Mins"),
                    b.get("activity_type", "A"),
                    b.get("location", "PADEL02"),
                    b.get("location_type", "Padel"),
                    b.get("location_desc", "Padel 02"),
                    b.get("export_id", "000093"),
                    target_date,
                    b.get("time", "09:00"),
                    int(b.get("duration_mins", 60)),
                    int(b.get("num_people", 1)),
                )
                if success:
                    await self.store.async_mark_booked(bid)
                    logger.info("SUCCESS: %s", desc)
                    booked += 1
                else:
                    await self.store.async_mark_failed(bid, "Uncertain result")
                    logger.warning("UNCERTAIN: %s", desc)
                    failed += 1
            except BookingError as e:
                await self.store.async_mark_failed(bid, str(e))
                logger.error("FAILED (BookingError): %s – %s", desc, e)
                failed += 1
            except Exception as e:  # noqa: BLE001
                await self.store.async_mark_failed(bid, str(e))
                logger.error("FAILED (unexpected): %s – %s", desc, e)
                failed += 1

        # Refresh sensor data after booking run
        await self.async_request_refresh()

        summary = {"attempted": len(pending), "booked": booked, "failed": failed}
        logger.info("Booking run complete: %s", summary)
        return summary
