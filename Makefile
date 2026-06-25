ROS2_WS ?= $(or $(SMARTFACTORY_ROS2_WS),/home/codelab/turtlebot3_ws)
ROS_DISTRO ?= jazzy
ROS_PACKAGES ?= smartfactory_bringup smartfactory_perception_ros

.PHONY: ai-setup ai-test ai-run contracts source-registry-surfaces deploy-validate docker-ai-config vision-profiles vision-up vision-up-webrtc vision-down vision-status vision-logs vision-check vision-webrtc-check vision-webrtc-status vision-run vision-config vision-smoke-local vision-smoke-main ros-test ros-build-bringup ros-launch-smoke status

ai-setup:
	./scripts/ai/setup_ai_server_env.sh

ai-test:
	./scripts/ai/test_ai_server.sh -q

ai-run:
	./scripts/ai/run_ai_server.sh --reload

contracts:
	python3 scripts/validate/validate_contracts.py

source-registry-surfaces:
	python3 scripts/generate/generate_source_registry_surfaces.py

deploy-validate:
	python3 scripts/validate/validate_deployment_assets.py

docker-ai-config:
	docker compose -f docker-compose.ai-server.yml config --quiet

vision-profiles:
	./scripts/vision/sf_vision.sh profiles

vision-up:
	./scripts/vision/sf_vision.sh up $${PROFILE:-lab-gopro-tb3}

vision-up-webrtc:
	./scripts/vision/sf_vision.sh up lab-gopro-tb3-webrtc

vision-down:
	./scripts/vision/sf_vision.sh down

vision-status:
	./scripts/vision/sf_vision.sh status

vision-logs:
	./scripts/vision/sf_vision.sh logs

vision-check:
	./scripts/vision/sf_vision.sh check $${PROFILE:-local-smoke}

vision-webrtc-check:
	./scripts/vision/run_webrtc_sidecar_mediamtx.sh --check

vision-webrtc-status:
	./scripts/vision/run_webrtc_sidecar_mediamtx.sh --status

vision-run:
	./scripts/vision/sf_vision.sh up $${PROFILE:-lab-gopro-tb3}

vision-config:
	./scripts/vision/sf_vision.sh print-config $${PROFILE:-lab-gopro-tb3}

vision-smoke-local:
	./scripts/vision/sf_vision.sh smoke

vision-smoke-main:
	./scripts/vision/smoke_main_dashboard_gateway.sh

ros-test:
	cd ros2/smartfactory_perception_ros && pytest -q

ros-build-bringup:
	bash -lc 'source /opt/ros/$(ROS_DISTRO)/setup.bash && cd $(ROS2_WS) && colcon build --symlink-install --packages-select $(ROS_PACKAGES)'

ros-launch-smoke:
	bash -lc 'source /opt/ros/$(ROS_DISTRO)/setup.bash && source $(ROS2_WS)/install/setup.bash && ros2 launch smartfactory_bringup central_pc_bringup.launch.py use_global_camera:=false use_robot_picams:=false use_ai_server:=false use_wms_bridge:=false use_nav2:=false use_ai_snapshot_clients:=false'

status:
	git status --short --branch
