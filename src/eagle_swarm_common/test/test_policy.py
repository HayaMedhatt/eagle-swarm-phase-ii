from eagle_swarm_common.policy import (
    best_bid,
    choose_leader,
    compute_task_cost,
    election_score,
    lower_priority_robot,
)


class BidStub:
    def __init__(self, bidder_id, total_cost):
        self.bidder_id = bidder_id
        self.total_cost = total_cost


def test_contract_net_cost_is_sum_of_explainable_components():
    cost = compute_task_cost(10.0, 90.0, "worker", 0.8)
    assert cost.distance == 10.0
    assert cost.battery_penalty == 4.0
    assert cost.role_penalty == 0.0
    assert round(cost.link_penalty, 6) == 6.0
    assert round(cost.total, 6) == 20.0


def test_coordinator_role_gets_election_bonus():
    normal = election_score(90.0, 0.9, 0.8, "worker")
    coordinator = election_score(90.0, 0.9, 0.8, "coordinator")
    assert coordinator - normal == 8.0


def test_bid_tie_break_is_deterministic():
    winner = best_bid([BidStub("worker_1", 12.0), BidStub("scout_1", 12.0)])
    assert winner.bidder_id == "scout_1"


def test_separation_rule_preserves_executing_robot():
    yielding = lower_priority_robot(
        "worker_1", "worker", "EXECUTING",
        "relay_1", "coordinator", "ACTIVE",
    )
    assert yielding == "relay_1"


class HeartbeatStub:
    def __init__(self, robot_id, battery, link_quality, capability, role):
        self.robot_id = robot_id
        self.battery = battery
        self.link_quality = link_quality
        self.capability = capability
        self.role = role


def test_leader_selection_uses_score_then_stable_id():
    relay = HeartbeatStub("relay_1", 90.0, 0.96, 0.93, "coordinator")
    scout = HeartbeatStub("scout_1", 100.0, 0.92, 0.90, "scout")
    assert choose_leader([scout, relay]).robot_id == "relay_1"


def test_leader_selection_empty_returns_none():
    assert choose_leader([]) is None


def test_cost_inputs_are_clamped_for_defensive_safety():
    cost = compute_task_cost(-5.0, 120.0, "worker", 1.5)
    assert cost.distance == 0.0
    assert cost.battery_penalty == 0.0
    assert cost.link_penalty == 0.0
