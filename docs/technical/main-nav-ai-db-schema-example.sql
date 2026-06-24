-- SmartFactory Main/Nav/AI DB schema example
-- Status: Draft schema example for architecture discussion
-- Target: PostgreSQL 15+
-- Notes:
-- - Use TEXT + CHECK for MVP flexibility; migrate to lookup tables/enums if stable.
-- - Store large images/videos outside DB and reference them through evidence_artifacts.
-- - Main Server owns final task/inventory/robot state transitions.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -----------------------------------------------------------------------------
-- 1. Maps / locations / docking markers
-- -----------------------------------------------------------------------------

CREATE TABLE maps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code text NOT NULL UNIQUE,
    name text NOT NULL,
    frame_id text NOT NULL DEFAULT 'map',
    map_version text,
    origin_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_maps_one_active ON maps (active) WHERE active;

CREATE TABLE map_zones (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    map_id uuid REFERENCES maps(id),
    code text NOT NULL UNIQUE,
    name text NOT NULL,
    zone_type text NOT NULL CHECK (zone_type IN ('INBOUND', 'STORAGE', 'OUTBOUND', 'WAIT', 'CHARGE', 'AISLE', 'RESTRICTED')),
    polygon_json jsonb,
    safety_policy_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE restricted_areas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    map_id uuid REFERENCES maps(id),
    zone_id uuid REFERENCES map_zones(id),
    code text NOT NULL UNIQUE,
    restriction_type text NOT NULL CHECK (restriction_type IN ('NO_GO', 'SLOW_ZONE', 'ONE_WAY', 'HUMAN_SHARED', 'DOCKING_EXCLUSIVE')),
    polygon_json jsonb,
    policy_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE waypoints (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    map_id uuid REFERENCES maps(id),
    zone_id uuid REFERENCES map_zones(id),
    code text NOT NULL UNIQUE,
    name text NOT NULL,
    waypoint_type text NOT NULL CHECK (waypoint_type IN ('APPROACH', 'DOCKING_START', 'PARKING', 'CHARGE', 'WAIT', 'RECOVERY')),
    frame_id text NOT NULL DEFAULT 'map',
    pose_x double precision NOT NULL,
    pose_y double precision NOT NULL,
    pose_yaw double precision NOT NULL,
    tolerance_xy_m double precision NOT NULL DEFAULT 0.10,
    tolerance_yaw_rad double precision NOT NULL DEFAULT 0.10,
    enabled boolean NOT NULL DEFAULT true,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE waypoint_edges (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    from_waypoint_id uuid NOT NULL REFERENCES waypoints(id) ON DELETE CASCADE,
    to_waypoint_id uuid NOT NULL REFERENCES waypoints(id) ON DELETE CASCADE,
    edge_type text NOT NULL DEFAULT 'BIDIRECTIONAL' CHECK (edge_type IN ('BIDIRECTIONAL', 'ONE_WAY')),
    corridor_zone_id uuid REFERENCES map_zones(id),
    nominal_distance_m double precision,
    max_robot_count integer NOT NULL DEFAULT 1,
    traversal_policy_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (from_waypoint_id <> to_waypoint_id)
);

CREATE INDEX idx_waypoint_edges_from ON waypoint_edges (from_waypoint_id, enabled);
CREATE INDEX idx_waypoint_edges_to ON waypoint_edges (to_waypoint_id, enabled);

CREATE TABLE docking_markers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    waypoint_id uuid REFERENCES waypoints(id),
    marker_family text NOT NULL DEFAULT 'ARUCO_4X4_50',
    marker_id integer NOT NULL,
    purpose text NOT NULL CHECK (purpose IN ('SLOT_DOCKING', 'PICKUP_DOCKING', 'DROPOFF_DOCKING', 'CHARGE_DOCKING', 'CALIBRATION')),
    expected_pose_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    docking_profile_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (marker_family, marker_id)
);

-- -----------------------------------------------------------------------------
-- 2. Robots / telemetry / lift
-- -----------------------------------------------------------------------------

CREATE TABLE robots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    robot_code text NOT NULL UNIQUE,               -- tb3_1, tb3_2
    namespace text NOT NULL UNIQUE,                -- /tb3_1, /tb3_2
    display_name text NOT NULL,
    status text NOT NULL DEFAULT 'OFFLINE' CHECK (status IN ('IDLE', 'RESERVED', 'MOVING', 'DOCKING', 'LIFTING', 'SAFETY_PAUSED', 'OPERATOR_PAUSED', 'EMERGENCY_STOPPED', 'ERROR', 'OFFLINE', 'STALE')),
    nav_status text,
    current_task_id uuid,
    current_step_id uuid,
    battery_level double precision,
    last_pose_json jsonb,
    last_heartbeat_at timestamptz,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE robot_capabilities (
    robot_id uuid NOT NULL REFERENCES robots(id) ON DELETE CASCADE,
    capability text NOT NULL CHECK (capability IN ('NAVIGATION', 'LIFT', 'PICAMERA', 'ARUCO_DOCKING', 'SAFETY_STOP')),
    enabled boolean NOT NULL DEFAULT true,
    config_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (robot_id, capability)
);

CREATE TABLE evidence_sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id text NOT NULL UNIQUE,
    source_system text NOT NULL CHECK (source_system IN ('AI_SERVER', 'NAV_SERVER', 'ROBOT', 'OPERATOR', 'MAIN_SERVER')),
    source_kind text NOT NULL CHECK (source_kind IN ('GLOBAL_CAMERA', 'ROBOT_PICAMERA', 'NAV_TELEMETRY', 'LIFT_SENSOR', 'OPERATOR', 'SYSTEM')),
    robot_id uuid REFERENCES robots(id),
    status text NOT NULL DEFAULT 'UNKNOWN' CHECK (status IN ('ONLINE', 'STALE', 'OFFLINE', 'DISABLED', 'UNKNOWN')),
    last_seen_at timestamptz,
    stale_after_s double precision NOT NULL DEFAULT 2.0,
    offline_after_s double precision NOT NULL DEFAULT 30.0,
    trusted_for_safety boolean NOT NULL DEFAULT false,
    trusted_for_inventory boolean NOT NULL DEFAULT false,
    config_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_evidence_sources_status ON evidence_sources (status, last_seen_at DESC);

CREATE TABLE source_health_samples (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_source_id uuid NOT NULL REFERENCES evidence_sources(id) ON DELETE CASCADE,
    status text NOT NULL CHECK (status IN ('ONLINE', 'STALE', 'OFFLINE', 'DISABLED', 'UNKNOWN')),
    latency_ms double precision,
    frame_seq bigint,
    observed_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_source_health_samples_source_time ON source_health_samples (evidence_source_id, observed_at DESC);

CREATE TABLE sensor_calibrations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    calibration_code text NOT NULL UNIQUE,
    calibration_type text NOT NULL CHECK (calibration_type IN ('CAMERA_INTRINSIC', 'CAMERA_EXTRINSIC', 'LIFT_HEIGHT', 'ARUCO_DOCKING_PROFILE')),
    version text NOT NULL,
    calibration_json jsonb NOT NULL,
    active boolean NOT NULL DEFAULT true,
    valid_from timestamptz NOT NULL DEFAULT now(),
    valid_until timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sensor_mounts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_source_id uuid NOT NULL REFERENCES evidence_sources(id) ON DELETE CASCADE,
    robot_id uuid REFERENCES robots(id),
    zone_id uuid REFERENCES map_zones(id),
    mount_type text NOT NULL CHECK (mount_type IN ('GLOBAL_FIXED', 'ROBOT_FRONT', 'ROBOT_LIFT', 'NAV_VIRTUAL')),
    frame_id text,
    transform_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    calibration_id uuid REFERENCES sensor_calibrations(id),
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_sensor_mounts_source ON sensor_mounts (evidence_source_id, active);

CREATE TABLE robot_state_samples (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    robot_id uuid NOT NULL REFERENCES robots(id) ON DELETE CASCADE,
    pose_json jsonb,
    velocity_json jsonb,
    battery_level double precision,
    lift_state text,
    nav_state text,
    health_status text,
    observed_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    raw_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_robot_state_samples_robot_time ON robot_state_samples (robot_id, observed_at DESC);

CREATE TABLE lift_state_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    robot_id uuid NOT NULL REFERENCES robots(id) ON DELETE CASCADE,
    task_id uuid,
    step_id uuid,
    state text NOT NULL CHECK (state IN ('LOWERED', 'RAISING', 'RAISED', 'LOWERING', 'ERROR', 'UNKNOWN')),
    height_mm double precision,
    load_detected boolean,
    observed_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_lift_state_events_robot_time ON lift_state_events (robot_id, observed_at DESC);

-- -----------------------------------------------------------------------------
-- 3. Inventory / parts / pallets / slots
-- -----------------------------------------------------------------------------

CREATE TABLE part_catalog (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    part_no text NOT NULL UNIQUE,
    name text NOT NULL,
    category text,
    spec_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE storage_slots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code text NOT NULL UNIQUE,
    zone_id uuid NOT NULL REFERENCES map_zones(id),
    approach_waypoint_id uuid REFERENCES waypoints(id),
    docking_marker_id uuid REFERENCES docking_markers(id),
    status text NOT NULL DEFAULT 'UNKNOWN' CHECK (status IN ('EMPTY', 'RESERVED', 'OCCUPIED', 'BLOCKED', 'QUARANTINED', 'UNKNOWN', 'STALE')),
    priority_score double precision NOT NULL DEFAULT 0,
    slot_policy_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_verified_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_storage_slots_zone_status ON storage_slots (zone_id, status, priority_score DESC);

CREATE TABLE pallets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pallet_code text NOT NULL UNIQUE,
    tag_id text,
    marker_id text,
    part_id uuid REFERENCES part_catalog(id),
    quantity integer NOT NULL DEFAULT 1 CHECK (quantity >= 0),
    status text NOT NULL DEFAULT 'UNKNOWN' CHECK (status IN ('INBOUND', 'STORED', 'RESERVED_OUTBOUND', 'ON_ROBOT', 'OUTBOUND', 'QUARANTINED', 'UNKNOWN', 'EXCEPTION')),
    current_slot_id uuid REFERENCES storage_slots(id),
    current_robot_id uuid REFERENCES robots(id),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (NOT (current_slot_id IS NOT NULL AND current_robot_id IS NOT NULL))
);

CREATE UNIQUE INDEX uq_pallets_one_active_per_slot ON pallets (current_slot_id) WHERE current_slot_id IS NOT NULL AND status IN ('STORED', 'RESERVED_OUTBOUND');
CREATE UNIQUE INDEX uq_pallets_one_active_per_robot ON pallets (current_robot_id) WHERE current_robot_id IS NOT NULL AND status IN ('ON_ROBOT', 'QUARANTINED');
CREATE INDEX idx_pallets_status ON pallets (status);

-- -----------------------------------------------------------------------------
-- 4. Evidence policies first because steps reference them
-- -----------------------------------------------------------------------------

CREATE TABLE evidence_policies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_name text NOT NULL,
    step_type text NOT NULL,
    version integer NOT NULL DEFAULT 1,
    policy_json jsonb NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (policy_name, version)
);

-- -----------------------------------------------------------------------------
-- 5. Work orders / tasks / task steps
-- -----------------------------------------------------------------------------

CREATE TABLE work_orders (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_no bigserial UNIQUE,
    order_type text NOT NULL CHECK (order_type IN ('INBOUND_STORE', 'OUTBOUND_PICK', 'SLOT_VERIFY', 'MOVE_ONLY', 'RECOVERY')),
    status text NOT NULL DEFAULT 'CREATED' CHECK (status IN ('CREATED', 'PLANNED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'MANUAL_REVIEW')),
    priority integer NOT NULL DEFAULT 0,
    requested_by text,
    requested_payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_work_orders_status_priority ON work_orders (status, priority DESC, created_at);

CREATE TABLE tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_no bigserial UNIQUE,                         -- External integer task ref if API/AI contracts need one.
    work_order_id uuid NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    task_type text NOT NULL CHECK (task_type IN ('STORE_PALLET', 'PICK_PALLET', 'MOVE_ONLY', 'VERIFY_SLOT', 'RECOVERY')),
    status text NOT NULL DEFAULT 'PLANNED' CHECK (status IN ('PLANNED', 'READY', 'RUNNING', 'BLOCKED', 'SAFETY_PAUSED', 'OPERATOR_PAUSED', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'MANUAL_REVIEW')),
    priority integer NOT NULL DEFAULT 0,
    assigned_robot_id uuid REFERENCES robots(id),
    target_pallet_id uuid REFERENCES pallets(id),
    source_waypoint_id uuid REFERENCES waypoints(id),
    target_waypoint_id uuid REFERENCES waypoints(id),
    source_slot_id uuid REFERENCES storage_slots(id),
    target_slot_id uuid REFERENCES storage_slots(id),
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    not_before_at timestamptz,
    timeout_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_tasks_status_priority ON tasks (status, priority DESC, created_at);
CREATE INDEX idx_tasks_robot_active ON tasks (assigned_robot_id, status) WHERE status IN ('READY', 'RUNNING', 'BLOCKED', 'MANUAL_REVIEW');

CREATE TABLE reservations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reservation_type text NOT NULL CHECK (reservation_type IN ('ROBOT', 'SLOT', 'PALLET', 'ZONE', 'DOCKING_MARKER')),
    robot_id uuid REFERENCES robots(id),
    slot_id uuid REFERENCES storage_slots(id),
    pallet_id uuid REFERENCES pallets(id),
    zone_id uuid REFERENCES map_zones(id),
    docking_marker_id uuid REFERENCES docking_markers(id),
    task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'COMMITTED', 'RELEASED', 'EXPIRED', 'CANCELLED')),
    reserved_quantity integer,
    expires_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    released_at timestamptz,
    release_reason text,
    CHECK (
        (reservation_type = 'ROBOT' AND robot_id IS NOT NULL)
        OR (reservation_type = 'SLOT' AND slot_id IS NOT NULL)
        OR (reservation_type = 'PALLET' AND pallet_id IS NOT NULL)
        OR (reservation_type = 'ZONE' AND zone_id IS NOT NULL)
        OR (reservation_type = 'DOCKING_MARKER' AND docking_marker_id IS NOT NULL)
    )
);

CREATE INDEX idx_reservations_task ON reservations (task_id, status);
CREATE UNIQUE INDEX uq_reservations_active_robot ON reservations (robot_id) WHERE reservation_type = 'ROBOT' AND status = 'ACTIVE';
CREATE UNIQUE INDEX uq_reservations_active_slot ON reservations (slot_id) WHERE reservation_type = 'SLOT' AND status = 'ACTIVE';
CREATE UNIQUE INDEX uq_reservations_active_pallet ON reservations (pallet_id) WHERE reservation_type = 'PALLET' AND status = 'ACTIVE';

CREATE TABLE task_dependencies (
    task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    depends_on_task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    dependency_type text NOT NULL DEFAULT 'SUCCESS_REQUIRED' CHECK (dependency_type IN ('SUCCESS_REQUIRED', 'FINISH_REQUIRED')),
    PRIMARY KEY (task_id, depends_on_task_id),
    CHECK (task_id <> depends_on_task_id)
);

CREATE TABLE task_steps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    sequence_no integer NOT NULL,
    step_type text NOT NULL CHECK (step_type IN (
        'RESERVE_RESOURCE',
        'MOVE_TO_INBOUND',
        'MOVE_TO_STORAGE_SLOT',
        'MOVE_TO_OUTBOUND',
        'DOCK_AT_INBOUND_MARKER',
        'DOCK_AT_SLOT_MARKER',
        'DOCK_AT_OUTBOUND_MARKER',
        'LIFT_UP',
        'LIFT_DOWN',
        'VERIFY_LOAD',
        'VERIFY_DROPOFF',
        'VERIFY_SLOT',
        'COMMIT_INVENTORY',
        'RECOVERY_ACTION'
    )),
    status text NOT NULL DEFAULT 'PLANNED' CHECK (status IN ('PLANNED', 'READY', 'LEASED', 'COMMAND_SENT', 'EXECUTING', 'WAITING_EVIDENCE', 'VERIFYING', 'SUCCEEDED', 'RETRY_WAIT', 'BLOCKED', 'SAFETY_PAUSED', 'OPERATOR_PAUSED', 'EMERGENCY_STOPPED', 'MANUAL_REVIEW', 'FAILED', 'CANCELLED')),
    evidence_policy_id uuid REFERENCES evidence_policies(id),
    nav_command_id uuid,
    retry_count integer NOT NULL DEFAULT 0,
    max_retries integer NOT NULL DEFAULT 1,
    not_before_at timestamptz,
    timeout_at timestamptz,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (task_id, sequence_no)
);

CREATE INDEX idx_task_steps_ready ON task_steps (status, not_before_at, sequence_no) WHERE status IN ('READY', 'RETRY_WAIT');
CREATE INDEX idx_task_steps_task_status ON task_steps (task_id, status, sequence_no);

ALTER TABLE robots
    ADD CONSTRAINT fk_robots_current_task
    FOREIGN KEY (current_task_id) REFERENCES tasks(id) ON DELETE SET NULL;

ALTER TABLE robots
    ADD CONSTRAINT fk_robots_current_step
    FOREIGN KEY (current_step_id) REFERENCES task_steps(id) ON DELETE SET NULL;

ALTER TABLE lift_state_events
    ADD CONSTRAINT fk_lift_state_events_task
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL;

ALTER TABLE lift_state_events
    ADD CONSTRAINT fk_lift_state_events_step
    FOREIGN KEY (step_id) REFERENCES task_steps(id) ON DELETE SET NULL;

-- -----------------------------------------------------------------------------
-- 6. Resource locks / scheduler leases
-- -----------------------------------------------------------------------------

CREATE TABLE resource_locks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_type text NOT NULL CHECK (resource_type IN ('ROBOT', 'SLOT', 'ZONE', 'PALLET', 'DOCKING_MARKER')),
    resource_id uuid NOT NULL,
    task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    step_id uuid REFERENCES task_steps(id) ON DELETE CASCADE,
    lock_status text NOT NULL DEFAULT 'ACTIVE' CHECK (lock_status IN ('ACTIVE', 'RELEASED', 'EXPIRED')),
    acquired_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz,
    released_at timestamptz,
    owner text NOT NULL DEFAULT 'main-scheduler'
);

