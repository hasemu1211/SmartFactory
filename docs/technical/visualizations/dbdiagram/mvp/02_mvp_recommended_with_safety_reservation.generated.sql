-- SQL dump generated using DBML (dbml.dbdiagram.io)
-- Database: PostgreSQL
-- Generated at: 2026-06-23T07:43:49.480Z

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

CREATE TYPE "command_status" AS ENUM (
  'PENDING',
  'SENT',
  'ACKED',
  'SUCCEEDED',
  'FAILED',
  'TIMEOUT',
  'CANCELLED'
);

CREATE TYPE "task_result" AS ENUM (
  'SUCCESS',
  'FAILURE',
  'CANCELLED'
);

CREATE TYPE "evidence_event_type" AS ENUM (
  'FRAME',
  'DETECT',
  'NAV_REACHED',
  'ARUCO_DETECTED',
  'LOAD_DETECTED',
  'SLOT_CONFIRMED',
  'HUMAN_DETECTED',
  'HUMAN_CLEAR',
  'ERROR',
  'STATUS'
);

CREATE TYPE "inventory_event_type" AS ENUM (
  'INBOUND',
  'OUTBOUND',
  'MOVE',
  'ADJUST',
  'CORRECTION',
  'RESERVED',
  'RELEASED'
);

CREATE TYPE "incident_status" AS ENUM (
  'OPEN',
  'STOP_SENT',
  'STOPPED',
  'CLEAR_PENDING',
  'RESUME_ALLOWED',
  'CLOSED'
);

CREATE TYPE "reservation_status" AS ENUM (
  'ACTIVE',
  'RELEASED',
  'EXPIRED',
  'CANCELLED'
);

CREATE TABLE "locations" (
  "id" uuid PRIMARY KEY,
  "code" text UNIQUE NOT NULL,
  "name" text NOT NULL,
  "location_type" text NOT NULL,
  "parent_location_id" uuid,
  "approach_location_id" uuid,
  "status" text NOT NULL,
  "pose_x" float8,
  "pose_y" float8,
  "pose_yaw" float8,
  "capacity" integer,
  "aruco_marker_id" integer,
  "metadata_json" jsonb
);

CREATE TABLE "robots" (
  "id" uuid PRIMARY KEY,
  "robot_code" text UNIQUE NOT NULL,
  "robot_name" text NOT NULL,
  "status" robot_status NOT NULL,
  "battery_level" float8,
  "camera_id" uuid,
  "lift_id" uuid,
  "current_location_id" uuid,
  "active_task_id" uuid,
  "last_seen_at" timestamptz
);

CREATE TABLE "items" (
  "id" uuid PRIMARY KEY,
  "item_code" text UNIQUE NOT NULL,
  "item_name" text NOT NULL,
  "unit" text NOT NULL DEFAULT 'ea'
);

CREATE TABLE "inventory" (
  "item_id" uuid NOT NULL,
  "location_id" uuid NOT NULL,
  "quantity" integer NOT NULL DEFAULT 0,
  "updated_at" timestamptz,
  PRIMARY KEY ("item_id", "location_id")
);

CREATE TABLE "tasks" (
  "id" uuid PRIMARY KEY,
  "task_no" bigint UNIQUE,
  "task_type" text NOT NULL,
  "status" task_status NOT NULL,
  "priority" integer NOT NULL DEFAULT 0,
  "robot_id" uuid,
  "item_id" uuid,
  "quantity" integer NOT NULL DEFAULT 1,
  "source_location_id" uuid,
  "target_location_id" uuid,
  "command_payload_json" jsonb,
  "error_reason" text,
  "created_at" timestamptz,
  "updated_at" timestamptz
);

CREATE TABLE "commands" (
  "id" uuid PRIMARY KEY,
  "task_id" uuid,
  "robot_id" uuid,
  "sequence_no" integer NOT NULL DEFAULT 1,
  "command_type" text NOT NULL,
  "target_system" text NOT NULL,
  "status" command_status NOT NULL,
  "required_evidence_type" evidence_event_type,
  "idempotency_key" text UNIQUE NOT NULL,
  "request_json" jsonb,
  "response_json" jsonb,
  "deadline_at" timestamptz,
  "created_at" timestamptz,
  "updated_at" timestamptz
);

