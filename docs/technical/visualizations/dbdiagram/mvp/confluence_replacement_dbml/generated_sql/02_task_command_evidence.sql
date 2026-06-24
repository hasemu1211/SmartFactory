-- SQL dump generated using DBML (dbml.dbdiagram.io)
-- Database: PostgreSQL
-- Generated at: 2026-06-24T04:23:57.794Z

CREATE TABLE "tasks" (
  "id" bigint PRIMARY KEY,
  "task_type" text NOT NULL,
  "status" text NOT NULL,
  "priority" integer NOT NULL DEFAULT 0,
  "robot_id" text,
  "item_id" text,
  "quantity" integer NOT NULL DEFAULT 1,
  "from_location_id" text,
  "to_location_id" text,
  "started_at" timestamptz,
  "finished_at" timestamptz
);

CREATE TABLE "commands" (
  "id" bigint PRIMARY KEY,
  "task_id" bigint,
  "robot_id" text,
  "sequence_no" integer NOT NULL,
  "command_type" text NOT NULL,
  "target_system" text NOT NULL,
  "status" text NOT NULL,
  "location_id" text,
  "required_evidence_type" text,
  "idempotency_key" text UNIQUE NOT NULL,
  "request_json" jsonb,
  "response_json" jsonb
);

CREATE TABLE "evidence_events" (
  "id" bigint PRIMARY KEY,
  "event_type" text NOT NULL,
  "source" text NOT NULL,
  "robot_id" text,
  "task_id" bigint,
  "command_id" bigint,
  "location_id" text,
  "confidence" float8,
  "severity" text NOT NULL DEFAULT 'INFO',
  "trusted" boolean NOT NULL DEFAULT false,
  "image_uri" text,
  "data_json" jsonb,
  "observed_at" timestamptz
);

CREATE TABLE "task_logs" (
  "id" bigint PRIMARY KEY,
  "task_id" bigint NOT NULL,
  "robot_id" text,
  "result" text NOT NULL,
  "snapshot_json" jsonb,
  "logged_at" timestamptz NOT NULL
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

CREATE TABLE "robots" (
  "id" text PRIMARY KEY,
  "domain_id" integer NOT NULL,
  "status" text NOT NULL
);

CREATE TABLE "items" (
  "id" text PRIMARY KEY
);

CREATE TABLE "locations" (
  "id" text PRIMARY KEY,
  "type" text NOT NULL,
  "status" text NOT NULL,
  "approach_id" text,
  "marker_id" integer
);

CREATE UNIQUE INDEX ON "commands" ("task_id", "sequence_no");

COMMENT ON COLUMN "tasks"."task_type" IS 'INBOUND/OUTBOUND/MOVE/RECOVERY/CHARGING';

COMMENT ON COLUMN "tasks"."status" IS 'PENDING/RUNNING/PAUSED/COMPLETED/FAILED/CANCELLED/NEEDS_REVIEW';

COMMENT ON COLUMN "commands"."sequence_no" IS 'task 내부 실행 순서';

COMMENT ON COLUMN "commands"."command_type" IS 'NAV_GOAL/PICK_UP/DROP_OFF/STOP/RESUME/START_CHARGING/STOP_CHARGING';

COMMENT ON COLUMN "commands"."target_system" IS 'NAV_SERVER/AI_SERVER/ROBOT_BRIDGE';

COMMENT ON COLUMN "commands"."status" IS 'PENDING/SENT/ACKED/SUCCEEDED/FAILED/TIMEOUT/CANCELLED';

COMMENT ON COLUMN "commands"."location_id" IS 'API 요청 합성에 사용할 목표/작업 위치';

COMMENT ON COLUMN "commands"."required_evidence_type" IS 'NAV_REACHED/ITEM_PICKED/ITEM_PLACED/HUMAN_CLEAR';

COMMENT ON COLUMN "commands"."request_json" IS 'task/location/command 필드로 합성한 실제 API 요청 스냅샷';

COMMENT ON COLUMN "evidence_events"."event_type" IS 'NAV_REACHED/ARUCO_DETECTED/LOAD_DETECTED/ITEM_PICKED/ITEM_PLACED/SLOT_CONFIRMED/HUMAN_DETECTED/HUMAN_CLEAR/ERROR/STATUS';

COMMENT ON COLUMN "evidence_events"."source" IS 'global_cam_01/tb3_1_picam/nav_server/operator';

COMMENT ON COLUMN "evidence_events"."severity" IS 'INFO/WARN/ERROR/SAFETY';

COMMENT ON COLUMN "reservations"."type" IS 'ROBOT/LOCATION/ITEM';

COMMENT ON COLUMN "reservations"."status" IS 'ACTIVE/RELEASED/EXPIRED/CANCELLED';

ALTER TABLE "tasks" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("from_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("to_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commands" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commands" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commands" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("command_id") REFERENCES "commands" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "task_logs" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "task_logs" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "locations" ADD FOREIGN KEY ("approach_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;