CREATE UNIQUE INDEX uq_resource_locks_one_active ON resource_locks (resource_type, resource_id) WHERE lock_status = 'ACTIVE';
CREATE INDEX idx_resource_locks_task ON resource_locks (task_id, step_id);

CREATE TABLE scheduler_leases (
    step_id uuid PRIMARY KEY REFERENCES task_steps(id) ON DELETE CASCADE,
    lease_owner text NOT NULL,
    lease_token uuid NOT NULL DEFAULT gen_random_uuid(),
    acquired_at timestamptz NOT NULL DEFAULT now(),
    heartbeat_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);

CREATE INDEX idx_scheduler_leases_expiry ON scheduler_leases (expires_at);

-- -----------------------------------------------------------------------------
-- 7. Commanding: Main -> Nav, Nav -> Main
-- -----------------------------------------------------------------------------

CREATE TABLE command_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    command_type text NOT NULL CHECK (command_type IN ('NAV_GOAL', 'DOCK_ARUCO', 'LIFT_UP', 'LIFT_DOWN', 'STOP', 'PAUSE', 'RESUME', 'CANCEL_COMMAND', 'MANUAL_TAKEOVER', 'RECOVERY')),
    target_system text NOT NULL DEFAULT 'NAV_SERVER',
    robot_id uuid REFERENCES robots(id),
    task_id uuid REFERENCES tasks(id) ON DELETE SET NULL,
    step_id uuid REFERENCES task_steps(id) ON DELETE SET NULL,
    status text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'SENT', 'ACCEPTED', 'ACTIVE', 'SUCCEEDED', 'FAILED', 'ABORTED', 'TIMEOUT', 'ESTOPPED', 'SAFETY_PAUSED', 'EMERGENCY_STOPPED', 'CANCEL_REQUESTED', 'CANCELLED')),
    idempotency_key text NOT NULL UNIQUE,
    attempt_no integer NOT NULL DEFAULT 1,
    fencing_token uuid NOT NULL DEFAULT gen_random_uuid(),
    map_id uuid REFERENCES maps(id),
    map_version text,
    calibration_version text,
    deadline_at timestamptz,
    cancel_requested_at timestamptz,
    cancel_ack_at timestamptz,
    cancelled_at timestamptz,
    superseded_by_command_id uuid REFERENCES command_requests(id),
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    response_json jsonb,
    error_code text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_command_requests_status ON command_requests (status, created_at);
