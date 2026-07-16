"""Deterministic end-to-end PX4/Gazebo assessment demonstration.

Sequence: three takeoffs -> hover -> sector movement -> RGB cue -> thermal
confirmation -> Contract-Net allocation -> target transit -> landing.
"""

from __future__ import annotations

from typing import Dict, Optional

import os
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

from eagle_swarm_common.coverage import (
    pairwise_minimum_distance,
    plan_coverage_waypoints,
)
from eagle_swarm_msgs.msg import Heartbeat, TargetBeacon, TaskAward


def retained_qos(depth: int = 10) -> QoSProfile:
    return QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
    )


class MissionDemo(Node):
    def __init__(self) -> None:
        super().__init__("mission_demo")
        self.declare_parameter("target_x", 10.0)
        self.declare_parameter("target_y", 0.0)
        self.declare_parameter("auto_land", True)
        self.declare_parameter("land_delay_sec", 0.5)
        self.declare_parameter("target_cue_delay_sec", 2.0)
        self.declare_parameter("startup_timeout_sec", 150.0)
        self.declare_parameter("sector_timeout_sec", 45.0)
        self.declare_parameter("coverage_seed", -1)
        self.declare_parameter("coverage_min_step", 2.5)
        self.declare_parameter("coverage_max_step", 3.5)
        self.declare_parameter("coverage_min_separation", 2.8)

        self.target_x = float(self.get_parameter("target_x").value)
        self.target_y = float(self.get_parameter("target_y").value)
        self.auto_land = bool(self.get_parameter("auto_land").value)
        self.land_delay_sec = float(self.get_parameter("land_delay_sec").value)
        self.target_cue_delay_sec = float(
            self.get_parameter("target_cue_delay_sec").value
        )
        self.startup_timeout_sec = float(
            self.get_parameter("startup_timeout_sec").value
        )
        self.sector_timeout_sec = float(
            self.get_parameter("sector_timeout_sec").value
        )

        self.required = {"scout_1", "worker_1", "relay_1"}

        # Randomized but constrained fan-out coverage.  The pure planner
        # rejects unsafe samples and the logged seed reproduces the geometry.
        requested_seed = int(
            os.environ.get(
                "COVERAGE_SEED",
                str(self.get_parameter("coverage_seed").value),
            )
        )
        self.coverage_seed_used = (
            requested_seed
            if requested_seed >= 0
            else time.time_ns() & 0xFFFFFFFF
        )
        minimum_step = float(self.get_parameter("coverage_min_step").value)
        maximum_step = float(self.get_parameter("coverage_max_step").value)
        minimum_separation = float(
            self.get_parameter("coverage_min_separation").value
        )
        self.sector_waypoints = plan_coverage_waypoints(
            seed=self.coverage_seed_used,
            minimum_step=minimum_step,
            maximum_step=maximum_step,
            minimum_pairwise_separation=minimum_separation,
        )
        waypoint_description = ", ".join(
            f"{robot_id}=({point[0]:.2f}, {point[1]:.2f})"
            for robot_id, point in sorted(self.sector_waypoints.items())
        )
        planned_separation = pairwise_minimum_distance(self.sector_waypoints)
        self.get_logger().warn(
            f"RANDOM COVERAGE seed={self.coverage_seed_used}; "
            f"planned_min_separation={planned_separation:.2f}m: "
            f"{waypoint_description}"
        )

        self.heartbeats: Dict[str, Heartbeat] = {}
        self.stage = "WAIT_ACTIVE"
        self.stage_started = self.get_clock().now()
        self.winner_id: Optional[str] = None
        self.land_sent = False

        self.target_pub = self.create_publisher(
            TargetBeacon, "/swarm/target_beacon", retained_qos()
        )
        self.mission_pub = self.create_publisher(
            String, "/swarm/mission_command", 20
        )
        self.create_subscription(Heartbeat, "/swarm/heartbeat", self.on_hb, 50)
        self.create_subscription(
            TaskAward, "/swarm/task_award", self.on_award, retained_qos()
        )
        self.create_timer(0.5, self.tick)
        self.get_logger().info(
            "Mission demo waiting for scout_1, worker_1 and relay_1 to become ACTIVE"
        )

    def on_hb(self, msg: Heartbeat) -> None:
        self.heartbeats[msg.robot_id] = msg

    def on_award(self, msg: TaskAward) -> None:
        if msg.target_id == "person_001":
            self.winner_id = msg.winner_id
            self.get_logger().info(
                f"Mission observed award: {msg.target_id} -> {msg.winner_id} "
                f"by {msg.assigned_by}"
            )

    def all_active(self) -> bool:
        return all(
            robot_id in self.heartbeats
            and self.heartbeats[robot_id].state in {"ACTIVE", "SECTOR_READY"}
            for robot_id in self.required
        )

    def all_sector_ready(self) -> bool:
        return all(
            robot_id in self.heartbeats
            and self.heartbeats[robot_id].state == "SECTOR_READY"
            for robot_id in self.required
        )

    def elapsed(self) -> float:
        return (
            self.get_clock().now() - self.stage_started
        ).nanoseconds / 1e9

    def set_stage(self, stage: str) -> None:
        self.stage = stage
        self.stage_started = self.get_clock().now()

    def publish_sector_commands(self) -> None:
        for robot_id, (x, y) in self.sector_waypoints.items():
            self.mission_pub.publish(
                String(data=f"sector:{robot_id}:{x:.3f}:{y:.3f}")
            )
        self.get_logger().warn(
            "COVERAGE SECTORS commanded for all three aerial units"
        )

    def publish_target(self) -> None:
        msg = TargetBeacon()
        msg.target_id = "person_001"
        msg.position.x = self.target_x
        msg.position.y = self.target_y
        msg.position.z = 0.0
        msg.confidence = 0.94
        msg.urgency = 2
        msg.sender_id = "scout_1"
        msg.battery_state = float(
            self.heartbeats.get("scout_1", Heartbeat()).battery
        )
        msg.confirmation_source = "RGB cue + thermal confirmation"
        msg.stamp = self.get_clock().now().to_msg()
        self.target_pub.publish(msg)
        self.get_logger().warn(
            f"THERMAL CONFIRMED person_001 at "
            f"({self.target_x:.2f}, {self.target_y:.2f}); beacon published"
        )

    def tick(self) -> None:
        if self.stage == "WAIT_ACTIVE":
            if self.all_active():
                self.get_logger().warn(
                    "All three aerial units ACTIVE after takeoff and hover"
                )
                self.publish_sector_commands()
                self.set_stage("WAIT_SECTORS")
            elif self.elapsed() > self.startup_timeout_sec:
                states = {
                    robot_id: self.heartbeats.get(robot_id, Heartbeat()).state
                    or "NO_HEARTBEAT"
                    for robot_id in sorted(self.required)
                }
                self.get_logger().error(
                    f"Startup timeout; aerial states={states}. "
                    "Mission remains health-gated."
                )
                self.stage_started = self.get_clock().now()

        elif self.stage == "WAIT_SECTORS":
            if self.all_sector_ready():
                self.get_logger().warn(
                    "All three aerial units completed coverage-sector movement; "
                    "RGB CUE person_001 candidate"
                )
                self.set_stage("RGB_CUE")
            elif self.elapsed() > self.sector_timeout_sec:
                states = {
                    robot_id: self.heartbeats.get(robot_id, Heartbeat()).state
                    or "NO_HEARTBEAT"
                    for robot_id in sorted(self.required)
                }
                self.get_logger().error(
                    f"Sector movement timeout; aerial states={states}. "
                    "Target remains gated until all sectors are ready."
                )
                self.stage_started = self.get_clock().now()

        elif (
            self.stage == "RGB_CUE"
            and self.elapsed() >= self.target_cue_delay_sec
        ):
            self.publish_target()
            self.set_stage("WAIT_AWARD")

        elif self.stage == "WAIT_AWARD":
            if self.winner_id:
                self.set_stage("WAIT_ARRIVAL")

        elif self.stage == "WAIT_ARRIVAL":
            winner = self.heartbeats.get(self.winner_id or "")
            if winner is not None and winner.state == "ARRIVED":
                self.get_logger().warn(
                    f"{self.winner_id} reached person_001; mission objective complete"
                )
                self.set_stage("ARRIVED")

        elif (
            self.stage == "ARRIVED"
            and self.auto_land
            and not self.land_sent
            and self.elapsed() >= self.land_delay_sec
        ):
            for robot_id in sorted(self.required):
                command = "land" if robot_id == self.winner_id else "return_home"
                self.mission_pub.publish(String(data=f"{command}:{robot_id}"))
            self.land_sent = True
            self.set_stage("LANDING")
            self.get_logger().warn(
                f"{self.winner_id} landing at the target; "
                "non-winning aerial units returning to their launch points"
            )

        elif self.stage == "LANDING":
            landed = all(
                self.heartbeats.get(robot_id, Heartbeat()).state == "LANDED"
                for robot_id in self.required
            )
            if landed:
                self.set_stage("COMPLETE")
                self.get_logger().warn(
                    "DEMO COMPLETE: takeoff, hover, sector coverage, detection, "
                    "allocation, target movement and landing"
                )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MissionDemo()
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
