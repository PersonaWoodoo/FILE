import logging
from typing import Optional

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardMarkup

from config import settings

log = logging.getLogger(__name__)


async def send_document_to_user(
    bot: Bot,
    telegram_id: int,
    file_path: str,
    title: str,
    fmt: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> bool:
    try:
        file = FSInputFile(file_path, filename=f"{title[:60]}.{fmt}")
        await bot.send_document(
            chat_id=telegram_id,
            document=file,
            caption=(
                f"✅ <b>Ваш документ готов!</b>\n\n"
                f"📄 <b>Название:</b> {title}\n"
                f"📁 <b>Формат:</b> {fmt.upper()}\n\n"
                f"Приятной работы с DocuFlow AI!"
            ),
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
        return True
    except Exception as e:
        log.exception("Не удалось отправить документ %s: %s", file_path, e)
        return False


def mini_app_url(path: str = "") -> str:
    base = settings.public_url.rstrip("/")
    return f"{base}/{path.lstrip('/')}" if path else base
