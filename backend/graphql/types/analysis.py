# GraphQL types for all analysis-related concepts.
#
# ARCHITECTURE NOTE — Future-proofing via union types:
# AnalysisResult is a union from day one, even though only TrajectoryReport is implemented.
# To add a new analysis method (PCA, RandomForest, etc.):
#   1. Define a new @strawberry.type (e.g. PCAReport) in this file
#   2. Add it to the AnalysisResult union below
#   3. Add a new ARQ task function in backend/workers/analysis_tasks.py
#   4. Add the new AnalysisMethod enum value (already done — stub out the resolver)
# Zero changes to Query, Mutation, or Subscription root types are needed.

from __future__ import annotations
from enum import Enum
from typing import Annotated, Optional, Union
import strawberry


# ── Enums ─────────────────────────────────────────────────────────────────────

@strawberry.enum
class JobStatus(Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


@strawberry.enum
class AnalysisMethod(Enum):
    TRAJECTORY    = "trajectory"       # Implemented — polynomial + 27-state classification
    PCA           = "pca"              # Stub — future
    RANDOM_FOREST = "random_forest"    # Stub — future
    NEURAL_NETWORK = "neural_network"  # Stub — future
    AUTOMATED     = "automated"        # Stub — future (backend auto-selects markers + method)


# ── Nested result types ────────────────────────────────────────────────────────

@strawberry.type
class Normalization:
    healthy_min: float
    healthy_max: float
    mid:         float
    half_range:  float


@strawberry.type
class ZoneBoundaryMeta:
    vulnerability_margin: float


@strawberry.type
class FitMetadata:
    coefficients:      list[float]
    t0_iso:            str
    polynomial_degree: int
    normalization:     Normalization
    zone_boundaries:   ZoneBoundaryMeta


@strawberry.type
class TrajectoryDatapoint:
    timestamp:                str
    x_hours:                  float
    raw_value:                float
    data_quality:             str
    health_score:             float
    fitted_value:             float
    zone:                     str
    f_prime:                  float
    f_double_prime:           float
    trajectory_state:         int
    time_to_transition_hours: Optional[float]


# ── Concrete result types ──────────────────────────────────────────────────────

@strawberry.type
class TrajectoryReport:
    """Derivative-based trajectory analysis — currently the only implemented method."""
    report_id:    str
    subject_id:   str
    module_id:    str
    marker_ids:   list[str]
    requested_at: str
    datapoints:   list[TrajectoryDatapoint]
    fit_metadata: FitMetadata


# Stub types — defined now so the union contract is established.
# Replace the placeholder fields with real ones when each method is implemented.

@strawberry.type
class PCAReport:
    """Principal Component Analysis across multiple markers — not yet implemented."""
    report_id: str
    message:   str = "PCA analysis not yet implemented"


@strawberry.type
class MLReport:
    """Machine-learning ensemble analysis — not yet implemented."""
    report_id: str
    message:   str = "ML analysis not yet implemented"


@strawberry.type
class AutomatedInsightReport:
    """Backend-automated marker + method selection — not yet implemented."""
    report_id: str
    message:   str = "Automated analysis not yet implemented"


# ── Union ─────────────────────────────────────────────────────────────────────

# THE KEY CONTRACT: adding a new report type here is a non-breaking schema addition.
# Modern Strawberry uses Annotated[Union[...], strawberry.union("Name")] syntax.
AnalysisResult = Annotated[
    Union[TrajectoryReport, PCAReport, MLReport, AutomatedInsightReport],
    strawberry.union("AnalysisResult"),
]


# ── Wrapper type ───────────────────────────────────────────────────────────────

@strawberry.type
class AnalysisJob:
    """
    Generic wrapper for any analysis computation, regardless of method.
    Returned immediately by submitAnalysis (status=PENDING) and streamed
    via jobStatus subscription as the worker progresses.
    """
    job_id:        str
    status:        JobStatus
    progress:      Optional[float]          # 0.0–1.0, published by worker
    created_at:    str
    result:        Optional[AnalysisResult] # populated when status=COMPLETED
    error_message: Optional[str]            # populated when status=FAILED


# ── Input types ───────────────────────────────────────────────────────────────

@strawberry.input
class TimeframeInput:
    start_time: str  # ISO 8601, e.g. "2026-01-01T00:00:00Z"
    end_time:   str


@strawberry.input
class TrajectoryParamsInput:
    """
    Parameters specific to TRAJECTORY method.
    Zone boundaries are provided by the caller (obtained from Query.zoneReference).
    """
    polynomial_degree:    int   = 3
    healthy_min:          float = 0.0
    healthy_max:          float = 1.0
    vulnerability_margin: float = 0.2


@strawberry.input
class AnalysisInput:
    """
    Unified input for all analysis methods.
    marker_ids is an array — multi-marker analysis is supported structurally from day one,
    even though the TRAJECTORY method currently uses only marker_ids[0].
    """
    subject_id:        str
    module_id:         str
    marker_ids:        list[str]      # Array: multi-marker future-ready
    method:            AnalysisMethod
    timeframe:         TimeframeInput
    trajectory_params: Optional[TrajectoryParamsInput] = None
    # Future: pca_params, ml_params, automated_params — add here, non-breaking


# ── Helper: build TrajectoryReport from worker result payload ──────────────────

def build_trajectory_report(data: dict) -> TrajectoryReport:
    """Converts the raw dict published by the worker into a TrajectoryReport."""
    result     = data["result"]
    raw_meta   = result["fit_metadata"]
    raw_norm   = raw_meta["normalization"]
    raw_zones  = raw_meta["zone_boundaries"]

    fit_metadata = FitMetadata(
        coefficients      = raw_meta["coefficients"],
        t0_iso            = raw_meta["t0_iso"],
        polynomial_degree = raw_meta["polynomial_degree"],
        normalization     = Normalization(
            healthy_min = raw_norm["healthy_min"],
            healthy_max = raw_norm["healthy_max"],
            mid         = raw_norm["mid"],
            half_range  = raw_norm["half_range"],
        ),
        zone_boundaries = ZoneBoundaryMeta(
            vulnerability_margin = raw_zones["vulnerability_margin"],
        ),
    )

    datapoints = [
        TrajectoryDatapoint(
            timestamp                = dp["timestamp"],
            x_hours                  = dp["x_hours"],
            raw_value                = dp["raw_value"],
            data_quality             = dp.get("data_quality", "good"),
            health_score             = dp["health_score"],
            fitted_value             = dp["fitted_value"],
            zone                     = dp["zone"],
            f_prime                  = dp["f_prime"],
            f_double_prime           = dp["f_double_prime"],
            trajectory_state         = dp["trajectory_state"],
            time_to_transition_hours = dp.get("time_to_transition_hours"),
        )
        for dp in result["datapoints"]
    ]

    return TrajectoryReport(
        report_id    = data["report_id"],
        subject_id   = data["subject_id"],
        module_id    = data["module_id"],
        marker_ids   = data["marker_ids"],
        requested_at = data["requested_at"],
        datapoints   = datapoints,
        fit_metadata = fit_metadata,
    )
