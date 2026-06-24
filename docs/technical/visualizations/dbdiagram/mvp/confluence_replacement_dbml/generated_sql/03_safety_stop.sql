-- SQL dump generated using DBML (dbml.dbdiagram.io)
-- Database: PostgreSQL
-- Generated at: 2026-06-24T04:24:03.948Z

CREATE TABLE "robots" (
  "id" text PRIMARY KEY,
  "domain_id" integer NOT NULL,
  "status" text NOT NULL,
  "active_task_id" bigint
);

CREATE TABLE "tasks" (
  "id" bigint PRIMARY KEY,
  "task_type" text NOT NULL,
  "status" text NOT NULL,
  "robot_id" text
);

CREATE TABLE "commands" (
  "id" bigint PRIMARY KEY,
  "task_id" bigint,
  "robot_id" text,
  "sequence_no" integer NOT NULL,
  "command_type" text NOT NULL,
  "target_system" text NOT NULL,
  "status" text NOT NULL,
  "idempotency_key" text UNIQUE NOT NULL
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
  "severity" text NOT NULL DEFAULT 'SAFETY',
  "trusted" boolean NOT NULL DEFAULT false,
  "image_uri" text,
  "observed_at" timestamptz
);

CREATE TABLE "safety_stops" (
  "id" bigint PRIMARY KEY,
  "status" text NOT NULL,
  "robot_id" text,
  "task_id" bigint,
  "detected_evidence_id" bigint,
  "stop_command_id" bigint,
  "clear_evidence_id" bigint,
  "opened_at" timestamptz,
  "closed_at" timestamptz
);

CREATE TABLE "locations" (
  "id" text PRIMARY KEY,
  "type" text NOT NULL
);

COMMENT ON COLUMN "robots"."id" IS 'tb3_1/tb3_2';

COMMENT ON COLUMN "robots"."status" IS 'MOVING/PAUSED/ERROR/etc';

COMMENT ON COLUMN "tasks"."task_type" IS 'INBOUND/OUTBOUND/MOVE/RECOVERY/CHARGING';

COMMENT ON COLUMN "tasks"."status" IS 'RUNNING/PAUSED/FAILED/etc';

COMMENT ON COLUMN "commands"."command_type" IS 'STOP/RESUME/NAV_GOAL/etc';

COMMENT ON COLUMN "commands"."target_system" IS 'NAV_SERVER/ROBOT_BRIDGE';

COMMENT ON COLUMN "commands"."status" IS 'PENDING/SENT/ACKED/SUCCEEDED/FAILED/TIMEOUT/CANCELLED';

COMMENT ON COLUMN "evidence_events"."event_type" IS 'HUMAN_DETECTED/HUMAN_CLEAR';

COMMENT ON COLUMN "evidence_events"."source" IS 'global_cam_01/tb3_1_picam/operator';

COMMENT ON COLUMN "safety_stops"."status" IS 'OPEN/STOP_SENT/STOPPED/CLEAR_PENDING/RESUME_ALLOWED/CLOSED';

COMMENT ON COLUMN "safety_stops"."detected_evidence_id" IS 'HUMAN_DETECTED';

COMMENT ON COLUMN "safety_stops"."stop_command_id" IS 'STOP';

COMMENT ON COLUMN "safety_stops"."clear_evidence_id" IS 'HUMAN_CLEAR';

ALTER TABLE "robots" ADD FOREIGN KEY ("active_task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commands" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commands" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("command_id") REFERENCES "commands" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_stops" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_stops" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_stops" ADD FOREIGN KEY ("detected_evidence_id") REFERENCES "evidence_events" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_stops" ADD FOREIGN KEY ("stop_command_id") REFERENCES "commands" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_stops" ADD FOREIGN KEY ("clear_evidence_id") REFERENCES "evidence_events" ("id") DEFERRABLE INITIALLY IMMEDIATE;
