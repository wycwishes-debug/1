"""Textual UI for StockTerm."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, Optional

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Static

from app.core.monitor import NewsAnalysisEvent, QuoteUpdate
from app.database.db import Database
from app.core.monitor import MonitorService
from app.ui.widgets import (
    AnalysisPanel,
    CommandInput,
    NewsFeedTable,
    SparklineWidget,
    WatchlistTable,
    NewsRow,
)


class StockTermApp(App):
    """Main Textual application."""

    CSS_PATH = "styles.css"
    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    current_ticker: Optional[str] = reactive(None)

    def __init__(self, event_queue: asyncio.Queue, db: Database, monitor: MonitorService) -> None:
        super().__init__()
        self.event_queue = event_queue
        self.db = db
        self.monitor = monitor
        self.latest_quotes: Dict[str, QuoteUpdate] = {}
        self.latest_analysis: Dict[str, NewsAnalysisEvent] = {}

    def compose(self) -> ComposeResult:
        yield Static("StockTerm — Cyber Terminal", id="title")
        with Horizontal(id="layout"):
            yield WatchlistTable(id="watchlist")
            with Vertical(id="main-area"):
                with Horizontal(id="top" ):
                    yield SparklineWidget(id="sparkline")
                    yield Static("--", id="price")
                yield NewsFeedTable(id="newsfeed")
                yield AnalysisPanel(id="analysis")
        yield Container(CommandInput(placeholder="/add TSLA, /del TSLA, /check NVDA, /quit"), id="command-bar")
        yield Footer()

    async def on_mount(self) -> None:
        await self._load_watchlist()
        self.run_worker(self._event_consumer(), name="event-consumer", group="background")

    async def _load_watchlist(self) -> None:
        table = self.query_one(WatchlistTable)
        for ticker in await self.db.fetch_watchlist():
            table.upsert_row(ticker, "--", "--")
        if table.row_count:
            table.cursor_coordinate = (0, 0)
            self.current_ticker = table.get_row_at(0)[0]

    async def _event_consumer(self) -> None:
        while True:
            event = await self.event_queue.get()
            if isinstance(event, QuoteUpdate):
                self.latest_quotes[event.ticker] = event
                await self.call_from_thread(self._handle_quote_update, event)
            elif isinstance(event, NewsAnalysisEvent):
                self.latest_analysis[event.ticker] = event
                await self.call_from_thread(self._handle_news_event, event)

    def _handle_quote_update(self, event: QuoteUpdate) -> None:
        table = self.query_one(WatchlistTable)
        last_update = datetime.now().strftime("%H:%M:%S")
        score = f"{event.percent:+.2f}%" if event.percent is not None else "--"
        table.upsert_row(event.ticker, score, last_update)
        if not self.current_ticker:
            self.current_ticker = event.ticker
        if event.ticker == self.current_ticker:
            self._update_price_and_chart(event)

    def _update_price_and_chart(self, quote: QuoteUpdate) -> None:
        sparkline = self.query_one(SparklineWidget)
        sparkline.set_series(quote.sparkline, quote.percent)
        price_widget = self.query_one("#price", Static)
        price_text = "--" if quote.price is None else f"{quote.price:.2f}"
        if quote.change is not None and quote.percent is not None:
            change_text = f" ({quote.change:+.2f}, {quote.percent:+.2f}%)"
        elif quote.change is not None:
            change_text = f" ({quote.change:+.2f})"
        else:
            change_text = ""
        price_widget.update(f"{self.current_ticker} {price_text}{change_text}")

    def _handle_news_event(self, event: NewsAnalysisEvent) -> None:
        newsfeed = self.query_one(NewsFeedTable)
        time_str = datetime.fromtimestamp(event.datetime).strftime("%H:%M") if event.datetime else "--"
        newsfeed.add_news(
            NewsRow(
                time=time_str,
                ticker=event.ticker,
                level=event.level,
                emotion=event.emotion,
                headline=event.headline,
            )
        )
        if event.ticker == self.current_ticker:
            self._update_analysis(event)

    def _update_analysis(self, event: NewsAnalysisEvent) -> None:
        panel = self.query_one(AnalysisPanel)
        panel.update_analysis(event.summary, event.reasoning, event.risks)

    @on(CommandInput.Submitted)
    async def handle_command(self, message: CommandInput.Submitted) -> None:
        cmd = message.value.strip()
        if not cmd:
            return
        if cmd.startswith("/add"):
            ticker = cmd.replace("/add", "").strip().upper()
            if ticker:
                await self.db.add_ticker(ticker)
                table = self.query_one(WatchlistTable)
                table.upsert_row(ticker, "--", "--")
        elif cmd.startswith("/del"):
            ticker = cmd.replace("/del", "").strip().upper()
            if ticker:
                await self.db.remove_ticker(ticker)
                table = self.query_one(WatchlistTable)
                for row_key, row in list(table.rows.items()):
                    if row[0] == ticker:
                        table.remove_row(row_key)
                        break
        elif cmd.startswith("/check"):
            ticker = cmd.replace("/check", "").strip().upper()
            if ticker:
                await self.monitor.poll_ticker_once(ticker)
        elif cmd.startswith("/quit"):
            await self.action_quit()

    @on(NewsFeedTable.Selected)
    def show_news_details(self, message: NewsFeedTable.Selected) -> None:
        ticker = message.row.ticker
        self.current_ticker = ticker
        analysis = self.latest_analysis.get(ticker)
        if analysis:
            self._update_analysis(analysis)
        quote = self.latest_quotes.get(ticker)
        if quote:
            self._update_price_and_chart(quote)

    @on("data_table.row_selected")
    def on_watchlist_selected(self, event) -> None:
        table = self.query_one(WatchlistTable)
        row = table.get_row(event.row_key)
        if row:
            self.current_ticker = row[0]
            analysis = self.latest_analysis.get(self.current_ticker)
            if analysis:
                self._update_analysis(analysis)
            quote = self.latest_quotes.get(self.current_ticker)
            if quote:
                self._update_price_and_chart(quote)
