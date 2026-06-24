-- SQL dump generated using DBML (dbml.dbdiagram.io)
-- Database: PostgreSQL
-- Generated at: 2026-06-24T04:23:51.689Z

CREATE TABLE "robots" (
  "id" text PRIMARY KEY,
  "domain_id" integer NOT NULL,
  "status" text NOT NULL,
  "battery_level" float8,
  "location_id" text,
  "active_task_id" bigint,
  "last_seen_at" timestamptz
);

CREATE TABLE "locations" (
  "id" text PRIMARY KEY,
  "type" text NOT NULL,
  "status" text NOT NULL,
  "parent_id" text,
  "approach_id" text,
  "x" float8,
  "y" float8,
  "yaw" float8,
  "marker_id" integer
);

CREATE TABLE "items" (
  "id" text PRIMARY KEY
);

CREATE TABLE "inventory" (
  "item_id" text NOT NULL,
  "location_id" text NOT NULL,
  "quantity" integer NOT NULL DEFAULT 0,
  "updated_at" timestamptz,
  PRIMARY KEY ("item_id", "location_id")
);

CREATE TABLE "reservations" (
  "id" bigint PRIMARY KEY,
  "type" text NOT NULL,
  "status" text NOT NULL,
  "task_id" bigint NOT NULL,
  "robot_id" text,
  "location_id" text,
  "item_id" text,
  "expires_at" timestamptz,
  "released_at" timestamptz
);

CREATE TABLE "tasks" (
  "id" bigint PRIMARY KEY,
  "task_type" text NOT NULL,
  "status" text NOT NULL
);

COMMENT ON COLUMN "robots"."id" IS 'tb3_1/tb3_2';

COMMENT ON COLUMN "robots"."domain_id" IS 'ROS_DOMAIN_ID';

COMMENT ON COLUMN "robots"."status" IS 'IDLE/RESERVED/MOVING/DOCKING/LIFTING/PAUSED/ERROR/OFFLINE/CHARGING';

COMMENT ON COLUMN "locations"."id" IS 'INBOUND_01/STORAGE_A_01/OUTBOUND_01/CHARGE_01';

COMMENT ON COLUMN "locations"."type" IS 'AREA/WAYPOINT/SLOT/CHARGE';

COMMENT ON COLUMN "locations"."status" IS 'AVAILABLE/RESERVED/OCCUPIED/BLOCKED/UNKNOWN';

COMMENT ON COLUMN "locations"."approach_id" IS '정밀주차 전 접근 waypoint';

COMMENT ON COLUMN "locations"."marker_id" IS 'ArUco marker id';

COMMENT ON COLUMN "items"."id" IS '품목 식별값. MVP에서는 id 하나만 사용';

COMMENT ON COLUMN "reservations"."type" IS 'ROBOT/LOCATION/ITEM';

COMMENT ON COLUMN "reservations"."status" IS 'ACTIVE/RELEASED/EXPIRED/CANCELLED';

COMMENT ON COLUMN "tasks"."task_type" IS 'INBOUND/OUTBOUND/MOVE/RECOVERY/CHARGING';

ALTER TABLE "robots" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "robots" ADD FOREIGN KEY ("active_task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "locations" ADD FOREIGN KEY ("parent_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "locations" ADD FOREIGN KEY ("approach_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "inventory" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "inventory" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("task_id") REFERENCES "tasks" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("robot_id") REFERENCES "robots" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("location_id") REFERENCES "locations" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "reservations" ADD FOREIGN KEY ("item_id") REFERENCES "items" ("id") DEFERRABLE INITIALLY IMMEDIATE;
