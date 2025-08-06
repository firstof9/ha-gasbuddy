# GasBuddy

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![Discord][discord-shield]][discord]
[![Community Forum][forum-shield]][forum]

_Component to integrate with [GasBuddy][GasBuddy] fuel price tracker._

**This component will set up the following platforms.**

Platform | Description
-- | --
`sensor` | Show info from an GasBuddy listed station.


## Installation via HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=firstof9&repository=ha-gasbuddy)

1. Follow the link [here](https://hacs.xyz/docs/faq/custom_repositories/)
2. Use the custom repo link https://github.com/firstof9/ha-gasbuddy
3. Select the category type `integration`
4. Then once it's there (still in HACS) click the INSTALL button
5. Restart Home Assistant
6. Once restarted, in the HA UI go to `Configuration` (the ⚙️ in the lower left) -> `Devices and Services` click `+ Add Integration` and search for `GasBuddy`

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
7. Once restarted, in the HA UI go to `Configuration` (the ⚙️ in the lower left) -> `Devices and Services` click `+ Add Integration` and search for `GasBuddy`
</details>

## Remedying Connection/timeout issues with FlareSolverr (Optional)

Since May 2025, GasBuddy implemented Cloudflare which may lead to blocking of requests to GasBuddy, and cause timeout and log errors. This would lead to the occasional missed data update to obtain the lastest gas prices, along with log errrors.

To circumvent this, FlareSolverr can used to bypass Cloudflare protection. FlareSolverr can be installed as a standalone docker container on your network [here]: https://github.com/FlareSolverr/FlareSolverr or as an addon in Home Assistant [here]: https://github.com/alexbelgium/hassio-addons/tree/master/flaresolverr. Once your FlareSolverr instance is up and running, you can re-configure your existing GasBuddy entries by clicking the 3 dots of EACH gas station entry, and entering your FlareSolverr URL, ie. `http://ip:port/v1`  

<img width="673" height="498" alt="image" src="https://github.com/user-attachments/assets/dbb7f99f-9f4d-4b2b-83c9-8419ba106a97" />

Future changes to your FlareSolverr instance can be edited the same way.

## Configuration is done in the UI

<!---->

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

***

## TODO

- [ ] Add tests


[GasBuddy]: https://gasbuddy.com/
[integration_blueprint]: https://github.com/firstof9/ha-gasbuddy
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
