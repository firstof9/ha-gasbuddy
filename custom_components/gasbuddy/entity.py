"""Support for GasBuddy entities."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription


@dataclass(frozen=True, kw_only=True)
class GasBuddySensorEntityDescription(SensorEntityDescription):
    """Class describing OpenEVSE select entities."""

    cash: bool | None = None
    price: bool | None = True
