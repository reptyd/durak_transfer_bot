import logging
import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.utils.markdown import hcode
from aiohttp import web
import asyncio
import re

BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def detect_profile_token(token: str) -> str | None:
    url = "https://durak.rstgames.com/api/v1/user/me"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=5) as resp:
                if resp.status == 200:
                    json_data = await resp.json()
                    return json_data.get("profileToken")
    except Exception:
        return None

async def try_transfer(profile_token: str, user_token: str) -> tuple[int, str]:
    url = "https://durak.rstgames.com/api/v1/account/transfer"
    headers = {"Content-Type": "application/json"}
    payload = {
        "sourceProfileToken": profile_token,
        "targetUserToken": user_token
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=10) as resp:
                text = await resp.text()
                return resp.status, text
    except Exception as e:
        return 500, str(e)

@dp.message(F.text)
async def handle_tokens(message: Message):
    tokens = re.findall(r"id_token=([\w\-\.]+)", message.text)
    if len(tokens) < 2:
        await message.answer("❗ Отправьте 2 ссылки с `id_token` в одном сообщении.")
        return

    token1, token2 = tokens[:2]
    profile = await detect_profile_token(token1)
    if profile:
        profile_token, user_token = profile, token2
    else:
        profile = await detect_profile_token(token2)
        if profile:
            profile_token, user_token = profile, token1
        else:
            await message.answer("❌ Не удалось определить `profileToken`. Проверьте, что ссылки актуальны (до 5 минут).")
            return

    status, text = await try_transfer(profile_token, user_token)
    if status == 200:
        await message.answer("✅ Профиль успешно перенесён.")
    else:
        safe_text = re.sub(r"<[^>]+>", "", text)[:1000]
        await message.answer(f"❌ Ошибка переноса (код {status}):\n{hcode(safe_text)}")

# Keep-alive web server
async def run_webserver():
    app = web.Application()
    app.add_routes([web.get("/", lambda request: web.Response(text="Bot is running."))])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, port=8080)
    await site.start()

async def main():
    await asyncio.gather(dp.start_polling(bot), run_webserver())

if __name__ == "__main__":
    asyncio.run(main())
