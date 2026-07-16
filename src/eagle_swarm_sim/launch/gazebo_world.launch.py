from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    world = PathJoinSubstitution([FindPackageShare('eagle_swarm_sim'), 'worlds', 'eagle_swarm.sdf'])
    return LaunchDescription([
        DeclareLaunchArgument('headless', default_value='false'),
        ExecuteProcess(
            cmd=['gz', 'sim', '-r', world],
            output='screen',
        ),
    ])
