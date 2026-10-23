from __future__ import annotations
import sqlite3

FACT_STATUSES = ("KNOWN", "NOT_PUBLIC_YET", "UNAVAILABLE", "AMBIGUOUS")

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS pit_facts (
  fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_id TEXT NOT NULL,
  ticker TEXT NOT NULL,
  fact_type TEXT NOT NULL,
  value_json TEXT,
  as_of TEXT NOT NULL,
  known_at TEXT,
  collected_at TEXT NOT NULL,
  event_at TEXT,
  effective_at TEXT,
  published_at TEXT,
  source TEXT NOT NULL,
  source_id TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('KNOWN','NOT_PUBLIC_YET','UNAVAILABLE','AMBIGUOUS')),
  UNIQUE(source, source_id, source_hash)
);

CREATE TABLE IF NOT EXISTS prediction_snapshots (
  snapshot_hash TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  model_version TEXT NOT NULL,
  rule_version TEXT NOT NULL,
  dataset_version TEXT NOT NULL,
  universe_version TEXT NOT NULL,
  cutoff TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  context_packet_hash TEXT NOT NULL,
  structure_score REAL,
  prediction_json TEXT,
  data_coverage_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outcomes (
  outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_hash TEXT NOT NULL,
  horizon_trading_days INTEGER NOT NULL,
  outcome_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(snapshot_hash) REFERENCES prediction_snapshots(snapshot_hash)
);

CREATE TRIGGER IF NOT EXISTS pit_facts_no_update
BEFORE UPDATE ON pit_facts BEGIN SELECT RAISE(ABORT, 'pit_facts is append-only'); END;
CREATE TRIGGER IF NOT EXISTS pit_facts_no_delete
BEFORE DELETE ON pit_facts BEGIN SELECT RAISE(ABORT, 'pit_facts is append-only'); END;
CREATE TRIGGER IF NOT EXISTS snapshots_no_update
BEFORE UPDATE ON prediction_snapshots BEGIN SELECT RAISE(ABORT, 'snapshot is immutable'); END;
CREATE TRIGGER IF NOT EXISTS snapshots_no_delete
BEFORE DELETE ON prediction_snapshots BEGIN SELECT RAISE(ABORT, 'snapshot is immutable'); END;
"""

def connect(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    return conn
