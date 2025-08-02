import re
import aiohttp
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from aiogram import Router
from config import BOT_TOKEN

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

PROFILE_RE = r'https:\/\/durak\.rstgames\.com\/link\/profile\?token=([a-zA-Z0-9_-]+)'
USER_RE = r'https:\/\/durak\.rstgames\.com\/link\/user\?token=([a-zA-Z0-9_-]+)'

@router.message()
async def handle_tokens(message: Message):
    profile_match = re.search(PROFILE_RE, message.text)
    user_match = re.search(USER_RE, message.text)

    if not (profile_match and user_match):
        await message.answer("Пожалуйста, отправьте 2 ссылки:\n1. Ссылка на профиль\n2. Ссылка на iCloud (из iOS)")
        return

    profile_token = profile_match.group(1)
    user_token = user_match.group(1)

    payload = {
        "sourceProfileToken": profile_token,
        "targetUserToken": user_token
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://durak.rstgames.com/api/v1/account/transfer",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as resp:
                status = resp.status
                text = await resp.text()
        except Exception as e:
            await message.answer(f"Ошибка при запросе к API: {e}")
            return

    if status == 200:
        await message.answer("✅ Профиль успешно перенесён!")
    else:
        await message.answer(f"❌ Ошибка переноса (код {status}):\n{text}")

# ---------------- WEB SERVER ----------------

async def ping(request):
    return web.Response(text="Bot is alive!")

async def run_webserver():
    app = web.Application()
    app.router.add_get("/", ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, port=8080)
    await site.start()

# ---------------- MAIN ----------------

async def main():
    await run_webserver()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
