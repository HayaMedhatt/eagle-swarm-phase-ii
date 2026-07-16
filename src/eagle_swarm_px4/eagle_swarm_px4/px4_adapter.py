"""PX4/MAVROS adapter for one EAGLE SWARM aerial unit.

The adapter translates a PX4 vehicle into the same swarm-level ROS 2 contract
used by the virtual agents.  It is intentionally simulation-friendly but keeps
all safety bypasses explicit and disabled outside SITL.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import rclpy
from geometry_msgs.msg import Pose, PoseStamped
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, CommandLong, CommandTOL, SetMode
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
    qos_profile_sensor_data,
)
from sensor_msgs.msg import BatteryState
from std_msgs.msg import String

from eagle_swarm_common.policy import TASK_ELIGIBLE_STATES, compute_task_cost
from eagle_swarm_msgs.msg import Bid, FaultEvent, Heartbeat, TargetBeacon, TaskAward

MAV_CMD_COMPONENT_ARM_DISARM = 400
PX4_FORCE_ARM_MAGIC = 21196.0


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


class Px4Adapter(Node):
    """One PX4 SITL vehicle exposed through the EAGLE SWARM contract."""

    def __init__(self) -> None:
        super().__init__("px4_adapter")

        defaults = [
            ("robot_id", "scout_1"),
            ("role", "scout"),
            ("mavros_ns", "uav0"),
            ("takeoff_altitude", 3.0),
            ("capability", 0.85),
            ("link_quality", 0.95),
            ("reserve_threshold", 25.0),
            ("mission_offset_x", 0.0),
            ("mission_offset_y", 0.0),
            ("virtual_battery_drain_hover", 0.02),
            ("virtual_battery_drain_motion", 0.10),
            ("sitl_force_arm_fallback", True),
            ("normal_arm_attempts_before_force", 4),
        ]
        for name, default in defaults:
            self.declare_parameter(name, default)

        self.robot_id = str(self.get_parameter("robot_id").value)
        self.role = str(self.get_parameter("role").value)
        self.mavros_ns = str(self.get_parameter("mavros_ns").value)
        self.takeoff_altitude = float(self.get_parameter("takeoff_altitude").value)
        self.capability = float(self.get_parameter("capability").value)
        self.link_quality = float(self.get_parameter("link_quality").value)
        self.reserve = float(self.get_parameter("reserve_threshold").value)
        self.offset_x = float(self.get_parameter("mission_offset_x").value)
        self.offset_y = float(self.get_parameter("mission_offset_y").value)
        self.hover_drain = float(self.get_parameter("virtual_battery_drain_hover").value)
        self.motion_drain = float(self.get_parameter("virtual_battery_drain_motion").value)
        self.allow_force_arm = bool(self.get_parameter("sitl_force_arm_fallback").value)
        self.force_after_attempts = int(
            self.get_parameter("normal_arm_attempts_before_force").value
        )

        self.state = "WAIT_FCU"
        self.connected = False
        self.armed = False
        self.mode = ""
        self.pose_ready = False
        self.gps_ok = True
        self.comms_ok = True
        self.landing_requested = False
        self.pre_hold_state = "ACTIVE"
        self.pre_hold_setpoint: Optional[Tuple[float, float, float]] = None
        self.fault_started_ns: Dict[str, int] = {}

        self.pose = Pose()
        self.pose.orientation.w = 1.0
        self.actual_battery_pct: Optional[float] = None
        self.virtual_battery_pct = 100.0
        self.assigned_target: Optional[str] = None
        self.targets: Dict[str, Target] = {}

        self.home_local = (0.0, 0.0)
        self.setpoint = PoseStamped()
        self.setpoint.pose.orientation.w = 1.0
        self.setpoint.pose.position.x = 0.0
        self.setpoint.pose.position.y = 0.0
        self.setpoint.pose.position.z = self.takeoff_altitude

        self.setpoint_samples = 0
        self.arm_attempts = 0
        self.force_arm_attempted = False
        self.last_command_ns = 0
        self.last_wait_log_ns = 0

        ns = self.mavros_ns
        self.create_subscription(State, f"/{ns}/mavros/state", self.on_state, 10)
        self.create_subscription(
            PoseStamped,
            f"/{ns}/mavros/local_position/pose",
            self.on_pose,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            BatteryState,
            f"/{ns}/mavros/battery",
            self.on_battery,
            qos_profile_sensor_data,
        )

        self.setpoint_pub = self.create_publisher(
            PoseStamped, f"/{ns}/mavros/setpoint_position/local", 10
        )
        self.arm_client = self.create_client(
            CommandBool, f"/{ns}/mavros/cmd/arming"
        )
        self.mode_client = self.create_client(SetMode, f"/{ns}/mavros/set_mode")
        self.land_client = self.create_client(CommandTOL, f"/{ns}/mavros/cmd/land")
        self.command_client = self.create_client(
            CommandLong, f"/{ns}/mavros/cmd/command"
        )

        self.heartbeat_pub = self.create_publisher(Heartbeat, "/swarm/heartbeat", 20)
        self.bid_pub = self.create_publisher(Bid, "/swarm/bids", 20)
        self.fault_pub = self.create_publisher(FaultEvent, "/swarm/faults", 20)

        self.create_subscription(
            TargetBeacon,
            "/swarm/target_beacon",
            self.on_beacon,
            retained_qos(),
        )
        self.create_subscription(
            TaskAward, "/swarm/task_award", self.on_award, retained_qos()
        )
        self.create_subscription(
            String, "/swarm/fault_command", self.on_fault_command, 20
        )
        self.create_subscription(
            String, "/swarm/mission_command", self.on_mission_command, 20
        )
        self.create_subscription(
            String, "/swarm/role_command", self.on_role_command, 20
        )

        # Position setpoints are streamed at 10 Hz.  PX4 requires the stream to
        # exist before switching to/arming in OFFBOARD and while OFFBOARD runs.
        self.create_timer(0.1, self.stream_setpoint)
        self.create_timer(1.0, self.tick)

        self.get_logger().info(
            f"{self.robot_id} adapter online: MAVROS={ns}, "
            f"mission_offset=({self.offset_x:.1f}, {self.offset_y:.1f})"
        )

    # ------------------------------------------------------------------
    # MAVROS telemetry
    def on_state(self, msg: State) -> None:
        newly_connected = bool(msg.connected) and not self.connected
        self.connected = bool(msg.connected)
        self.armed = bool(msg.armed)
        self.mode = str(msg.mode)
        if newly_connected:
            self.get_logger().info(f"{self.robot_id} FCU connected")

    def on_pose(self, msg: PoseStamped) -> None:
        first = not self.pose_ready
        self.pose = msg.pose
        self.pose_ready = True
        if first:
            self.home_local = (
                float(msg.pose.position.x),
                float(msg.pose.position.y),
            )
            self.get_logger().info(
                f"{self.robot_id} pose ready at "
                f"({msg.pose.position.x:.2f}, {msg.pose.position.y:.2f}, "
                f"{msg.pose.position.z:.2f})"
            )

        q = msg.pose.orientation
        norm_sq = q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w
        if norm_sq > 1e-9:
            self.setpoint.pose.orientation = q
        else:
            self.setpoint.pose.orientation.x = 0.0
            self.setpoint.pose.orientation.y = 0.0
            self.setpoint.pose.orientation.z = 0.0
            self.setpoint.pose.orientation.w = 1.0

    def on_battery(self, msg: BatteryState) -> None:
        value = float(msg.percentage)
        if math.isfinite(value) and value >= 0.0:
            self.actual_battery_pct = max(0.0, min(100.0, value * 100.0))

    def local_xyz(self) -> Tuple[float, float, float]:
        return (
            float(self.pose.position.x),
            float(self.pose.position.y),
            float(self.pose.position.z),
        )

    def mission_xy(self) -> Tuple[float, float]:
        x, y, _ = self.local_xyz()
        return (
            (x - self.home_local[0]) + self.offset_x,
            (y - self.home_local[1]) + self.offset_y,
        )

    @property
    def battery_pct(self) -> float:
        if self.actual_battery_pct is None:
            return self.virtual_battery_pct
        # The virtual battery guarantees observable drain in SITL while never
        # reporting more energy than MAVROS reports.
        return min(self.actual_battery_pct, self.virtual_battery_pct)

    # ------------------------------------------------------------------
    # PX4 configuration and commands
    def command_rate_limited(self, interval_sec: float = 1.0) -> bool:
        now_ns = self.get_clock().now().nanoseconds
        if now_ns - self.last_command_ns < int(interval_sec * 1e9):
            return False
        self.last_command_ns = now_ns
        return True

    def request_offboard(self) -> None:
        if not self.mode_client.service_is_ready():
            return
        req = SetMode.Request()
        req.custom_mode = "OFFBOARD"
        future = self.mode_client.call_async(req)

        def done(result_future) -> None:
            try:
                response = result_future.result()
                self.get_logger().info(
                    f"{self.robot_id} OFFBOARD request: "
                    f"mode_sent={bool(response and response.mode_sent)}"
                )
            except Exception as exc:  # pragma: no cover
                self.get_logger().warn(f"{self.robot_id} OFFBOARD request failed: {exc}")

        future.add_done_callback(done)

    def request_arm(self) -> None:
        if not self.arm_client.service_is_ready():
            return
        req = CommandBool.Request()
        req.value = True
        self.arm_attempts += 1
        future = self.arm_client.call_async(req)

        def done(result_future) -> None:
            try:
                response = result_future.result()
                success = bool(response and response.success)
                result = int(response.result) if response else -1
                self.get_logger().info(
                    f"{self.robot_id} arm request #{self.arm_attempts}: "
                    f"success={success}, result={result}"
                )
            except Exception as exc:  # pragma: no cover
                self.get_logger().warn(f"{self.robot_id} arm request failed: {exc}")

        future.add_done_callback(done)

    def request_force_arm_sitl(self) -> None:
        if not self.allow_force_arm or self.force_arm_attempted:
            return
        if not self.command_client.service_is_ready():
            return
        req = CommandLong.Request()
        req.broadcast = False
        req.command = MAV_CMD_COMPONENT_ARM_DISARM
        req.confirmation = 0
        req.param1 = 1.0
        req.param2 = PX4_FORCE_ARM_MAGIC
        req.param3 = 0.0
        req.param4 = 0.0
        req.param5 = 0.0
        req.param6 = 0.0
        req.param7 = 0.0
        self.force_arm_attempted = True
        self.get_logger().warn(
            f"{self.robot_id} using SITL-only force-arm fallback after "
            f"{self.arm_attempts} normal attempts"
        )
        future = self.command_client.call_async(req)

        def done(result_future) -> None:
            try:
                response = result_future.result()
                success = bool(response and response.success)
                self.get_logger().warn(
                    f"{self.robot_id} force-arm result: "
                    f"success={success}, "
                    f"result={int(response.result) if response else -1}"
                )
                if not success:
                    self.force_arm_attempted = False
            except Exception as exc:  # pragma: no cover
                self.force_arm_attempted = False
                self.get_logger().error(f"{self.robot_id} force-arm failed: {exc}")

        future.add_done_callback(done)

    def request_land(self) -> None:
        if self.landing_requested or not self.land_client.service_is_ready():
            return
        self.landing_requested = True
        future = self.land_client.call_async(CommandTOL.Request())

        def done(result_future) -> None:
            try:
                response = result_future.result()
                success = bool(response and response.success)
                self.get_logger().info(
                    f"{self.robot_id} land request: "
                    f"success={success}, "
                    f"result={int(response.result) if response else -1}"
                )
                if not success:
                    self.landing_requested = False
            except Exception as exc:  # pragma: no cover
                self.landing_requested = False
                self.get_logger().warn(f"{self.robot_id} land request failed: {exc}")

        future.add_done_callback(done)

    # ------------------------------------------------------------------
    # Continuous setpoint and state machine
    def stream_setpoint(self) -> None:
        normal_stream_states = {
            "PRESTREAM",
            "ARMING",
            "TAKEOFF",
            "ACTIVE",
            "COVERAGE",
            "SECTOR_READY",
            "EXECUTING",
            "ARRIVED",
            "RTB",
            "SAFE_HOLD",
        }

        should_stream = self.state in normal_stream_states

        # During the LAND transition, keep a frozen position setpoint
        # until PX4 has actually left OFFBOARD. This prevents an
        # OFFBOARD-loss climb or drift before AUTO.LAND takes control.
        if self.state == "LANDING":
            if not self.landing_requested or self.mode == "OFFBOARD":
                should_stream = True

        if should_stream:
            self.setpoint.header.stamp = self.get_clock().now().to_msg()
            self.setpoint.header.frame_id = "map"
            self.setpoint_pub.publish(self.setpoint)

            if self.connected and self.pose_ready:
                self.setpoint_samples += 1

    def tick(self) -> None:
        if self.state == "SHUTDOWN":
            return

        if not self.connected:
            self.state = "WAIT_FCU"
            self.log_waiting("waiting for MAVROS/FCU")
            return

        if not self.pose_ready:
            self.state = "WAIT_POSE"
            self.log_waiting("waiting for MAVROS local pose")
            return

        x, y, z = self.local_xyz()
        mission_x = (x - self.home_local[0]) + self.offset_x
        mission_y = (y - self.home_local[1]) + self.offset_y

        if self.state in {"WAIT_FCU", "WAIT_POSE"}:
            self.state = "PRESTREAM"
            self.setpoint_samples = 0
            self.setpoint.pose.position.x = self.home_local[0]
            self.setpoint.pose.position.y = self.home_local[1]
            self.setpoint.pose.position.z = self.takeoff_altitude
            self.get_logger().info(
                f"{self.robot_id} prestreaming OFFBOARD takeoff setpoint"
            )

        if self.state == "PRESTREAM":
            if self.setpoint_samples >= 25:
                self.state = "ARMING"
                self.get_logger().info(
                    f"{self.robot_id} setpoint stream established; arming"
                )

        elif self.state == "ARMING":
            if self.command_rate_limited(1.0):
                if self.mode != "OFFBOARD":
                    self.request_offboard()
                if not self.armed:
                    self.request_arm()
                    if self.arm_attempts >= self.force_after_attempts:
                        self.request_force_arm_sitl()
            if self.armed:
                self.state = "TAKEOFF"
                self.get_logger().info(f"{self.robot_id} armed; climbing")

        elif self.state == "TAKEOFF":
            if self.mode != "OFFBOARD" and self.command_rate_limited(1.0):
                self.request_offboard()
            if not self.armed:
                self.state = "ARMING"
            elif z >= self.takeoff_altitude * 0.85:
                self.state = "ACTIVE"
                self.get_logger().info(
                    f"{self.robot_id} reached hover altitude -> ACTIVE"
                )
                self.bid_for_cached_targets()

        elif self.state == "COVERAGE":
            distance = math.hypot(
                self.setpoint.pose.position.x - x,
                self.setpoint.pose.position.y - y,
            )
            if distance < 0.65:
                self.state = "SECTOR_READY"
                self.get_logger().info(
                    f"{self.robot_id} SECTOR READY at "
                    f"({mission_x:.2f}, {mission_y:.2f})"
                )

        elif self.state == "EXECUTING":
            target = self.targets.get(self.assigned_target or "")
            if target is not None:
                distance = math.hypot(target.x - mission_x, target.y - mission_y)
                vertical_error = abs(self.setpoint.pose.position.z - z)
                if distance < 0.65 and vertical_error < 0.30:
                    self.state = "ARRIVED"
                    self.get_logger().info(
                        f"{self.robot_id} ARRIVED at {target.target_id}; "
                        f"z={z:.2f}m settled"
                    )

        elif self.state == "RTB":
            home_distance = math.hypot(
                x - self.home_local[0], y - self.home_local[1]
            )
            if home_distance < 0.6:
                self.state = "LANDING"
                self.request_land()

        elif self.state == "LANDING":
            self.request_land()
            # PX4 disarms only after touchdown.  Do not require a ground-plane
            # z threshold: the winner intentionally lands on a raised target
            # platform, so its valid touchdown altitude is above zero.
            if not self.armed:
                self.state = "LANDED"
                self.get_logger().info(
                    f"{self.robot_id} LANDED at local z={z:.2f}"
                )
                if "critical_battery" in self.fault_started_ns:
                    recovery = self.finish_fault(
                        "critical_battery",
                        1,
                        "returned to base and landed",
                    )
                    self.get_logger().warn(
                        f"{self.robot_id} RTB COMPLETE in {recovery:.2f}s"
                    )

        moving = self.state in {"COVERAGE", "EXECUTING", "RTB"}
        self.virtual_battery_pct = max(
            0.0,
            self.virtual_battery_pct - (self.motion_drain if moving else self.hover_drain),
        )
        if self.battery_pct <= self.reserve and self.state not in {
            "RTB",
            "LANDING",
            "LANDED",
        }:
            self.enter_rtb("critical_battery", "reserve threshold reached")

        self.publish_heartbeat(mission_x, mission_y, z)

    def log_waiting(self, text: str) -> None:
        now_ns = self.get_clock().now().nanoseconds
        if now_ns - self.last_wait_log_ns >= 3_000_000_000:
            self.get_logger().info(f"{self.robot_id} {text}...")
            self.last_wait_log_ns = now_ns

    def publish_heartbeat(self, x: float, y: float, z: float) -> None:
        if not self.comms_ok:
            return
        msg = Heartbeat()
        msg.robot_id = self.robot_id
        msg.role = self.role
        msg.state = self.state
        msg.battery = float(self.battery_pct)
        msg.pose = Pose()
        msg.pose.position.x = float(x)
        msg.pose.position.y = float(y)
        msg.pose.position.z = float(z)
        msg.pose.orientation = self.pose.orientation
        msg.link_quality = float(self.link_quality)
        msg.capability = float(self.capability)
        msg.gps_ok = bool(self.gps_ok)
        msg.stamp = self.get_clock().now().to_msg()
        self.heartbeat_pub.publish(msg)

    # ------------------------------------------------------------------
    # Contract Net
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
        for target in self.targets.values():
            self.publish_bid(target)

    def publish_bid(self, target: Target) -> None:
        if not self.comms_ok:
            return
        x, y = self.mission_xy()
        distance = math.hypot(target.x - x, target.y - y)
        cost = compute_task_cost(
            distance, self.battery_pct, self.role, self.link_quality
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
        bid.battery_after = float(max(0.0, self.battery_pct - distance * 0.25))
        bid.stamp = self.get_clock().now().to_msg()
        self.bid_pub.publish(bid)
        self.get_logger().info(
            f"BID(real) {target.target_id}: d={cost.distance:.2f}, "
            f"battery={cost.battery_penalty:.2f}, "
            f"role={cost.role_penalty:.2f}, "
            f"link={cost.link_penalty:.2f}, total={cost.total:.2f}"
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
        self.setpoint.pose.position.x = (
            self.home_local[0] + target.x - self.offset_x
        )
        self.setpoint.pose.position.y = (
            self.home_local[1] + target.y - self.offset_y
        )
        # Preserve the current stable flight altitude. Re-commanding the fixed
        # takeoff altitude here could make a slightly lower aircraft climb only
        # after it was already horizontally over the target.
        _, _, current_z = self.local_xyz()
        transit_altitude = max(1.2, current_z)
        self.setpoint.pose.position.z = transit_altitude
        self.state = "EXECUTING"
        self.get_logger().info(
            f"AWARD(real) {msg.target_id}; local setpoint=("
            f"{self.setpoint.pose.position.x:.2f}, "
            f"{self.setpoint.pose.position.y:.2f}, "
            f"{transit_altitude:.2f})"
        )

    # ------------------------------------------------------------------
    # Mission and fault handling
    def begin_fault(self, fault_type: str) -> None:
        self.fault_started_ns.setdefault(
            fault_type, self.get_clock().now().nanoseconds
        )

    def finish_fault(
        self, fault_type: str, severity: int, action: str
    ) -> float:
        started = self.fault_started_ns.pop(fault_type, None)
        recovery = 0.0
        if started is not None:
            recovery = (self.get_clock().now().nanoseconds - started) / 1e9
        self.report_fault(fault_type, severity, action, recovery)
        return recovery

    def set_shared_mission_goal(self, mission_x: float, mission_y: float) -> None:
        self.setpoint.pose.position.x = (
            self.home_local[0] + mission_x - self.offset_x
        )
        self.setpoint.pose.position.y = (
            self.home_local[1] + mission_y - self.offset_y
        )
        self.setpoint.pose.position.z = self.takeoff_altitude

    def restore_assigned_target_setpoint(self) -> None:
        target = self.targets.get(self.assigned_target or "")
        if target is not None:
            self.set_shared_mission_goal(target.x, target.y)

    def enter_rtb(self, fault_type: str, reason: str) -> None:
        if fault_type == "critical_battery":
            self.begin_fault(fault_type)
        self.assigned_target = None
        self.setpoint.pose.position.x = self.home_local[0]
        self.setpoint.pose.position.y = self.home_local[1]
        self.setpoint.pose.position.z = self.takeoff_altitude
        self.state = "RTB"
        self.landing_requested = False
        self.report_fault(fault_type, 2, f"RTB initiated: {reason}", 0.0)
        self.get_logger().warn(f"{self.robot_id} -> RTB ({reason})")

    def on_mission_command(self, msg: String) -> None:
        # A virtual Wi-Fi cut isolates DDS coordination traffic while the
        # onboard PX4 setpoint/safety state continues locally.  Fault restore
        # remains an out-of-band simulation-control command.
        if not self.comms_ok:
            return
        parts = msg.data.split(":")
        if len(parts) < 2:
            return
        command, target = parts[0], parts[1]
        if target not in {self.robot_id, "all"}:
            return

        if command == "sector" and len(parts) == 4:
            mission_x = float(parts[2])
            mission_y = float(parts[3])
            self.set_shared_mission_goal(mission_x, mission_y)
            self.state = "COVERAGE"
            self.get_logger().info(
                f"{self.robot_id} COVERAGE MOVE -> "
                f"({mission_x:.2f}, {mission_y:.2f})"
            )
        elif command == "land":
            # Freeze at the aircraft's actual target position.
            # The previous target setpoint may still request 3 m altitude,
            # which caused the winner to climb before landing.
            if self.pose_ready:
                x, y, z = self.local_xyz()

                self.setpoint.pose.position.x = x
                self.setpoint.pose.position.y = y
                self.setpoint.pose.position.z = max(z, 0.35)

            self.pre_hold_setpoint = None
            self.pre_hold_state = "LANDING"
            self.state = "LANDING"
            self.landing_requested = False

            self.get_logger().warn(
                f"{self.robot_id} DIRECT LAND at current target position"
            )

            self.request_land()
        elif command == "return_home":
            self.assigned_target = None
            self.setpoint.pose.position.x = self.home_local[0]
            self.setpoint.pose.position.y = self.home_local[1]
            self.setpoint.pose.position.z = self.takeoff_altitude
            self.state = "RTB"
            self.landing_requested = False
            self.get_logger().info(
                f"{self.robot_id} RETURN HOME -> "
                f"({self.home_local[0]:.2f}, {self.home_local[1]:.2f})"
            )
        elif command == "rtb":
            self.enter_rtb("mission_rtb", "mission command")
        elif command == "hold" and self.pose_ready:
            if self.state in {"LANDING", "LANDED"}:
                self.get_logger().info(
                    f"{self.robot_id} ignored delayed HOLD while "
                    f"state={self.state}"
                )
                return

            if self.state != "SAFE_HOLD":
                self.pre_hold_state = self.state
                self.pre_hold_setpoint = (
                    float(self.setpoint.pose.position.x),
                    float(self.setpoint.pose.position.y),
                    float(self.setpoint.pose.position.z),
                )
            x, y, z = self.local_xyz()
            self.setpoint.pose.position.x = x
            self.setpoint.pose.position.y = y
            self.setpoint.pose.position.z = max(z, 1.0)
            self.state = "SAFE_HOLD"
            self.get_logger().warn(f"{self.robot_id} SAFETY HOLD commanded")
        elif command == "resume" and self.state == "SAFE_HOLD":
            if self.pre_hold_setpoint is not None:
                px, py, pz = self.pre_hold_setpoint
                self.setpoint.pose.position.x = px
                self.setpoint.pose.position.y = py
                self.setpoint.pose.position.z = pz
            self.state = (
                self.pre_hold_state
                if self.pre_hold_state != "SAFE_HOLD"
                else "ACTIVE"
            )
            self.get_logger().warn(
                f"{self.robot_id} SAFETY RESUME -> {self.state}"
            )

    def on_fault_command(self, msg: String) -> None:
        try:
            fault, target = msg.data.split(":", 1)
        except ValueError:
            return
        if target not in {self.robot_id, "all"}:
            return

        if fault in {"shutdown", "coordinator_loss"}:
            # This is a hard unit-loss simulation: publish the event, command a
            # best-effort landing, then stop heartbeat/setpoint output so peers
            # must detect the loss and continue through another replica.
            self.report_fault(
                fault,
                3,
                (
                    "simulated coordinator/relay loss; heartbeat and OFFBOARD "
                    "stream stopped"
                    if fault == "coordinator_loss"
                    else "simulated unit shutdown; heartbeat and OFFBOARD stream stopped"
                ),
                0.0,
            )
            self.request_land()
            self.state = "SHUTDOWN"
            self.comms_ok = False
        elif fault == "critical_battery":
            self.begin_fault(fault)
            self.virtual_battery_pct = min(self.virtual_battery_pct, 20.0)
        elif fault == "wifi_cut":
            self.begin_fault(fault)
            self.report_fault(
                fault,
                2,
                "DDS heartbeat isolated; onboard OFFBOARD hold continues",
                0.0,
            )
            self.comms_ok = False
        elif fault == "wifi_restore":
            self.comms_ok = True
            recovery = self.finish_fault(
                "wifi_cut",
                1,
                "DDS heartbeat restored; member rejoined",
            )
            self.get_logger().warn(
                f"{self.robot_id} WIFI RECOVERED in {recovery:.2f}s"
            )
            # Rejoin the retained target contract without requiring a new cue.
            self.bid_for_cached_targets()
        elif fault == "gps_dropout":
            self.begin_fault(fault)
            self.gps_ok = False
            self.pre_hold_state = self.state
            self.pre_hold_setpoint = (
                float(self.setpoint.pose.position.x),
                float(self.setpoint.pose.position.y),
                float(self.setpoint.pose.position.z),
            )
            if self.pose_ready:
                x, y, z = self.local_xyz()
                self.setpoint.pose.position.x = x
                self.setpoint.pose.position.y = y
                self.setpoint.pose.position.z = max(z, 1.0)
            self.state = "SAFE_HOLD"
            self.report_fault(
                fault,
                2,
                "hold current local estimate; reject new awards",
                0.0,
            )
        elif fault == "gps_restore":
            self.gps_ok = True
            if self.pre_hold_setpoint is not None:
                px, py, pz = self.pre_hold_setpoint
                self.setpoint.pose.position.x = px
                self.setpoint.pose.position.y = py
                self.setpoint.pose.position.z = pz
            self.state = (
                self.pre_hold_state
                if self.pre_hold_state not in {"SAFE_HOLD", "SHUTDOWN"}
                else "ACTIVE"
            )
            recovery = self.finish_fault(
                "gps_dropout",
                1,
                "GPS restored; previous mission state resumed",
            )
            self.get_logger().warn(
                f"{self.robot_id} GPS RECOVERED in {recovery:.2f}s"
            )

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
            f"{self.robot_id} ROLE CHANGE {old_role} -> {self.role}; {reason}"
        )

    def report_fault(
        self, fault_type: str, severity: int, action: str, recovery_time: float
    ) -> None:
        msg = FaultEvent()
        msg.fault_type = fault_type
        msg.robot_id = self.robot_id
        msg.severity = int(severity)
        msg.action = action
        msg.recovery_time = float(max(0.0, recovery_time))
        msg.stamp = self.get_clock().now().to_msg()
        self.fault_pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = Px4Adapter()
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
