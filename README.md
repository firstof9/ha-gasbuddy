# GasBuddy

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![Discord][discord-shield]][discord]
[![Community Forum][forum-shield]][forum]

_Integration to track fuel prices from [GasBuddy][GasBuddy]._

Looking for a custom Lovelace card? Check out the [GasBuddy Card][gasbuddy-card].

![GasBuddy Card][gasbuddy-card-screenshot]

**This integration will set up the following platforms.**

Platform | Description
-- | --
`sensor` | Show info, prices, and EV charging details from a GasBuddy listed station.


## Installation via HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=firstof9&repository=ha-gasbuddy)

1. Follow the link [here](https://hacs.xyz/docs/faq/custom_repositories/)
2. Use the custom repo link [https://github.com/firstof9/ha-gasbuddy][ha-gasbuddy]
3. Select the category type `integration`
4. Then once it's there (still in HACS) click the INSTALL button
5. Restart Home Assistant
6. Once restarted, in the HA UI go to `Settings` (the ⚙️ on the sidebar) -> `Devices & Services`, click `+ Add Integration` and search for `GasBuddy`

## Manual (non-HACS)
<details>
<summary>Instructions</summary>

<br>
You probably do not want to do this! Use the HACS method above unless you know what you are doing and have a good reason as to why you are installing manually
<br>

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `gasbuddy`.
4. Download _all_ the files from the `custom_components/gasbuddy/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. Once restarted, in the HA UI go to `Settings` (the ⚙️ on the sidebar) -> `Devices & Services`, click `+ Add Integration` and search for `GasBuddy`
</details>

## Remedying Connection/timeout issues with FlareSolverr (Optional)

Since May 2025, GasBuddy implemented Cloudflare which may lead to blocking of requests to GasBuddy, and cause timeout and log errors. This would lead to the occasional missed data update to obtain the latest gas prices, along with log errors.

To circumvent this, FlareSolverr can be used to bypass Cloudflare protection. FlareSolverr can be installed via [FlareSolverr standalone installation](https://github.com/FlareSolverr/FlareSolverr) or as a [FlareSolverr Home Assistant add-on](https://github.com/alexbelgium/hassio-addons/tree/master/flaresolverr). Once your FlareSolverr instance is up and running, you can re-configure your existing GasBuddy entries by clicking the 3 dots of each gas station entry and entering your FlareSolverr URL, i.e., `http://ip:port/v1`

<img width="673" height="498" alt="image" src="https://github.com/user-attachments/assets/dbb7f99f-9f4d-4b2b-83c9-8419ba106a97" />

Future changes to your FlareSolverr instance can be edited the same way.

## Configuration

Configuration is done via the Home Assistant UI. When adding the integration, you will be presented with several search options:

*   **Manual**: Enter the GasBuddy Station ID directly.
*   **Search by Home**: Uses your Home Assistant zone coordinates to find nearby stations.
*   **Search by Postal Code**: Enter a specific Zip or Postal Code to find stations in that area.
*   **Track Cheapest Nearby Gas**: Instead of a fixed station, follow whichever nearby station is currently cheapest for a fuel type and price type you choose (see [Cheapest gas tracker](#cheapest-gas-tracker)).

You can configure the following options by clicking **Configure** on the integration card:
*   **Polling interval**: Polling frequency in seconds.
*   **Show per liter/gallon in unit of measure**: Standardizes price representation.
*   **Show stations on map**: Enables rendering of stations on the Map panel.
*   **Enable EV charging sensors**: Toggles dedicated EV charging sensors that report connector counts and charging power per connector type. Entity IDs depend on the station name you configure; the sensor keys created include `ev_level1`, `ev_level2`, `ev_dc_fast`, `ev_j1772` (+ `_power`), `ev_ccs` (+ `_power`), `ev_chademo` (+ `_power`), `ev_nacs` (+ `_power`), and `ev_status`.

### Cheapest gas tracker

The **Track Cheapest Nearby Gas** option creates an entry that follows the lowest-priced nearby station rather than a single fixed station. On every refresh it re-checks and updates to whichever nearby station is currently cheapest, so the sensor always reflects the best nearby price.

When you add it, choose:

*   **Fuel type**: Regular, Midgrade, Premium, Diesel, E85, or UNL88.
*   **Price type**:
    *   **Best**: the lowest of the available credit, cash, and deal prices.
    *   **Credit**: the standard posted (credit) price.
    *   **Cash**: the cash price.
    *   **Deal/GasBuddy Pay**: the GasBuddy Pay / deal price.

Leave the postal code blank to search around your Home Assistant home coordinates, or enter a specific Zip/Postal Code to track the cheapest station in that area.

## Services

The following services are available:

Service | Description | Arguments
:--- | :--- | :---
`gasbuddy.lookup_gps` | Lookup prices using GPS coordinates from a list of entities (e.g., `device_tracker` or `person`). | `entity_id` (Required), `limit` (Optional, 1-99), `solver` (Optional)
`gasbuddy.lookup_zip` | Lookup prices via ZIP/Postal code. | `zipcode` (Required), `limit` (Optional, 1-99), `solver` (Optional)
`gasbuddy.ev_lookup_gps` | Lookup nearby EV stations using GPS coordinates from a list of entities. | `entity_id` (Required), `limit` (Optional), `radius` (Optional), `solver` (Optional)
`gasbuddy.ev_lookup_zip` | Lookup nearby EV stations via ZIP/Postal code. | `zipcode` (Required), `limit` (Optional), `radius` (Optional), `solver` (Optional)
`gasbuddy.clear_cache` | Clear the cache for specific device(s). | `device_id` (Required)

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

***



[GasBuddy]: https://gasbuddy.com/
[gasbuddy-card]: https://github.com/firstof9/gasbuddy-card
[gasbuddy-card-screenshot]: https://github.com/firstof9/gasbuddy-card/raw/main/screenshots/gas_station.png
[ha-gasbuddy]: https://github.com/firstof9/ha-gasbuddy
[buymecoffee]: https://www.buymeacoffee.com/firstof9
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/firstof9/ha-gasbuddy.svg?style=for-the-badge
[commits]: https://github.com/firstof9/ha-gasbuddy/commits/main
[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[discord]: https://discord.gg/Qa5fW2R
[discord-shield]: https://img.shields.io/discord/330944238910963714.svg?style=for-the-badge
[exampleimg]: example.png
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/firstof9/ha-gasbuddy.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-Chris%20Nowak%20%40firstof9-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/firstof9/ha-gasbuddy.svg?style=for-the-badge
[releases]: https://github.com/firstof9/ha-gasbuddy/releases
