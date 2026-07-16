"""Deterministic, constrained coverage-sector planning.

The planner deliberately separates *randomness* from *safety*.  Each member
samples a waypoint inside its role-specific angular wedge, while a pairwise
separation gate rejects unsafe samples.  The logged seed reproduces any run.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Dict, Mapping, Tuple


Point2D = Tuple[float, float]


@dataclass(frozen=True)
class CoverageSector:
    """A launch point and an allowed angular wedge in the mission frame."""

    home_x: float
    home_y: float
    min_angle_deg: float
    max_angle_deg: float


DEFAULT_SECTORS: Mapping[str, CoverageSector] = {
    "scout_1": CoverageSector(0.0, 0.0, -15.0, 15.0),
    "worker_1": CoverageSector(0.0, 3.0, 45.0, 70.0),
    "relay_1": CoverageSector(0.0, -3.0, -70.0, -45.0),
}


def pairwise_minimum_distance(points: Mapping[str, Point2D]) -> float:
    """Return the minimum 2-D distance, or infinity for fewer than 2 points."""
    items = sorted(points.items())
    if len(items) < 2:
        return math.inf
    minimum = math.inf
    for index, (_, point_a) in enumerate(items):
        for _, point_b in items[index + 1 :]:
            minimum = min(
                minimum,
                math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1]),
            )
    return minimum


def plan_coverage_waypoints(
    seed: int,
    minimum_step: float = 2.5,
    maximum_step: float = 3.5,
    minimum_pairwise_separation: float = 2.8,
    sectors: Mapping[str, CoverageSector] = DEFAULT_SECTORS,
    max_attempts: int = 200,
) -> Dict[str, Point2D]:
    """Sample reproducible waypoints that remain safely separated.

    Args:
        seed: Seed recorded in the mission log for exact replay.
        minimum_step: Minimum radial displacement from each launch point.
        maximum_step: Maximum radial displacement from each launch point.
        minimum_pairwise_separation: Required separation between sampled goals.
        sectors: Per-robot launch point and angular wedge.
        max_attempts: Bounded retry count before declaring configuration error.
    """
    if minimum_step <= 0.0 or maximum_step < minimum_step:
        raise ValueError("coverage step range must satisfy 0 < min <= max")
    if minimum_pairwise_separation < 0.0:
        raise ValueError("minimum_pairwise_separation cannot be negative")
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    if not sectors:
        raise ValueError("at least one coverage sector is required")

    rng = random.Random(int(seed))
    for _ in range(max_attempts):
        waypoints: Dict[str, Point2D] = {}
        for robot_id, sector in sorted(sectors.items()):
            if sector.max_angle_deg < sector.min_angle_deg:
                raise ValueError(f"invalid angular wedge for {robot_id}")
            distance = rng.uniform(minimum_step, maximum_step)
            angle = math.radians(
                rng.uniform(sector.min_angle_deg, sector.max_angle_deg)
            )
            waypoints[robot_id] = (
                sector.home_x + distance * math.cos(angle),
                sector.home_y + distance * math.sin(angle),
            )

        if pairwise_minimum_distance(waypoints) >= minimum_pairwise_separation:
            return waypoints

    raise RuntimeError(
        "unable to sample safely separated coverage waypoints; "
        "relax the separation or widen the sectors"
    )
