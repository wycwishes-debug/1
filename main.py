"""Application entrypoint for StockTerm.

This module configures logging, initializes the database, launches the
monitoring service, and runs the Textual UI. The environment variable
``TEXTUAL_LOG`` must be set before importing :mod:`textual` to allow the
framework to emit its own logs to ``textual.log``.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

# Configure Textual logging destination before importing textual modules.
os.environ.setdefault("TEXTUAL_LOG", "textual.log")

from app.utils.logging import setup_logging
from app.database.db import Database
from app.core.monitor import MonitorService
from app.ui.app import StockTermApp


async def _async_main() -> None:
    """Initialize subsystems and run the TUI application."""

    log_path = setup_logging()
    log_dir = Path(log_path).parent

    db = Database(Path("stockterm.db"))
    await db.initialize()

    event_queue: asyncio.Queue = asyncio.Queue()
    monitor = MonitorService(db=db, event_queue=event_queue, log_dir=log_dir)
    monitor_task = asyncio.create_task(monitor.run())

    app = StockTermApp(event_queue=event_queue, db=db, monitor=monitor)

    try:
        await app.run_async()
    finally:
        monitor.stop()
        await monitor_task
        await db.close()


def main() -> None:
    """Synchronous entrypoint wrapper."""

    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
