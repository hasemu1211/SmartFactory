-- SQL dump generated using DBML (dbml.dbdiagram.io)
-- Database: PostgreSQL
-- Generated at: 2026-06-24T03:07:29.200Z

CREATE TABLE "locations" (
  "code" text PRIMARY KEY,
  "kind" text NOT NULL,
  "status" text NOT NULL,
  "parent_code" text,
  "approach_code" text,
  "x" float8,
  "y" float8,
  "yaw" float8,
  "marker_id" integer
);

CREATE TABLE "robots" (
  "code" text PRIMARY KEY,
  "status" text NOT NULL,
  "battery" float8,
  "location_code" text,
  "current_task_id" bigint,
  "last_seen_at" timestamptz
);

CREATE TABLE "items" (
  "code" text PRIMARY KEY,
  "unit" text NOT NULL DEFAULT 'ea'
);

CREATE TABLE "stock" (
  "item_code" text NOT NULL,
  "location_code" text NOT NULL,
  "quantity" integer NOT NULL DEFAULT 0,
  "updated_at" timestamptz,
  PRIMARY KEY ("item_code", "location_code")
);

CREATE TABLE "tasks" (
  "id" bigint PRIMARY KEY,
  "kind" text NOT NULL,
  "status" text NOT NULL,
  "priority" integer NOT NULL DEFAULT 0,
  "robot_code" text,
  "item_code" text,
  "quantity" integer NOT NULL DEFAULT 1,
  "from_location_code" text,
  "to_location_code" text,
  "error" text,
  "created_at" timestamptz,
  "started_at" timestamptz,
  "finished_at" timestamptz
);

CREATE TABLE "reservations" (
  "id" bigint PRIMARY KEY,
  "kind" text NOT NULL,
  "status" text NOT NULL,
  "task_id" bigint NOT NULL,
  "robot_code" text,
  "location_code" text,
  "item_code" text,
  "expires_at" timestamptz,
  "released_at" timestamptz
);

CREATE TABLE "commands" (
  "id" bigint PRIMARY KEY,
  "task_id" bigint,
  "robot_code" text,
  "order_no" integer NOT NULL DEFAULT 1,
  "kind" text NOT NULL,
  "target" text NOT NULL,
  "status" text NOT NULL,
  "required_proof" text,
  "request_key" text UNIQUE NOT NULL,
  "request_json" jsonb,
  "response_json" jsonb,
  "deadline_at" timestamptz,
  "created_at" timestamptz,
  "updated_at" timestamptz
);

CREATE TABLE "proofs" (
  "id" bigint PRIMARY KEY,
  "kind" text NOT NULL,
  "source" text NOT NULL,
  "robot_code" text,
  "task_id" bigint,
  "command_id" bigint,
  "location_code" text,
  "confidence" float8,
  "level" text NOT NULL DEFAULT 'INFO',
  "trusted" boolean NOT NULL DEFAULT false,
  "image_uri" text,
  "data_json" jsonb,
  "seen_at" timestamptz
);

CREATE TABLE "safety_stops" (
  "id" bigint PRIMARY KEY,
  "status" text NOT NULL,
  "robot_code" text,
  "task_id" bigint,
  "detected_proof_id" bigint,
  "stop_command_id" bigint,
  "clear_proof_id" bigint,
  "opened_at" timestamptz,
  "closed_at" timestamptz
);

CREATE TABLE "stock_logs" (
  "id" bigint PRIMARY KEY,
  "item_code" text NOT NULL,
  "location_code" text,
  "task_id" bigint,
  "kind" text NOT NULL,
  "change_qty" integer NOT NULL,
  "before_qty" integer,
  "after_qty" integer,
  "note" text,
  "changed_at" timestamptz NOT NULL
);

CREATE INDEX ON "locations" ("kind");

CREATE INDEX ON "locations" ("status");

CREATE INDEX ON "locations" ("parent_code");

CREATE INDEX ON "locations" ("approach_code");

CREATE INDEX ON "robots" ("status");

CREATE INDEX ON "robots" ("location_code");

CREATE INDEX ON "robots" ("current_task_id");

CREATE INDEX ON "robots" ("last_seen_at");

CREATE INDEX ON "stock" ("location_code");

CREATE INDEX ON "tasks" ("status");

CREATE INDEX ON "tasks" ("robot_code");

CREATE INDEX ON "tasks" ("item_code");

CREATE INDEX ON "tasks" ("from_location_code");

CREATE INDEX ON "tasks" ("to_location_code");

CREATE INDEX ON "tasks" ("created_at");

CREATE INDEX ON "reservations" ("status");

CREATE INDEX ON "reservations" ("task_id");

CREATE INDEX ON "reservations" ("robot_code");

CREATE INDEX ON "reservations" ("location_code");

CREATE INDEX ON "reservations" ("item_code");

CREATE INDEX ON "reservations" ("expires_at");

CREATE INDEX ON "commands" ("task_id");

CREATE INDEX ON "commands" ("robot_code");

CREATE INDEX ON "commands" ("status");

CREATE INDEX ON "commands" ("required_proof");

CREATE INDEX ON "commands" ("created_at");

CREATE UNIQUE INDEX ON "commands" ("task_id", "order_no");

CREATE INDEX ON "proofs" ("kind");

CREATE INDEX ON "proofs" ("source");

CREATE INDEX ON "proofs" ("robot_code");

CREATE INDEX ON "proofs" ("task_id");

CREATE INDEX ON "proofs" ("command_id");

CREATE INDEX ON "proofs" ("location_code");

CREATE INDEX ON "proofs" ("trusted");

