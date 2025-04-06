# Liiga Statistics Integration for Home Assistant

This custom integration creates leaderboards for Finnish Liiga hockey statistics in your Home Assistant instance.

## Features

- Player statistics leaderboards for various categories
- Automatically updates from Liiga.fi API
- Configurable number of players in each leaderboard
- Multiple statistic categories supported
- Player images for visual representation

## Installation

1. Create a directory structure in your Home Assistant configuration folder:
   ```
   /config/custom_components/liigastats/
   ```

2. Copy all files from this repository to the above directory:
   - `__init__.py`
   - `sensor.py`
   - `config_flow.py`
   - `manifest.json`
   - `strings.json`

3. Restart Home Assistant
4. Go to Settings > Devices & Services > Add Integration and search for "Liiga Statistics"

## Configuration

### Via UI

1. Enter the URL to the Liiga API:
   - For player stats: `https://liiga.fi/api/v2/players/stats/2024/runkosarja`
   - For standings: `https://liiga.fi/api/v1/standings/2024`
   
2. Select which statistic categories you want to track (comma-separated):
   - `points` - Total points
   - `goals` - Goals scored
   - `assists` - Assists
   - `plusminus` - Plus/minus
   - `penalties` - Penalty minutes
   - `games` - Games played
   - `toi` - Time on ice 
   - `shots` - Shots
   - `faceoffs` - Faceoff win percentage
   - `blocks` - Blocked shots
   - `hits` - Hits

3. Set how many players to show in each leaderboard (default: 10)

### Via Configuration.yaml

```yaml
liigastats:
  url: "https://liiga.fi/api/v2/players/stats/2024/runkosarja"
  categories:
    - points
    - goals
    - assists
    - plusminus
    - penalties
  top_n: 10
```

## Displaying the Data

The integration creates sensors for each statistic category. Each sensor includes:
- State: Name of the leader in that category
- Attributes: Full leaderboard data and leader image URL

### Basic Markdown Card

```yaml
type: markdown
content: >
  ## Liiga Points Leaders

  {% for player in state_attr('sensor.liiga_points_leaders', 'leaders') %}
  **{{player.rank}}. {{player.name}} ({{player.team}})**: {{player.value}} in {{player.games}} games
  {% endfor %}
```

### Card with Player Image

```yaml
type: vertical-stack
cards:
  - type: picture-entity
    entity: sensor.liiga_points_leaders
    name: Points Leader
    image: "{{ state_attr('sensor.liiga_points_leaders', 'leader_image_url') }}"
    show_state: false
    show_name: true
  - type: markdown
    content: >
      {% set leader = state_attr('sensor.liiga_points_leaders', 'leaders')[0] %}
      ## {{ leader.name }} ({{ leader.team }})
      **Points:** {{ leader.value }} in {{ leader.games }} games
      **Number:** {{ leader.number }}
      **Position:** {{ leader.position }}
```

### Full Leaderboard with Images

You can use custom cards like `grid` or `vertical-stack` with multiple `horizontal-stack` cards to create a more visual leaderboard.

## Player Images

The integration extracts player IDs from the API response and generates image URLs in the format:
```
https://liiga.fi/static/media/players/{player_id}.jpg
```

These images are included in the sensor attributes and can be used in your Lovelace cards.
