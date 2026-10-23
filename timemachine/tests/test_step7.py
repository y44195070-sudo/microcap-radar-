import os, sys, unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),"..")))
from src.schema import connect
from src.time_utils import normalize_utc, TimestampError
from src.pit import add_fact, get_context
from src.snapshot import build_snapshot
from src.trading_calendar import get_eod_cutoff
from src.massive_provider import MassiveProvider, massive_verdict
from src.sec_ingest import parse_sec_header, accepted_to_utc, ingest_sec_header

SKYQ='''<ACCEPTANCE-DATETIME>20260112172619\nACCESSION NUMBER: 0001096906-26-000077\nCONFORMED SUBMISSION TYPE: 8-K\nCONFORMED PERIOD OF REPORT: 20260112\nFILED AS OF DATE: 20260112\nCENTRAL INDEX KEY: 0001812447\n'''
UBER='''<ACCEPTANCE-DATETIME>20260112070438\nACCESSION NUMBER: 0001543151-26-000005\nCONFORMED SUBMISSION TYPE: 8-K\nCONFORMED PERIOD OF REPORT: 20260112\nFILED AS OF DATE: 20260112\nCENTRAL INDEX KEY: 0001543151\n'''

class Step7Tests(unittest.TestCase):
 def test_same_instant_offsets(self): self.assertEqual(normalize_utc('2026-01-10T16:00:00-05:00'),'2026-01-10T21:00:00Z')
 def test_naive_rejected(self):
  with self.assertRaises(TimestampError): normalize_utc('2026-01-10T16:00:00')
 def test_explicit_source_timezone(self): self.assertEqual(normalize_utc('2026-01-10T16:00:00',source_timezone='America/New_York'),'2026-01-10T21:00:00Z')
 def test_dst(self):
  self.assertEqual(normalize_utc('2026-01-10T16:00:00-05:00'),'2026-01-10T21:00:00Z')
  self.assertEqual(normalize_utc('2026-07-10T16:00:00-04:00'),'2026-07-10T20:00:00Z')
 def test_cutoff_boundary(self):
  c=connect(); add_fact(c,entity_id='X',ticker='X',fact_type='x',value=1,as_of='2026-01-12T21:00:00Z',known_at='2026-01-12T21:00:00Z',collected_at='2026-02-01T00:00:00Z',source='T',source_id='1')
  self.assertEqual(len(get_context(c,'X','2026-01-12T16:00:00-05:00')['facts']),1)
 def test_snapshot_timezone_reproducible(self):
  c=connect(); add_fact(c,entity_id='X',ticker='X',fact_type='x',value=1,as_of='2026-01-12T20:00:00Z',known_at='2026-01-12T20:00:00Z',collected_at='2026-02-01T00:00:00Z',source='T',source_id='1')
  a=get_context(c,'X','2026-01-12T16:00:00-05:00'); b=get_context(c,'X','2026-01-12T21:00:00Z'); self.assertEqual(a['context_packet_hash'],b['context_packet_hash'])
 def test_calendar_january(self):
  self.assertEqual(get_eod_cutoff('2026-01-12'),'2026-01-12T21:00:00Z')
  with self.assertRaises(ValueError): get_eod_cutoff('2026-01-19')
 def test_calendar_dst_and_early_close(self):
  self.assertEqual(get_eod_cutoff('2026-07-10'),'2026-07-10T20:00:00Z')
  self.assertEqual(get_eod_cutoff('2026-11-27'),'2026-11-27T18:00:00Z')
 def test_real_sec_acceptance_samples(self):
  self.assertEqual(accepted_to_utc(parse_sec_header(SKYQ)['accepted_raw']),'2026-01-12T22:26:19Z')
  self.assertEqual(accepted_to_utc(parse_sec_header(UBER)['accepted_raw']),'2026-01-12T12:04:38Z')
 def test_sec_before_after_cutoff_and_idempotency(self):
  c=connect(); collected='2026-10-23T00:00:00Z'
  ingest_sec_header(c,header_text=UBER,ticker='UBER',collected_at=collected,source_url='SEC')
  ingest_sec_header(c,header_text=SKYQ,ticker='SKYQ',collected_at=collected,source_url='SEC')
  self.assertEqual(len(get_context(c,'CIK0001543151','2026-01-12T21:00:00Z')['facts']),1)
  self.assertEqual(len(get_context(c,'CIK0001812447','2026-01-12T21:00:00Z')['facts']),0)
  self.assertEqual(ingest_sec_header(c,header_text=UBER,ticker='UBER',collected_at=collected,source_url='SEC'),'DUPLICATE_SKIPPED')
 def test_massive_without_key_is_unverified(self):
  p=MassiveProvider(api_key=None); p.api_key=None; rows=p.coverage_report('2026-01-12'); self.assertTrue(all(not r['verified'] for r in rows)); self.assertEqual(massive_verdict(rows),'CONDITIONAL')

if __name__=='__main__': unittest.main()
