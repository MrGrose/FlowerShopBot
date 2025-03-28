import os
import django
import asyncio
from aiogram import Bot, Dispatcher
from environs import Env
from bot.handlers import router


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "FlowerShopProject.settings")
django.setup()


async def main():
    env = Env()
    env.read_env()
    tg_token = env.str("TG_TOKEN1")
    bot = Bot(token=tg_token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Бот выключен')