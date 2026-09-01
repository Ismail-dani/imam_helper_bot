import os
import sys
import asyncio
import logging
from aiohttp import web

sys.path.insert(0, os.path.abspath("src"))
from bot import dp, bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def health_check(request):
    return web.Response(text="Imam AI Bot is running 24/7!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 7860))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Веб-сервер запущен на порту {port}")

async def main():
    await start_web_server()
    logging.info("Запуск Telegram Polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
