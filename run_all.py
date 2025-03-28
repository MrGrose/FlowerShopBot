import asyncio
from multiprocessing import Process
import os
import django


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "FlowerShopProject.settings")
django.setup()


def run_django():
    os.system("python manage.py runserver")


async def run_bot():
    from bot_main import main
    await main()


def main():
    django_process = Process(target=run_django)
    django_process.start()
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\nОстановка сервера Django и бота...")
        django_process.terminate()


if __name__ == "__main__":
    main()
