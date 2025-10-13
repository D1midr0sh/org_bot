import json
from pathlib import Path
from threading import RLock
from typing import Any

DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True)


class JsonStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = RLock()
        if not self.path.exists():
            self._write({} if self.path.suffix == '.json' else [])

    def _read(self) -> Any:
        if not self.path.exists():
            return {} if self.path.suffix == '.json' else []
        with self._lock:
            with self.path.open('r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {} if self.path.suffix == '.json' else []

    def _write(self, data: Any) -> None:
        with self._lock:
            with self.path.open('w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def get(self) -> Any:
        return self._read()

    def set(self, data: Any) -> None:
        self._write(data)

    def update(self, updater):
        with self._lock:
            data = self._read()
            new_data = updater(data)
            self._write(new_data)
            return new_data


user_settings_store = JsonStore(DATA_DIR / 'user_settings.json')
user_requests_store = JsonStore(DATA_DIR / 'user_requests.json')
rate_limits_store = JsonStore(DATA_DIR / 'rate_limits.json')
