from django.core.management.base import BaseCommand
from django.conf import settings
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
import asyncio
from bot.handlers.handlers import router
from aiogram.client.default import DefaultBotProperties


class Command(BaseCommand):
    help = 'Запуск Telegram бота'

    def handle(self, *args, **options):
        async def main():
            bot = Bot(
                token=settings.TG_BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )

            dp = Dispatcher()
            dp.include_router(router)

            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)

        asyncio.run(main())