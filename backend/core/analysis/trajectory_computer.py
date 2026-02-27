# Receives datapoints and zone parameters,  runs the 2-derivative analysis, and returns a fully copmuted dict. PURELY COMPUTATIONAL, 
# meaning that it just does the math with no database calls or API dependencies. 

# f(x) — health score h(raw) classified into a zone (Non-pathology / Vulnerability / Pathology)
# f'(x)  — first derivative: direction of change (Improving / Stable / Worsening)
# f''(x) — second derivative: curvature (Accelerating / Steady / Decelerating)

# Raw marker values are first normalized to a scalar health-score via a u-shaped transform:
#   mid = (healthy_min + healthy_max) / 2
#   half_range = (healthy_max - healthy_min) / 2
#   h(raw)= 1 - |raw - mid| / half_range

#   h = 1.0  when raw = mid (optimal centre of healthy range)
#   h = 0.0  when raw = healthy_min or healthy_max (at the healthy edge)
#   h < 0    when raw is outside the healthy range

# Because h>0 is always healthier (reglardless of whether the underlying marker should be high or low), f'(x) > always means "improving"
# without any per-marker directionality. The polynomical is fitted to h-values; all derivatives and zone assignments operate in h-space.

# The 3 sign-classes combine into one of 27 discrete trajectory states. 


import numpy as np
from datetime import datetime

# Constants
DERIVATIVE_ZERO_THRESHOLD = 0.001
IMAGINARY_TOLERANCE = 1e-6


# Normalization
def _normalize(raw: float, mid: float, half_range: float) -> float:
    return 1.0 - abs(raw - mid) / half_range


# Zone Assignment 
def _assign_zone_from_score(h: float, vulnerability_margin: float) -> str:
    if h > vulnerability_margin:
        return "non_pathology"
    if h < -vulnerability_margin:
        return "pathology"
    return "vulnerability"


# Derivative Sign Classification
def _sign_class(value: float) -> int:
    if value > DERIVATIVE_ZERO_THRESHOLD:
        return 1
    if value < -DERIVATIVE_ZERO_THRESHOLD:
        return -1
    return 0


# Trajectory state number, offset into the 27-state table contributed by each zone.
_ZONE_OFFSET = {1: 0, 0: 9, -1: 18}
_FP_OFFSET = {1: 0, 0: 3, -1: 6}
_FPP_INDEX = {1: 1, 0: 2, -1: 3}

def _trajectory_state(zone: str, fp_sign: int, fpp_sign: int) -> int:
    zone_sign = {"non_pathology": 1, "vulnerability": 0, "pathology": -1}[zone]
    return _ZONE_OFFSET[zone_sign] + _FP_OFFSET[fp_sign] + _FPP_INDEX[fpp_sign]


# Time-to-zone-transition
def _time_to_transition(
    coeffs: np.ndarray,
    vulnerability_margin: float,
    x_current: float,
) -> float | None:
    
    candidate_times = []
    for boundary_value in (vulnerability_margin, 0.0, -vulnerability_margin):
        shifted = coeffs.copy()
        shifted[-1] -= boundary_value
        roots = np.roots(shifted)
        for root in roots:
            if abs(root.imag) > IMAGINARY_TOLERANCE:
                continue
            t = root.real
            if t > x_current:
                candidate_times.append(t)
    return float(min(candidate_times)) if candidate_times else None


# Compute Trajectory Mega Function (puts everything together in 6 steps)

def compute_trajectory(
    data_points: list[dict],
    zone_boundaries: dict,
    polynomial_degree: int,
) -> dict:

    # ── Guard: need enough points to fit the requested polynomial degree ─────
    min_points = polynomial_degree + 1
    if len(data_points) < min_points:
        raise ValueError(
            f"A degree-{polynomial_degree} polynomial requires at least {min_points} "
            f"data points, but only {len(data_points)} were provided."
        )

    # Step 1: Extract parameters and normalization constants
    healthy_min = zone_boundaries["healthy_min"]
    healthy_max = zone_boundaries["healthy_max"]
    vulnerability_margin = zone_boundaries["vulnerability_margin"]

    mid        = (healthy_min + healthy_max) / 2.0
    half_range = (healthy_max - healthy_min) / 2.0

    # ── Step 2: Build x (time) and y (health score) arrays
    t0: datetime = data_points[0]["parsed_timestamp"]

    x_hours: list[float] = [
        (dp["parsed_timestamp"] - t0).total_seconds() / 3600.0
        for dp in data_points
    ]
    h_values: list[float] = [
        _normalize(dp["value"], mid, half_range)
        for dp in data_points
    ]

    x_arr = np.array(x_hours, dtype=float)
    y_arr = np.array(h_values, dtype=float)

    # Step 3: Fit the polynomial
    coeffs = np.polyfit(x_arr, y_arr, polynomial_degree)

    # Step 4: Derive first and second derivative polynomials
    coeffs_p1 = np.polyder(coeffs, 1)
    coeffs_p2 = np.polyder(coeffs, 2)

    # Step 5: Compute per-datapoint results
    result_points = []

    for i, dp in enumerate(data_points):
        x = x_hours[i]

        # The health score for this data point, computed from the RAW value.
        health_score = h_values[i]

        # Evaluate the fitted polynomial at this x-coordinate (h-units).
        fitted_value = float(np.polyval(coeffs, x))

        # Evaluate first and second derivatives at x (h-units/hour).
        f_prime        = float(np.polyval(coeffs_p1, x))
        f_double_prime = float(np.polyval(coeffs_p2, x))

        # Assign zone from the health score of the RAW measured value.
        zone = _assign_zone_from_score(health_score, vulnerability_margin)

        # Classify derivative magnitudes into ternary sign classes.
        fp_sign  = _sign_class(f_prime)
        fpp_sign = _sign_class(f_double_prime)

        # Look up the integer trajectory state (1–27).
        state = _trajectory_state(zone, fp_sign, fpp_sign)

        # Find the nearest future time at which the h-polynomial crosses a boundary.
        transition = _time_to_transition(coeffs, vulnerability_margin, x)

        result_points.append({
            "timestamp":                dp["timestamp"],
            "x_hours":                  round(x, 6),
            "raw_value":                dp["value"],
            "data_quality":             dp.get("data_quality", "good"),
            "health_score":             round(health_score, 6),
            "fitted_value":             round(fitted_value, 6),
            "zone":                     zone,
            "f_prime":                  round(f_prime, 6),
            "f_double_prime":           round(f_double_prime, 6),
            "trajectory_state":         state,
            "time_to_transition_hours": round(transition, 4) if transition is not None else None,
        })

    # ── Step 6: Assemble fit_metadata for the frontend ────────────────────────
    #
    # The Svelte TrajectoryChart component evaluates the polynomial at 100+
    # equally-spaced x-values client-side to draw the smooth fitted curve.
    # It needs coefficients, t0_iso, polynomial degree, normalization parameters, and zone-boundaries
    t0_iso = t0.isoformat().replace("+00:00", "Z")

    fit_metadata = {
        "coefficients":      coeffs.tolist(),
        "t0_iso":            t0_iso,
        "polynomial_degree": polynomial_degree,
        "normalization": {
            "healthy_min": healthy_min,
            "healthy_max": healthy_max,
            "mid":         mid,
            "half_range":  half_range,
        },
        "zone_boundaries": {
            "vulnerability_margin": vulnerability_margin,
        },
    }

    return {
        "datapoints":  result_points,
        "fit_metadata": fit_metadata,
    }