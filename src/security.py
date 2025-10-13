import re
import time
from typing import Dict

from .utils.json_store import rate_limits_store
from .config import settings

URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)


class RateLimiter:
    def __init__(self, per_minute: int | None = None):
        self.per_minute = per_minute or settings.rate_limit_per_minute

    def allowed(self, user_id: int) -> bool:
        now = int(time.time())
        window = now // 60
        rl = rate_limits_store.get() or {}
        user = rl.get(str(user_id), {"window": window, "count": 0})
        if user["window"] != window:
            user = {"window": window, "count": 0}
        if user["count"] >= self.per_minute:
            return False
        user["count"] += 1
        rl[str(user_id)] = user
        rate_limits_store.set(rl)
        return True


def sanitize(text: str) -> str:
    # Remove obvious malicious links (basic)
    return URL_PATTERN.sub("[ссылка скрыта]", text)
