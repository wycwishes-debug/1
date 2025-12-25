"""Background monitoring service.

The monitor polls external data sources and pushes updates into an
``asyncio.Queue`` for the UI to consume. It deliberately avoids keeping a
reference to any UI objects to keep concerns separated.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, time
from typing import Iterable, List, Optional, Set
from zoneinfo import ZoneInfo

import aiohttp
from plyer import notification

from app.ai.gemini import AnalysisResult, GeminiClient
from app.database.db import AnalysisRecord, Database, NewsRecord
from app.data_sources import finnhub, yahoo

logger = logging.getLogger(__name__)


@dataclass
class QuoteUpdate:
    ticker: str
    price: Optional[float]
    change: Optional[float]
    percent: Optional[float]
    sparkline: List[float]


@dataclass
class NewsAnalysisEvent:
    ticker: str
    headline: str
    datetime: int
    summary: str
    emotion: str
    level: int
    reasoning: str
    risks: str


def _market_open_now() -> bool:
    eastern = ZoneInfo("America/New_York")
    now = datetime.now(tz=eastern)
    open_time = time(9, 30, tzinfo=eastern)
    close_time = time(16, 0, tzinfo=eastern)
    return open_time <= now.timetz() <= close_time and now.weekday() < 5


class MonitorService:
    """Fetches quotes, news, and AI insights asynchronously."""

    def __init__(self, db: Database, event_queue: asyncio.Queue, log_dir) -> None:
        self.db = db
        self.queue = event_queue
        self.log_dir = log_dir
        self._running = True
        self._seen_urls: Set[str] = set()
        self.finnhub_client = finnhub.FinnhubClient(token=os.getenv("FINNHUB_TOKEN"))
        self.gemini_client = GeminiClient()

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        """Main polling loop."""

        async with aiohttp.ClientSession() as session:
            while self._running:
                try:
                    await self._poll_once(session)
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001
                    logger.exception("Monitor polling iteration failed")
                await asyncio.sleep(45 if _market_open_now() else 300)

    async def poll_ticker_once(self, ticker: str) -> None:
        """Manually trigger a single ticker refresh.

        This helper is used by manual UI commands and does not interfere
        with the primary loop.
        """

        async with aiohttp.ClientSession() as session:
            await self._process_ticker(session, ticker)

    async def _poll_once(self, session: aiohttp.ClientSession) -> None:
        watchlist = await self.db.fetch_watchlist()
        if not watchlist:
            return

        await asyncio.gather(*(self._process_ticker(session, ticker) for ticker in watchlist))
        await self._process_general_news(session, watchlist)

    async def _process_ticker(self, session: aiohttp.ClientSession, ticker: str) -> None:
        quote = await self.finnhub_client.fetch_quote(session, ticker)
        sparkline = await yahoo.fetch_intraday_sparkline(session, ticker)
        update = QuoteUpdate(
            ticker=ticker.upper(),
            price=quote.get("price") if quote else None,
            change=quote.get("change") if quote else None,
            percent=quote.get("percent") if quote else None,
            sparkline=sparkline,
        )
        await self.queue.put(update)

        news_items = await self.finnhub_client.fetch_company_news(session, ticker)
        await self._handle_news_items(news_items)

    async def _process_general_news(
        self, session: aiohttp.ClientSession, tickers: Iterable[str]
    ) -> None:
        news_items = await self.finnhub_client.fetch_general_news(session, tickers)
        await self._handle_news_items(news_items)

    async def _handle_news_items(self, items: List[finnhub.FinnhubNews]) -> None:
        for item in items:
            if item.url in self._seen_urls:
                continue
            self._seen_urls.add(item.url)
            await self.db.record_news(
                NewsRecord(
                    ticker=item.ticker,
                    headline=item.headline,
                    url=item.url,
                    datetime=item.datetime,
                )
            )
            analysis = await self.gemini_client.analyze(item.ticker, item.headline, item.summary)
            await self.db.record_analysis(
                AnalysisRecord(
                    ticker=analysis.ticker,
                    emotion=analysis.emotion,
                    level=analysis.level,
                    summary=analysis.summary,
                    reasoning=analysis.reasoning,
                    risks=analysis.risks,
                )
            )

            event = NewsAnalysisEvent(
                ticker=analysis.ticker,
                headline=item.headline,
                datetime=item.datetime,
                summary=analysis.summary,
                emotion=analysis.emotion,
                level=analysis.level,
                reasoning=analysis.reasoning,
                risks=analysis.risks,
            )
            await self.queue.put(event)

            if analysis.level >= 4:
                self._notify(item, analysis)

    def _notify(self, news: finnhub.FinnhubNews, analysis: AnalysisResult) -> None:
        try:
            notification.notify(
                title=f"🚨 {analysis.ticker} L{analysis.level} {analysis.emotion}",
                message=news.headline,
                app_name="StockTerm",
                timeout=5,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to dispatch desktop notification")
