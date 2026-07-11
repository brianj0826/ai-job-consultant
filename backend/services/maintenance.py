"""Small, stoppable background maintenance workers."""
from __future__ import annotations

import logging
import threading
from typing import Callable

from backend.services.database import cleanup_expired_auth_sessions


class PeriodicSessionCleanup:
    def __init__(
        self,
        interval_seconds: float,
        retention_days: int,
        *,
        cleanup: Callable[[int], int] = cleanup_expired_auth_sessions,
        logger: logging.Logger | None = None,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("cleanup interval must be positive")
        self.interval_seconds = interval_seconds
        self.retention_days = retention_days
        self.cleanup = cleanup
        self.logger = logger or logging.getLogger("aiagent.maintenance")
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="auth-session-cleanup",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=max(0.0, timeout))
        self._thread = None

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                removed = self.cleanup(self.retention_days)
                if removed:
                    self.logger.info("Removed %s expired authentication sessions", removed)
            except Exception:
                # The worker must survive transient DB outages; readiness will
                # independently keep an unhealthy instance out of rotation.
                self.logger.exception("Periodic authentication-session cleanup failed")
