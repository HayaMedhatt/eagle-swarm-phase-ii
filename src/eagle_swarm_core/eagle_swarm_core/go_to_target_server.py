"""Namespaced GoToTarget action bridge for one swarm vehicle.

The action remains above the vehicle adapter: it validates a goal, publishes the
existing mission command, and reports progress from heartbeat state. This keeps
one motion authority inside the PX4 adapter while still exposing the assessment
Action interface to an operator or mission planner.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Optional, Tuple

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

from eagle_swarm_common.policy import TASK_ELIGIBLE_STATES
from eagle_swarm_msgs.action import GoToTarget
from eagle_swarm_msgs.msg import Heartbeat


ABORT_STATES = {"RTB", "LANDING", "LANDED", "SHUTDOWN", "WAIT_FCU", "WAIT_POSE"}


class GoToTargetServer(Node):
    """Expose one vehicle through a safe, namespaced transit action."""

    def __init__(self) -> None:
        super().__init__("go_to_target_server")
        self.declare_parameter("robot_id", "scout_1")
        self.declare_parameter("arrival_tolerance", 0.65)
        self.declare_parameter("goal_timeout_sec", 90.0)
        self.declare_parameter("heartbeat_timeout_sec", 3.2)
        self.declare_parameter("minimum_safety_margin", 2.0)

        self.robot_id = str(self.get_parameter("robot_id").value)
        self.arrival_tolerance = float(
            self.get_parameter("arrival_tolerance").value
        )
        self.goal_timeout = float(self.get_parameter("goal_timeout_sec").value)
        self.heartbeat_timeout = float(
            self.get_parameter("heartbeat_timeout_sec").value
        )
        self.minimum_safety_margin = float(
            self.get_parameter("minimum_safety_margin").value
        )

        self.lock = threading.Lock()
        self.latest_heartbeat: Optional[Heartbeat] = None
        self.latest_received_monotonic = 0.0
        self.goal_active = False
        self.command_pub = self.create_publisher(
            String, "/swarm/mission_command", 20
        )
        self.create_subscription(Heartbeat, "/swarm/heartbeat", self.on_hb, 50)

        action_name = f"/drone/{self.robot_id}/go_to_target"
        self.action_server = ActionServer(
            self,
            GoToTarget,
            action_name,
            execute_callback=self.execute,
            goal_callback=self.on_goal,
            cancel_callback=self.on_cancel,
            callback_group=ReentrantCallbackGroup(),
        )
        self.get_logger().info(f"Action server ready: {action_name}")

    def on_hb(self, msg: Heartbeat) -> None:
        if msg.robot_id != self.robot_id:
            return
        with self.lock:
            self.latest_heartbeat = msg
            self.latest_received_monotonic = time.monotonic()

    def heartbeat_snapshot(self) -> Tuple[Optional[Heartbeat], float]:
        with self.lock:
            return self.latest_heartbeat, self.latest_received_monotonic

    def on_goal(self, request: GoToTarget.Goal) -> GoalResponse:
        heartbeat, received = self.heartbeat_snapshot()
        age = time.monotonic() - received
        with self.lock:
            if self.goal_active:
                self.get_logger().warn(
                    f"Reject goal for {self.robot_id}: another action is active"
                )
                return GoalResponse.REJECT
        if request.safety_margin < self.minimum_safety_margin:
            self.get_logger().warn(
                f"Reject goal for {self.robot_id}: safety_margin="
                f"{request.safety_margin:.2f} < {self.minimum_safety_margin:.2f}"
            )
            return GoalResponse.REJECT
        if (
            heartbeat is None
            or age >= self.heartbeat_timeout
            or heartbeat.state not in TASK_ELIGIBLE_STATES
        ):
            state = heartbeat.state if heartbeat is not None else "NO_HEARTBEAT"
            self.get_logger().warn(
                f"Reject goal for {self.robot_id}: state={state}, age={age:.2f}s"
            )
            return GoalResponse.REJECT
        with self.lock:
            self.goal_active = True
        return GoalResponse.ACCEPT

    @staticmethod
    def on_cancel(_goal_handle) -> CancelResponse:
        return CancelResponse.ACCEPT

    def execute(self, goal_handle):
        try:
            return self._execute(goal_handle)
        finally:
            with self.lock:
                self.goal_active = False

    def _execute(self, goal_handle):
        target = goal_handle.request.target_pose.position
        target_x = float(target.x)
        target_y = float(target.y)
        command = f"sector:{self.robot_id}:{target_x:.3f}:{target_y:.3f}"
        self.command_pub.publish(String(data=command))
        self.get_logger().info(
            f"ACTION GOAL {self.robot_id} -> ({target_x:.2f}, {target_y:.2f}), "
            f"margin={goal_handle.request.safety_margin:.2f}"
        )

        started = time.monotonic()
        result = GoToTarget.Result()
        while rclpy.ok():
            if goal_handle.is_cancel_requested:
                self.command_pub.publish(String(data=f"hold:{self.robot_id}"))
                heartbeat, _ = self.heartbeat_snapshot()
                remaining = self.distance_to(heartbeat, target_x, target_y)
                result.success = False
                result.final_state = "CANCELED_SAFE_HOLD"
                result.distance_remaining = float(remaining)
                goal_handle.canceled()
                return result

            heartbeat, received = self.heartbeat_snapshot()
            age = time.monotonic() - received
            remaining = self.distance_to(heartbeat, target_x, target_y)

            feedback = GoToTarget.Feedback()
            if heartbeat is not None:
                feedback.current_pose = heartbeat.pose
                feedback.state = heartbeat.state
            else:
                feedback.state = "NO_HEARTBEAT"
            feedback.distance_remaining = float(remaining)
            goal_handle.publish_feedback(feedback)

            if heartbeat is None or age >= self.heartbeat_timeout:
                result.success = False
                result.final_state = "ABORTED_HEARTBEAT_TIMEOUT"
                result.distance_remaining = float(remaining)
                goal_handle.abort()
                return result

            if heartbeat.state in ABORT_STATES:
                result.success = False
                result.final_state = f"ABORTED_{heartbeat.state}"
                result.distance_remaining = float(remaining)
                goal_handle.abort()
                return result

            if remaining <= self.arrival_tolerance:
                result.success = True
                result.final_state = heartbeat.state or "ARRIVED"
                result.distance_remaining = float(remaining)
                goal_handle.succeed()
                return result

            if time.monotonic() - started >= self.goal_timeout:
                self.command_pub.publish(String(data=f"hold:{self.robot_id}"))
                result.success = False
                result.final_state = "ABORTED_TIMEOUT_SAFE_HOLD"
                result.distance_remaining = float(remaining)
                goal_handle.abort()
                return result

            time.sleep(0.2)

        result.success = False
        result.final_state = "ABORTED_SHUTDOWN"
        result.distance_remaining = 0.0
        goal_handle.abort()
        return result

    @staticmethod
    def distance_to(
        heartbeat: Optional[Heartbeat], target_x: float, target_y: float
    ) -> float:
        if heartbeat is None:
            return 1.0e9
        dx = target_x - float(heartbeat.pose.position.x)
        dy = target_y - float(heartbeat.pose.position.y)
        return math.hypot(dx, dy)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = GoToTargetServer()
    executor = MultiThreadedExecutor(num_threads=3)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.action_server.destroy()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
