"""Config flow for ESP Booker integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_CLUB_ID,
    CONF_BOOK_HOUR,
    CONF_BOOK_MINUTE,
    CONF_ADVANCE_DAYS,
    DEFAULT_CLUB_ID,
    DEFAULT_BOOK_HOUR,
    DEFAULT_BOOK_MINUTE,
    DEFAULT_ADVANCE_DAYS,
)
from .esp_client import ESPBookingClient, BookingError

logger = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLUB_ID, default=DEFAULT_CLUB_ID): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_BOOK_HOUR, default=DEFAULT_BOOK_HOUR): vol.All(
            int, vol.Range(min=0, max=23)
        ),
        vol.Optional(CONF_BOOK_MINUTE, default=DEFAULT_BOOK_MINUTE): vol.All(
            int, vol.Range(min=0, max=59)
        ),
        vol.Optional(CONF_ADVANCE_DAYS, default=DEFAULT_ADVANCE_DAYS): vol.All(
            int, vol.Range(min=1, max=14)
        ),
    }
)


async def _validate_credentials(
    hass, club_id: str, username: str, password: str
) -> dict[str, str]:
    """Validate ESP credentials by attempting a login."""
    client = ESPBookingClient(club_id, username, password)
    try:
        await hass.async_add_executor_job(client.login)
    except BookingError:
        return {"base": "invalid_auth"}
    except Exception:  # noqa: BLE001
        return {"base": "cannot_connect"}
    return {}


class ESPBookerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ESP Booker."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return ESPBookerOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — collect credentials and schedule config."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await _validate_credentials(
                self.hass,
                user_input[CONF_CLUB_ID],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if not errors:
                await self.async_set_unique_id(
                    f"{user_input[CONF_CLUB_ID]}_{user_input[CONF_USERNAME]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"ESP Booker ({user_input[CONF_USERNAME]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class ESPBookerOptionsFlow(OptionsFlow):
    """Handle options for ESP Booker."""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage schedule options."""
        if user_input is not None:
            # Update the config entry data with new schedule values
            new_data = {**self._config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data
            )
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        current = self._config_entry.data
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_BOOK_HOUR,
                    default=current.get(CONF_BOOK_HOUR, DEFAULT_BOOK_HOUR),
                ): vol.All(int, vol.Range(min=0, max=23)),
                vol.Optional(
                    CONF_BOOK_MINUTE,
                    default=current.get(CONF_BOOK_MINUTE, DEFAULT_BOOK_MINUTE),
                ): vol.All(int, vol.Range(min=0, max=59)),
                vol.Optional(
                    CONF_ADVANCE_DAYS,
                    default=current.get(CONF_ADVANCE_DAYS, DEFAULT_ADVANCE_DAYS),
                ): vol.All(int, vol.Range(min=1, max=14)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
