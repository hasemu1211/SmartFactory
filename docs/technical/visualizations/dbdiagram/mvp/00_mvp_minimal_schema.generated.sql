-- SQL dump generated using DBML (dbml.dbdiagram.io)
-- Database: PostgreSQL
-- Generated at: 2026-06-23T06:04:37.988Z

CREATE TYPE "robot_status" AS ENUM (
  'IDLE',
  'RESERVED',
  'MOVING',
  'DOCKING',
  'LIFTING',
  'PAUSED',
  'ERROR',
  'OFFLINE',
  'CHARGING'
);

CREATE TYPE "task_status" AS ENUM (
  'PENDING',
  'RUNNING',
  'PAUSED',
  'COMPLETED',
  'FAILED',
  'CANCELLED',
  'NEEDS_REVIEW'
);

CREATE TYPE "step_status" AS ENUM (
  'PENDING',
  'READY',
  'COMMAND_SENT',
  'EXECUTING',
  'WAITING_EVIDENCE',
  'COMPLETED',
  'FAILED',
  'SKIPPED'
);

CREATE TYPE "command_status" AS ENUM (
  'PENDING',
  'SENT',
  'ACKED',
  'SUCCEEDED',
  'FAILED',
  'TIMEOUT',
  'CANCELLED'
);

CREATE TYPE "incident_status" AS ENUM (
  'OPEN',
  'STOP_SENT',
  'STOPPED',
  'CLEAR_PENDING',
  'RESUME_ALLOWED',
  'CLOSED'
);

CREATE TABLE "locations" (
  "id" uuid PRIMARY KEY,
  "code" text UNIQUE NOT NULL,
  "location_type" text NOT NULL,
  "parent_location_id" uuid,
  "approach_location_id" uuid,
  "status" text NOT NULL,
  "pose_x" float8,
  "pose_y" float8,
  "pose_yaw" float8,
  "aruco_marker_id" integer,
  "metadata_json" jsonb
);

CREATE TABLE "robots" (
  "id" uuid PRIMARY KEY,
  "robot_code" text UNIQUE NOT NULL,
  "namespace" text UNIQUE NOT NULL,
  "status" robot_status NOT NULL,
  "battery_level" float8,
  "current_location_id" uuid,
  "active_task_id" uuid,
  "last_seen_at" timestamptz
);

CREATE TABLE "evidence_sources" (
  "id" uuid PRIMARY KEY,
  "source_code" text UNIQUE NOT NULL,
  "source_type" text NOT NULL,
  "robot_id" uuid,
  "status" text NOT NULL,
  "trusted_for_safety" boolean NOT NULL,
  "trusted_for_inventory" boolean NOT NULL,
  "last_seen_at" timestamptz
);

CREATE TABLE "inventory_units" (
  "id" uuid PRIMARY KEY,
  "unit_code" text UNIQUE NOT NULL,
  "part_no" text NOT NULL,
  "part_name" text,
  "quantity" integer NOT NULL,
  "status" text NOT NULL,
  "current_location_id" uuid,
  "current_robot_id" uuid,
  "updated_at" timestamptz
);

CREATE TABLE "tasks" (
  "id" uuid PRIMARY KEY,
  "task_no" bigint UNIQUE,
  "task_type" text NOT NULL,
  "status" task_status NOT NULL,
  "priority" integer NOT NULL,
  "robot_id" uuid,
  "inventory_unit_id" uuid,
  "source_location_id" uuid,
  "target_location_id" uuid,
  "error_reason" text,
  "created_at" timestamptz,
  "updated_at" timestamptz
);

CREATE TABLE "task_steps" (
  "id" uuid PRIMARY KEY,
  "task_id" uuid NOT NULL,
  "sequence_no" integer NOT NULL,
  "step_type" text NOT NULL,
  "status" step_status NOT NULL,
  "command_id" uuid,
  "required_evidence" text,
  "retry_count" integer NOT NULL,
  "timeout_at" timestamptz
);

