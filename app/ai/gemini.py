"""Gemini client wrapper enforcing JSON output.

The client uses the synchronous ``google.generativeai`` SDK under the hood
but exposes an ``async`` API using :func:`asyncio.to_thread` to avoid
blocking the event loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict

import google.generativeai as genai

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    ticker: str
    emotion: str
    level: int
    summary: str
    reasoning: str
    risks: str

    @classmethod
    def neutral(cls, ticker: str, summary: str = "暂无可靠分析") -> "AnalysisResult":
        return cls(
            ticker=ticker,
            emotion="neutral",
            level=3,
            summary=summary,
            reasoning="无法从模型获得详细推理，保持中性立场。",
            risks="暂无补充风险。",
        )


JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "ticker": {"type": "string"},
        "emotion": {"type": "string", "enum": ["positive", "negative", "neutral"]},
        "level": {"type": "integer", "minimum": 1, "maximum": 5},
        "summary": {"type": "string"},
        "reasoning": {"type": "string"},
        "risks": {"type": "string"},
    },
    "required": ["ticker", "emotion", "level", "summary", "reasoning", "risks"],
}


class GeminiClient:
    """Async Gemini wrapper for deterministic JSON responses."""

    def __init__(self, model: str = "gemini-1.5-flash", api_key: str | None = None) -> None:
        self.model_name = model
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set; falling back to neutral responses only.")
        else:
            genai.configure(api_key=self.api_key)
        self._model = genai.GenerativeModel(self.model_name)

    async def analyze(self, ticker: str, headline: str, body: str | None = None) -> AnalysisResult:
        """Run analysis for a news item.

        The method always returns a valid :class:`AnalysisResult`. If the API
        fails or returns invalid JSON, a neutral placeholder is used instead
        of propagating the error.
        """

        if not self.api_key:
            return AnalysisResult.neutral(ticker, summary=headline)

        prompt = (
            "你是一名华尔街事件驱动分析师。根据以下新闻标题与可选摘要，"
            "给出结构化的交易影响判断。输出必须严格符合提供的 JSON Schema。"
        )

        content = f"Ticker: {ticker}\nHeadline: {headline}\nSummary: {body or 'N/A'}"

        try:
            response = await asyncio.to_thread(
                self._model.generate_content,
                [prompt, content],
                generation_config={
                    "response_mime_type": "application/json",
                    "response_schema": JSON_SCHEMA,
                },
            )
            raw_text = response.text if hasattr(response, "text") else str(response)
            data: Dict[str, Any] = json.loads(raw_text)
            return AnalysisResult(
                ticker=data.get("ticker", ticker).upper(),
                emotion=data.get("emotion", "neutral"),
                level=int(data.get("level", 3)),
                summary=data.get("summary", headline),
                reasoning=data.get("reasoning", "未提供"),
                risks=data.get("risks", "未提供"),
            )
        except Exception:  # noqa: BLE001 - resilient fallback
            logger.exception("Gemini analysis failed; returning neutral fallback.")
            return AnalysisResult.neutral(ticker, summary=headline)
