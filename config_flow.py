"""Config flow for Liiga Statistics integration."""
import logging
from typing import Any, Dict, Optional

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN, DEFAULT_PLAYERS_URL, DEFAULT_GOALIES_URL

_LOGGER = logging.getLogger(__name__)

DEFAULT_CATEGORIES = "points,goals,assists,plusminus,shots,shotpct"
DEFAULT_GOALIE_CATEGORIES = "wins,savepct,gaa,shutouts"

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("url", default=DEFAULT_PLAYERS_URL): str,
        vol.Required("goalie_url", default=DEFAULT_GOALIES_URL): str,
        vol.Optional("categories", default=DEFAULT_CATEGORIES): str,
        vol.Optional("goalie_categories", default=DEFAULT_GOALIE_CATEGORIES): str,
        vol.Optional("top_n", default=10): int,
    }
)

async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    
    # Check player stats API
    try:
        async with session.get(data["url"]) as resp:
            if resp.status != 200:
                raise CannotConnect(f"Invalid response from player API: {resp.status}")
            
            # Try to parse JSON
            await resp.json()
            
    except aiohttp.ClientError as err:
        raise CannotConnect(f"Error connecting to player API: {err}")
    except ValueError:
        raise InvalidData("Invalid JSON data returned from player API")
    
    # Check goalie stats API
    try:
        async with session.get(data["goalie_url"]) as resp:
            if resp.status != 200:
                raise CannotConnect(f"Invalid response from goalie API: {resp.status}")
            
            # Try to parse JSON
            await resp.json()
            
    except aiohttp.ClientError as err:
        raise CannotConnect(f"Error connecting to goalie API: {err}")
    except ValueError:
        raise InvalidData("Invalid JSON data returned from goalie API")
    
    # Return info to be stored in the config entry
    return {"title": "Liiga Stats"}

class LiigaStatsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Liiga Statistics."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                
                # Process categories from comma-separated string to list
                categories = [c.strip() for c in user_input["categories"].split(",")]
                user_input["categories"] = categories
                
                # Process goalie categories from comma-separated string to list
                goalie_categories = [c.strip() for c in user_input["goalie_categories"].split(",")]
                user_input["goalie_categories"] = goalie_categories
                
                return self.async_create_entry(title=info["title"], data=user_input)
            
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidData:
                errors["base"] = "invalid_data"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidData(HomeAssistantError):
    """Error to indicate invalid data was received."""
