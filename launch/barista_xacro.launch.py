import os
from ament_index_python.packages import (get_package_prefix, get_package_share_directory)
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription)
from launch.substitutions import (PathJoinSubstitution, LaunchConfiguration, Command)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import SetParameter, Node

import xacro

def generate_launch_description():
    
    ####### DATA INPUT ##########
    package_description = "barista_robot_description"

    pkg_box_bot_gazebo = get_package_share_directory(package_description)
    gz_sim_pkg = get_package_share_directory("ros_gz_sim")

    # Set Gazebo Resource Paths
    install_dir_path_description = os.path.join(get_package_prefix(package_description), "share")
    gazebo_models_path = os.path.join(pkg_box_bot_gazebo, "models")
    description_meshes_path = os.path.join(pkg_box_bot_gazebo, "meshes")
    
    gazebo_resource_paths = [install_dir_path_description, gazebo_models_path, description_meshes_path]
    current_gz_resource_path = os.environ.get("GZ_SIM_RESOURCE_PATH", "")
    
    for resource_path in gazebo_resource_paths:
        if resource_path not in current_gz_resource_path:
            current_gz_resource_path = f"{current_gz_resource_path}:{resource_path}" if current_gz_resource_path else resource_path
    os.environ["GZ_SIM_RESOURCE_PATH"] = current_gz_resource_path

    # Setup Gazebo Sim (FIXED gz_args)
    world_path = os.path.join(pkg_box_bot_gazebo, 'worlds', 'barista_robot_empty.world')
    gz_args = f"-r {world_path}"

    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gz_sim_pkg, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': gz_args}.items(),
    )
    
    # convert XACRO file into URDF
    xacro_file = os.path.join(pkg_box_bot_gazebo, 'xacro', 'barista_robot_model.urdf.xacro')
    doc = xacro.parse(open(xacro_file))
    xacro.process_doc(doc)
    params = {'robot_description': doc.toxml()}

    #
    declare_include_laser = DeclareLaunchArgument(
        "include_laser",
        default_value="true",
        description="Include the laser scanner in the URDF"
    )
    
    # Robot State Publisher
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher_node',
        emulate_tty=True,
        parameters=[{
            'use_sim_time': True, 
            'robot_description': Command([
                'xacro ', xacro_file, 
                ' include_laser:=', LaunchConfiguration('include_laser')
            ])
        }],
        output="screen"
    )
    
    # RVIZ Configuration
    rviz_config_dir = os.path.join(pkg_box_bot_gazebo, 'rviz', 'urdf_vis.rviz')
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        output='screen',
        name='rviz_node',
        parameters=[{'use_sim_time': True}],
        arguments=['-d', rviz_config_dir]
    )

    # Spawn the Robot Arguments
    declare_spawn_model_name = DeclareLaunchArgument("model_name", default_value="my_robot", description="Model Spawn Name")
    declare_spawn_x = DeclareLaunchArgument("x", default_value="0.0", description="Model Spawn X Axis Value")
    declare_spawn_y = DeclareLaunchArgument("y", default_value="0.0", description="Model Spawn Y Axis Value")
    declare_spawn_z = DeclareLaunchArgument("z", default_value="0.2", description="Model Spawn Z Axis Value")
    declare_spawn_yaw = DeclareLaunchArgument("yaw", default_value="3.14", description="Model Spawn Yaw Value")
    
    # Spawn Node
    gz_spawn_entity = Node(
        package="ros_gz_sim",
        executable="create",
        name="my_robot_spawn",
        arguments=[
            "-name", LaunchConfiguration("model_name"),
            "-allow_renaming", "true",
            "-topic", "robot_description",
            "-x", LaunchConfiguration("x"),
            "-y", LaunchConfiguration("y"),
            "-z", LaunchConfiguration("z"),
            "-Y", LaunchConfiguration("yaw"),
        ],
        output="screen",
    )

    # ROS-Gazebo Bridge (FIXED cmd_vel mapping)
    gz_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="gz_bridge",
        arguments=[
            "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
            "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist", # Changed to ']' for ROS -> Gazebo only
            "/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V",
            "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
            "/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model",
            "/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan",
        ],
        output="screen",
    )        
    
    return LaunchDescription([
         SetParameter(name="use_sim_time", value=True),
         declare_include_laser,
         declare_spawn_model_name,
         declare_spawn_x,
         declare_spawn_y,
         declare_spawn_z,
         declare_spawn_yaw,
         gz_spawn_entity,
         gz_bridge,
         gz_sim,
         robot_state_publisher_node,
         rviz_node,
    ])