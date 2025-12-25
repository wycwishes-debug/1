"""Custom Textual widgets for StockTerm."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from textual import events
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Input, Markdown, Static

SPARK_BARS = "▁▂▃▄▅▆▇█"


def _spark_bar(value: float, min_v: float, max_v: float) -> str:
    if max_v == min_v:
        return SPARK_BARS[0]
    index = int((value - min_v) / (max_v - min_v) * (len(SPARK_BARS) - 1))
    return SPARK_BARS[max(0, min(index, len(SPARK_BARS) - 1))]


class SparklineWidget(Static):
    """Render a sparkline using unicode blocks."""

    values: List[float] = reactive([], layout=True)
    percent: Optional[float] = reactive(None, layout=True)

    def set_series(self, values: Iterable[float], percent: Optional[float]) -> None:
        self.values = list(values)
        self.percent = percent

    def render(self) -> str:
        if not self.values:
            return "(no data)"
        min_v, max_v = min(self.values), max(self.values)
        bars = [_spark_bar(v, min_v, max_v) for v in self.values]
        pct = f" {self.percent:+.2f}%" if self.percent is not None else ""
        return "".join(bars) + pct


class WatchlistTable(DataTable):
    """Left sidebar watchlist."""

    def on_mount(self) -> None:
        self.add_columns("Ticker", "Score", "Last Update")
        self.cursor_type = "row"
        self.zebra_stripes = True

    def upsert_row(self, ticker: str, score: str, last_update: str) -> None:
        existing = None
        for row_key, row in self.rows.items():
            if row[0] == ticker:
                existing = row_key
                break
        if existing is not None:
            self.update_row(existing, ticker, score, last_update)
        else:
            self.add_row(ticker, score, last_update)


@dataclass
class NewsRow:
    time: str
    ticker: str
    level: int
    emotion: str
    headline: str


class NewsFeedTable(DataTable):
    """Scrollable news feed."""

    class Selected(Message):
        def __init__(self, sender: Widget, row: NewsRow) -> None:
            self.row = row
            super().__init__(sender)

    def on_mount(self) -> None:
        self.add_columns("Time", "Ticker", "Lvl", "Emotion", "Headline")
        self.cursor_type = "row"
        self.zebra_stripes = True

    def add_news(self, row: NewsRow) -> None:
        style = self._emotion_style(row.emotion, row.level)
        self.add_row(row.time, row.ticker, f"L{row.level}", row.emotion, row.headline, style=style)
        self.scroll_end(animate=False)

    def _emotion_style(self, emotion: str, level: int) -> str:
        base = {
            "positive": "green",
            "negative": "red",
            "neutral": "#888888",
        }.get(emotion, "#888888")
        if level >= 4:
            return f"bold {base} on #222222"
        return base

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = self.get_row(event.row_key)
        if row:
            news_row = NewsRow(
                time=str(row[0]),
                ticker=str(row[1]),
                level=int(str(row[2]).lstrip("L")),
                emotion=str(row[3]),
                headline=str(row[4]),
            )
            self.post_message(self.Selected(self, news_row))


class AnalysisPanel(Markdown):
    """Markdown renderer for reasoning and risks."""

    def update_analysis(self, summary: str, reasoning: str, risks: str) -> None:
        body = f"**Summary**: {summary}\n\n**Reasoning**\n{reasoning}\n\n**Risks**\n{risks}"
        self.update(body)


class CommandInput(Input):
    """Footer command bar."""

    class Submitted(Message):
        def __init__(self, sender: Widget, value: str) -> None:
            self.value = value
            super().__init__(sender)

    def on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            self.post_message(self.Submitted(self, self.value))
            self.value = ""
            event.stop()
        else:
            return super().on_key(event)


class NewsMarkdown(Static):
    """Placeholder for detailed markdown view."""

    content: str = reactive("", layout=True)

    def set_content(self, content: str) -> None:
        self.content = content

    def render(self) -> str:
        return self.content or "选择一条新闻以查看详情"
