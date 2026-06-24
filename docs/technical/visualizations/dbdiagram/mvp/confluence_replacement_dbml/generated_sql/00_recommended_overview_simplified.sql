-- SQL dump generated using DBML (dbml.dbdiagram.io)
-- Database: PostgreSQL
-- Generated at: 2026-06-24T04:23:45.537Z

CREATE TABLE "locations" (
  "id" text PRIMARY KEY,
  "type" text NOT NULL,
  "status" text NOT NULL,
  "approach_id" text,
  "marker_id" integer
);

CREATE TABLE "robots" (
  "id" text PRIMARY KEY,
  "domain_id" integer NOT NULL,
  "status" text NOT NULL,
  "battery_level" float8,
  "location_id" text,
  "active_task_id" bigint
);

CREATE TABLE "items" (
  "id" text PRIMARY KEY
);

CREATE TABLE "inventory" (
  "item_id" text NOT NULL,
  "location_id" text NOT NULL,
  "quantity" integer NOT NULL,
  PRIMARY KEY ("item_id", "location_id")
);

CREATE TABLE "tasks" (
  "id" bigint PRIMARY KEY,
  "task_type" text NOT NULL,
  "status" text NOT NULL,
  "robot_id" text,
  "item_id" text,
  "from_location_id" text,
  "to_location_id" text
);

CREATE TABLE "reservations" (
  "id" bigint PRIMARY KEY,
  "type" text NOT NULL,
  "status" text NOT NULL,
  "task_id" bigint NOT NULL,
  "robot_id" text,
  "location_id" text,
  "item_id" text
);

CREATE TABLE "commands" (
  "id" bigint PRIMARY KEY,
  "task_id" bigint,
  "robot_id" text,
  "sequence_no" integer NOT NULL,
  "command_type" text NOT NULL,
  "status" text NOT NULL,
  "location_id" text,
  "required_evidence_type" text
);

CREATE TABLE "evidence_events" (
  "id" bigint PRIMARY KEY,
  "event_type" text NOT NULL,
  "source" text NOT NULL,
  "robot_id" text,
  "task_id" bigint,
  "command_id" bigint,
  "location_id" text,
  "trusted" boolean NOT NULL DEFAULT false
);

CREATE TABLE "safety_stops" (
  "id" bigint PRIMARY KEY,
  "status" text NOT NULL,
  "robot_id" text,
  "task_id" bigint,
  "detected_evidence_id" bigint,
  "stop_command_id" bigint,
  "clear_evidence_id" bigint
);

CREATE TABLE "task_logs" (
  "id" bigint PRIMARY KEY,
  "task_id" bigint NOT NULL,
  "robot_id" text,
  "result" text NOT NULL,
  "snapshot_json" jsonb,
  "logged_at" timestamptz NOT NULL
);

CREATE TABLE "item_change_logs" (
  "id" bigint PRIMARY KEY,
  "item_id" text NOT NULL,
  "location_id" text,
  "task_id" bigint,
  "event_type" text NOT NULL,
  "quantity_change" integer NOT NULL
);

COMMENT ON COLUMN "locations"."id" IS 'INBOUND_01/STORAGE_A_01/OUTBOUND_01/CHARGE_01';

COMMENT ON COLUMN "locations"."type" IS 'AREA/WAYPOINT/SLOT/CHARGE';

COMMENT ON COLUMN "locations"."status" IS 'AVAILABLE/RESERVED/OCCUPIED/BLOCKED/UNKNOWN';

COMMENT ON COLUMN "locations"."marker_id" IS 'ArUco marker id';

COMMENT ON COLUMN "robots"."id" IS 'tb3_1/tb3_2';

COMMENT ON COLUMN "robots"."domain_id" IS 'ROS_DOMAIN_ID';

COMMENT ON COLUMN "robots"."status" IS 'IDLE/RESERVED/MOVING/DOCKING/LIFTING/PAUSED/ERROR/OFFLINE/CHARGING';

COMMENT ON COLUMN "items"."id" IS 'BOLT_M3/MOTOR_A/SENSOR_KIT';

COMMENT ON COLUMN "tasks"."task_type" IS 'INBOUND/OUTBOUND/MOVE/RECOVERY/CHARGING';

COMMENT ON COLUMN "tasks"."status" IS 'PENDING/RUNNING/PAUSED/COMPLETED/FAILED/CANCELLED/NEEDS_REVIEW';

COMMENT ON COLUMN "reservations"."type" IS 'ROBOT/LOCATION/ITEM';

COMMENT ON COLUMN "reservations"."status" IS 'ACTIVE/RELEASED/EXPIRED/CANCELLED';

COMMENT ON COLUMN "commands"."sequence_no" IS 'task 내부 실행 순서';

COMMENT ON COLUMN "commands"."command_type" IS 'NAV_GOAL/PICK_UP/DROP_OFF/STOP/RESUME/START_CHARGING/STOP_CHARGING';

COMMENT ON COLUMN "commands"."status" IS 'PENDING/SENT/ACKED/SUCCEEDED/FAILED/TIMEOUT/CANCELLED';

COMMENT ON COLUMN "commands"."required_evidence_type" IS 'NAV_REACHED/ITEM_PICKED/ITEM_PLACED/HUMAN_CLEAR';

COMMENT ON COLUMN "evidence_events"."event_type" IS 'NAV_REACHED/ITEM_PICKED/ITEM_PLACED/HUMAN_DETECTED/HUMAN_CLEAR/etc';

COMMENT ON COLUMN "evidence_events"."source" IS 'global_cam_01/tb3_1_picam/nav_server/operator';

COMMENT ON COLUMN "safety_stops"."status" IS 'OPEN/STOP_SENT/STOPPED/CLEAR_PENDING/RESUME_ALLOWED/CLOSED';

COMMENT ON COLUMN "task_logs"."result" IS 'SUCCESS/FAILURE/CANCELLED/NEEDS_REVIEW';

COMMENT ON COLUMN "item_change_logs"."event_type" IS 'INBOUND/OUTBOUND/MOVE/ADJUST/CORRECTION/RESERVED/RELEASED';

ALTER TABLE "locations" ADD FOREIGN KEY ("approach_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "robots" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "robots" ADD FOREIGN KEY ("active_task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "inventory" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "inventory" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("from_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("to_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commands" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commands" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commands" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("command_id") REFERENCES "commands" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_stops" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_stops" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_stops" ADD FOREIGN KEY ("detected_evidence_id") REFERENCES "evidence_events" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_stops" ADD FOREIGN KEY ("stop_command_id") REFERENCES "commands" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_stops" ADD FOREIGN KEY ("clear_evidence_id") REFERENCES "evidence_events" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "task_logs" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "task_logs" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "item_change_logs" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "item_change_logs" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "item_change_logs" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;
