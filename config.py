"""Настройки. Значения берутся из файла .env рядом с этим файлом или из переменных окружения."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


# Старые имена из proxy.py тоже понимаем
_ALIASES = {"ATHLETE": "INTERVALS_ATHLETE_ID"}


def _parse_value(raw: str) -> str:
    value = raw.strip()
    if value[:1] in ('"', "'"):
        # значение в кавычках: всё после закрывающей кавычки (например, комментарий) отбрасываем
        end = value.find(value[0], 1)
        return value[1:end] if end > 0 else value[1:]
    # без кавычек: комментарий начинается с « #»
    return value.split(" #", 1)[0].split("\t#", 1)[0].strip()


def _load_env_file() -> None:
    path = BASE_DIR / ".env"
    if not path.exists():
        return
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = _ALIASES.get(key.strip(), key.strip())
        value = _parse_value(value)
        if value:  # пустые строки из шаблона не затирают заполненные
            values[key] = value
    for key, value in values.items():
        os.environ.setdefault(key, value)  # переменные окружения важнее файла


_load_env_file()

INTERVALS_API_KEY = os.getenv("INTERVALS_API_KEY", "")
INTERVALS_ATHLETE_ID = os.getenv("INTERVALS_ATHLETE_ID", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

LANGUAGE = os.getenv("LANGUAGE", "ru").strip().lower()
if LANGUAGE not in ("ru", "en"):
    LANGUAGE = "ru"

MODEL = os.getenv("MODEL", "claude-sonnet-5")
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2048"))

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8765"))

DB_PATH = BASE_DIR / "data" / "coach.db"
PROMPTS_DIR = BASE_DIR / "prompts"
STATIC_DIR = BASE_DIR / "static"

# Сколько раундов вызова инструментов допускается за один ответ
MAX_TOOL_ROUNDS = 8
# Сколько последних обменов репликами хранить в контексте дословно
HISTORY_KEEP_TURNS = 12
# Когда несжатых обменов больше этого числа, старые сворачиваются в резюме
HISTORY_COMPACT_AT = 18
