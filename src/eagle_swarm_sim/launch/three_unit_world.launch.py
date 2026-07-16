from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    use_gazebo = LaunchConfiguration('use_gazebo')
    world = PathJoinSubstitution([
        FindPackageShare('eagle_swarm_sim'), 'worlds', 'eagle_swarm.sdf'
    ])
    return LaunchDescription([
        DeclareLaunchArgument(
            'use_gazebo', default_value='true',
            description='Start Gazebo Sim with the EAGLE SWARM world.'),
        ExecuteProcess(
            cmd=['gz', 'sim', '-r', world],
            output='screen', condition=IfCondition(use_gazebo)),
        Node(
            package='eagle_swarm_sim', executable='safety_monitor',
            output='screen'),
    ])