CREATE INDEX idx_command_requests_step ON command_requests (step_id);

ALTER TABLE task_steps
    ADD CONSTRAINT fk_task_steps_nav_command
    FOREIGN KEY (nav_command_id) REFERENCES command_requests(id) ON DELETE SET NULL;

CREATE TABLE command_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    command_id uuid NOT NULL REFERENCES command_requests(id) ON DELETE CASCADE,
    source_system text NOT NULL DEFAULT 'NAV_SERVER',
    external_event_id text NOT NULL DEFAULT (gen_random_uuid())::text,
    event_sequence integer,
    event_type text NOT NULL CHECK (event_type IN ('ACCEPTED', 'STARTED', 'FEEDBACK', 'SUCCEEDED', 'FAILED', 'ABORTED', 'TIMEOUT', 'ESTOPPED', 'SAFETY_PAUSED', 'EMERGENCY_STOPPED', 'CANCEL_ACKED', 'CANCELLED')),
    fencing_token uuid,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    observed_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_command_events_command_time ON command_events (command_id, observed_at DESC);
CREATE UNIQUE INDEX uq_command_events_external ON command_events (source_system, external_event_id);
CREATE UNIQUE INDEX uq_command_events_sequence ON command_events (command_id, event_sequence) WHERE event_sequence IS NOT NULL;

