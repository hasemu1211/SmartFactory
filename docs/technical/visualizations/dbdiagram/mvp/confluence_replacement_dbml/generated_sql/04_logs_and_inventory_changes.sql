-- SQL dump generated using DBML (dbml.dbdiagram.io)
-- Database: PostgreSQL
-- Generated at: 2026-06-24T04:24:10.095Z

CREATE TABLE "tasks" (
  "id" bigint PRIMARY KEY,
  "task_type" text NOT NULL,
  "status" text NOT NULL,
  "robot_id" text,
  "item_id" text,
  "quantity" integer NOT NULL,
  "from_location_id" text,
  "to_location_id" text,
  "error_reason" text,
  "started_at" timestamptz,
  "finished_at" timestamptz
);

CREATE TABLE "task_logs" (
  "id" bigint PRIMARY KEY,
  "task_id" bigint NOT NULL,
  "robot_id" text,
  "item_id" text,
  "task_type" text NOT NULL,
  "result" text NOT NULL,
  "quantity" integer,
  "from_location_id" text,
  "to_location_id" text,
  "started_at" timestamptz,
  "finished_at" timestamptz,
  "fail_reason" text,
  "summary" text,
  "snapshot_json" jsonb,
  "logged_at" timestamptz NOT NULL
);

CREATE TABLE "inventory" (
  "item_id" text NOT NULL,
  "location_id" text NOT NULL,
  "quantity" integer NOT NULL DEFAULT 0,
  "updated_at" timestamptz,
  PRIMARY KEY ("item_id", "location_id")
);

CREATE TABLE "item_change_logs" (
  "id" bigint PRIMARY KEY,
  "item_id" text NOT NULL,
  "location_id" text,
  "task_id" bigint,
  "event_type" text NOT NULL,
  "quantity_change" integer NOT NULL,
  "quantity_before" integer,
  "quantity_after" integer,
  "reason" text,
  "changed_at" timestamptz NOT NULL
);

CREATE TABLE "evidence_events" (
  "id" bigint PRIMARY KEY,
  "event_type" text NOT NULL,
  "task_id" bigint,
  "command_id" bigint,
  "trusted" boolean NOT NULL DEFAULT false,
  "image_uri" text,
  "observed_at" timestamptz
);

CREATE TABLE "commands" (
  "id" bigint PRIMARY KEY,
  "task_id" bigint,
  "sequence_no" integer NOT NULL,
  "command_type" text NOT NULL,
  "status" text NOT NULL,
  "required_evidence_type" text
);

CREATE TABLE "robots" (
  "id" text PRIMARY KEY,
  "domain_id" integer NOT NULL
);

CREATE TABLE "items" (
  "id" text PRIMARY KEY
);

CREATE TABLE "locations" (
  "id" text PRIMARY KEY,
  "type" text NOT NULL,
  "status" text NOT NULL
);

COMMENT ON COLUMN "tasks"."task_type" IS 'INBOUND/OUTBOUND/MOVE/RECOVERY/CHARGING';

COMMENT ON COLUMN "tasks"."status" IS 'COMPLETED/FAILED/CANCELLED/NEEDS_REVIEW';

COMMENT ON COLUMN "task_logs"."result" IS 'SUCCESS/FAILURE/CANCELLED/NEEDS_REVIEW';

COMMENT ON COLUMN "item_change_logs"."event_type" IS 'INBOUND/OUTBOUND/MOVE/ADJUST/CORRECTION/RESERVED/RELEASED';

COMMENT ON COLUMN "evidence_events"."event_type" IS 'ITEM_PICKED/ITEM_PLACED/SLOT_CONFIRMED/etc';

COMMENT ON COLUMN "commands"."command_type" IS 'PICK_UP/DROP_OFF/NAV_GOAL/etc';

ALTER TABLE "tasks" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("from_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("to_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "task_logs" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "task_logs" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "task_logs" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "task_logs" ADD FOREIGN KEY ("from_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "task_logs" ADD FOREIGN KEY ("to_location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "inventory" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "inventory" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "item_change_logs" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "item_change_logs" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "item_change_logs" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "evidence_events" ADD FOREIGN KEY ("command_id") REFERENCES "commands" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commands" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;
