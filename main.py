import asyncio
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession

from database import init_db, AsyncSessionLocal
from services.marzban import MarzbanAPI
from handlers import start, cabinet, payment, referral, admin, support, promocode

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MARZBAN_URL = os.getenv("MARZBAN_URL")
MARZBAN_USERNAME = os.getenv("MARZBAN_USERNAME")
MARZBAN_PASSWORD = os.getenv("MARZBAN_PASSWORD")


async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    marzban = MarzbanAPI(MARZBAN_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD)

    # Middleware для передачи сессии и marzban в хендлеры
    async def db_middleware(handler, event, data):
        async with AsyncSessionLocal() as session:
            data["session"] = session
            data["marzban"] = marzban
            return await handler(event, data)

    dp.update.middleware(db_middleware)

    # Регистрируем хендлеры
    dp.include_router(start.router)
    dp.include_router(cabinet.router)
    dp.include_router(payment.router)
    dp.include_router(referral.router)
    dp.include_router(admin.router)
    dp.include_router(support.router)
    dp.include_router(promocode.router)

    # Инициализируем БД
    await init_db()

    print("🤖 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())