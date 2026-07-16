"""Replicated swarm coordination: membership, election and Contract Net.

One instance is launched for each participating robot.  Every replica observes
the same DDS traffic and computes the same deterministic leader.  Only the
replica owned by the elected leader publishes awards.  This removes the single
central allocator failure point while retaining an auditable ROS 2 graph.
"""

from __future__ import annotations

from typing import Dict, Tuple

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

from eagle_swarm_msgs.msg import (
    Bid,
    FaultEvent,
    Heartbeat,
    LeaderState,
    TaskAward,
    TargetBeacon,
)
from eagle_swarm_common.policy import (
    LEADER_INELIGIBLE_STATES,
    TASK_ELIGIBLE_STATES,
    best_bid,
    choose_leader,
    election_score,
)


def retained_qos(depth: int = 10) -> QoSProfile:
    return QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
    )


class Coordinator(Node):
    """A deterministic coordinator replica owned by one swarm member."""

    def __init__(self) -> None:
        super().__init__("swarm_coordinator")
        self.declare_parameter("owner_id", "")
        self.declare_parameter("bid_window_sec", 2.5)
        self.declare_parameter("heartbeat_timeout_sec", 3.2)
        self.declare_parameter("initial_election_timeout_sec", 15.0)
        self.declare_parameter(
            "expected_member_ids",
            ["scout_1", "worker_1", "relay_1", "ground_relay"],
        )
        self.owner_id = str(self.get_parameter("owner_id").value)
        self.bid_window_sec = float(self.get_parameter("bid_window_sec").value)
        self.heartbeat_timeout_sec = float(
            self.get_parameter("heartbeat_timeout_sec").value
        )
        self.initial_election_timeout_sec = float(
            self.get_parameter("initial_election_timeout_sec").value
        )
        self.expected_member_ids = set(
            str(item)
            for item in self.get_parameter("expected_member_ids").value
        )

        self.robots: Dict[str, Tuple[Heartbeat, rclpy.time.Time]] = {}
        self.bids: Dict[str, Dict[str, Bid]] = {}
        self.targets: Dict[str, TargetBeacon] = {}
        self.target_seen_at: Dict[str, rclpy.time.Time] = {}
        self.assignments: Dict[str, str] = {}
        self.completed_targets = set()
        self.offline_since: Dict[str, rclpy.time.Time] = {}
        self.offline_reported = set()
        self.leader = ""
        self.epoch = 0
        self.last_reason = "startup"
        self.disabled = False
        self.started_at = self.get_clock().now()
        self.initial_membership_announced = False

        self.create_subscription(Heartbeat, "/swarm/heartbeat", self.on_hb, 50)
        self.create_subscription(Bid, "/swarm/bids", self.on_bid, 50)
        self.create_subscription(
            String, "/swarm/fault_command", self.on_fault_command, 20
        )
        self.create_subscription(
            TargetBeacon,
            "/swarm/target_beacon",
            self.on_target,
            retained_qos(),
        )
        # All replicas consume the retained award so a newly elected replica
        # immediately inherits the current assignment state.
        self.create_subscription(
            TaskAward,
            "/swarm/task_award",
            self.on_award_seen,
            retained_qos(),
        )
        self.award_pub = self.create_publisher(
            TaskAward, "/swarm/task_award", retained_qos()
        )
        self.beacon_pub = self.create_publisher(
            TargetBeacon, "/swarm/target_beacon", retained_qos()
        )
        self.leader_pub = self.create_publisher(
            LeaderState, "/swarm/leader", retained_qos()
        )
        self.fault_pub = self.create_publisher(FaultEvent, "/swarm/faults", 20)
        self.create_timer(0.5, self.evaluate)
        self.get_logger().info(
            f"Coordinator replica online owner={self.owner_id or 'central-fallback'}"
        )

    def now_msg(self):
        return self.get_clock().now().to_msg()

    def is_authority(self) -> bool:
        return (
            not self.disabled
            and (not self.owner_id or self.owner_id == self.leader)
        )

    def on_fault_command(self, msg: String) -> None:
        """Stop the replica colocated with a simulated failed robot."""
        try:
            fault, target = msg.data.split(":", 1)
        except ValueError:
            return
        if fault not in {"shutdown", "coordinator_loss"} or target not in {self.owner_id, "all"}:
            return
        self.disabled = True
        self.get_logger().error(
            f"Coordinator replica owner={self.owner_id} stopped by fault injection"
        )

    def publish_fault(
        self,
        fault_type: str,
        robot_id: str,
        severity: int,
        action: str,
        recovery_time: float,
    ) -> None:
        if not self.is_authority():
            return
        msg = FaultEvent()
        msg.fault_type = fault_type
        msg.robot_id = robot_id
        msg.severity = int(severity)
        msg.action = action
        msg.recovery_time = float(max(0.0, recovery_time))
        msg.stamp = self.now_msg()
        self.fault_pub.publish(msg)

    def on_hb(self, msg: Heartbeat) -> None:
        now = self.get_clock().now()
        if msg.robot_id in self.offline_since:
            outage = (now - self.offline_since.pop(msg.robot_id)).nanoseconds / 1e9
            self.offline_reported.discard(msg.robot_id)
            self.publish_fault(
                "heartbeat_restored",
                msg.robot_id,
                1,
                "member rejoined DDS membership and is eligible by state",
                outage,
            )
            if self.is_authority():
                self.get_logger().warn(
                    f"RECOVER {msg.robot_id} heartbeat after {outage:.2f}s"
                )
        self.robots[msg.robot_id] = (msg, now)

    def on_bid(self, msg: Bid) -> None:
        if msg.target_id in self.assignments or msg.target_id in self.completed_targets:
            return
        self.bids.setdefault(msg.target_id, {})[msg.bidder_id] = msg

    def on_target(self, msg: TargetBeacon) -> None:
        if msg.confidence < 0.75 or msg.target_id in self.completed_targets:
            return
        is_new = msg.target_id not in self.targets
        self.targets[msg.target_id] = msg
        if is_new:
            self.target_seen_at[msg.target_id] = self.get_clock().now()
            if self.is_authority():
                self.get_logger().info(
                    f"Confirmed target {msg.target_id}; opening "
                    f"{self.bid_window_sec:.1f}s bid window"
                )

    def on_award_seen(self, msg: TaskAward) -> None:
        if msg.target_id in self.completed_targets:
            return
        self.assignments[msg.target_id] = msg.winner_id
        self.bids.pop(msg.target_id, None)

    @staticmethod
    def election_score(hb: Heartbeat) -> float:
        return election_score(
            hb.battery,
            hb.link_quality,
            hb.capability,
            hb.role,
        )

    def publish_leader(self) -> None:
        if not self.is_authority():
            return
        msg = LeaderState()
        msg.leader_id = self.leader
        msg.reason = self.last_reason
        msg.election_epoch = self.epoch
        msg.stamp = self.now_msg()
        self.leader_pub.publish(msg)

    def evaluate(self) -> None:
        if self.disabled:
            return
        now = self.get_clock().now()
        alive = []
        alive_by_id: Dict[str, Heartbeat] = {}

        for robot_id, (heartbeat, received_at) in self.robots.items():
            age = (now - received_at).nanoseconds / 1e9
            if age < self.heartbeat_timeout_sec and heartbeat.state != "SHUTDOWN":
                alive.append(heartbeat)
                alive_by_id[robot_id] = heartbeat
            elif robot_id not in self.offline_since:
                self.offline_since[robot_id] = received_at

        operational = [
            hb for hb in alive if hb.state not in LEADER_INELIGIBLE_STATES
        ]
        # Avoid noisy transient leaders while DDS membership is still forming.
        # The first election waits for all expected members, with a bounded
        # timeout so a genuinely absent unit cannot block startup forever.
        membership_ready = self.expected_member_ids.issubset(alive_by_id)
        startup_elapsed = (now - self.started_at).nanoseconds / 1e9
        if not self.leader and not membership_ready:
            if startup_elapsed < self.initial_election_timeout_sec:
                return
            if not self.initial_membership_announced:
                missing = sorted(self.expected_member_ids - set(alive_by_id))
                self.get_logger().warn(
                    "Initial election timeout; proceeding without "
                    f"members={missing}"
                )
                self.initial_membership_announced = True
        elif membership_ready and not self.initial_membership_announced:
            self.get_logger().info(
                "Initial DDS membership stable; starting deterministic election"
            )
            self.initial_membership_announced = True

        selected = choose_leader(operational)
        new_leader = selected.robot_id if selected is not None else ""
        if new_leader != self.leader:
            old_leader = self.leader
            self.leader = new_leader
            self.epoch += 1
            self.last_reason = (
                "heartbeat timeout/weighted battery-link-capability score; "
                f"previous={old_leader or 'none'}"
            )
            if self.is_authority():
                self.get_logger().warn(
                    f"LEADER {old_leader or 'none'} -> {new_leader or 'none'} "
                    f"epoch={self.epoch}"
                )
                if old_leader and new_leader:
                    old_hb = alive_by_id.get(old_leader)
                    if old_hb is None:
                        last_seen = self.robots.get(old_leader, (None, now))[1]
                        recovery = (now - last_seen).nanoseconds / 1e9
                        self.publish_fault(
                            "coordinator_loss_recovery",
                            old_leader,
                            2,
                            f"new leader elected after timeout: {new_leader}",
                            recovery,
                        )
                    elif old_hb.state in LEADER_INELIGIBLE_STATES:
                        self.publish_fault(
                            "leader_handover",
                            old_leader,
                            1,
                            f"leader state={old_hb.state}; authority moved to {new_leader}",
                            0.0,
                        )
        self.publish_leader()

        # Publish one measured timeout event when a member disappears.
        for robot_id, started in list(self.offline_since.items()):
            if robot_id in alive_by_id or robot_id in self.offline_reported:
                continue
            detection = (now - started).nanoseconds / 1e9
            if detection >= self.heartbeat_timeout_sec:
                self.publish_fault(
                    "heartbeat_timeout",
                    robot_id,
                    2,
                    "member excluded; active task released for re-auction",
                    detection,
                )
                self.offline_reported.add(robot_id)

        unavailable_states = LEADER_INELIGIBLE_STATES
        for target_id, winner_id in list(self.assignments.items()):
            hb = alive_by_id.get(winner_id)

            if hb is not None and hb.state == "ARRIVED":
                self.completed_targets.add(target_id)
                del self.assignments[target_id]
                self.bids.pop(target_id, None)
                if self.is_authority():
                    self.get_logger().info(
                        f"COMPLETE {target_id}: winner {winner_id} confirmed ARRIVED"
                    )
                continue

            unavailable = hb is None or hb.state in unavailable_states
            if unavailable:
                if self.is_authority():
                    self.get_logger().warn(
                        f"REASSIGN {target_id}: previous winner "
                        f"{winner_id} unavailable"
                    )
                    self.publish_fault(
                        "task_reassignment",
                        winner_id,
                        2,
                        f"target {target_id} re-opened for Contract-Net bidding",
                        0.0,
                    )
                del self.assignments[target_id]
                self.bids.pop(target_id, None)
                self.target_seen_at[target_id] = now
                beacon = self.targets.get(target_id)
                if beacon is not None and self.is_authority():
                    self.beacon_pub.publish(beacon)

        alive_ids = set(alive_by_id)
        for target_id, offers in list(self.bids.items()):
            if target_id in self.assignments or target_id in self.completed_targets:
                continue
            seen_at = self.target_seen_at.get(target_id, now)
            elapsed = (now - seen_at).nanoseconds / 1e9
            if elapsed < self.bid_window_sec:
                continue

            valid = [
                bid
                for bid in offers.values()
                if bid.bidder_id in alive_ids
                and alive_by_id[bid.bidder_id].state in TASK_ELIGIBLE_STATES
            ]
            if not valid or not self.is_authority():
                continue

            winner = best_bid(valid)
            award = TaskAward()
            award.target_id = target_id
            award.winner_id = winner.bidder_id
            award.assigned_by = self.leader or "distributed_fallback"
            award.winning_cost = float(winner.total_cost)
            award.stamp = self.now_msg()
            # Store before publish to prevent a duplicate evaluation cycle.
            self.assignments[target_id] = winner.bidder_id
            self.bids.pop(target_id, None)
            self.award_pub.publish(award)
            self.get_logger().info(
                f"ALLOCATE {target_id}->{winner.bidder_id} "
                f"cost={winner.total_cost:.2f}; bids={len(valid)}; "
                f"authority={self.owner_id or 'central-fallback'}"
            )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = Coordinator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
