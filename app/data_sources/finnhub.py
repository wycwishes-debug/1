"""Finnhub async client using :mod:`aiohttp`."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "https://finnhub.io/api/v1"


@dataclass
class FinnhubNews:
    ticker: str
    headline: str
    url: str
    datetime: int
    summary: str | None = None


class FinnhubClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token
        if not self.token:
            logger.warning("FINNHUB_TOKEN is not set; API calls will likely fail.")

    async def _get(self, session: aiohttp.ClientSession, path: str, params: dict | None = None) -> dict:
        params = params or {}
        if self.token:
            params["token"] = self.token
        async with session.get(f"{BASE_URL}{path}", params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def fetch_company_news(
        self, session: aiohttp.ClientSession, ticker: str, days: int = 3
    ) -> List[FinnhubNews]:
        """Fetch company-specific news and return unique entries."""

        start = datetime.now(timezone.utc).date().toordinal() - days
        today = datetime.now(timezone.utc).date().toordinal()
        start_date = datetime.fromordinal(start).date().isoformat()
        end_date = datetime.fromordinal(today).date().isoformat()

        data = await self._get(
            session,
            "/company-news",
            {"symbol": ticker.upper(), "from": start_date, "to": end_date},
        )
        items: List[FinnhubNews] = []
        for entry in data:
            items.append(
                FinnhubNews(
                    ticker=ticker.upper(),
                    headline=entry.get("headline", ""),
                    url=entry.get("url", ""),
                    datetime=int(entry.get("datetime", 0)),
                    summary=entry.get("summary"),
                )
            )
        return items

    async def fetch_general_news(
        self, session: aiohttp.ClientSession, tickers: Iterable[str]
    ) -> List[FinnhubNews]:
        """Fetch general news and filter by tickers mentioned."""

        data = await self._get(session, "/news", {"category": "general"})
        watch = {t.upper() for t in tickers}
        items: List[FinnhubNews] = []
        for entry in data:
            headline = entry.get("headline", "")
            summary = entry.get("summary", "") or ""
            for ticker in watch:
                if ticker in headline or ticker in summary:
                    items.append(
                        FinnhubNews(
                            ticker=ticker,
                            headline=headline,
                            url=entry.get("url", ""),
                            datetime=int(entry.get("datetime", 0)),
                            summary=summary,
                        )
                    )
                    break
        return items

    async def fetch_quote(self, session: aiohttp.ClientSession, ticker: str) -> Optional[dict]:
        """Fetch real-time quote for ticker."""

        try:
            data = await self._get(session, "/quote", {"symbol": ticker.upper()})
            return {
                "price": data.get("c"),
                "change": data.get("d"),
                "percent": data.get("dp"),
                "high": data.get("h"),
                "low": data.get("l"),
                "prev_close": data.get("pc"),
                "timestamp": data.get("t"),
            }
        except Exception:
            logger.exception("Failed to fetch quote for %s", ticker)
            return None
