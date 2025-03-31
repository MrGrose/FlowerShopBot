import asyncio
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "FlowerShopProject.settings")
import django
django.setup()

from aiogram import Bot, Dispatcher
from bot.handlers import router
from django.conf import settings


async def main():
    bot = Bot(token=settings.TG_BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Бот выключен')