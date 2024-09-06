"""Support for GasBuddy entities."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription


@dataclass
class GasBuddySensorEntityDescription(SensorEntityDescription):
    """Class describing OpenEVSE select entities."""

    cash: bool | None = None
