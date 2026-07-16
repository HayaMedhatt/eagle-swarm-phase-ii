"""Independent separation-rule safety monitor.

This is a lightweight alternative to full ORCA/RVO.  It predicts risk using the
latest 3-D swarm poses, commands the lower-priority aerial unit to hold before
the hard safety margin is crossed, logs near misses, and resumes the unit after
separation is restored.
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from eagle_swarm_common.policy import lower_priority_robot
from eagle_swarm_msgs.msg import Heartbeat, SafetyEvent


class SafetyMonitor(Node):
    def __init__(self) -> None:
        super().__init__("safety_monitor")
        self.declare_parameter("safety_margin", 2.0)
        self.declare_parameter("intervention_margin", 2.6)
        self.declare_parameter("release_margin", 3.2)
        self.declare_parameter("heartbeat_timeout_sec", 3.2)
        self.safety_margin = float(self.get_parameter("safety_margin").value)
        self.intervention_margin = float(
            self.get_parameter("intervention_margin").value
        )
        self.release_margin = float(self.get_parameter("release_margin").value)
        self.heartbeat_timeout = float(
            self.get_parameter("heartbeat_timeout_sec").value
        )

        self.robots: Dict[str, Tuple[Heartbeat, rclpy.time.Time]] = {}
        self.held_pairs: Dict[Tuple[str, str], str] = {}
        self.near_miss_pairs = set()
        self.event_pub = self.create_publisher(
            SafetyEvent, "/swarm/safety_events", 20
        )
        self.command_pub = self.create_publisher(
            String, "/swarm/mission_command", 20
        )
        self.create_subscription(Heartbeat, "/swarm/heartbeat", self.on_hb, 50)
        self.create_timer(0.25, self.check)

    def on_hb(self, msg: Heartbeat) -> None:
        self.robots[msg.robot_id] = (msg, self.get_clock().now())

    @staticmethod
    def distance_3d(a: Heartbeat, b: Heartbeat) -> float:
        dx = a.pose.position.x - b.pose.position.x
        dy = a.pose.position.y - b.pose.position.y
        dz = a.pose.position.z - b.pose.position.z
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    @staticmethod
    def is_airborne_member(msg: Heartbeat) -> bool:
        if msg.role == "ground_relay":
            return False
        return msg.state in {
            "ACTIVE",
            "COVERAGE",
            "SECTOR_READY",
            "EXECUTING",
            "ARRIVED",
            "SAFE_HOLD",
        } and msg.pose.position.z > 0.5

    def publish_event(
        self,
        event_type: str,
        robot_a: str,
        robot_b: str,
        separation: float,
        action: str,
    ) -> None:
        event = SafetyEvent()
        event.event_type = event_type
        event.robot_a = robot_a
        event.robot_b = robot_b
        event.separation = float(separation)
        event.action = action
        event.stamp = self.get_clock().now().to_msg()
        self.event_pub.publish(event)

    def check(self) -> None:
        now = self.get_clock().now()
        active = {}
        for robot_id, (msg, received_at) in self.robots.items():
            age = (now - received_at).nanoseconds / 1e9
            if age < self.heartbeat_timeout and self.is_airborne_member(msg):
                active[robot_id] = msg

        current_pairs = set()
        ids = sorted(active)
        for index, robot_a in enumerate(ids):
            for robot_b in ids[index + 1 :]:
                pair = (robot_a, robot_b)
                current_pairs.add(pair)
                msg_a = active[robot_a]
                msg_b = active[robot_b]
                separation = self.distance_3d(msg_a, msg_b)

                if separation < self.intervention_margin:
                    yielding = self.held_pairs.get(pair)
                    if yielding is None:
                        yielding = lower_priority_robot(
                            robot_a,
                            msg_a.role,
                            msg_a.state,
                            robot_b,
                            msg_b.role,
                            msg_b.state,
                        )
                        self.held_pairs[pair] = yielding
                        self.command_pub.publish(String(data=f"hold:{yielding}"))
                        event_type = (
                            "NEAR_MISS"
                            if separation < self.safety_margin
                            else "SEPARATION_INTERVENTION"
                        )
                        if event_type == "NEAR_MISS":
                            self.near_miss_pairs.add(pair)
                        action = (
                            f"hold {yielding}; preserve higher-priority path; "
                            f"release above {self.release_margin:.1f}m"
                        )
                        self.publish_event(
                            event_type,
                            robot_a,
                            robot_b,
                            separation,
                            action,
                        )
                        self.get_logger().warn(
                            f"{event_type} {robot_a}/{robot_b} "
                            f"d={separation:.2f}m -> hold {yielding}"
                        )
                    elif (
                        separation < self.safety_margin
                        and pair not in self.near_miss_pairs
                    ):
                        # An intervention can still tighten below the hard
                        # margin before the yielding vehicle opens distance.
                        # Record that escalation exactly once for the episode.
                        self.near_miss_pairs.add(pair)
                        self.publish_event(
                            "NEAR_MISS",
                            robot_a,
                            robot_b,
                            separation,
                            f"hold {yielding} remains active below hard margin",
                        )
                        self.get_logger().error(
                            f"NEAR_MISS {robot_a}/{robot_b} "
                            f"d={separation:.2f}m; hold {yielding} remains active"
                        )

                elif separation > self.release_margin and pair in self.held_pairs:
                    yielding = self.held_pairs.pop(pair)
                    self.near_miss_pairs.discard(pair)
                    self.command_pub.publish(String(data=f"resume:{yielding}"))
                    self.publish_event(
                        "SEPARATION_CLEAR",
                        robot_a,
                        robot_b,
                        separation,
                        f"resume {yielding}",
                    )
                    self.get_logger().info(
                        f"SEPARATION CLEAR {robot_a}/{robot_b} "
                        f"d={separation:.2f}m -> resume {yielding}"
                    )

        # If a pair disappears because a member landed or timed out, release the
        # held robot rather than leaving it frozen indefinitely.
        for pair in list(self.held_pairs):
            if pair not in current_pairs:
                yielding = self.held_pairs.pop(pair)
                self.near_miss_pairs.discard(pair)
                self.command_pub.publish(String(data=f"resume:{yielding}"))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SafetyMonitor()
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
