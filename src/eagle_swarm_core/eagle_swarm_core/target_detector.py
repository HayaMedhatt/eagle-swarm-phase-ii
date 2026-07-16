import random

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from eagle_swarm_msgs.msg import TargetBeacon


def retained_qos():
    return QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        history=HistoryPolicy.KEEP_LAST,
        depth=10,
    )


class TargetDetector(Node):
    def __init__(self):
        super().__init__('target_detector')
        self.sent = False
        self.declare_parameter('sender_id', 'scout_1')
        self.declare_parameter('delay', 8.0)
        self.declare_parameter('scenario_seed', 0)
        self.sender = self.get_parameter('sender_id').value
        self.rng = random.Random(int(self.get_parameter('scenario_seed').value))
        self.publisher = self.create_publisher(
            TargetBeacon, '/swarm/target_beacon', retained_qos())
        self.timer = self.create_timer(
            float(self.get_parameter('delay').value), self.emit)

    def emit(self):
        if self.sent:
            return
        message = TargetBeacon()
        message.target_id = 'person_001'
        # Keep the target inside the Digital Twin mission map while varying every run.
        message.position.x = round(self.rng.uniform(-9.0, 9.0), 2)
        message.position.y = round(self.rng.uniform(-6.0, 9.0), 2)
        message.confidence = round(self.rng.uniform(0.82, 0.97), 2)
        message.urgency = self.rng.randint(1, 3)
        message.sender_id = self.sender
        message.battery_state = round(self.rng.uniform(70.0, 98.0), 1)
        message.confirmation_source = 'RGB cue + simulated thermal confirmation'
        message.stamp = self.get_clock().now().to_msg()
        self.publisher.publish(message)
        self.sent = True
        self.get_logger().warn(
            f'CONFIRMED TARGET {message.target_id} at '
            f'({message.position.x:.2f}, {message.position.y:.2f}) '
            f'confidence={message.confidence:.2f}'
        )


def main(args=None):
    rclpy.init(args=args)
    node = TargetDetector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