CREATE TABLE "evidence_events" (
  "id" uuid PRIMARY KEY,
  "event_type" evidence_event_type NOT NULL,
  "source_type" text NOT NULL,
  "source_code" text,
  "robot_id" uuid,
  "task_id" uuid,
  "command_id" uuid,
  "location_id" uuid,
  "confidence" float8,
  "severity" text NOT NULL DEFAULT 'INFO',
  "trusted_for_policy" boolean NOT NULL DEFAULT false,
  "evidence_text" text,
  "evidence_img_uri" text,
  "payload_json" jsonb,
  "observed_at" timestamptz,
  "created_at" timestamptz
);

CREATE TABLE "safety_incidents" (
  "id" uuid PRIMARY KEY,
  "status" incident_status NOT NULL,
  "robot_id" uuid,
  "task_id" uuid,
  "command_id" uuid,
  "triggering_evidence_id" uuid,
  "stop_command_id" uuid,
  "clear_evidence_id" uuid,
  "opened_at" timestamptz,
  "stopped_at" timestamptz,
  "closed_at" timestamptz,
  "note" text
);

CREATE TABLE "resource_reservations" (
  "id" uuid PRIMARY KEY,
  "reservation_type" text NOT NULL,
  "status" reservation_status NOT NULL,
  "task_id" uuid NOT NULL,
  "robot_id" uuid,
  "location_id" uuid,
  "item_id" uuid,
  "expires_at" timestamptz,
  "created_at" timestamptz,
  "released_at" timestamptz
);

CREATE TABLE "task_logs" (
  "id" uuid PRIMARY KEY,
  "task_id" uuid,
  "robot_id" uuid,
  "item_id" uuid,
  "quantity" integer,
  "task_type" text NOT NULL,
  "source_location_id" uuid,
  "target_location_id" uuid,
  "started_at" timestamptz NOT NULL,
  "finished_at" timestamptz,
  "result" task_result NOT NULL,
  "fail_reason" text,
  "detail" text,
  "command_payload_json" jsonb
);

CREATE TABLE "item_change_logs" (
  "id" uuid PRIMARY KEY,
  "item_id" uuid NOT NULL,
  "location_id" uuid,
  "task_id" uuid,
  "event_type" inventory_event_type NOT NULL,
  "quantity_change" integer NOT NULL,
  "quantity_before" integer,
  "quantity_after" integer,
  "reason" text,
  "changed_at" timestamptz NOT NULL
);

CREATE INDEX ON "locations" ("location_type");

CREATE INDEX ON "locations" ("status");

CREATE INDEX ON "locations" ("parent_location_id");

CREATE INDEX ON "locations" ("approach_location_id");

CREATE INDEX ON "robots" ("status");

CREATE INDEX ON "robots" ("current_location_id");

CREATE INDEX ON "robots" ("active_task_id");

CREATE INDEX ON "robots" ("last_seen_at");

CREATE INDEX ON "inventory" ("location_id");

CREATE INDEX ON "tasks" ("status");

CREATE INDEX ON "tasks" ("robot_id");

CREATE INDEX ON "tasks" ("item_id");

CREATE INDEX ON "tasks" ("source_location_id");

CREATE INDEX ON "tasks" ("target_location_id");

CREATE INDEX ON "tasks" ("created_at");

CREATE INDEX ON "commands" ("task_id");

CREATE INDEX ON "commands" ("robot_id");

CREATE INDEX ON "commands" ("status");

CREATE INDEX ON "commands" ("required_evidence_type");

CREATE INDEX ON "commands" ("created_at");

CREATE UNIQUE INDEX ON "commands" ("task_id", "sequence_no");

CREATE INDEX ON "evidence_events" ("event_type");

CREATE INDEX ON "evidence_events" ("severity");

CREATE INDEX ON "evidence_events" ("source_type");

CREATE INDEX ON "evidence_events" ("robot_id");

CREATE INDEX ON "evidence_events" ("task_id");

CREATE INDEX ON "evidence_events" ("command_id");

CREATE INDEX ON "evidence_events" ("location_id");

CREATE INDEX ON "evidence_events" ("trusted_for_policy");

CREATE INDEX ON "evidence_events" ("created_at");

CREATE INDEX ON "safety_incidents" ("status");

CREATE INDEX ON "safety_incidents" ("robot_id");

CREATE INDEX ON "safety_incidents" ("task_id");

CREATE INDEX ON "safety_incidents" ("triggering_evidence_id");

CREATE INDEX ON "safety_incidents" ("opened_at");

CREATE INDEX ON "resource_reservations" ("status");

CREATE INDEX ON "resource_reservations" ("task_id");

