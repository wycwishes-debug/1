"""Placeholder screens for future onboarding flows."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Markdown


class WelcomeScreen(Screen):
    """Simple first-run welcome screen."""

    def compose(self) -> ComposeResult:
        yield Markdown(
            """
            # 欢迎使用 StockTerm
            - 纯键盘操作：使用左侧表格选择股票，回车查看详情。
            - 底部命令：/add TSLA, /del TSLA, /check NVDA, /quit。
            按下开始键进入仪表盘。
            """
        )
        yield Button("进入", id="enter")

    def on_button_pressed(self, event: Button.Pressed) -> None:  # type: ignore[override]
        if event.button.id == "enter":
            self.app.pop_screen()
