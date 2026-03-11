# Builds a single composite health-score timeseries from multiple per-marker timeseries.
#
# Pipeline per marker:
#   raw values → feature transform → h normalization → missing-data fill
# Then:
#   union time grid → weighted average of h values → composite timeseries
#
# The composite timeseries is fed directly into trajectory_computer.compute_trajectory()
# with synthetic zone_boundaries that make h(composite_h) = composite_h:
#   healthy_min = 0, healthy_max = 2  →  mid=1, half_range=1  →  h(v) = v  for v∈[0,1]

from __future__ import annotations
import logging
import math
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Synthetic zone boundaries for composite mode
COMPOSITE_HEALTHY_MIN = 0.0
COMPOSITE_HEALTHY_MAX = 2.0


def composite_zone_boundaries(vulnerability_margin: float) -> dict:
    """Zone boundaries that make h(composite_h) = composite_h in trajectory_computer."""
    return {
        "healthy_min":          COMPOSITE_HEALTHY_MIN,
        "healthy_max":          COMPOSITE_HEALTHY_MAX,
        "vulnerability_margin": vulnerability_margin,
    }


# ── Transforms ─────────────────────────────────────────────────────────────────

def _normalize_h(raw: float, healthy_min: float, healthy_max: float) -> float:
    mid        = (healthy_min + healthy_max) / 2.0
    half_range = (healthy_max - healthy_min) / 2.0
    if half_range == 0:
        return 1.0
    return 1.0 - abs(raw - mid) / half_range


def _apply_log(values: list[float]) -> list[float]:
    return [math.log(v) if (not math.isnan(v) and v > 0) else float("nan") for v in values]


def _apply_rolling_avg(
    timestamps: list[datetime],
    values:     list[float],
    window_hours: float,
) -> list[float]:
    half_window = timedelta(hours=window_hours / 2.0)
    result = []
    for i, ts in enumerate(timestamps):
        window_vals = [
            values[j]
            for j in range(len(timestamps))
            if abs((timestamps[j] - ts)) <= half_window and not math.isnan(values[j])
        ]
        result.append(sum(window_vals) / len(window_vals) if window_vals else float("nan"))
    return result


def _apply_lag(
    timestamps: list[datetime],
    values:     list[float],
    lag_hours:  float,
) -> tuple[list[datetime], list[float]]:
    """Shift timestamps backward by lag_hours (positive = shift data forward in time)."""
    lag = timedelta(hours=lag_hours)
    return [ts - lag for ts in timestamps], values


def _apply_min_max_normalize(values: list[float]) -> list[float]:
    valid = [v for v in values if not math.isnan(v)]
    if not valid:
        return values
    vmin, vmax = min(valid), max(valid)
    if vmax == vmin:
        return [1.0 if not math.isnan(v) else float("nan") for v in values]
    return [(v - vmin) / (vmax - vmin) if not math.isnan(v) else float("nan") for v in values]


def _fill_missing(
    timestamps: list[datetime],
    values:     list[float],
    strategy:   str,
) -> list[float]:
    result = list(values)
    if strategy == "forward_fill":
        last_valid: float = float("nan")
        for i, v in enumerate(result):
            if not math.isnan(v):
                last_valid = v
            elif not math.isnan(last_valid):
                result[i] = last_valid
    elif strategy == "zero":
        result = [0.0 if math.isnan(v) else v for v in result]
    elif strategy == "interpolate":
        valid_indices = [i for i, v in enumerate(result) if not math.isnan(v)]
        for i in range(len(result)):
            if not math.isnan(result[i]):
                continue
            lo = next((j for j in reversed(valid_indices) if j < i), None)
            hi = next((j for j in valid_indices if j > i),            None)
            if lo is not None and hi is not None:
                t         = (i - lo) / (hi - lo)
                result[i] = result[lo] + t * (result[hi] - result[lo])
            elif lo is not None:
                result[i] = result[lo]
            elif hi is not None:
                result[i] = result[hi]
    # strategy == "skip": leave NaN — those timestamps will be excluded from composite
    return result


# ── Main entry point ───────────────────────────────────────────────────────────