CREATE TABLE docking_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    command_id uuid REFERENCES command_requests(id) ON DELETE SET NULL,
    robot_id uuid NOT NULL REFERENCES robots(id) ON DELETE CASCADE,
    task_id uuid REFERENCES tasks(id) ON DELETE SET NULL,
    step_id uuid REFERENCES task_steps(id) ON DELETE SET NULL,
    docking_marker_id uuid REFERENCES docking_markers(id),
    attempt_no integer NOT NULL DEFAULT 1,
    target_pose_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    observed_pose_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_xy_m double precision,
    error_yaw_rad double precision,
    stable_frame_count integer,
    result text NOT NULL CHECK (result IN ('STARTED', 'SUCCEEDED', 'FAILED', 'MARKER_LOST', 'TIMEOUT', 'ABORTED')),
    failure_reason text,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    raw_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_docking_attempts_step_time ON docking_attempts (step_id, started_at DESC);
CREATE INDEX idx_docking_attempts_marker_time ON docking_attempts (docking_marker_id, started_at DESC);

-- -----------------------------------------------------------------------------
-- 8. Evidence / artifacts
-- -----------------------------------------------------------------------------

CREATE TABLE evidence_artifacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_type text NOT NULL CHECK (artifact_type IN ('IMAGE', 'OVERLAY_IMAGE', 'VIDEO_CLIP', 'JSON', 'LOG')),
    uri text NOT NULL,
    content_hash text,
    content_type text,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    pii_redacted boolean NOT NULL DEFAULT false,
    access_policy text NOT NULL DEFAULT 'internal',
    retention_until timestamptz,
    deleted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE evidence_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_event_id text NOT NULL DEFAULT (gen_random_uuid())::text,
    dedupe_key text NOT NULL DEFAULT (gen_random_uuid())::text,
    source_system text NOT NULL CHECK (source_system IN ('AI_SERVER', 'NAV_SERVER', 'ROBOT', 'OPERATOR', 'MAIN_SERVER')),
    source_id text,                                 -- global_cam_01, tb3_1_picam, nav_tb3_1, etc.
    robot_id uuid REFERENCES robots(id),
    task_id uuid REFERENCES tasks(id) ON DELETE SET NULL,
    step_id uuid REFERENCES task_steps(id) ON DELETE SET NULL,
    evidence_type text NOT NULL CHECK (evidence_type IN (
        'GLOBAL_CAM_PALLET_SEEN',
        'PALLET_TAG_DETECTED',
        'ARUCO_MARKER_DETECTED',
        'DOCKING_POSE_ESTIMATE',
        'ROBOT_REACHED_GOAL',
        'LIFT_LOAD_DETECTED',
        'LIFT_LOAD_CLEARED',
        'SLOT_OCCUPIED_CONFIRMED',
        'SLOT_EMPTY_CONFIRMED',
        'HUMAN_DETECTED',
        'HUMAN_CLEAR',
        'OBSTACLE_DETECTED',
        'VISION_STALE',
        'OPERATOR_CONFIRM',
        'NAV_FAILURE',
        'LIFT_FAILURE'
    )),
    confidence double precision CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    severity text NOT NULL DEFAULT 'INFO' CHECK (severity IN ('INFO', 'WARN', 'ERROR', 'SAFETY_CRITICAL')),
    trusted_for_policy boolean NOT NULL DEFAULT false,
    expires_at timestamptz,
    observed_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    normalized_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    normalized_hash text,
    artifact_ref_id uuid REFERENCES evidence_artifacts(id),
    UNIQUE (source_system, external_event_id),
    UNIQUE (source_system, dedupe_key)
);

