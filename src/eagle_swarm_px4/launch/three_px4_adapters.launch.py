from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    # Offsets match the three Gazebo spawn positions used by the launcher.
    vehicles = [
        # robot_id, role, MAVROS namespace, link, capability, world x, world y
        ("scout_1", "scout", "uav0", 0.92, 0.90, 0.0, 0.0),
        ("worker_1", "worker", "uav1", 0.90, 0.86, 0.0, 3.0),
        ("relay_1", "coordinator", "uav2", 0.96, 0.93, 0.0, -3.0),
    ]

    nodes = []
    for robot_id, role, namespace, link, capability, offset_x, offset_y in vehicles:
        nodes.append(
            Node(
                package="eagle_swarm_px4",
                executable="px4_adapter",
                name=f"{robot_id}_px4_adapter",
                output="screen",
                parameters=[
                    {
                        "robot_id": robot_id,
                        "role": role,
                        "mavros_ns": namespace,
                        "takeoff_altitude": 3.0,
                        "link_quality": link,
                        "capability": capability,
                        "reserve_threshold": 25.0,
                        "mission_offset_x": offset_x,
                        "mission_offset_y": offset_y,
                        "sitl_force_arm_fallback": True,
                        "normal_arm_attempts_before_force": 8,
                    }
                ],
            )
        )

    return LaunchDescription(nodes)
