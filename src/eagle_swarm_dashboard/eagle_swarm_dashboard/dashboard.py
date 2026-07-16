import os
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from eagle_swarm_msgs.msg import FaultEvent, Heartbeat, LeaderState, TargetBeacon, TaskAward


def retained_qos(depth=10):
    return QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
    )


class Dashboard(Node):
    def __init__(self):
        super().__init__('dashboard')
        self.robots = {}
        self.leader = '—'
        self.target = '—'
        self.award = '—'
        self.fault = '—'
        self.create_subscription(Heartbeat, '/swarm/heartbeat', self.on_heartbeat, 50)
        self.create_subscription(LeaderState, '/swarm/leader', self.on_leader, retained_qos())
        self.create_subscription(TargetBeacon, '/swarm/target_beacon', self.on_target, retained_qos())
        self.create_subscription(TaskAward, '/swarm/task_award', self.on_award, retained_qos())
        self.create_subscription(FaultEvent, '/swarm/faults', self.on_fault, 20)
        self.create_timer(1.0, self.render)

    def on_heartbeat(self, msg):
        self.robots[msg.robot_id] = (msg, self.get_clock().now())

    def on_leader(self, msg):
        self.leader = f'{msg.leader_id or "none"} (epoch {msg.election_epoch})'

    def on_target(self, msg):
        self.target = (
            f'{msg.target_id} conf={msg.confidence:.2f} via {msg.confirmation_source}'
        )

    def on_award(self, msg):
        self.award = (
            f'{msg.target_id} → {msg.winner_id} cost={msg.winning_cost:.2f}'
        )

    def on_fault(self, msg):
        self.fault = f'{msg.fault_type}@{msg.robot_id}: {msg.action}'

    def render(self):
        now = self.get_clock().now()
        os.system('clear')
        print('EAGLE SWARM — DIGITAL TWIN / OPS VIEW')
        print('=' * 88)
        print('Leader:', self.leader)
        print('Target:', self.target)
        print('Award :', self.award)
        print('Fault :', self.fault)
        print('-' * 88)
        print(f'{"ROBOT":16}{"ROLE":16}{"STATE":14}{"BATT":8}{"LINK":8}{"AGE":8}{"POSE"}')
        for robot_id in sorted(self.robots):
            msg, received_at = self.robots[robot_id]
            age = (now - received_at).nanoseconds / 1e9
            display_state = msg.state if age < 3.2 else 'OFFLINE'
            print(
                f'{robot_id:16}{msg.role:16}{display_state:14}'
                f'{msg.battery:7.1f}{msg.link_quality:8.2f}{age:7.1f}s '
                f'({msg.pose.position.x:5.1f},{msg.pose.position.y:5.1f})'
            )


def main(args=None):
    rclpy.init(args=args)
    node = Dashboard()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
