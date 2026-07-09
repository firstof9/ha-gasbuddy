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

To circumvent this, FlareSolverr can be used to bypass Cloudflare protection. FlareSolverr can be installed via [FlareSolverr standalone installation](https://github.com/FlareSolverr/FlareSolverr) or as a [FlareSolverr Home Assistant add-on](https://github.com/alexbelgium/hassio-addons/tree/master/flaresolverr). Once your FlareSolverr instance is up and running, you can configure your FlareSolverr URL and timeout globally on the **GasBuddy Virtual Hub** by clicking **Configure** on the integration card.

<img width="673" height="498" alt="image" src="https://github.com/user-attachments/assets/dbb7f99f-9f4d-4b2b-83c9-8419ba106a97" />

Future changes to your FlareSolverr instance can be edited the same way.

## Configuration

Configuration is done via the Home Assistant UI. When adding the integration, you will be presented with several search options:

*   **Manual**: Enter the GasBuddy Station ID directly.
*   **Search by Home**: Uses your Home Assistant zone coordinates to find nearby stations.
*   **Search by Postal Code**: Enter a specific Zip or Postal Code to find stations in that area.
*   **Track Cheapest Nearby Gas**: Instead of a fixed station, follow whichever nearby station is currently cheapest for a fuel type and price type you choose (see [Cheapest gas tracker](#cheapest-gas-tracker)).

### Global Options (Virtual Hub)
By clicking **Configure** on the main **GasBuddy Virtual Hub** integration card, you can manage global settings that apply across all tracked stations:
*   **FlareSolverr URL**: The URL to your FlareSolverr instance.
*   **FlareSolverr timeout**: Timeout value in milliseconds.
*   **Brand Price Adjustments**: YAML or JSON map for per-brand discounts or markups (see [Brand Price Adjustments](#brand-price-adjustments)).

### Station Options (Subentries)
Tracked gas stations are managed as **subentries** under the GasBuddy Virtual Hub. You can configure station-specific settings by clicking **Reconfigure** next to the specific station subentry under the Virtual Hub device/integration card:
*   **Polling interval**: Polling frequency in seconds (default is 3600).
*   **Show per liter/gallon in unit of measure**: Standardizes price representation.
*   **Show stations on map**: Enables rendering of stations on the Map panel.
*   **Enable EV charging sensors**: Toggles dedicated EV charging sensors that report connector counts and charging power per connector type (see [Sensors](#sensors) for details).
*   **Fetch Gas Prices**: Toggles retrieving fuel prices for the station.
*   **Display discounted price**: Toggles showing the discounted price as the state value of the sensor (applying brand adjustments).

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

You can optionally configure inclusion and exclusion filters to restrict tracking to specific brands or stations.

#### Brand Price Adjustments

You can configure price adjustments (e.g. discounts or markups) per brand when setting up the cheapest station or configuring the integration options for any tracked station. These adjustments apply when determining which station is cheapest or show up as the `discounted_price` attribute on the price sensors. By default, the reported state remains the actual retail price at the pump.

If you want the sensor state value itself to show the discounted price, you can enable the **Display discounted price** option in the station's reconfigure screen.

Specify adjustments as a YAML or JSON map, where the key is either the brand name (case-insensitive) or the brand ID, and the value is the adjustment amount (a negative number for a discount, or positive for a markup).

> [!IMPORTANT]
> **Adjustment Units**: The adjustment value must use the same unit as the station's raw price before any metric conversions.
> - For dollar-based stations (e.g. USD/gallon), use dollar amounts (e.g., `-0.10` for $0.10).
> - For cents-based stations (e.g. CAD/cents-per-liter), use cents (e.g., `-5.0` for a 5¢ discount).

For example, if you receive a $0.10 discount at Walmart and a $0.05 discount at Costco (on a US/dollar-based station):
```yaml
Walmart: -0.10
Costco: -0.05
```

For Canadian/metric stations where prices are retrieved in cents-per-liter (e.g. a 5¢ per liter discount at Costco):
```yaml
Costco: -5.0
```

This ensures a Walmart station with a posted price of $3.50 will be compared as $3.40 (or reported as $3.40 state value if the discount display toggle is active), while also exposing the `discounted_price` attribute as `3.40`.

## Sensors

The integration provides a variety of sensors depending on your configuration options and the capabilities of the tracked station. Sensors are categorized into three groups:

### General & Station Info
These general sensors track the station status and name.

| Sensor Name | Sensor Key | Default | Description |
| :--- | :--- | :--- | :--- |
| **Last Updated** | `last_updated` | **Enabled** | The timestamp when the integration last successfully fetched data |
| **Station Status** | `open_status` | Disabled | Current opening status of the station (e.g., Open, Closed) |
| **Station Name** | `name` | Disabled | The name of the station |

### Fuel Price Sensors
These sensors are created if **Fetch Gas Prices** (`fetch_gas`) is enabled (default). Only fuel types sold at the station will have sensors created.

| Sensor Name | Sensor Key | Default | Description |
| :--- | :--- | :--- | :--- |
| **Regular Gas** | `regular_gas` | **Enabled** | Credit/Standard price of Regular gas |
| **Regular Gas (Cash)** | `regular_gas_cash` | Disabled | Cash price of Regular gas |
| **Regular Gas (Deal)** | `regular_gas_deal` | Disabled | Deal/GasBuddy Pay price of Regular gas |
| **MidGrade Gas** | `midgrade_gas` | **Enabled** | Credit/Standard price of MidGrade gas |
| **MidGrade Gas (Cash)** | `midgrade_gas_cash` | Disabled | Cash price of MidGrade gas |
| **MidGrade Gas (Deal)** | `midgrade_gas_deal` | Disabled | Deal/GasBuddy Pay price of MidGrade gas |
| **Premium Gas** | `premium_gas` | **Enabled** | Credit/Standard price of Premium gas |
| **Premium Gas (Cash)** | `premium_gas_cash` | Disabled | Cash price of Premium gas |
| **Premium Gas (Deal)** | `premium_gas_deal` | Disabled | Deal/GasBuddy Pay price of Premium gas |
| **Diesel** | `diesel` | Disabled | Credit/Standard price of Diesel |
| **Diesel (Cash)** | `diesel_cash` | Disabled | Cash price of Diesel |
| **Diesel (Deal)** | `diesel_deal` | Disabled | Deal/GasBuddy Pay price of Diesel |
| **E85** | `e85` | Disabled | Credit/Standard price of E85 |
| **E85 (Cash)** | `e85_cash` | Disabled | Cash price of E85 |
| **E85 (Deal)** | `e85_deal` | Disabled | Deal/GasBuddy Pay price of E85 |
| **UNL88** | `e15` | Disabled | Credit/Standard price of UNL88 |
| **UNL88 (Cash)** | `e15_cash` | Disabled | Cash price of UNL88 |
| **UNL88 (Deal)** | `e15_deal` | Disabled | Deal/GasBuddy Pay price of UNL88 |

#### Fuel Price Sensor Attributes
Each fuel price sensor exposes the following attributes where available:
*   `attribution`: Data credit/source (e.g. "Member credit via GasBuddy")
*   `last_updated`: Timestamp of when this specific price was last updated on GasBuddy
*   `station_id`: GasBuddy station ID
*   `formatted_price`: Price formatted with currency/unit (e.g. `$3.45/gallon` or `145.9¢/liter`)
*   `deal_price`: The discounted price (if a GasBuddy deal is active)
*   `phone`: The telephone number of the station
*   `star_rating`: User rating out of 5 stars
*   `address`: Formatted address of the station
*   `amenities`: List of amenities available at the station (e.g. Convenience Store, Car Wash)
*   `latitude` & `longitude`: GPS coordinates (only exposed if **Show stations on map** option is enabled)

### EV Charging Sensors
These sensors are only created if **Enable EV charging sensors** (`ev_charging`) is checked in the options.

| Sensor Name | Sensor Key | Default | Description |
| :--- | :--- | :--- | :--- |
| **EV Station Status** | `ev_status` | Disabled | The current status of the charging station |
| **EV Charging Network** | `ev_network` | **Enabled** | Name of the charging network (e.g. ChargePoint, Tesla) |
| **EV Charging Network Website** | `ev_network_web` | Disabled | Website of the charging network |
| **EV Charging Pricing** | `ev_pricing` | **Enabled** | Pricing rules/rates for charging |
| **EV Access Hours** | `ev_access_hours` | **Enabled** | Hours when the charging station is accessible |
| **EV Access** | `ev_access` | **Enabled** | Access type or restrictions |
| **EV Payment Accepted** | `ev_cards_accepted` | Disabled | Payment cards or methods accepted |
| **EV Last Confirmed** | `ev_date_last_confirmed` | **Enabled** | Timestamp of when the EV data was last verified |
| **EV Level 1 Chargers** | `ev_level1` | Disabled | Number of Level 1 chargers at the station |
| **EV Level 2 Chargers** | `ev_level2` | **Enabled** | Number of Level 2 chargers at the station |
| **EV DC Fast Chargers** | `ev_dc_fast` | **Enabled** | Number of DC Fast chargers at the station |
| **EV J1772 Connectors** | `ev_j1772` | **Enabled** | Number of J1772 connectors |
| **EV J1772 Connector Power** | `ev_j1772_power` | Disabled | Charging power of J1772 connectors (kW) |
| **EV CCS Connectors** | `ev_ccs` | **Enabled** | Number of CCS connectors |
| **EV CCS Connector Power** | `ev_ccs_power` | Disabled | Charging power of CCS connectors (kW) |
| **EV CHAdeMO Connectors** | `ev_chademo` | **Enabled** | Number of CHAdeMO connectors |
| **EV CHAdeMO Connector Power** | `ev_chademo_power` | Disabled | Charging power of CHAdeMO connectors (kW) |
| **EV NACS Connectors** | `ev_nacs` | **Enabled** | Number of NACS (Tesla) connectors |
| **EV NACS Connector Power** | `ev_nacs_power` | Disabled | Charging power of NACS connectors (kW) |

#### EV Charging Sensor Attributes
EV-related sensors expose the following attributes where available:
*   `station_id`: GasBuddy station ID
*   `station_name`: Name of the EV charging station
*   `station_address`: Full address of the EV charging station
*   `distance_miles`: Distance to the station in miles (if queried by coordinates)
*   `network`: EV network name
*   `pricing`: Charging pricing/rates
*   `access_hours`: Access hours
*   `website`: Network website (only present on `ev_network`)
*   `latitude` & `longitude`: GPS coordinates (only exposed if **Show stations on map** option is enabled)

## Services

The following services are available:

Service | Description | Arguments
:--- | :--- | :---
`gasbuddy.lookup_gps` | Lookup prices using GPS coordinates from a list of entities (e.g., `device_tracker` or `person`). | `entity_id` (Required), `limit` (Optional, 1-99), `solver` (Optional)
`gasbuddy.lookup_zip` | Lookup prices via ZIP/Postal code. | `zipcode` (Required), `limit` (Optional, 1-99), `solver` (Optional)
`gasbuddy.ev_lookup_gps` | Lookup nearby EV stations using GPS coordinates from a list of entities. | `entity_id` (Required), `limit` (Optional), `radius` (Optional), `solver` (Optional)
`gasbuddy.ev_lookup_zip` | Lookup nearby EV stations via ZIP/Postal code. | `zipcode` (Required), `limit` (Optional), `radius` (Optional), `solver` (Optional)
`gasbuddy.clear_cache` | Clear the cache for specific device(s). | `device_id` (Required)

## National Average Price / Trends

Although the integration's standard sensors track specific physical stations, you can create a template sensor to track the national average gas price (or other regional trends) using the `gasbuddy.lookup_zip` service.

To do this, add a trigger-based template sensor to your `configuration.yaml` (adjusting the postal code and polling interval to your preference):

```yaml
template:
  - trigger:
      - platform: time_pattern
        hours: "/6" # Fetch data every 6 hours
    action:
      - action: gasbuddy.lookup_zip
        data:
          postal_code: "12345" # Replace with your postal code
        response_variable: gasbuddy_data
    sensor:
      - name: "National Average Gas Price"
        unique_id: national_average_gas_price
        state: >
          {{ (gasbuddy_data.trend | selectattr('area', 'eq', 'United States') | first).average_price }}
        unit_of_measurement: "USD/gal"
        attributes:
          lowest_price: >
            {{ (gasbuddy_data.trend | selectattr('area', 'eq', 'United States') | first).lowest_price }}
```

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
