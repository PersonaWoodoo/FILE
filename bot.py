import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from sqlalchemy.orm import Session

from config import settings
from database import SessionLocal, init_db
from handlers import start, documents, payments, admin

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("docuflow.bot")


async def provide_session():
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="app", description="Открыть приложение"),
        BotCommand(command="premium", description="Тарифы Premium"),
        BotCommand(command="documents", description="Мои документы"),
        BotCommand(command="referral", description="Пригласить друга"),
        BotCommand(command="help", description="Помощь"),
    ])


async def main() -> None:
    init_db()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(_SessionMiddleware())
    dp.callback_query.middleware(_SessionMiddleware())

    dp.include_router(admin.router)
    dp.include_router(payments.router)
    dp.include_router(documents.router)
    dp.include_router(start.router)

    await set_commands(bot)
    log.info("DocuFlow AI бот запущен (polling)")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


class _SessionMiddleware:
    """Пробрасывает SQLAlchemy-сессию в handlers как аргумент `session`."""

    async def __call__(self, handler, event, data):
        session = SessionLocal()
        data["session"] = session
        try:
            result = await handler(event, data)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Остановка бота")
