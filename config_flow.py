"""Config flow for Liiga Player Statistics integration."""
import logging
from typing import Any, Dict, Optional

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN, _compute_api_url

_LOGGER = logging.getLogger(__name__)

DEFAULT_CATEGORIES = "points,goals,assists,plusminus,powerplaygoals"

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional("categories", default=DEFAULT_CATEGORIES): str,
        vol.Optional("top_n", default=5): int,
    }
)


async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input and verify API connectivity."""
    session = async_get_clientsession(hass)
    url = _compute_api_url()

    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise CannotConnect(f"Invalid response from API: {resp.status}")
            await resp.json()
    except (aiohttp.ClientError, aiohttp.ContentTypeError) as err:
        raise CannotConnect(f"Error connecting: {err}")
    except Exception:
        raise InvalidData("Invalid JSON data returned from API")

    return {"title": "Liiga Player Stats"}


class LiigaStatsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Liiga Player Statistics."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                categories = [c.strip() for c in user_input["categories"].split(",")]
                user_input["categories"] = categories
                return self.async_create_entry(title=info["title"], data=user_input)

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidData:
                errors["base"] = "invalid_data"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidData(HomeAssistantError):
    """Error to indicate invalid data was received."""
