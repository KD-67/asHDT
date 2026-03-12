from __future__ import annotations
import strawberry


@strawberry.type
class Datapoint:
    measured_at:  str
    value:        float
    unit:         str
    data_quality: str


@strawberry.type
class Dataset:
    """Summary of a subject's marker dataset (entry count only — no raw data)."""
    module_id:   str
    marker_id:   str
    entry_count: int


@strawberry.input
class DatapointInput:
    measured_at:  str
    value:        float
    unit:         str
    data_quality: str = "good"
