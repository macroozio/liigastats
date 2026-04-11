"""
Custom Home Assistant integration for Finnish Liiga hockey player statistics.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta, datetime, timezone, date
import aiohttp

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

DOMAIN = "liigastats"
SCAN_INTERVAL = timedelta(hours=1)

PLATFORMS = ["sensor"]


def _compute_api_url() -> str:
    """Compute the Liiga API URL for the current season and tournament phase.

    Season end year:  if month >= September the new season has started and
                      ends next calendar year; otherwise it ends this year.
    Tournament phase: playoffs run roughly mid-March through May;
                      everything else is regular season (runkosarja).
    """
    today = date.today()
    month = today.month

    if month >= 9:
        season_end_year = today.year + 1
    else:
        season_end_year = today.year

    if month in (4, 5) or (month == 3 and today.day >= 15):
        tournament = "playoffs"
    else:
        tournament = "runkosarja"

    return (
        f"https://liiga.fi/api/v2/players/stats/summed/"
        f"{season_end_year}/{season_end_year}/{tournament}/true"
        f"?dataType=basicStats"
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Liiga Player Stats from a config entry."""
    categories = entry.data.get(
        "categories",
        ["points", "goals", "assists", "plusminus", "powerplaygoals"],
    )
    top_n = entry.data.get("top_n", 5)

    coordinator = LiigaPlayerStatsDataUpdateCoordinator(
        hass, categories=categories, top_n=top_n
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class LiigaPlayerStatsDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Finnish Hockey player data from Liiga.fi API."""

    def __init__(
        self, hass: HomeAssistant, categories: list[str], top_n: int
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.categories = categories
        self.top_n = top_n
        self.session = async_get_clientsession(hass)
        self.last_update_success_time = None
        self.current_url = None  # logged for debugging

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            data = await self._fetch_data()
            if data:
                self.last_update_success_time = datetime.now(timezone.utc)
            return data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Liiga API: {err}")

    async def _fetch_data(self):
        """Fetch the actual data from Liiga.fi API."""
        url = _compute_api_url()
        self.current_url = url
        _LOGGER.debug("Fetching Liiga player data from %s", url)

        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    _LOGGER.error("Liiga API returned status %s for %s", resp.status, url)
                    return {}

                data = await resp.json()
                return self._process_data(data)
        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching data from Liiga API: %s", err)
            return {}

    def _process_data(self, data):
        """Process the fetched data into leaderboards."""
        result = {}

        category_mapping = {
            "points": "points",
            "goals": "goals",
            "assists": "assists",
            "plusminus": "plusMinus",
            "powerplaygoals": "powerPlayGoals",
            "shots": "shots",
            "shotpercentage": "shotPercentage",
            "xge": "xge",
            "games": "playedGames",
            "winninggoals": "winningGoal",
        }

        # API returns a flat list when using dataType=basicStats.
        if isinstance(data, list):
            all_players = data
        elif isinstance(data, dict) and "playerStats" in data:
            all_players = data.get("playerStats", [])
        elif isinstance(data, dict) and "players" in data:
            all_players = data.get("players", [])
        else:
            all_players = []

        if not all_players:
            _LOGGER.warning("No player data found in API response or unrecognized format")
            return result

        # Exclude goalkeepers — this integration is for skaters only.
        skaters = [p for p in all_players if not p.get("goalkeeper", False)]

        if not skaters:
            _LOGGER.warning("No skater data found after filtering out goalkeepers")
            return result

        for category in self.categories:
            if category not in category_mapping:
                continue

            api_field = category_mapping[category]
            valid_skaters = [
                p for p in skaters if self._has_valid_field(p, api_field)
            ]

            # Lower is better for nothing here; all skater stats rank highest first.
            sorted_skaters = sorted(
                valid_skaters,
                key=lambda x: self._safe_get_value(x, api_field),
                reverse=True,
            )

            top_players = []
            for i, player in enumerate(sorted_skaters[: self.top_n], 1):
                full_name = (
                    f"{player.get('firstName', '')} {player.get('lastName', '')}"
                ).strip()
                team = player.get("teamName", player.get("teamShortName", "Unknown"))

                top_players.append(
                    {
                        "rank": i,
                        "name": full_name,
                        "team": team,
                        "value": self._safe_get_value(player, api_field),
                        "games": player.get("playedGames", 0),
                        "position": player.get("role", ""),
                        "number": player.get("jersey", ""),
                        "player_id": player.get("playerId", ""),
                        "image_url": player.get("pictureUrl", "") or "",
                        "goals": player.get("goals", 0),
                        "assists": player.get("assists", 0),
                        "points": player.get("points", 0),
                        "plus_minus": player.get("plusMinus", 0),
                    }
                )

            result[category] = top_players

        return result

    def _has_valid_field(self, player, field):
        """Return True if the player has a usable numeric value for field."""
        value = player.get(field)
        if value is None:
            return False
        try:
            float(str(value).replace(",", ".").replace("%", ""))
            return True
        except (ValueError, TypeError):
            return False

    def _safe_get_value(self, player, field):
        """Return a float value for the given field, defaulting to 0."""
        value = player.get(field, 0)
        try:
            return float(str(value).replace(",", ".").replace("%", ""))
        except (ValueError, TypeError):
            return 0.0