CREATE TABLE "resource_reservations" (
  "id" uuid PRIMARY KEY,
  "resource_type" text NOT NULL,
  "resource_id" uuid NOT NULL,
  "task_id" uuid NOT NULL,
  "status" text NOT NULL,
  "expires_at" timestamptz,
  "created_at" timestamptz
);

CREATE TABLE "commands" (
  "id" uuid PRIMARY KEY,
  "task_id" uuid,
  "step_id" uuid,
  "robot_id" uuid,
  "command_type" text NOT NULL,
  "target_system" text NOT NULL,
  "status" command_status NOT NULL,
  "idempotency_key" text UNIQUE NOT NULL,
  "request_json" jsonb,
  "response_json" jsonb,
  "deadline_at" timestamptz,
  "created_at" timestamptz,
  "updated_at" timestamptz
);

CREATE TABLE "evidence_events" (
  "id" uuid PRIMARY KEY,
  "source_id" uuid,
  "task_id" uuid,
  "step_id" uuid,
  "robot_id" uuid,
  "evidence_type" text NOT NULL,
  "confidence" float8,
  "severity" text NOT NULL,
  "trusted_for_policy" boolean NOT NULL,
  "artifact_uri" text,
  "payload_json" jsonb,
  "observed_at" timestamptz,
  "created_at" timestamptz
);

CREATE TABLE "safety_incidents" (
  "id" uuid PRIMARY KEY,
  "robot_id" uuid,
  "task_id" uuid,
  "step_id" uuid,
  "status" incident_status NOT NULL,
  "triggering_evidence_id" uuid,
  "stop_command_id" uuid,
  "clear_evidence_id" uuid,
  "opened_at" timestamptz,
  "closed_at" timestamptz
);

CREATE TABLE "event_log" (
  "id" uuid PRIMARY KEY,
  "event_type" text NOT NULL,
  "entity_type" text NOT NULL,
  "entity_id" uuid NOT NULL,
  "task_id" uuid,
  "step_id" uuid,
  "robot_id" uuid,
  "command_id" uuid,
  "evidence_id" uuid,
  "from_status" text,
  "to_status" text,
  "actor" text NOT NULL,
  "message" text,
  "payload_json" jsonb,
  "created_at" timestamptz
);

CREATE UNIQUE INDEX ON "task_steps" ("task_id", "sequence_no");

CREATE INDEX ON "resource_reservations" ("resource_type", "resource_id", "status");

COMMENT ON COLUMN "locations"."code" IS 'INBOUND_01/STORAGE_A_01/OUTBOUND_01/CHARGE_01';

COMMENT ON COLUMN "locations"."location_type" IS 'AREA/WAYPOINT/SLOT/CHARGE';

COMMENT ON COLUMN "locations"."parent_location_id" IS 'AREA contains WAYPOINT/SLOT';

COMMENT ON COLUMN "locations"."approach_location_id" IS 'SLOT approach waypoint';

COMMENT ON COLUMN "locations"."status" IS 'AVAILABLE/RESERVED/OCCUPIED/BLOCKED/UNKNOWN';

COMMENT ON COLUMN "locations"."aruco_marker_id" IS 'nullable; used for precision docking';

COMMENT ON COLUMN "robots"."robot_code" IS 'tb3_1/tb3_2';

COMMENT ON COLUMN "evidence_sources"."source_code" IS 'global_cam_01/tb3_1_picam/nav_server';

COMMENT ON COLUMN "evidence_sources"."source_type" IS 'GLOBAL_CAMERA/PICAMERA/NAV/ROBOT/OPERATOR';

COMMENT ON COLUMN "evidence_sources"."status" IS 'ONLINE/OFFLINE/STALE';

COMMENT ON COLUMN "inventory_units"."unit_code" IS 'pallet or tote code';

