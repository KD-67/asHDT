# GraphQL types for markersets: named, persisted compositions of markers with
# feature-engineering config. Markersets are the primary input unit for multi-marker
# analysis methods.

from __future__ import annotations
from typing import Optional
import strawberry


# ── Output types ───────────────────────────────────────────────────────────────

@strawberry.type
class MarkerFeatureConfig:
    module_id:              str
    marker_id:              str
    weight:                 float
    active:                 bool
    transform_type:         str            # none | log | rolling_avg | lag | normalize
    transform_window_hours: Optional[float]
    transform_lag_hours:    Optional[float]
    missing_data:           str            # interpolate | forward_fill | skip | zero


@strawberry.type
class MarkersetTemplate:
    markerset_id: str
    name:         str
    description:  Optional[str]
    markers:      list[MarkerFeatureConfig]
    created_at:   str


@strawberry.type
class MarkersetInstance:
    instance_id:  str
    subject_id:   str
    markerset_id: Optional[str]   # None for custom (no template)
    name:         str
    markers:      list[MarkerFeatureConfig]   # resolved template + overrides
    created_at:   str


# ── Input types ────────────────────────────────────────────────────────────────

@strawberry.input
class TransformConfigInput:
    type:         str            = "none"
    window_hours: Optional[float] = None
    lag_hours:    Optional[float] = None


@strawberry.input
class MarkerFeatureConfigInput:
    module_id:    str
    marker_id:    str
    weight:       float = 1.0
    active:       bool  = True
    transform:    Optional[TransformConfigInput] = None
    missing_data: str   = "interpolate"


@strawberry.input
class CreateMarkersetTemplateInput:
    name:        str
    description: str = ""
    markers:     list[MarkerFeatureConfigInput]


@strawberry.input
class CreateMarkersetInstanceInput:
    markerset_id: Optional[str] = None   # FK to template; None = custom
    name:         str            = ""
    markers:      list[MarkerFeatureConfigInput]


# ── Dict helpers (DB ↔ GQL conversion) ────────────────────────────────────────

def feature_config_from_dict(d: dict) -> MarkerFeatureConfig:
    t = d.get("transform") or {}
    return MarkerFeatureConfig(
        module_id              = d["module_id"],
        marker_id              = d["marker_id"],
        weight                 = d.get("weight", 1.0),
        active                 = d.get("active", True),
        transform_type         = t.get("type", "none"),
        transform_window_hours = t.get("window_hours"),
        transform_lag_hours    = t.get("lag_hours"),
        missing_data           = d.get("missing_data", "interpolate"),
    )


def feature_config_input_to_dict(inp: MarkerFeatureConfigInput) -> dict:
    t = inp.transform or TransformConfigInput()
    return {
        "module_id":    inp.module_id,
        "marker_id":    inp.marker_id,
        "weight":       inp.weight,
        "active":       inp.active,
        "transform": {
            "type":         t.type,
            "window_hours": t.window_hours,
            "lag_hours":    t.lag_hours,
        },
        "missing_data": inp.missing_data,
    }
