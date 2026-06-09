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
	bash -lc 'source /opt/ros/jazzy/setup.bash && cd /home/codelab/ros2_ws && colcon build --symlink-install --packages-select smartfactory_bringup'

ros-launch-smoke:
	bash -lc 'source /opt/ros/jazzy/setup.bash && source /home/codelab/ros2_ws/install/setup.bash && ros2 launch smartfactory_bringup central_pc_bringup.launch.py use_global_camera:=false use_robot_picams:=false use_ai_server:=false use_wms_bridge:=false use_nav2:=false'

status:
	git status --short --branch
