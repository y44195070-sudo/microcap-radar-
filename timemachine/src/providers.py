from __future__ import annotations
from abc import ABC, abstractmethod

class MarketDataProvider(ABC):
    @abstractmethod
    def universe(self, trading_date: str): ...

    @abstractmethod
    def daily_ohlcv(self, ticker: str, trading_date: str, *, adjusted: bool = False): ...

    @abstractmethod
    def ticker_events(self, ticker: str): ...

    @abstractmethod
    def coverage_report(self, trading_date: str): ...
