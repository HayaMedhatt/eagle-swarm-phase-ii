"""Single routing service for role-change requests.

The assessment specifies one `/swarm/request_role_change` service carrying a
robot ID. This node owns that service and routes accepted changes over a topic,
avoiding multiple competing service servers with the same name.
"""

from __future__ import annotations

from typing import Dict, Tuple

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from eagle_swarm_msgs.msg import Heartbeat
from eagle_swarm_msgs.srv import RequestRoleChange


ALLOWED_ROLES = {"scout", "worker", "coordinator", "ground_relay"}


class RoleManager(Node):
    """Validate and route role changes to one named swarm member."""

    def __init__(self) -> None:
        super().__init__("role_manager")
        self.declare_parameter("heartbeat_timeout_sec", 3.2)
        self.heartbeat_timeout = float(
            self.get_parameter("heartbeat_timeout_sec").value
        )
        self.members: Dict[str, Tuple[Heartbeat, rclpy.time.Time]] = {}
        self.publisher = self.create_publisher(String, "/swarm/role_command", 10)
        self.create_subscription(Heartbeat, "/swarm/heartbeat", self.on_hb, 50)
        self.create_service(
            RequestRoleChange,
            "/swarm/request_role_change",
            self.on_request,
        )

    def on_hb(self, msg: Heartbeat) -> None:
        self.members[msg.robot_id] = (msg, self.get_clock().now())

    def on_request(self, request, response):
        member = self.members.get(request.robot_id)
        if member is None:
            response.accepted = False
            response.message = f"unknown robot: {request.robot_id}"
            return response

        heartbeat, received_at = member
        age = (self.get_clock().now() - received_at).nanoseconds / 1e9
        if age >= self.heartbeat_timeout or heartbeat.state == "SHUTDOWN":
            response.accepted = False
            response.message = f"offline robot: {request.robot_id}"
            return response
        if request.requested_role not in ALLOWED_ROLES:
            response.accepted = False
            response.message = f"unsupported role: {request.requested_role}"
            return response

        self.publisher.publish(
            String(
                data=(
                    f"{request.robot_id}|{request.requested_role}|{request.reason}"
                )
            )
        )
        response.accepted = True
        response.message = (
            f"{request.robot_id}: {heartbeat.role} -> {request.requested_role}; "
            f"{request.reason}"
        )
        self.get_logger().warn(response.message)
        return response


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RoleManager()
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
