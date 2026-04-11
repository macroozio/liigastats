"""Sensor platform for Liiga Player Statistics."""
from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, LiigaPlayerStatsDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Category-specific formatting and icons
CATEGORY_CONFIG = {
    "points": {
        "name": "Points",
        "icon": "mdi:star",
        "value_suffix": "",
        "precision": 0
    },
    "goals": {
        "name": "Goals",
        "icon": "mdi:hockey-puck",
        "value_suffix": "",
        "precision": 0
    },
    "assists": {
        "name": "Assists",
        "icon": "mdi:handshake",
        "value_suffix": "",
        "precision": 0
    },
    "plusminus": {
        "name": "Plus/Minus",
        "icon": "mdi:plus-minus",
        "value_suffix": "",
        "precision": 0
    },
    "powerplaygoals": {
        "name": "Power Play Goals",
        "icon": "mdi:lightning-bolt",
        "value_suffix": "",
        "precision": 0
    },
    "shots": {
        "name": "Shots",
        "icon": "mdi:hockey-sticks",
        "value_suffix": "",
        "precision": 0
    },
    "shotpercentage": {
        "name": "Shot Percentage",
        "icon": "mdi:percent",
        "value_suffix": "%",
        "precision": 1
    },
    "xge": {
        "name": "Expected Goals Effect",
        "icon": "mdi:chart-line",
        "value_suffix": "",
        "precision": 2
    },
    "games": {
        "name": "Games",
        "icon": "mdi:calendar-check",
        "value_suffix": "",
        "precision": 0
    },
    "winninggoals": {
        "name": "Game-Winning Goals",
        "icon": "mdi:trophy",
        "value_suffix": "",
        "precision": 0
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for category in coordinator.categories:
        sensors.append(LiigaPlayerStatsLeaderboardSensor(coordinator, category))

    async_add_entities(sensors, True)


class LiigaPlayerStatsLeaderboardSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Liiga Player Leaderboard sensor."""

    def __init__(
        self, coordinator: LiigaPlayerStatsDataUpdateCoordinator, category: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.category = category

        category_config = CATEGORY_CONFIG.get(category, {
            "name": category.capitalize(),
            "icon": "mdi:hockey-puck",
            "value_suffix": "",
            "precision": 0
        })

        self._attr_name = f"Liiga Player {category_config['name']} Leaders"
        self._attr_unique_id = f"liigastats_{category}_leaderboard"
        self._attr_icon = category_config["icon"]
        self.value_suffix = category_config["value_suffix"]
        self.precision = category_config["precision"]

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        if not self.coordinator.data or self.category not in self.coordinator.data:
            return "Unknown"

        leaders = self.coordinator.data.get(self.category, [])
        if not leaders:
            return "No data"

        return leaders[0].get("name", "Unknown")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or self.category not in self.coordinator.data:
            return {}

        leaders = self.coordinator.data.get(self.category, [])

        formatted_leaders = []
        for player in leaders:
            if self.precision == 0:
                formatted_value = f"{int(player.get('value', 0))}{self.value_suffix}"
            else:
                formatted_value = f"{player.get('value', 0):.{self.precision}f}{self.value_suffix}"

            plus_minus = player.get("plus_minus", 0)
            pm_str = f"+{plus_minus}" if plus_minus > 0 else str(plus_minus)

            formatted_leaders.append({
                "rank": player.get("rank", 0),
                "name": player.get("name", "Unknown"),
                "team": player.get("team", "Unknown"),
                "value": formatted_value,
                "games": player.get("games", 0),
                "position": player.get("position", ""),
                "number": player.get("number", ""),
                "image_url": player.get("image_url", ""),
                "goals": player.get("goals", 0),
                "assists": player.get("assists", 0),
                "points": player.get("points", 0),
                "plus_minus": pm_str,
                "gap": f"{player.get('goals', 0)}-{player.get('assists', 0)}-{player.get('points', 0)}",
            })

        leader_image_url = leaders[0].get("image_url", "") if leaders else ""

        return {
            "leaders": formatted_leaders,
            "last_updated": self.coordinator.last_update_success_time.isoformat() if self.coordinator.last_update_success_time else None,
            "category": self.category,
            "category_name": CATEGORY_CONFIG.get(self.category, {}).get("name", self.category.capitalize()),
            "leader_image_url": leader_image_url,
        }
