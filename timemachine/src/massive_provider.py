from __future__ import annotations
import json, os
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from .providers import MarketDataProvider

class MassiveAccessError(RuntimeError): pass

class MassiveProvider(MarketDataProvider):
    BASE="https://api.massive.com"
    def __init__(self, api_key: str | None = None):
        self.api_key=api_key or os.getenv("MASSIVE_API_KEY")

    def _get(self, path, params=None):
        if not self.api_key:
            raise MassiveAccessError("UNVERIFIED — API ACCESS REQUIRED: set MASSIVE_API_KEY")
        q=dict(params or {}); q["apiKey"]=self.api_key
        req=Request(f"{self.BASE}{path}?{urlencode(q)}", headers={"User-Agent":"MicrocapRadar-TimeMachine/1.0"})
        with urlopen(req, timeout=30) as r:
            return json.load(r)

    def universe(self, trading_date: str):
        results=[]; url="/v3/reference/tickers"; params={"market":"stocks","active":"true","date":trading_date,"limit":1000}
        while url:
            data=self._get(url, params); results.extend(data.get("results",[])); nxt=data.get("next_url")
            if not nxt: break
            url=nxt.replace(self.BASE,"").split("?",1)[0]; params={"cursor":nxt.split("cursor=",1)[1].split("&",1)[0]} if "cursor=" in nxt else {}
        return results

    def daily_ohlcv(self, ticker: str, trading_date: str, *, adjusted: bool=False):
        return self._get(f"/v2/aggs/ticker/{ticker}/range/1/day/{trading_date}/{trading_date}", {"adjusted":str(adjusted).lower(),"limit":50000})

    def ticker_events(self, ticker: str):
        return self._get(f"/vX/reference/tickers/{ticker}/events")

    def coverage_report(self, trading_date: str):
        tests=["historical_universe","delisted_survivors","pre_ipo_exclusion","ticker_changes","reverse_split_raw_price","unadjusted_ohlc","unadjusted_volume","halt_vs_missing","exchange_classification","security_type_classification"]
        tested=datetime.now(timezone.utc).isoformat()
        if not self.api_key:
            return [{"test":t,"required":True,"available":None,"verified":False,"coverage":None,"failure_reason":"UNVERIFIED — API ACCESS REQUIRED","source":"Massive","tested_at":tested} for t in tests]
        return [{"test":t,"required":True,"available":None,"verified":False,"coverage":None,"failure_reason":"API configured; explicit January 2026 sample verification still required","source":"Massive","tested_at":tested} for t in tests]

def massive_verdict(rows):
    required=[r for r in rows if r["required"]]
    if any(r["verified"] is False for r in required): return "CONDITIONAL"
    return "PASS" if required and all(r.get("coverage")==1.0 for r in required) else "CONDITIONAL"
