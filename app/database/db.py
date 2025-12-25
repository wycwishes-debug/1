"""Async SQLite database helpers for StockTerm."""

from __future__ import annotations

import aiosqlite
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class NewsRecord:
    ticker: str
    headline: str
    url: str
    datetime: int


@dataclass
class AnalysisRecord:
    ticker: str
    emotion: str
    level: int
    summary: str
    reasoning: str
    risks: str


class Database:
    """Lightweight wrapper around :mod:`aiosqlite` for app storage."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._conn: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Open the database and ensure the schema exists."""

        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS watchlist (
                ticker TEXT PRIMARY KEY,
                created_at INTEGER DEFAULT (strftime('%s','now'))
            );

            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                headline TEXT NOT NULL,
                url TEXT NOT NULL,
                datetime INTEGER NOT NULL,
                UNIQUE(url)
            );

            CREATE TABLE IF NOT EXISTS analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                emotion TEXT NOT NULL,
                level INTEGER NOT NULL,
                summary TEXT NOT NULL,
                reasoning TEXT NOT NULL,
                risks TEXT NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s','now'))
            );
            """
        )
        await self._conn.commit()

        # Seed a default watchlist if empty.
        existing = await self.fetch_watchlist()
        if not existing:
            await self.add_tickers(["AAPL", "MSFT", "TSLA"])

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def add_ticker(self, ticker: str) -> None:
        await self.add_tickers([ticker])

    async def add_tickers(self, tickers: Iterable[str]) -> None:
        assert self._conn is not None
        await self._conn.executemany(
            "INSERT OR IGNORE INTO watchlist(ticker) VALUES (?)",
            [(ticker.upper(),) for ticker in tickers],
        )
        await self._conn.commit()

    async def remove_ticker(self, ticker: str) -> None:
        assert self._conn is not None
        await self._conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.upper(),))
        await self._conn.commit()

    async def fetch_watchlist(self) -> List[str]:
        assert self._conn is not None
        async with self._conn.execute("SELECT ticker FROM watchlist ORDER BY ticker") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def record_news(self, record: NewsRecord) -> None:
        assert self._conn is not None
        await self._conn.execute(
            "INSERT OR IGNORE INTO news(ticker, headline, url, datetime) VALUES (?, ?, ?, ?)",
            (record.ticker, record.headline, record.url, record.datetime),
        )
        await self._conn.commit()

    async def fetch_recent_news(self, limit: int = 50) -> List[NewsRecord]:
        assert self._conn is not None
        async with self._conn.execute(
            "SELECT ticker, headline, url, datetime FROM news ORDER BY datetime DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [NewsRecord(**dict(row)) for row in rows]

    async def record_analysis(self, record: AnalysisRecord) -> None:
        assert self._conn is not None
        await self._conn.execute(
            """
            INSERT INTO analysis(ticker, emotion, level, summary, reasoning, risks)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.ticker,
                record.emotion,
                record.level,
                record.summary,
                record.reasoning,
                record.risks,
            ),
        )
        await self._conn.commit()

    async def fetch_latest_analysis(self, ticker: str) -> Optional[AnalysisRecord]:
        assert self._conn is not None
        async with self._conn.execute(
            """
            SELECT ticker, emotion, level, summary, reasoning, risks
            FROM analysis
            WHERE ticker = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (ticker.upper(),),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return AnalysisRecord(**dict(row))
            return None
