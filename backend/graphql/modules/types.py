from __future__ import annotations
from typing import Optional
import strawberry


@strawberry.type
class Marker:
    marker_id:        str
    marker_name:      str
    description:      Optional[str]
    unit:             str
    volatility_class: str

    @classmethod
    def from_dict(cls, d: dict) -> "Marker":
        return cls(
            marker_id        = d["marker_id"],
            marker_name      = d.get("marker_name")      or "",
            description      = d.get("description"),
            unit             = d.get("unit")             or "",
            volatility_class = d.get("volatility_class") or "",
        )


@strawberry.type
class Module:
    module_id:   str
    module_name: str
    description: Optional[str]
    markers:     list[Marker]

    @classmethod
    def from_dict(cls, d: dict) -> "Module":
        return cls(
            module_id   = d["module_id"],
            module_name = d.get("module_name") or "",
            description = d.get("description"),
            markers     = [Marker.from_dict(m) for m in d.get("markers", [])],
        )


@strawberry.type
class DemographicZone:
    """A single sex/age-specific zone boundary row."""
    sex:                  str
    age:                  int
    healthy_min:          float
    healthy_max:          float
    vulnerability_margin: float


@strawberry.input
class ModuleInput:
    module_id:   str
    module_name: str = ""
    description: str = ""
    format:      str = "json"


@strawberry.input
class ModuleUpdateInput:
    module_name: str = ""
    description: str = ""


@strawberry.input
class MarkerInput:
    marker_id:            str
    marker_name:          str = ""
    description:          str = ""
    unit:                 str = ""
    volatility_class:     str = ""
    healthy_min:          float = 0.0
    healthy_max:          float = 1.0
    vulnerability_margin: float = 0.2


@strawberry.input
class MarkerUpdateInput:
    marker_name:          str = ""
    description:          str = ""
    unit:                 str = ""
    volatility_class:     str = ""
    healthy_min:          float = 0.0
    healthy_max:          float = 1.0
    vulnerability_margin: float = 0.2


@strawberry.input
class DemographicZoneInput:
    sex:                  str
    age:                  int
    healthy_min:          float
    healthy_max:          float
    vulnerability_margin: float


@strawberry.input
class ZoneBoundaryInput:
    healthy_min:          float
    healthy_max:          float
    vulnerability_margin: float
