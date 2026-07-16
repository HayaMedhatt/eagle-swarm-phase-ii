import os
import random
import secrets

from launch import LaunchDescription
from launch.actions import LogInfo
from launch_ros.actions import Node


def generate_launch_description():
    """Create a fresh, bounded virtual scenario on every launch.

    Set EAGLE_SWARM_SEED to reproduce a run exactly, for example:
    EAGLE_SWARM_SEED=42 ros2 launch eagle_swarm_core swarm_logic.launch.py
    """
    seed_text = os.getenv("EAGLE_SWARM_SEED")
    seed = int(seed_text) if seed_text is not None else secrets.randbits(32)
    rng = random.Random(seed)

    specs = [
        ("scout_1", "scout", (-9.0, -1.0), (-7.0, 7.0), (90.0, 100.0), (0.78, 0.99), (0.82, 0.99)),
        ("worker_1", "worker", (1.0, 9.0), (-7.0, 7.0), (90.0, 100.0), (0.78, 0.99), (0.78, 0.96)),
        ("relay_1", "coordinator", (-4.0, 4.0), (-9.0, -2.0), (90.0, 100.0), (0.88, 1.00), (0.82, 0.98)),
        ("ground_relay", "ground_relay", (-9.0, 9.0), (-10.0, -7.0), (90.0, 100.0), (0.90, 1.00), (0.70, 0.90)),
    ]

    nodes = [LogInfo(msg=f"EAGLE SWARM scenario seed: {seed}")]
    for owner_id, *_ in specs:
        nodes.append(
            Node(
                package="eagle_swarm_core",
                executable="coordinator",
                name=f"coordinator_{owner_id}",
                output="screen",
                parameters=[{"owner_id": owner_id}],
            )
        )
    nodes.append(
        Node(
            package="eagle_swarm_core",
            executable="role_manager",
            name="role_manager",
            output="screen",
        )
    )

    for robot_id in ("scout_1", "worker_1", "relay_1"):
        nodes.append(
            Node(
                package="eagle_swarm_core",
                executable="go_to_target_server",
                name=f"go_to_target_{robot_id}",
                output="screen",
                parameters=[{"robot_id": robot_id}],
            )
        )

    for robot_id, role, xr, yr, br, lr, cr in specs:
        nodes.append(
            Node(
                package="eagle_swarm_core",
                executable="agent",
                name=robot_id,
                output="screen",
                parameters=[
                    {
                        "robot_id": robot_id,
                        "role": role,
                        "x": round(rng.uniform(*xr), 2),
                        "y": round(rng.uniform(*yr), 2),
                        "battery": round(rng.uniform(*br), 2),
                        "link_quality": round(rng.uniform(*lr), 3),
                        "capability": round(rng.uniform(*cr), 3),
                        "drain_rate": round(rng.uniform(0.12, 0.28), 3),
                    }
                ],
            )
        )

    nodes.append(
        Node(
            package="eagle_swarm_core",
            executable="target_detector",
            output="screen",
            parameters=[{"scenario_seed": seed + 1009}],
        )
    )
    nodes.append(
        Node(
            package="eagle_swarm_sim",
            executable="safety_monitor",
            output="screen",
        )
    )
    return LaunchDescription(nodes)