CREATE INDEX idx_evidence_events_step_time ON evidence_events (step_id, observed_at DESC);
CREATE INDEX idx_evidence_events_task_type ON evidence_events (task_id, evidence_type, observed_at DESC);
CREATE INDEX idx_evidence_events_safety ON evidence_events (severity, observed_at DESC) WHERE severity = 'SAFETY_CRITICAL';

CREATE TABLE safety_incidents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_type text NOT NULL CHECK (incident_type IN ('HUMAN_DETECTED', 'OBSTACLE_DETECTED', 'EMERGENCY_STOP', 'NAV_FAULT', 'OPERATOR_STOP')),
    status text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'CLEARING', 'CLEARED', 'MANUAL_RESET_REQUIRED', 'RESOLVED')),
    robot_id uuid REFERENCES robots(id),
    task_id uuid REFERENCES tasks(id) ON DELETE SET NULL,
    step_id uuid REFERENCES task_steps(id) ON DELETE SET NULL,
    triggering_evidence_id uuid REFERENCES evidence_events(id),
    clear_evidence_id uuid REFERENCES evidence_events(id),
    stop_command_id uuid REFERENCES command_requests(id),
    acknowledged_by text,
    acknowledged_at timestamptz,
    expires_at timestamptz,
    opened_at timestamptz NOT NULL DEFAULT now(),
    cleared_at timestamptz,
    resolved_at timestamptz,
    resolved_by text,
    resume_authorized_by text,
    policy_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_safety_incidents_open ON safety_incidents (status, opened_at DESC) WHERE status <> 'RESOLVED';

