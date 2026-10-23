from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone

class LeakageError(RuntimeError): pass


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256_obj(obj):
    return hashlib.sha256(_canon(obj).encode("utf-8")).hexdigest()

def add_fact(conn, *, entity_id, ticker, fact_type, value, as_of, known_at, source, source_id, status="KNOWN", collected_at=None, event_at=None, effective_at=None, published_at=None):
    collected_at = collected_at or datetime.now(timezone.utc).isoformat()
    source_hash = sha256_obj({"source":source,"source_id":source_id,"fact_type":fact_type,"value":value,"as_of":as_of,"known_at":known_at,"status":status})
    conn.execute("""INSERT INTO pit_facts(entity_id,ticker,fact_type,value_json,as_of,known_at,collected_at,event_at,effective_at,published_at,source,source_id,source_hash,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (entity_id,ticker,fact_type,_canon(value),as_of,known_at,collected_at,event_at,effective_at,published_at,source,source_id,source_hash,status))
    conn.commit()
    return source_hash

def get_context(conn, entity_id, cutoff):
    rows = conn.execute("SELECT * FROM pit_facts WHERE entity_id=? ORDER BY fact_id", (entity_id,)).fetchall()
    facts=[]
    for r in rows:
        if r["status"] != "KNOWN":
            continue
        if not r["known_at"]:
            raise LeakageError(f"KNOWN fact lacks known_at: {r['source_id']}")
        if r["known_at"] > cutoff:
            continue
        facts.append({k:r[k] for k in r.keys()})
    # Defense in depth: packet must contain no future-known fact.
    if any(f["known_at"] > cutoff for f in facts):
        raise LeakageError("future fact entered context packet")
    packet={"entity_id":entity_id,"cutoff":cutoff,"facts":facts}
    packet["context_packet_hash"] = sha256_obj(packet)
    return packet

def assert_context_clean(packet):
    cutoff=packet["cutoff"]
    if any(f.get("known_at") and f["known_at"] > cutoff for f in packet["facts"]):
        raise LeakageError("context packet contains future-known fact")
    return True