CREATE INDEX ON "proofs" ("seen_at");

CREATE INDEX ON "safety_stops" ("status");

CREATE INDEX ON "safety_stops" ("robot_code");

CREATE INDEX ON "safety_stops" ("task_id");

CREATE INDEX ON "safety_stops" ("detected_proof_id");

CREATE INDEX ON "safety_stops" ("opened_at");

CREATE INDEX ON "stock_logs" ("item_code");

CREATE INDEX ON "stock_logs" ("location_code");

CREATE INDEX ON "stock_logs" ("task_id");

CREATE INDEX ON "stock_logs" ("kind");

CREATE INDEX ON "stock_logs" ("changed_at");

COMMENT ON COLUMN "locations"."code" IS 'INBOUND_01/STORAGE_A_01/OUTBOUND_01/CHARGE_01';

COMMENT ON COLUMN "locations"."kind" IS 'AREA/WAYPOINT/SLOT/CHARGE';

COMMENT ON COLUMN "locations"."status" IS 'AVAILABLE/RESERVED/OCCUPIED/BLOCKED/UNKNOWN';

COMMENT ON COLUMN "locations"."marker_id" IS 'ArUco marker id, nullable';

COMMENT ON COLUMN "robots"."code" IS 'tb3_1/tb3_2';

COMMENT ON COLUMN "robots"."status" IS 'IDLE/RESERVED/MOVING/DOCKING/LIFTING/PAUSED/ERROR/OFFLINE/CHARGING';

COMMENT ON COLUMN "items"."code" IS 'BOLT_M3/MOTOR_A/SENSOR_KIT';

COMMENT ON COLUMN "tasks"."kind" IS 'INBOUND/OUTBOUND/MOVE/RECOVERY';

COMMENT ON COLUMN "tasks"."status" IS 'PENDING/RUNNING/PAUSED/COMPLETED/FAILED/CANCELLED/NEEDS_REVIEW';

COMMENT ON COLUMN "reservations"."kind" IS 'ROBOT/LOCATION/ITEM';

COMMENT ON COLUMN "reservations"."status" IS 'ACTIVE/RELEASED/EXPIRED/CANCELLED';

COMMENT ON COLUMN "commands"."order_no" IS 'command order inside a task';

COMMENT ON COLUMN "commands"."kind" IS 'NAV_GOAL/DOCK_ARUCO/LIFT_UP/LIFT_DOWN/STOP/RESUME';

COMMENT ON COLUMN "commands"."target" IS 'NAV_SERVER/AI_SERVER/ROBOT_BRIDGE';

COMMENT ON COLUMN "commands"."status" IS 'PENDING/SENT/ACKED/SUCCEEDED/FAILED/TIMEOUT/CANCELLED';

COMMENT ON COLUMN "commands"."required_proof" IS 'NAV_REACHED/ARUCO_DETECTED/LOAD_DETECTED/SLOT_CONFIRMED';

COMMENT ON COLUMN "commands"."request_key" IS 'idempotency key';

COMMENT ON COLUMN "proofs"."kind" IS 'NAV_REACHED/ARUCO_DETECTED/LOAD_DETECTED/SLOT_CONFIRMED/HUMAN_DETECTED/HUMAN_CLEAR/ERROR/STATUS';

COMMENT ON COLUMN "proofs"."source" IS 'global_cam_01/tb3_1_picam/nav_server/operator';

COMMENT ON COLUMN "proofs"."level" IS 'INFO/WARN/ERROR/SAFETY';

COMMENT ON COLUMN "safety_stops"."status" IS 'OPEN/STOP_SENT/STOPPED/CLEAR_PENDING/RESUME_ALLOWED/CLOSED';

COMMENT ON COLUMN "stock_logs"."kind" IS 'INBOUND/OUTBOUND/MOVE/ADJUST/CORRECTION/RESERVED/RELEASED';

ALTER TABLE "locations" ADD FOREIGN KEY ("parent_code") REFERENCES "locations" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "locations" ADD FOREIGN KEY ("approach_code") REFERENCES "locations" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "robots" ADD FOREIGN KEY ("location_code") REFERENCES "locations" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "stock" ADD FOREIGN KEY ("item_code") REFERENCES "items" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "stock" ADD FOREIGN KEY ("location_code") REFERENCES "locations" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("robot_code") REFERENCES "robots" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("item_code") REFERENCES "items" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("from_location_code") REFERENCES "locations" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tasks" ADD FOREIGN KEY ("to_location_code") REFERENCES "locations" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("robot_code") REFERENCES "robots" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("location_code") REFERENCES "locations" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("item_code") REFERENCES "items" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commands" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "commands" ADD FOREIGN KEY ("robot_code") REFERENCES "robots" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "proofs" ADD FOREIGN KEY ("robot_code") REFERENCES "robots" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "proofs" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "proofs" ADD FOREIGN KEY ("command_id") REFERENCES "commands" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "proofs" ADD FOREIGN KEY ("location_code") REFERENCES "locations" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_stops" ADD FOREIGN KEY ("robot_code") REFERENCES "robots" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_stops" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_stops" ADD FOREIGN KEY ("detected_proof_id") REFERENCES "proofs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_stops" ADD FOREIGN KEY ("stop_command_id") REFERENCES "commands" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "safety_stops" ADD FOREIGN KEY ("clear_proof_id") REFERENCES "proofs" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "stock_logs" ADD FOREIGN KEY ("item_code") REFERENCES "items" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "stock_logs" ADD FOREIGN KEY ("location_code") REFERENCES "locations" ("code") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "stock_logs" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "robots" ADD FOREIGN KEY ("current_task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;