CREATE TABLE safety_incident_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id uuid NOT NULL REFERENCES safety_incidents(id) ON DELETE CASCADE,
    event_type text NOT NULL CHECK (event_type IN ('DETECTED', 'INTERRUPT_SENT', 'STOP_ACKED', 'CLEAR_CANDIDATE', 'CLEAR_ACCEPTED', 'CLEAR_REJECTED', 'RESUME_AUTHORIZED', 'RESOLVED', 'MANUAL_RESET')),
    evidence_event_id uuid REFERENCES evidence_events(id),
    command_event_id uuid REFERENCES command_events(id),
    operator_id text,
    observed_at timestamptz NOT NULL DEFAULT now(),
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_safety_incident_events_incident_time ON safety_incident_events (incident_id, observed_at DESC);

CREATE TABLE operator_actions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id text NOT NULL,
    action_type text NOT NULL CHECK (action_type IN ('CREATE_ORDER', 'CANCEL_ORDER', 'PAUSE_TASK', 'RESUME_TASK', 'ACK_SAFETY', 'MANUAL_CONFIRM', 'MANUAL_REJECT', 'RELEASE_LOCK', 'ADJUST_INVENTORY')),
    target_entity_type text NOT NULL CHECK (target_entity_type IN ('WORK_ORDER', 'TASK', 'TASK_STEP', 'ROBOT', 'SLOT', 'PALLET', 'SAFETY_INCIDENT', 'RESERVATION')),
    target_entity_id uuid NOT NULL,
    reason text,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_operator_actions_target ON operator_actions (target_entity_type, target_entity_id, created_at DESC);

CREATE TABLE manual_control_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    robot_id uuid NOT NULL REFERENCES robots(id),
    operator_id text NOT NULL,
    status text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'HANDOVER_REQUIRED', 'RECONCILING', 'CLOSED', 'ABORTED')),
    reason text,
    started_at timestamptz NOT NULL DEFAULT now(),
    handover_required_at timestamptz,
    reconciled_at timestamptz,
    closed_at timestamptz,
    reconcile_snapshot_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_manual_control_sessions_robot_status ON manual_control_sessions (robot_id, status, started_at DESC);

-- -----------------------------------------------------------------------------
-- 9. Decision audit / transitions / API logs
-- -----------------------------------------------------------------------------

CREATE TABLE decision_snapshots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid REFERENCES tasks(id) ON DELETE SET NULL,
    step_id uuid REFERENCES task_steps(id) ON DELETE SET NULL,
    decision_type text NOT NULL CHECK (decision_type IN ('SCHEDULER_PICK', 'EVIDENCE_EVAL', 'RETRY_DECISION', 'RESOURCE_LOCK', 'RECOVERY_DECISION')),
    policy_version text,
    normalized_input_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    result_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_decision_snapshots_step_time ON decision_snapshots (step_id, created_at DESC);

