import argparse
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class Injector(Node):
    """Publish one fault command several times, then exit cleanly."""

    def __init__(self, command: str):
        super().__init__('fault_injector')
        self.command = command
        self.publisher = self.create_publisher(String, '/swarm/fault_command', 10)

    def publish_command(self) -> None:
        message = String(data=self.command)
        # Repeated sends avoid a race while DDS discovers short-lived publishers.
        for _ in range(3):
            self.publisher.publish(message)
            rclpy.spin_once(self, timeout_sec=0.15)
        self.get_logger().warn(f'INJECT {self.command}')


def main(args=None):
    parser = argparse.ArgumentParser(description='Inject a deterministic swarm fault.')
    parser.add_argument(
        '--type', required=True,
        choices=['shutdown', 'wifi_cut', 'wifi_restore', 'gps_dropout',
                 'gps_restore', 'critical_battery', 'coordinator_loss'])
    parser.add_argument('--robot', default='relay_1')
    parsed = parser.parse_args(args=args)
    rclpy.init()
    node = Injector(f'{parsed.type}:{parsed.robot}')
    try:
        node.publish_command()
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
