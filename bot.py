import re
import aiohttp
import asyncio
import html
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from aiogram import Router
from config import BOT_TOKEN

bot = Bot(
    token=7957577211:AAHZ4XRF35VKC_trcbxF1Lw5kSwS3PlfG88,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

@router.message()
async def handle_tokens(message: Message):
    # Ищем все token=... в любых ссылках
    tokens = re.findall(r'token=([a-zA-Z0-9._-]{10,})', message.text)

    if len(tokens) != 2:
        await message.answer(
            "Пожалуйста, отправьте сообщение с двумя ссылками, содержащими токены.\n"
            "Поддерживаются ссылки вида:\n"
            "- https://durak.rstgames.com/link/profile?token=...\n"
            "- https://durak.rstgames.com/play/?id_token=...\n"
            "- https://durak.rstgames.com/link/user?token=..."
        )
        return

    # Принимаем оба токена в любом порядке
    profile_token, user_token = tokens

    # Пробуем угадать порядок по содержимому текста
    if "user" in message.text and message.text.index("user") < message.text.index("token="):
        user_token, profile_token = tokens

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
            await message.answer(f"Ошибка при запросе к API: <pre>{html.escape(str(e))}</pre>", parse_mode="HTML")
            return

    if status == 200:
        await message.answer("✅ Профиль успешно перенесён!")
    else:
        safe_text = html.escape(text)
        await message.answer(
            f"❌ Ошибка переноса (код {status}):\n<pre>{safe_text}</pre>",
            parse_mode="HTML"
        )

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
