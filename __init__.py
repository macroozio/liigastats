"""
Custom Home Assistant integration for Finnish Liiga hockey statistics.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta, datetime
import json
import aiohttp

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

DOMAIN = "liigastats"
SCAN_INTERVAL = timedelta(hours=1)  # Update hourly - Liiga stats don't change that often

# Configuration schema for configuration.yaml
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required("url"): cv.string,
                vol.Optional("categories", default=["points", "goals", "assists"]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional("top_n", default=5): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["sensor"]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Liiga Stats component."""
    if DOMAIN not in config:
        return True

    hass.data[DOMAIN] = {}
    
    url = config[DOMAIN]["url"]
    categories = config[DOMAIN]["categories"]
    top_n = config[DOMAIN]["top_n"]
    
    coordinator = LiigaStatsDataUpdateCoordinator(
        hass, url=url, categories=categories, top_n=top_n
    )
    
    await coordinator.async_refresh()
    
    hass.data[DOMAIN]["coordinator"] = coordinator
    
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.helpers.discovery.async_load_platform(
                platform, DOMAIN, {}, config
            )
        )
    
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Liiga Stats from a config entry."""
    url = entry.data["url"]
    categories = entry.data.get("categories", ["points", "goals", "assists"])
    top_n = entry.data.get("top_n", 5)
    
    coordinator = LiigaStatsDataUpdateCoordinator(
        hass, url=url, categories=categories, top_n=top_n
    )
    
    await coordinator.async_refresh()
    
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

class LiigaStatsDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Finnish Hockey data from Liiga.fi API."""

    def __init__(
        self, hass: HomeAssistant, url: str, categories: list[str], top_n: int
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.url = url
        self.categories = categories
        self.top_n = top_n
        self.session = async_get_clientsession(hass)
        self.last_update_success_time = None

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            data = await self._fetch_data()
            if data:
                # On successful data fetch, update the timestamp
                self.last_update_success_time = datetime.now()
            return data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Liiga API: {err}")

    async def _fetch_data(self):
        """Fetch the actual data from Liiga.fi API."""
        try:
            async with self.session.get(self.url) as resp:
                if resp.status != 200:
                    _LOGGER.error("Liiga API returned status %s", resp.status)
                    return {}
                
                data = await resp.json()
                
                # Debug log to see the actual structure
                _LOGGER.debug("API Response structure: %s", type(data))
                if isinstance(data, dict):
                    _LOGGER.debug("API Response keys: %s", data.keys())
                
                return self._process_data(data)
        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching data from Liiga API: %s", err)
            return {}

    def _process_data(self, data):
        """Process the fetched data into leaderboards based on the new Liiga.fi API structure."""
        result = {}
        
        # Map of our category names to API field names
        category_mapping = {
            "points": "points",
            "goals": "goals",
            "assists": "assists",
            "plusminus": "plusMinus",
            "penalties": "penaltyMinutes",
            "games": "games",
            "toi": "timeOnIce",
            "toiavg": "timeOnIceAvg",
            "shots": "shots",
            "shotpct": "shotPercentage",
            "faceoffs": "contestWonPercentage",
            "xg": "expectedGoals",
            "xge": "xge",
            "ppg": "powerplayGoals",
            "shg": "penaltykillGoals",
            "gwg": "winningGoals"
        }
        
        # Handle different API response structures
        players = []
        
        # Check if data contains a list of players directly or is nested
        if isinstance(data, list):
            players = data
        elif isinstance(data, dict) and "playerStats" in data:
            players = data.get("playerStats", [])
        elif isinstance(data, dict) and "players" in data:
            players = data.get("players", [])
        
        if not players:
            _LOGGER.warning("No player data found in API response or unrecognized format")
            _LOGGER.debug("API Response type: %s", type(data))
            return result
        
        # Create leaderboards for each category
        for category in self.categories:
            if category in category_mapping:
                api_field = category_mapping[category]
                
                # Filter out players who don't have the required field or are goalkeepers if relevant
                valid_players = [p for p in players if self._has_valid_field(p, api_field)]
                
                # For field player stats, filter out goalkeepers
                if category not in ["toi", "toiavg", "games"]:
                    valid_players = [p for p in valid_players if p.get("goalkeeper", True) is False]
                
                # Sort players by the category
                sorted_players = sorted(
                    valid_players, 
                    key=lambda x: self._safe_get_value(x, api_field),
                    reverse=True
                )
                
                # Take top N players
                top_players = []
                for i, player in enumerate(sorted_players[:self.top_n], 1):
                    full_name = f"{player.get('firstName', '')} {player.get('lastName', '')}"
                    team = player.get('teamName', player.get('teamShortName', 'Unknown'))
                    
                    top_players.append({
                        "rank": i,
                        "name": full_name.strip(),
                        "team": team,
                        "value": self._safe_get_value(player, api_field),
                        "games": player.get('games', 0),
                        "position": player.get('role', ''),
                        "number": player.get('jersey', ''),
                        "player_id": player.get('playerId', ''),
                        "image_url": player.get('pictureUrl', '')
                    })
                
                # Store in result
                result[category] = top_players
        
        return result
    
    def _has_valid_field(self, player, field):
        """Check if player has the field and it can be converted to a number."""
        if field not in player:
            return False
            
        value = player.get(field)
        if value is None:
            return False
            
        # Try to convert to float
        try:
            if isinstance(value, str):
                float(value.replace(',', '.').replace('%', ''))
            else:
                float(value)
            return True
        except (ValueError, TypeError):
            return False
    
    def _safe_get_value(self, player, field):
        """Safely get a numeric value from player data, with appropriate type conversion."""
        value = player.get(field, 0)
        
        # Handle percentage values or string representations
        if isinstance(value, str):
            try:
                return float(value.replace(',', '.').replace('%', ''))
            except (ValueError, TypeError):
                return 0
        
        return float(value) if value is not None else 0
