from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import time

from fastapi import HTTPException, status

from app.core.config import get_settings


class AuthRateLimitService:
    _events: dict[str, deque[float]] = defaultdict(deque)
    _lock = Lock()

    def __init__(self) -> None:
        self.settings = get_settings()

    def enforce_login(self, client_ip: str, email: str) -> None:
        self._enforce("login", client_ip, email, self.settings.auth_login_rate_limit_count)

    def enforce_register(self, client_ip: str, email: str) -> None:
        self._enforce("register", client_ip, email, self.settings.auth_register_rate_limit_count)

    def enforce_email_action(self, action: str, client_ip: str, email: str) -> None:
        self._enforce(action, client_ip, email, self.settings.auth_email_rate_limit_count)

    def _enforce(self, action: str, client_ip: str, email: str, limit: int) -> None:
        identifier = f"{action}:{client_ip.strip().lower()}:{email.strip().lower()}"
        now = time()
        window_start = now - self.settings.auth_rate_limit_window_seconds
        with self._lock:
            events = self._events[identifier]
            while events and events[0] < window_start:
                events.popleft()
            if len(events) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many authentication attempts. Please try again later.",
                )
            events.append(now)