CREATE INDEX ON "resource_reservations" ("robot_id");

CREATE INDEX ON "resource_reservations" ("location_id");

CREATE INDEX ON "resource_reservations" ("item_id");

CREATE INDEX ON "resource_reservations" ("expires_at");

CREATE INDEX ON "task_logs" ("task_id");

CREATE INDEX ON "task_logs" ("robot_id");

CREATE INDEX ON "task_logs" ("result");

CREATE INDEX ON "task_logs" ("started_at");

CREATE INDEX ON "item_change_logs" ("item_id");

CREATE INDEX ON "item_change_logs" ("location_id");

CREATE INDEX ON "item_change_logs" ("task_id");

CREATE INDEX ON "item_change_logs" ("event_type");

CREATE INDEX ON "item_change_logs" ("changed_at");

COMMENT ON COLUMN "locations"."code" IS 'INBOUND_01/STORAGE_A_01/OUTBOUND_01/CHARGE_01';

COMMENT ON COLUMN "locations"."location_type" IS 'AREA/WAYPOINT/SLOT/CHARGE';

COMMENT ON COLUMN "locations"."status" IS 'AVAILABLE/RESERVED/OCCUPIED/BLOCKED/UNKNOWN';

COMMENT ON COLUMN "robots"."robot_code" IS 'tb3_1/tb3_2';

COMMENT ON COLUMN "robots"."camera_id" IS 'optional external hardware id; no FK in MVP';

COMMENT ON COLUMN "robots"."lift_id" IS 'optional external hardware id; no FK in MVP';

COMMENT ON COLUMN "tasks"."task_type" IS 'INBOUND/OUTBOUND/MOVE/RECOVERY';

COMMENT ON COLUMN "commands"."sequence_no" IS 'Lightweight step order inside a task';

COMMENT ON COLUMN "commands"."command_type" IS 'NAV_GOAL/DOCK_ARUCO/LIFT_UP/LIFT_DOWN/STOP/RESUME';

COMMENT ON COLUMN "commands"."target_system" IS 'NAV_SERVER/AI_SERVER/ROBOT_BRIDGE';

COMMENT ON COLUMN "commands"."required_evidence_type" IS 'nullable; required evidence before command is accepted as complete';

COMMENT ON COLUMN "evidence_events"."source_type" IS 'GLOBAL_CAMERA/PICAMERA/NAV_SERVER/ROBOT/OPERATOR';

COMMENT ON COLUMN "evidence_events"."source_code" IS 'global_cam_01/tb3_1_picam/nav_server';

COMMENT ON COLUMN "evidence_events"."severity" IS 'INFO/WARN/ERROR/SAFETY';

COMMENT ON COLUMN "safety_incidents"."triggering_evidence_id" IS 'usually HUMAN_DETECTED';

COMMENT ON COLUMN "safety_incidents"."clear_evidence_id" IS 'usually HUMAN_CLEAR';

COMMENT ON COLUMN "resource_reservations"."reservation_type" IS 'ROBOT/LOCATION/ITEM';

COMMENT ON COLUMN "resource_reservations"."robot_id" IS 'set when reservation_type=ROBOT';

COMMENT ON COLUMN "resource_reservations"."location_id" IS 'set when reservation_type=LOCATION';

COMMENT ON COLUMN "resource_reservations"."item_id" IS 'set when reservation_type=ITEM';

ALTER TABLE "locations" ADD FOREIGN KEY ("parent_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "locations" ADD FOREIGN KEY ("approach_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "robots" ADD FOREIGN KEY ("current_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "inventory" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "inventory" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("source_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("target_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commands" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commands" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("command_id") REFERENCES "commands" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_incidents" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_incidents" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_incidents" ADD FOREIGN KEY ("command_id") REFERENCES "commands" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_incidents" ADD FOREIGN KEY ("triggering_evidence_id") REFERENCES "evidence_events" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_incidents" ADD FOREIGN KEY ("stop_command_id") REFERENCES "commands" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_incidents" ADD FOREIGN KEY ("clear_evidence_id") REFERENCES "evidence_events" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "resource_reservations" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "resource_reservations" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "resource_reservations" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "resource_reservations" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "task_logs" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "task_logs" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "task_logs" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "task_logs" ADD FOREIGN KEY ("source_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "task_logs" ADD FOREIGN KEY ("target_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "item_change_logs" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "item_change_logs" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "item_change_logs" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "robots" ADD FOREIGN KEY ("active_task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;
