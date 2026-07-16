"""Reusable ROS 2 swarm agent for aerial and ground simulation members."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import rclpy
from geometry_msgs.msg import Pose
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

from eagle_swarm_common.policy import TASK_ELIGIBLE_STATES, compute_task_cost
from eagle_swarm_msgs.msg import Bid, FaultEvent, Heartbeat, TargetBeacon, TaskAward


def retained_qos(depth: int = 10) -> QoSProfile:
    return QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
    )


@dataclass
class Target:
    target_id: str
    x: float
    y: float
    confidence: float


class SwarmAgent(Node):
    """Open/Closed agent with heartbeat, bidding, RTB and fault recovery."""

    def __init__(self) -> None:
        super().__init__("swarm_agent")
        defaults = [
            ("robot_id", "scout_1"),
            ("role", "scout"),
            ("x", 0.0),
            ("y", 0.0),
            ("battery", 100.0),
            ("link_quality", 1.0),
            ("capability", 0.8),
            ("drain_rate", 0.20),
            ("reserve_threshold", 25.0),
        ]
        for name, default in defaults:
            self.declare_parameter(name, default)

        self.robot_id = str(self.get_parameter("robot_id").value)
        self.role = str(self.get_parameter("role").value)
        self.x = float(self.get_parameter("x").value)
        self.y = float(self.get_parameter("y").value)
        self.home: Tuple[float, float] = (self.x, self.y)
        self.battery = float(self.get_parameter("battery").value)
        self.link_quality = float(self.get_parameter("link_quality").value)
        self.capability = float(self.get_parameter("capability").value)
        self.drain_rate = float(self.get_parameter("drain_rate").value)
        self.reserve = float(self.get_parameter("reserve_threshold").value)

        self.state = "ACTIVE"
        self.gps_ok = True
        self.comms_ok = True
        self.assigned_target: Optional[str] = None
        self.targets: Dict[str, Target] = {}
        self.cruise_speed = 0.8
        self.nav_goal: Optional[Tuple[float, float]] = None
        self.nav_kind = ""
        self.pre_hold_state = "ACTIVE"
        self.fault_started_ns: Dict[str, int] = {}

        self.hb_pub = self.create_publisher(Heartbeat, "/swarm/heartbeat", 20)
        self.bid_pub = self.create_publisher(Bid, "/swarm/bids", 20)
        self.fault_pub = self.create_publisher(FaultEvent, "/swarm/faults", 20)
        self.create_subscription(
            TargetBeacon, "/swarm/target_beacon", self.on_beacon, retained_qos()
        )
        self.create_subscription(
            TaskAward, "/swarm/task_award", self.on_award, retained_qos()
        )
        self.create_subscription(String, "/swarm/fault_command", self.on_fault, 20)
        self.create_subscription(
            String, "/swarm/mission_command", self.on_mission_command, 20
        )
        self.create_subscription(String, "/swarm/role_command", self.on_role_command, 20)
        self.create_timer(1.0, self.tick)
        self.get_logger().info(f"{self.robot_id} online role={self.role}")

    def now(self):
        return self.get_clock().now().to_msg()

    def pose(self) -> Pose:
        pose = Pose()
        pose.position.x = self.x
        pose.position.y = self.y
        pose.orientation.w = 1.0
        return pose

    def begin_fault(self, fault_type: str) -> None:
        self.fault_started_ns.setdefault(
            fault_type, self.get_clock().now().nanoseconds
        )

    def finish_fault(
        self, fault_type: str, severity: int, action: str
    ) -> float:
        start = self.fault_started_ns.pop(fault_type, None)
        recovery = 0.0
        if start is not None:
            recovery = (self.get_clock().now().nanoseconds - start) / 1e9
        self.report_fault(fault_type, severity, action, recovery)
        return recovery

    def publish_heartbeat(self) -> None:
        if not self.comms_ok or self.state == "SHUTDOWN":
            return
        msg = Heartbeat()
        msg.robot_id = self.robot_id
        msg.role = self.role
        msg.state = self.state
        msg.battery = float(self.battery)
        msg.pose = self.pose()
        msg.link_quality = float(self.link_quality)
        msg.capability = float(self.capability)
        msg.gps_ok = self.gps_ok
        msg.stamp = self.now()
        self.hb_pub.publish(msg)

    def tick(self) -> None:
        if self.state == "SHUTDOWN":
            return

        moving = self.state in {"EXECUTING", "COVERAGE"}
        motion_factor = 1.0 if moving else 0.25
        self.battery = max(0.0, self.battery - self.drain_rate * motion_factor)

        if moving and self.nav_goal is not None:
            goal_x, goal_y = self.nav_goal
            dx = goal_x - self.x
            dy = goal_y - self.y
            distance = math.hypot(dx, dy)
            if distance <= 0.35:
                self.x = goal_x
                self.y = goal_y
                if self.nav_kind == "target":
                    self.state = "ARRIVED"
                    self.get_logger().info(
                        f"ARRIVED {self.assigned_target} at ({self.x:.2f}, {self.y:.2f})"
                    )
                else:
                    self.state = "SECTOR_READY"
                    self.get_logger().info(
                        f"SECTOR READY at ({self.x:.2f}, {self.y:.2f})"
                    )
            else:
                step = min(self.cruise_speed, distance)
                self.x += step * dx / distance
                self.y += step * dy / distance

        if self.battery <= self.reserve and self.state not in {
            "RTB",
            "LANDED",
            "SHUTDOWN",
        }:
            self.begin_fault("critical_battery")
            self.state = "RTB"
            self.assigned_target = None
            self.nav_goal = self.home
            self.nav_kind = "rtb"
            self.report_fault(
                "critical_battery",
                2,
                "reserve threshold detected; RTB initiated and task released",
                0.0,
            )

        if self.state == "RTB":
            dx = self.home[0] - self.x
            dy = self.home[1] - self.y
            distance = math.hypot(dx, dy)
            if distance < 0.4:
                self.x, self.y = self.home
                self.state = "LANDED"
                recovery = self.finish_fault(
                    "critical_battery",
                    1,
                    "returned to base and landed",
                )
                self.get_logger().warn(
                    f"RTB COMPLETE in {recovery:.2f}s"
                )
            else:
                step = min(self.cruise_speed, distance)
                self.x += step * dx / distance
                self.y += step * dy / distance

        self.publish_heartbeat()

    def on_beacon(self, msg: TargetBeacon) -> None:
        target = Target(
            target_id=msg.target_id,
            x=float(msg.position.x),
            y=float(msg.position.y),
            confidence=float(msg.confidence),
        )
        self.targets[msg.target_id] = target
        if self.comms_ok and self.state in TASK_ELIGIBLE_STATES:
            self.publish_bid(target)

    def bid_for_cached_targets(self) -> None:
        if not self.comms_ok or self.state not in TASK_ELIGIBLE_STATES:
            return
        for target in self.targets.values():
            self.publish_bid(target)

    def publish_bid(self, target: Target) -> None:
        if not self.comms_ok:
            return
        distance = math.hypot(target.x - self.x, target.y - self.y)
        cost = compute_task_cost(
            distance, self.battery, self.role, self.link_quality
        )
        bid = Bid()
        bid.bidder_id = self.robot_id
        bid.target_id = target.target_id
        bid.distance_cost = float(cost.distance)
        bid.battery_penalty = float(cost.battery_penalty)
        bid.role_penalty = float(cost.role_penalty)
        bid.link_penalty = float(cost.link_penalty)
        bid.total_cost = float(cost.total)
        bid.eta = float(distance / 2.0)
        bid.battery_after = float(max(0.0, self.battery - distance * 0.25))
        bid.stamp = self.now()
        self.bid_pub.publish(bid)
        self.get_logger().info(
            f"BID {target.target_id}: distance={cost.distance:.2f} "
            f"battery={cost.battery_penalty:.2f} role={cost.role_penalty:.2f} "
            f"link={cost.link_penalty:.2f} total={cost.total:.2f}"
        )

    def on_award(self, msg: TaskAward) -> None:
        if not self.comms_ok:
            return
        if msg.winner_id != self.robot_id:
            return
        target = self.targets.get(msg.target_id)
        if target is None:
            self.get_logger().error(
                f"Cannot execute {msg.target_id}: target position unavailable"
            )
            return
        if self.state not in TASK_ELIGIBLE_STATES:
            self.get_logger().warn(
                f"Ignoring award for {msg.target_id} while state={self.state}"
            )
            return
        self.assigned_target = msg.target_id
        self.nav_goal = (target.x, target.y)
        self.nav_kind = "target"
        self.state = "EXECUTING"
        self.get_logger().info(
            f"AWARD {msg.target_id} cost={msg.winning_cost:.2f}"
        )

    def on_fault(self, msg: String) -> None:
        try:
            fault, target = msg.data.split(":", 1)
        except ValueError:
            return
        if target not in {self.robot_id, "all"}:
            return

        if fault in {"shutdown", "coordinator_loss"}:
            action = (
                "simulated coordinator/relay loss; heartbeat stopped"
                if fault == "coordinator_loss"
                else "simulated node shutdown; heartbeat stopped"
            )
            self.report_fault(fault, 3, action, 0.0)
            self.state = "SHUTDOWN"
            self.comms_ok = False
        elif fault == "wifi_cut":
            self.begin_fault(fault)
            self.report_fault(
                fault, 2, "communications isolated; local safety continues", 0.0
            )
            self.comms_ok = False
        elif fault == "wifi_restore":
            self.comms_ok = True
            recovery = self.finish_fault(
                "wifi_cut", 1, "communications restored and member rejoined"
            )
            self.get_logger().warn(f"WIFI RECOVERED in {recovery:.2f}s")
            self.bid_for_cached_targets()
        elif fault == "gps_dropout":
            self.begin_fault(fault)
            self.pre_hold_state = self.state
            self.gps_ok = False
            self.state = "SAFE_HOLD"
            self.report_fault(
                fault, 2, "hold position using local estimate", 0.0
            )
        elif fault == "gps_restore":
            self.gps_ok = True
            self.state = (
                self.pre_hold_state
                if self.pre_hold_state not in {"SAFE_HOLD", "SHUTDOWN"}
                else "ACTIVE"
            )
            recovery = self.finish_fault(
                "gps_dropout", 1, "GPS restored; previous mission state resumed"
            )
            self.get_logger().warn(f"GPS RECOVERED in {recovery:.2f}s")
        elif fault == "critical_battery":
            self.begin_fault(fault)
            self.battery = min(self.battery, 20.0)

    def on_mission_command(self, msg: String) -> None:
        if not self.comms_ok:
            return
        parts = msg.data.split(":")
        if len(parts) < 2:
            return
        command, target = parts[0], parts[1]
        if target not in {self.robot_id, "all"}:
            return

        if command == "sector" and len(parts) == 4:
            self.nav_goal = (float(parts[2]), float(parts[3]))
            self.nav_kind = "sector"
            self.state = "COVERAGE"
            self.get_logger().info(
                f"COVERAGE MOVE -> ({self.nav_goal[0]:.2f}, {self.nav_goal[1]:.2f})"
            )
        elif command == "hold":
            if self.state != "SAFE_HOLD":
                self.pre_hold_state = self.state
            self.state = "SAFE_HOLD"
            self.get_logger().warn("SAFETY HOLD commanded")
        elif command == "resume" and self.state == "SAFE_HOLD":
            self.state = (
                self.pre_hold_state
                if self.pre_hold_state != "SAFE_HOLD"
                else "ACTIVE"
            )
            self.get_logger().warn(f"SAFETY RESUME -> {self.state}")
        elif command == "rtb":
            self.state = "RTB"
            self.assigned_target = None
            self.nav_goal = self.home
            self.nav_kind = "rtb"
        elif command == "land":
            self.state = "LANDED"

    def on_role_command(self, msg: String) -> None:
        if not self.comms_ok:
            return
        try:
            target, requested_role, reason = msg.data.split("|", 2)
        except ValueError:
            return
        if target != self.robot_id:
            return
        old_role = self.role
        self.role = requested_role
        self.get_logger().warn(
            f"ROLE CHANGE {old_role} -> {self.role}; {reason}"
        )

    def report_fault(
        self,
        fault_type: str,
        severity: int,
        action: str,
        recovery: float,
    ) -> None:
        msg = FaultEvent()
        msg.fault_type = fault_type
        msg.robot_id = self.robot_id
        msg.severity = int(severity)
        msg.action = action
        msg.recovery_time = float(max(0.0, recovery))
        msg.stamp = self.now()
        self.fault_pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SwarmAgent()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
