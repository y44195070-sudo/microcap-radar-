import sqlite3, unittest
from timemachine.src.schema import connect
from timemachine.src.pit import add_fact, get_context, assert_context_clean, LeakageError
from timemachine.src.snapshot import build_snapshot, seal_snapshot
from timemachine.src.prediction import PredictionEngine, OutcomeAccessError

CUT="2026-01-10T21:00:00+00:00"

class TimeMachineTests(unittest.TestCase):
    def setUp(self):
        self.db=connect()
        add_fact(self.db,entity_id="CIK1",ticker="TEST",fact_type="price",value=1.25,as_of=CUT,known_at=CUT,source="market",source_id="p1")

    def test_A_future_fact_leakage(self):
        add_fact(self.db,entity_id="CIK1",ticker="TEST",fact_type="warrant_exercise",value=1000000,as_of="2026-01-08T00:00:00+00:00",known_at="2026-01-12T14:00:00+00:00",source="sec",source_id="8k-late")
        ctx=get_context(self.db,"CIK1",CUT)
        self.assertNotIn("warrant_exercise",[f["fact_type"] for f in ctx["facts"]])

    def test_B_filing_revision_does_not_change_old_snapshot(self):
        ctx=get_context(self.db,"CIK1",CUT)
        snap=build_snapshot(run_id="r1",model_version="A0",rule_version="unfrozen",dataset_version="d1",universe_version="u1",context_packet=ctx)
        old_hash=snap["snapshot_hash"]
        seal_snapshot(self.db,snap)
        add_fact(self.db,entity_id="CIK1",ticker="TEST",fact_type="os",value=9000000,as_of="2026-01-05T00:00:00+00:00",known_at="2026-01-15T12:00:00+00:00",source="sec",source_id="amendment")
        self.assertEqual(old_hash,self.db.execute("SELECT snapshot_hash FROM prediction_snapshots").fetchone()[0])
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE prediction_snapshots SET model_version='X'")

    def test_C_future_corporate_action_not_in_context(self):
        add_fact(self.db,entity_id="CIK1",ticker="TEST",fact_type="reverse_split",value={"ratio":"1:20"},as_of="2026-01-20T00:00:00+00:00",known_at="2026-01-18T12:00:00+00:00",source="corp",source_id="rs1")
        ctx=get_context(self.db,"CIK1",CUT)
        self.assertNotIn("reverse_split",[f["fact_type"] for f in ctx["facts"]])

    def test_D_outcome_isolation(self):
        engine=PredictionEngine(lambda e,c:get_context(self.db,e,c))
        with self.assertRaises(OutcomeAccessError): engine.outcomes("CIK1")

    def test_E_reproducibility(self):
        ctx1=get_context(self.db,"CIK1",CUT); ctx2=get_context(self.db,"CIK1",CUT)
        self.assertEqual(ctx1["context_packet_hash"],ctx2["context_packet_hash"])
        kw=dict(run_id="r",model_version="A0",rule_version="unfrozen",dataset_version="d1",universe_version="u1",structure_score=None,prediction=None,data_coverage={})
        self.assertEqual(build_snapshot(context_packet=ctx1,**kw)["snapshot_hash"],build_snapshot(context_packet=ctx2,**kw)["snapshot_hash"])

    def test_negative_control_rejects_injected_future_fact(self):
        ctx=get_context(self.db,"CIK1",CUT)
        ctx["facts"].append({"known_at":"2026-01-11T00:00:00+00:00"})
        with self.assertRaises(LeakageError): assert_context_clean(ctx)

    def test_append_only_fact(self):
        with self.assertRaises(sqlite3.IntegrityError): self.db.execute("UPDATE pit_facts SET ticker='X'")
        with self.assertRaises(sqlite3.IntegrityError): self.db.execute("DELETE FROM pit_facts")

if __name__ == "__main__": unittest.main()
