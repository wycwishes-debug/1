"""Yahoo Finance HTTP helpers (no yfinance dependency)."""

from __future__ import annotations

import logging
from typing import List, Optional

import aiohttp

logger = logging.getLogger(__name__)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


def _normalize_series(prices: List[float]) -> List[float]:
    if not prices:
        return []
    base = prices[0] or 1.0
    return [((p - base) / base) * 100 for p in prices]


async def fetch_intraday_sparkline(
    session: aiohttp.ClientSession, ticker: str, range_: str = "1d", interval: str = "5m"
) -> List[float]:
    """Return percentage change series for sparkline rendering."""

    url = CHART_URL.format(ticker=ticker.upper())
    params = {"range": range_, "interval": interval}
    try:
        async with session.get(url, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()
            result = data.get("chart", {}).get("result", [])
            if not result:
                return []
            closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
            closes = [c for c in closes if c is not None]
            return _normalize_series(closes)
    except Exception:
        logger.exception("Failed to fetch sparkline for %s", ticker)
        return []


async def fetch_price_from_chart(session: aiohttp.ClientSession, ticker: str) -> Optional[float]:
    """Fetch the latest closing price from the chart endpoint."""

    url = CHART_URL.format(ticker=ticker.upper())
    params = {"range": "1d", "interval": "1d"}
    try:
        async with session.get(url, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()
            result = data.get("chart", {}).get("result", [])
            if not result:
                return None
            closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
            closes = [c for c in closes if c is not None]
            return closes[-1] if closes else None
    except Exception:
        logger.exception("Failed to fetch price for %s", ticker)
        return None
