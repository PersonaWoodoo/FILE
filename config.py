import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except ValueError:
        return default


def _list_int(name: str, default: str = "") -> list[int]:
    raw = os.getenv(name, default)
    out = []
    for part in raw.replace(" ", "").split(","):
        if part:
            try:
                out.append(int(part))
            except ValueError:
                pass
    return out


@dataclass(frozen=True)
class Settings:
    bot_token: str
    bot_username: str
    admin_ids: list[int]
    public_url: str
    webhook_secret: str

    ai_api_key: str
    ai_base_url: str
    ai_model: str

    database_url: str

    free_generations: int
    premium_generations: int
    premium_days: int

    max_file_size: int
    rate_limit_per_minute: int

    generated_dir: str
    data_dir: str
    static_dir: str
    frontend_dir: str

    log_level: str
    port: int


def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN не задан в .env")

    public_url = os.getenv("PUBLIC_URL", "").strip().rstrip("/")
    if not public_url.startswith("https://"):
        raise RuntimeError("PUBLIC_URL должен начинаться с https://")

    admin_ids = _list_int("ADMIN_IDS", "8959461245")
    if not admin_ids:
        raise RuntimeError("ADMIN_IDS пуст")

    ai_api_key = os.getenv("AI_API_KEY", "").strip()
    if not ai_api_key:
        raise RuntimeError("AI_API_KEY не задан в .env")

    return Settings(
        bot_token=bot_token,
        bot_username=os.getenv("BOT_USERNAME", "").strip().lstrip("@"),
        admin_ids=admin_ids,
        public_url=public_url,
        webhook_secret=os.getenv("WEBHOOK_SECRET", "").strip() or "change-me",
        ai_api_key=ai_api_key,
        ai_base_url=(
            os.getenv(
                "AI_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta/openai/",
            ).rstrip("/")
            + "/"
        ),
        ai_model=os.getenv("AI_MODEL", "gemini-2.5-flash-lite"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./data/docuflow.db"),
        free_generations=_int("FREE_GENERATIONS", 1),
        premium_generations=_int("PREMIUM_GENERATIONS", 100),
        premium_days=_int("PREMIUM_DAYS", 30),
        max_file_size=_int("MAX_FILE_SIZE", 10 * 1024 * 1024),
        rate_limit_per_minute=_int("RATE_LIMIT_PER_MINUTE", 30),
        generated_dir=os.getenv("GENERATED_DIR", "generated"),
        data_dir=os.getenv("DATA_DIR", "data"),
        static_dir=os.getenv("STATIC_DIR", "static"),
        frontend_dir=os.getenv("FRONTEND_DIR", "frontend"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        port=_int("PORT", 8000),
    )


settings = load_settings()
