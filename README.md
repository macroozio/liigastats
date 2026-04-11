# Liiga Player Statistics

A custom [Home Assistant](https://www.home-assistant.io/) integration that fetches Finnish Liiga hockey skater statistics from the [liiga.fi](https://liiga.fi) API and exposes them as sensors with leaderboards.

## Features

- Fetches live skater stats from the official Liiga.fi API v2
- Season year and tournament phase (regular season / playoffs) are **auto-detected from the current date** — no manual configuration needed
- Goalkeepers are automatically excluded — skaters only
- One sensor per stat category, each exposing a ranked leaderboard as attributes
- Configurable categories and leaderboard depth
- Hourly updates
- Includes a ready-made dashboard card with auto-advancing slides

## Installation

1. Copy the `liigastats` folder into your Home Assistant `custom_components` directory:
   ```
   config/custom_components/liigastats/
   ```
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **Liiga Player Statistics**.
4. Configure the categories and leaderboard size (see below).

## Configuration

During setup you only choose:

| Field | Default | Description |
|---|---|---|
| Categories | `points,goals,assists,plusminus,powerplaygoals` | Comma-separated list of stat categories to track |
| Top N | `5` | Number of players to show per leaderboard |

The API URL, season year, and tournament phase are computed automatically:
- **Season year** — if the current month is September or later, the season end year is next calendar year; otherwise it is the current year.
- **Tournament** — playoffs (April–May and mid-March onward); everything else is regular season (`runkosarja`).

### Available categories

| Category | Description |
|---|---|
| `points` | Total points (goals + assists) |
| `goals` | Goals scored |
| `assists` | Assists |
| `plusminus` | Plus/minus rating |
| `powerplaygoals` | Power play goals |
| `shots` | Total shots on goal |
| `shotpercentage` | Shot percentage |
| `xge` | Expected goals effect |
| `games` | Games played |
| `winninggoals` | Game-winning goals |

## Sensors

Each configured category creates one sensor, e.g.:

- `sensor.liiga_player_points_leaders`
- `sensor.liiga_player_goals_leaders`
- `sensor.liiga_player_assists_leaders`
- `sensor.liiga_player_plus_minus_leaders`
- `sensor.liiga_player_power_play_goals_leaders`

The sensor **state** is the name of the current leader. The **attributes** contain:

```yaml
leaders:
  - rank: 1
    name: Firstname Lastname
    team: Tappara
    value: "62"
    games: 50
    goals: 24
    assists: 38
    points: 62
    plus_minus: "+18"
    gap: "24-38-62"
    position: OL
    number: "21"
    image_url: https://...
category: points
category_name: Points
leader_image_url: https://...
last_updated: "2026-04-11T18:00:00+00:00"
```

The `gap` field contains a `G-A-P` string (goals-assists-points) for easy display. The `plus_minus` field is pre-formatted with a `+` sign for positive values.

## Dashboard card

`customcard.yaml` contains a ready-made card using [`custom:simple-swipe-card`](https://github.com/nutteloost/simple-swipe-card) and [`custom:html-template-card`](https://github.com/PiotrMachowski/Home-Assistant-custom-components-Html-Template-Card).

Install both custom cards via HACS, then paste the contents of `customcard.yaml` into a new manual card in your dashboard.

The card auto-advances through five slides every 10 seconds:

1. Points Leaders
2. Goals Leaders
3. Assists Leaders
4. +/- Leaders
5. Power Play Goals Leaders

Each slide shows a responsive grid of player cards with team colour badges, stat value, games played, and G-A-P breakdown.

## Requirements

- Home Assistant 2024.1 or later
- [`custom:simple-swipe-card`](https://github.com/nutteloost/simple-swipe-card) (for the dashboard card)
- [`custom:html-template-card`](https://github.com/PiotrMachowski/Home-Assistant-custom-components-Html-Template-Card) (for the dashboard card)

## Data source

Data is fetched from:
```
https://liiga.fi/api/v2/players/stats/summed/{year}/{year}/{tournament}/true?dataType=basicStats
```

This is the same API that powers the official Liiga.fi website. Goalkeepers are filtered out on the integration side using the `goalkeeper` field returned by the API.
