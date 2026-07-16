import math

import pytest

from eagle_swarm_common.coverage import (
    DEFAULT_SECTORS,
    pairwise_minimum_distance,
    plan_coverage_waypoints,
)


def test_same_seed_reproduces_identical_waypoints():
    first = plan_coverage_waypoints(seed=42)
    second = plan_coverage_waypoints(seed=42)
    assert first == second


def test_different_seed_changes_at_least_one_waypoint():
    first = plan_coverage_waypoints(seed=42)
    second = plan_coverage_waypoints(seed=43)
    assert first != second


def test_waypoints_remain_inside_step_and_angular_wedges():
    minimum_step = 2.5
    maximum_step = 3.5
    points = plan_coverage_waypoints(
        seed=1234,
        minimum_step=minimum_step,
        maximum_step=maximum_step,
    )
    for robot_id, point in points.items():
        sector = DEFAULT_SECTORS[robot_id]
        dx = point[0] - sector.home_x
        dy = point[1] - sector.home_y
        distance = math.hypot(dx, dy)
        angle = math.degrees(math.atan2(dy, dx))
        assert minimum_step <= distance <= maximum_step
        assert sector.min_angle_deg <= angle <= sector.max_angle_deg


def test_pairwise_safety_gate_is_enforced():
    points = plan_coverage_waypoints(
        seed=2180021560,
        minimum_pairwise_separation=2.8,
    )
    assert pairwise_minimum_distance(points) >= 2.8


def test_invalid_step_range_is_rejected():
    with pytest.raises(ValueError):
        plan_coverage_waypoints(seed=1, minimum_step=4.0, maximum_step=3.0)
