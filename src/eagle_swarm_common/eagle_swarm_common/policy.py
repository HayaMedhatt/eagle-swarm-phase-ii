"""Pure swarm decision policies shared by aerial and ground units.

Keeping the cost and election rules free of ROS dependencies makes them easy to
unit-test and demonstrates the Open/Closed design used by the Ground Relay.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


ROLE_PENALTIES = {
    "worker": 0.0,
    "scout": 2.0,
    "ground_relay": 5.0,
    "coordinator": 8.0,
}

ROLE_PRIORITIES = {
    "ground_relay": 1,
    "worker": 2,
    "scout": 3,
    "coordinator": 4,
}

LEADER_INELIGIBLE_STATES = {
    "RTB",
    "LANDING",
    "LANDED",
    "SHUTDOWN",
    "SAFE_HOLD",
    "WAIT_FCU",
    "WAIT_POSE",
}

TASK_ELIGIBLE_STATES = {"ACTIVE", "SECTOR_READY", "ARRIVED"}


@dataclass(frozen=True)
class CostBreakdown:
    distance: float
    battery_penalty: float
    role_penalty: float
    link_penalty: float
    total: float


def compute_task_cost(
    distance: float,
    battery_pct: float,
    role: str,
    link_quality: float,
) -> CostBreakdown:
    """Return the assessment's explainable Contract-Net cost components."""
    distance_cost = max(0.0, float(distance))
    battery = min(100.0, max(0.0, float(battery_pct)))
    link = min(1.0, max(0.0, float(link_quality)))
    battery_penalty = (100.0 - battery) * 0.4
    role_penalty = ROLE_PENALTIES.get(role, 10.0)
    link_penalty = (1.0 - link) * 30.0
    total = distance_cost + battery_penalty + role_penalty + link_penalty
    return CostBreakdown(
        distance=distance_cost,
        battery_penalty=battery_penalty,
        role_penalty=role_penalty,
        link_penalty=link_penalty,
        total=total,
    )


def election_score(
    battery_pct: float,
    link_quality: float,
    capability: float,
    role: str,
) -> float:
    """Weighted battery/link/capability score with coordinator preference."""
    role_bonus = 8.0 if role == "coordinator" else 0.0
    return (
        float(battery_pct) * 0.5
        + float(link_quality) * 30.0
        + float(capability) * 20.0
        + role_bonus
    )


def lower_priority_robot(
    robot_a: str,
    role_a: str,
    state_a: str,
    robot_b: str,
    role_b: str,
    state_b: str,
) -> str:
    """Choose which robot yields under the deterministic separation rule."""
    # Preserve an executing robot when the other vehicle is merely holding or
    # patrolling.  Otherwise use role priority and then a stable ID tie-break.
    exec_a = state_a == "EXECUTING"
    exec_b = state_b == "EXECUTING"
    if exec_a != exec_b:
        return robot_b if exec_a else robot_a

    priority_a = ROLE_PRIORITIES.get(role_a, 0)
    priority_b = ROLE_PRIORITIES.get(role_b, 0)
    if priority_a != priority_b:
        return robot_a if priority_a < priority_b else robot_b
    return max(robot_a, robot_b)


def best_bid(bids: Iterable[object]):
    """Select the lowest total cost with a deterministic bidder-ID tie-break."""
    return min(bids, key=lambda bid: (float(bid.total_cost), str(bid.bidder_id)))


def choose_leader(candidates: Iterable[object]):
    """Choose the highest-scoring leader with a stable robot-ID tie-break.

    Candidate objects must expose battery, link_quality, capability, role and
    robot_id attributes.  Returning ``None`` for an empty iterable makes the
    policy easy to reuse in both ROS and offline tests.
    """
    ranked = sorted(
        candidates,
        key=lambda candidate: (
            -election_score(
                candidate.battery,
                candidate.link_quality,
                candidate.capability,
                candidate.role,
            ),
            str(candidate.robot_id),
        ),
    )
    return ranked[0] if ranked else None