def build_composite_timeseries(
    marker_timeseries: list[dict],
) -> list[dict]:
    """
    Takes per-marker timeseries data and produces a single composite health-score series.

    Each element of marker_timeseries is:
        {
            "config":          dict  (MarkerFeatureConfig-like with module_id, marker_id,
                                      weight, active, transform{type,window_hours,lag_hours},
                                      missing_data),
            "datapoints":      list[dict]  (from read_timeseries; each has "value",
                                            "measured_at", "parsed_timestamp"),
            "zone_boundaries": dict  (healthy_min, healthy_max, vulnerability_margin),
        }

    Returns list of dicts compatible with trajectory_computer.compute_trajectory():
        [{"measured_at": str, "value": float, "data_quality": str, "parsed_timestamp": datetime}, ...]

    Call trajectory_computer with composite_zone_boundaries(vulnerability_margin).
    """
    active_markers = [m for m in marker_timeseries if m["config"].get("active", True)]
    if not active_markers:
        raise ValueError("No active markers in markerset.")

    processed: list[dict] = []

    for m in active_markers:
        config   = m["config"]
        dps      = m["datapoints"]
        zone_bnd = m["zone_boundaries"]

        if not dps:
            logger.warning(
                "Marker %s/%s has no datapoints in the requested timeframe; skipping.",
                config.get("module_id"), config.get("marker_id"),
            )
            continue

        timestamps  = [dp["parsed_timestamp"] for dp in dps]
        raw_values  = [float(dp["value"]) for dp in dps]

        # Apply transform
        transform      = config.get("transform") or {}
        transform_type = transform.get("type", "none")

        if transform_type == "log":
            raw_values = _apply_log(raw_values)
        elif transform_type == "rolling_avg":
            raw_values = _apply_rolling_avg(timestamps, raw_values, transform.get("window_hours", 24.0))
        elif transform_type == "normalize":
            raw_values = _apply_min_max_normalize(raw_values)
        elif transform_type == "lag":
            timestamps, raw_values = _apply_lag(timestamps, raw_values, transform.get("lag_hours", 0.0))
        # "none": pass through

        # Normalize raw → h score using marker-specific zone boundaries
        h_min = zone_bnd["healthy_min"]
        h_max = zone_bnd["healthy_max"]
        h_values = [
            _normalize_h(v, h_min, h_max) if not math.isnan(v) else float("nan")
            for v in raw_values
        ]

        # Handle missing h values
        h_values = _fill_missing(timestamps, h_values, config.get("missing_data", "interpolate"))

        processed.append({
            "timestamps": timestamps,
            "h_values":   h_values,
            "weight":     config.get("weight", 1.0),
        })

    if not processed:
        raise ValueError("All markers had no datapoints after filtering. Cannot build composite.")

    # Union of all timestamps across markers
    all_timestamps: set[datetime] = set()
    for m in processed:
        all_timestamps.update(m["timestamps"])
    sorted_timestamps = sorted(all_timestamps)

    # Build composite at each timestamp
    composite_points = []
    for ts in sorted_timestamps:
        weighted_sum = 0.0
        weight_sum   = 0.0

        for m in processed:
            ts_list = m["timestamps"]
            h_list  = m["h_values"]

            if ts in ts_list:
                idx = ts_list.index(ts)
                h   = h_list[idx]
            else:
                # Linear interpolation across marker's own timestamps
                lo_ts = max((t for t in ts_list if t <= ts), default=None)
                hi_ts = min((t for t in ts_list if t >= ts), default=None)
                if lo_ts is not None and hi_ts is not None and lo_ts != hi_ts:
                    lo_idx = ts_list.index(lo_ts)
                    hi_idx = ts_list.index(hi_ts)
                    frac   = (ts - lo_ts).total_seconds() / (hi_ts - lo_ts).total_seconds()
                    h      = h_list[lo_idx] + frac * (h_list[hi_idx] - h_list[lo_idx])
                elif lo_ts is not None:
                    h = h_list[ts_list.index(lo_ts)]
                elif hi_ts is not None:
                    h = h_list[ts_list.index(hi_ts)]
                else:
                    h = float("nan")

            if not math.isnan(h):
                w             = m["weight"]
                weighted_sum += w * h
                weight_sum   += w

        if weight_sum == 0:
            continue  # no valid data at this timestamp

        composite_h = weighted_sum / weight_sum
        composite_h = max(-1.0, min(1.0, composite_h))   # clamp to [-1, 1]

        composite_points.append({
            "measured_at":      ts.isoformat().replace("+00:00", "Z"),
            "value":            composite_h,
            "data_quality":     "good",
            "parsed_timestamp": ts,
        })

    if not composite_points:
        raise ValueError("Composite timeseries is empty after alignment.")

    return composite_points
