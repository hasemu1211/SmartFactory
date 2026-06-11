ROS2_WS ?= $(or $(SMARTFACTORY_ROS2_WS),/home/codelab/turtlebot3_ws)
ROS_DISTRO ?= jazzy
ROS_PACKAGES ?= smartfactory_bringup smartfactory_perception_ros

.PHONY: ai-setup ai-test ai-run contracts ros-build-bringup ros-launch-smoke status

ai-setup:
	./scripts/setup_ai_server_env.sh

ai-test:
	./scripts/test_ai_server.sh -q

ai-run:
	./scripts/run_ai_server.sh --reload

contracts:
	python3 scripts/validate_contracts.py

ros-build-bringup:
	bash -lc 'source /opt/ros/$(ROS_DISTRO)/setup.bash && cd $(ROS2_WS) && colcon build --symlink-install --packages-select $(ROS_PACKAGES)'

ros-launch-smoke:
	bash -lc 'source /opt/ros/$(ROS_DISTRO)/setup.bash && source $(ROS2_WS)/install/setup.bash && ros2 launch smartfactory_bringup central_pc_bringup.launch.py use_global_camera:=false use_robot_picams:=false use_ai_server:=false use_wms_bridge:=false use_nav2:=false use_ai_snapshot_clients:=false'

status:
	git status --short --branch