CREATE TABLE state_transitions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type text NOT NULL CHECK (entity_type IN ('WORK_ORDER', 'TASK', 'TASK_STEP', 'ROBOT', 'SLOT', 'PALLET', 'COMMAND', 'LOCK', 'LEASE', 'RESERVATION', 'SAFETY_INCIDENT')),
    entity_id uuid NOT NULL,
    from_status text,
    to_status text NOT NULL,
    reason_code text NOT NULL,
    actor_id text,
    actor_role text,
    request_id text,
    trace_id text,
    source_ip text,
    transition_key text,
    evidence_event_id uuid REFERENCES evidence_events(id),
    command_id uuid REFERENCES command_requests(id),
    decision_snapshot_id uuid REFERENCES decision_snapshots(id),
    created_by text NOT NULL,                       -- scheduler, nav_event, ai_event, operator, reducer
    created_at timestamptz NOT NULL DEFAULT now(),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    prev_hash text,
    transition_hash text
);

CREATE INDEX idx_state_transitions_entity_time ON state_transitions (entity_type, entity_id, created_at DESC);
CREATE INDEX idx_state_transitions_reason ON state_transitions (reason_code, created_at DESC);
CREATE UNIQUE INDEX uq_state_transitions_key ON state_transitions (transition_key) WHERE transition_key IS NOT NULL;

CREATE TABLE api_call_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid REFERENCES tasks(id) ON DELETE SET NULL,
    step_id uuid REFERENCES task_steps(id) ON DELETE SET NULL,
    command_id uuid REFERENCES command_requests(id) ON DELETE SET NULL,
    target_system text NOT NULL,
    method text NOT NULL,
    url text NOT NULL,
    request_json jsonb,
    request_hash text,
    response_status integer,
    response_json jsonb,
    response_hash text,
    idempotency_key text,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    error_code text,
    error_message text,
    redaction_policy_version text
);

CREATE INDEX idx_api_call_logs_step_time ON api_call_logs (step_id, started_at DESC);

CREATE TABLE service_identities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name text NOT NULL UNIQUE,
    service_type text NOT NULL CHECK (service_type IN ('MAIN_SERVER', 'NAV_SERVER', 'AI_SERVER', 'ROBOT_BRIDGE', 'OPERATOR_UI')),
    auth_scheme text NOT NULL CHECK (auth_scheme IN ('MTLS', 'HMAC', 'JWT', 'LOCAL_DEV')),
    key_id text,
    allowed_actions jsonb NOT NULL DEFAULT '[]'::jsonb,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    rotated_at timestamptz
);

CREATE TABLE api_auth_audit (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    service_identity_id uuid REFERENCES service_identities(id),
    endpoint text NOT NULL,
    method text NOT NULL,
    auth_result text NOT NULL CHECK (auth_result IN ('ALLOW', 'DENY', 'ERROR')),
    request_id text,
    source_ip text,
    reason text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_api_auth_audit_time ON api_auth_audit (created_at DESC, auth_result);

-- -----------------------------------------------------------------------------
-- 10. Inventory transactions
-- -----------------------------------------------------------------------------

CREATE TABLE inventory_transactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pallet_id uuid NOT NULL REFERENCES pallets(id),
    transaction_type text NOT NULL CHECK (transaction_type IN ('RECEIVE', 'STORE', 'PICK', 'SHIP', 'ADJUST', 'VERIFY', 'RESERVE', 'RELEASE_RESERVATION')),
    from_waypoint_id uuid REFERENCES waypoints(id),
    to_waypoint_id uuid REFERENCES waypoints(id),
    from_slot_id uuid REFERENCES storage_slots(id),
    to_slot_id uuid REFERENCES storage_slots(id),
    from_robot_id uuid REFERENCES robots(id),
    to_robot_id uuid REFERENCES robots(id),
    task_id uuid REFERENCES tasks(id) ON DELETE SET NULL,
    step_id uuid REFERENCES task_steps(id) ON DELETE SET NULL,
    evidence_event_id uuid REFERENCES evidence_events(id),
    quantity integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_inventory_transactions_pallet_time ON inventory_transactions (pallet_id, created_at DESC);
CREATE INDEX idx_inventory_transactions_task ON inventory_transactions (task_id, step_id);
CREATE UNIQUE INDEX uq_inventory_transactions_step_type ON inventory_transactions (step_id, transaction_type) WHERE step_id IS NOT NULL;

-- -----------------------------------------------------------------------------
-- 11. Integration reliability: inbox/outbox
-- -----------------------------------------------------------------------------

CREATE TABLE inbox_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system text NOT NULL,
    external_event_id text NOT NULL,
    event_type text NOT NULL,
    payload_json jsonb NOT NULL,
    processing_status text NOT NULL DEFAULT 'PENDING' CHECK (processing_status IN ('PENDING', 'PROCESSED', 'FAILED', 'DUPLICATE', 'DEAD_LETTERED')),
    retry_count integer NOT NULL DEFAULT 0,
    max_attempts integer NOT NULL DEFAULT 5,
    next_attempt_at timestamptz,
    received_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz,
    dead_lettered_at timestamptz,
    error_message text,
    UNIQUE (source_system, external_event_id)
);

