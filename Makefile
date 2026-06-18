ROS2_WS ?= $(or $(SMARTFACTORY_ROS2_WS),/home/codelab/turtlebot3_ws)
ROS_DISTRO ?= jazzy
ROS_PACKAGES ?= smartfactory_bringup smartfactory_perception_ros

.PHONY: ai-setup ai-test ai-run contracts source-registry-surfaces deploy-validate docker-ai-config vision-check vision-run vision-config vision-smoke-local vision-smoke-main ros-test ros-build-bringup ros-launch-smoke status

ai-setup:
	./scripts/setup_ai_server_env.sh

ai-test:
	./scripts/test_ai_server.sh -q

ai-run:
	./scripts/run_ai_server.sh --reload

contracts:
	python3 scripts/validate_contracts.py

source-registry-surfaces:
	python3 scripts/generate_source_registry_surfaces.py

deploy-validate:
	python3 scripts/validate_deployment_assets.py

docker-ai-config:
	docker compose -f docker-compose.ai-server.yml config --quiet

vision-check:
	VISION_MODEL_WORKER_ENABLED=$${VISION_MODEL_WORKER_ENABLED:-false} ./scripts/run_d1_vision_multi_source_gateway_bundle.sh --check

vision-run:
	./scripts/run_d1_vision_multi_source_gateway_bundle.sh

vision-config:
	./scripts/run_d1_vision_multi_source_gateway_bundle.sh --print-config

vision-smoke-local:
	./scripts/run_d1_vision_multi_source_gateway_bundle.sh --smoke-local

vision-smoke-main:
	./scripts/smoke_main_dashboard_gateway.sh

ros-test:
	cd ros2/smartfactory_perception_ros && pytest -q

ros-build-bringup:
	bash -lc 'source /opt/ros/$(ROS_DISTRO)/setup.bash && cd $(ROS2_WS) && colcon build --symlink-install --packages-select $(ROS_PACKAGES)'

ros-launch-smoke:
	bash -lc 'source /opt/ros/$(ROS_DISTRO)/setup.bash && source $(ROS2_WS)/install/setup.bash && ros2 launch smartfactory_bringup central_pc_bringup.launch.py use_global_camera:=false use_robot_picams:=false use_ai_server:=false use_wms_bridge:=false use_nav2:=false use_ai_snapshot_clients:=false'

status:
	git status --short --branch
