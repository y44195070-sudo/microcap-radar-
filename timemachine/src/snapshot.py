from __future__ import annotations
import json
from datetime import datetime, timezone
from .pit import sha256_obj, assert_context_clean


def build_snapshot(*, run_id, model_version, rule_version, dataset_version, universe_version, context_packet, structure_score=None, prediction=None, data_coverage=None, created_at=None):
    assert_context_clean(context_packet)
    body={
      "run_id":run_id,"model_version":model_version,"rule_version":rule_version,
      "dataset_version":dataset_version,"universe_version":universe_version,
      "cutoff":context_packet["cutoff"],"entity_id":context_packet["entity_id"],
      "context_packet_hash":context_packet["context_packet_hash"],
      "structure_score":structure_score,"prediction":prediction,
      "data_coverage":data_coverage or {},
      # created_at deliberately excluded from deterministic hash payload.
    }
    snapshot_hash=sha256_obj(body)
    return {**body,"snapshot_hash":snapshot_hash,"created_at":created_at or datetime.now(timezone.utc).isoformat()}

def seal_snapshot(conn, snapshot):
    conn.execute("""INSERT INTO prediction_snapshots(snapshot_hash,run_id,model_version,rule_version,dataset_version,universe_version,cutoff,entity_id,context_packet_hash,structure_score,prediction_json,data_coverage_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (snapshot["snapshot_hash"],snapshot["run_id"],snapshot["model_version"],snapshot["rule_version"],snapshot["dataset_version"],snapshot["universe_version"],snapshot["cutoff"],snapshot["entity_id"],snapshot["context_packet_hash"],snapshot["structure_score"],json.dumps(snapshot["prediction"],sort_keys=True),json.dumps(snapshot["data_coverage"],sort_keys=True),snapshot["created_at"]))
    conn.commit()
    return snapshot["snapshot_hash"]