COMMENT ON COLUMN "inventory_units"."status" IS 'INBOUND/STORED/RESERVED/ON_ROBOT/OUTBOUND/UNKNOWN';

COMMENT ON COLUMN "tasks"."task_type" IS 'INBOUND_STORE/OUTBOUND_PICK/MOVE/RECOVERY';

COMMENT ON COLUMN "task_steps"."step_type" IS 'MOVE/DOCK/LIFT_UP/LIFT_DOWN/VERIFY/COMMIT/STOP';

COMMENT ON COLUMN "task_steps"."required_evidence" IS 'e.g. NAV_REACHED, ARUCO_DETECTED, LOAD_DETECTED, SLOT_CONFIRMED';

COMMENT ON COLUMN "resource_reservations"."resource_type" IS 'ROBOT/LOCATION/INVENTORY_UNIT';

COMMENT ON COLUMN "resource_reservations"."resource_id" IS 'polymorphic id; enforce in app or with later constraints';

COMMENT ON COLUMN "resource_reservations"."status" IS 'ACTIVE/RELEASED/EXPIRED/CANCELLED';

COMMENT ON COLUMN "commands"."command_type" IS 'NAV_GOAL/DOCK_ARUCO/LIFT_UP/LIFT_DOWN/STOP/RESUME';

COMMENT ON COLUMN "commands"."target_system" IS 'NAV_SERVER/AI_SERVER/ROBOT_BRIDGE';

COMMENT ON COLUMN "evidence_events"."evidence_type" IS 'NAV_REACHED/ARUCO_DETECTED/LOAD_DETECTED/SLOT_CONFIRMED/HUMAN_DETECTED/HUMAN_CLEAR';

COMMENT ON COLUMN "evidence_events"."severity" IS 'INFO/WARN/ERROR/SAFETY';

COMMENT ON COLUMN "event_log"."event_type" IS 'STATUS_CHANGED/COMMAND_EVENT/API_CALL/OPERATOR_ACTION/INVENTORY_CHANGED/ERROR';

COMMENT ON COLUMN "event_log"."entity_type" IS 'TASK/STEP/ROBOT/COMMAND/EVIDENCE/INVENTORY/LOCATION/INCIDENT';

COMMENT ON COLUMN "event_log"."actor" IS 'MAIN/NAV/AI/ROBOT/OPERATOR/SCHEDULER';

ALTER TABLE "locations" ADD FOREIGN KEY ("parent_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "locations" ADD FOREIGN KEY ("approach_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "robots" ADD FOREIGN KEY ("current_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_sources" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "inventory_units" ADD FOREIGN KEY ("current_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "inventory_units" ADD FOREIGN KEY ("current_robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("inventory_unit_id") REFERENCES "inventory_units" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("source_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("target_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "task_steps" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "resource_reservations" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commands" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commands" ADD FOREIGN KEY ("step_id") REFERENCES "task_steps" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commands" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("source_id") REFERENCES "evidence_sources" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("step_id") REFERENCES "task_steps" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_incidents" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_incidents" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_incidents" ADD FOREIGN KEY ("step_id") REFERENCES "task_steps" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_incidents" ADD FOREIGN KEY ("triggering_evidence_id") REFERENCES "evidence_events" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_incidents" ADD FOREIGN KEY ("stop_command_id") REFERENCES "commands" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_incidents" ADD FOREIGN KEY ("clear_evidence_id") REFERENCES "evidence_events" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "event_log" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "event_log" ADD FOREIGN KEY ("step_id") REFERENCES "task_steps" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "event_log" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "event_log" ADD FOREIGN KEY ("command_id") REFERENCES "commands" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "event_log" ADD FOREIGN KEY ("evidence_id") REFERENCES "evidence_events" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "robots" ADD FOREIGN KEY ("active_task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "task_steps" ADD FOREIGN KEY ("command_id") REFERENCES "commands" ("id") DEFERRABLE INITIALLY IMMEDIATE;
