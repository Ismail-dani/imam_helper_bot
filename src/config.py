"""Конфигурация проекта: чтение переменных окружения из .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Корень проекта (на уровень выше src/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Загружаем переменные из .env
load_dotenv(BASE_DIR / ".env")


def _get(name: str, default: str | None = None) -> str | None:
    """Читает переменную окружения, пустую строку трактует как None."""
    value = os.getenv(name, default)
    return value if value else None


# --- Telegram Bot ---
TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")

# --- Telegram API (Telethon) ---
TELEGRAM_API_ID = _get("TELEGRAM_API_ID")
TELEGRAM_API_HASH = _get("TELEGRAM_API_HASH")

# --- LLM / транскрипция ---
OPENAI_API_KEY = _get("OPENAI_API_KEY")
GROQ_API_KEY = _get("GROQ_API_KEY")

# --- Google Gemini (транскрипция аудио) ---
GEMINI_API_KEY = _get("GEMINI_API_KEY") or _get("GOOGLE_API_KEY")
# gemini-3.6-flash проверен рабочим на бесплатном ключе (200 OK, качество ок).
# Модели gemini-2.5-* на новых аккаунтах закрыты (404 «no longer available»),
# а pro-модели требуют включённого billing (на free tier лимит 0).
GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-3.6-flash")

# --- Целевые группы: "id1,id2,@name" -> список строк ---
TARGET_GROUPS = [
    g.strip() for g in (_get("TARGET_GROUPS") or "").split(",") if g.strip()
]

# --- Пути хранения ---
STORAGE_DIR = BASE_DIR / "storage"
AUDIO_DIR = STORAGE_DIR / "audio"
TRANSCRIPTIONS_DIR = STORAGE_DIR / "transcriptions"
VECTOR_DB_DIR = BASE_DIR / "vector_db"

# Гарантируем наличие директорий
for _d in (AUDIO_DIR, TRANSCRIPTIONS_DIR, VECTOR_DB_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def validate() -> list[str]:
    """Возвращает список отсутствующих обязательных переменных."""
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    return missing
