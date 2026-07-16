from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def coordinator_replicas():
    return [
        Node(
            package="eagle_swarm_core",
            executable="coordinator",
            name=f"coordinator_{owner}",
            output="screen",
            parameters=[{"owner_id": owner, "bid_window_sec": 2.5}],
        )
        for owner in ("scout_1", "worker_1", "relay_1", "ground_relay")
    ]


def go_to_target_servers():
    return [
        Node(
            package="eagle_swarm_core",
            executable="go_to_target_server",
            name=f"go_to_target_{robot_id}",
            output="screen",
            parameters=[{"robot_id": robot_id}],
        )
        for robot_id in ("scout_1", "worker_1", "relay_1")
    ]


def generate_launch_description():
    target_x = LaunchConfiguration("target_x")
    target_y = LaunchConfiguration("target_y")
    auto_land = LaunchConfiguration("auto_land")
    target_cue_delay = LaunchConfiguration("target_cue_delay_sec")

    adapters_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [
                get_package_share_directory("eagle_swarm_px4"),
                "/launch/three_px4_adapters.launch.py",
            ]
        )
    )

    nodes = [
        DeclareLaunchArgument("target_x", default_value="10.0"),
        DeclareLaunchArgument("target_y", default_value="0.0"),
        DeclareLaunchArgument("auto_land", default_value="true"),
        DeclareLaunchArgument("target_cue_delay_sec", default_value="2.0"),
    ]
    nodes.extend(coordinator_replicas())
    nodes.extend(go_to_target_servers())
    nodes.extend(
        [
            Node(
                package="eagle_swarm_core",
                executable="role_manager",
                name="role_manager",
                output="screen",
            ),
            # Scored Open/Closed extension: this ground unit uses the unchanged
            # generic SwarmAgent and the same DDS contract as aerial units.
            Node(
                package="eagle_swarm_core",
                executable="agent",
                name="ground_relay",
                output="screen",
                parameters=[
                    {
                        "robot_id": "ground_relay",
                        "role": "ground_relay",
                        "x": -12.0,
                        "y": -8.0,
                        "battery": 88.0,
                        "link_quality": 0.62,
                        "capability": 0.55,
                        "drain_rate": 0.03,
                    }
                ],
            ),
            adapters_launch,
            Node(
                package="eagle_swarm_sim",
                executable="safety_monitor",
                name="safety_monitor",
                output="screen",
            ),
            Node(
                package="eagle_swarm_dashboard",
                executable="digital_twin",
                name="digital_twin",
                output="screen",
            ),
            Node(
                package="eagle_swarm_core",
                executable="mission_demo",
                name="mission_demo",
                output="screen",
                parameters=[
                    {
                        "target_x": ParameterValue(target_x, value_type=float),
                        "target_y": ParameterValue(target_y, value_type=float),
                        "auto_land": ParameterValue(auto_land, value_type=bool),
                        "land_delay_sec": 0.0,
                        "target_cue_delay_sec": ParameterValue(
                            target_cue_delay, value_type=float
                        ),
                        "startup_timeout_sec": 150.0,
                        "sector_timeout_sec": 45.0,
                    }
                ],
            ),
        ]
    )
    return LaunchDescription(nodes)
