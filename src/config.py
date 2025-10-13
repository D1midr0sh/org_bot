import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _parse_admins(value: str) -> list[int]:
    if not value:
        return []
    ids = []
    for part in value.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids


@dataclass
class Settings:
    telegram_token: str = os.getenv('TELEGRAM_TOKEN', '')
    llm_provider: str = 'yandex'

    # YandexGPT
    yandex_api_key: str = os.getenv('YANDEX_API_KEY', '')  # alternative to IAM token
    yandex_iam_token: str = os.getenv('YANDEX_IAM_TOKEN', '')
    yandex_folder_id: str = os.getenv('YANDEX_FOLDER_ID', '')
    yandex_model: str = os.getenv('YANDEX_MODEL', 'yandexgpt-lite')
    yandex_api_url: str = os.getenv('YANDEX_API_URL', 'https://rest-assistant.api.cloud.yandex.net/v1')

    admin_ids: list[int] = None

    log_level: str = os.getenv('LOG_LEVEL', 'INFO')
    rate_limit_per_minute: int = int(os.getenv('RATE_LIMIT_PER_MINUTE', '12'))
    max_alternatives: int = int(os.getenv('MAX_ALTERNATIVES', '3'))
    style_mode: str = os.getenv('STYLE_MODE', 'auto')
    always_strict: bool = os.getenv('ALWAYS_STRICT', '0') in ('1', 'true', 'yes', 'on')

    def __post_init__(self):
        self.admin_ids = _parse_admins(os.getenv('ADMIN_IDS', ''))


settings = Settings()