CREATE TABLE outbox_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type text NOT NULL,
    target_system text NOT NULL,
    aggregate_type text NOT NULL,
    aggregate_id uuid NOT NULL,
    payload_json jsonb NOT NULL,
    delivery_status text NOT NULL DEFAULT 'PENDING' CHECK (delivery_status IN ('PENDING', 'SENT', 'ACKED', 'FAILED', 'DEAD_LETTERED')),
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz,
    acked_at timestamptz,
    next_attempt_at timestamptz,
    delivery_deadline_at timestamptz,
    retry_count integer NOT NULL DEFAULT 0,
    max_attempts integer NOT NULL DEFAULT 5,
    dead_lettered_at timestamptz,
    error_message text
);

CREATE INDEX idx_outbox_events_pending ON outbox_events (delivery_status, created_at) WHERE delivery_status IN ('PENDING', 'FAILED');

CREATE TABLE dead_letter_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_table text NOT NULL CHECK (source_table IN ('inbox_events', 'outbox_events')),
    source_event_id uuid NOT NULL,
    reason_code text NOT NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    resolved_by text
);

-- -----------------------------------------------------------------------------
-- 12. Useful views
-- -----------------------------------------------------------------------------

CREATE VIEW slot_occupancy_current AS
SELECT
    s.id AS slot_id,
    s.code AS slot_code,
    s.status AS slot_status,
    p.id AS pallet_id,
    p.pallet_code,
    p.part_id,
    p.quantity,
    p.status AS pallet_status
FROM storage_slots s
LEFT JOIN pallets p
    ON p.current_slot_id = s.id
   AND p.status IN ('STORED', 'RESERVED_OUTBOUND');

CREATE VIEW active_robot_tasks AS
SELECT
    r.id AS robot_id,
    r.robot_code,
    r.status AS robot_status,
    t.id AS task_id,
    t.status AS task_status,
    ts.id AS step_id,
    ts.step_type,
    ts.status AS step_status
FROM robots r
LEFT JOIN tasks t ON t.assigned_robot_id = r.id AND t.status IN ('READY', 'RUNNING', 'BLOCKED', 'MANUAL_REVIEW')
LEFT JOIN task_steps ts ON ts.task_id = t.id AND ts.status NOT IN ('SUCCEEDED', 'FAILED', 'CANCELLED');

-- -----------------------------------------------------------------------------
-- 13. Seed examples for core zones/robots (adjust poses to real map)
-- -----------------------------------------------------------------------------

INSERT INTO maps (code, name, map_version) VALUES
    ('MAIN_LAB_MAP', 'Main lab MVP map', 'draft')
ON CONFLICT (code) DO NOTHING;

INSERT INTO map_zones (map_id, code, name, zone_type)
SELECT m.id, z.code, z.name, z.zone_type
FROM maps m
CROSS JOIN (VALUES
    ('INBOUND', '입고지역', 'INBOUND'),
    ('STORAGE_A', '창고지역 A', 'STORAGE'),
    ('OUTBOUND', '출고지역', 'OUTBOUND'),
    ('WAIT', '대기지역', 'WAIT')
) AS z(code, name, zone_type)
WHERE m.code = 'MAIN_LAB_MAP'
ON CONFLICT (code) DO NOTHING;

INSERT INTO robots (robot_code, namespace, display_name, status) VALUES
    ('tb3_1', '/tb3_1', 'TurtleBot3 #1', 'OFFLINE'),
    ('tb3_2', '/tb3_2', 'TurtleBot3 #2', 'OFFLINE')
ON CONFLICT (robot_code) DO NOTHING;

INSERT INTO robot_capabilities (robot_id, capability)
SELECT id, cap
FROM robots
CROSS JOIN (VALUES ('NAVIGATION'), ('LIFT'), ('PICAMERA'), ('ARUCO_DOCKING'), ('SAFETY_STOP')) AS c(cap)
ON CONFLICT DO NOTHING;

INSERT INTO evidence_sources (source_id, source_system, source_kind, robot_id, status, trusted_for_safety, trusted_for_inventory)
SELECT 'tb3_1_picam', 'AI_SERVER', 'ROBOT_PICAMERA', id, 'UNKNOWN', true, true FROM robots WHERE robot_code = 'tb3_1'
ON CONFLICT (source_id) DO NOTHING;

INSERT INTO evidence_sources (source_id, source_system, source_kind, robot_id, status, trusted_for_safety, trusted_for_inventory)
SELECT 'tb3_2_picam', 'AI_SERVER', 'ROBOT_PICAMERA', id, 'UNKNOWN', true, true FROM robots WHERE robot_code = 'tb3_2'
ON CONFLICT (source_id) DO NOTHING;

INSERT INTO evidence_sources (source_id, source_system, source_kind, status, trusted_for_safety, trusted_for_inventory) VALUES
    ('global_cam_01', 'AI_SERVER', 'GLOBAL_CAMERA', 'UNKNOWN', false, false)
ON CONFLICT (source_id) DO NOTHING;
