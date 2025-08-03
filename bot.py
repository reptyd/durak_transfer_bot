import logging
import html
import re
import aiohttp

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.markdown import hbold
from aiogram.filters import CommandStart

BOT_TOKEN = 'YOUR_BOT_TOKEN'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())


async def extract_token_from_play_url(url: str) -> str | None:
    """Пытается получить profileToken по ссылке на play"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                text = await resp.text()
                token_match = re.search(r'"profileToken"\s*:\s*"([^"]+)"', text)
                if token_match:
                    return token_match.group(1)
    except Exception as e:
        logging.exception("Ошибка при извлечении токена")
    return None


async def send_transfer_request(profile_token: str, user_token: str) -> tuple[int, str]:
    url = 'https://durak.rstgames.com/api/v1/account/transfer'
    headers = {"Content-Type": "application/json"}
    payload = {
        "sourceProfileToken": profile_token,
        "targetUserToken": user_token
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                text = await resp.text()
                return resp.status, text
    except Exception as e:
        return 500, str(e)


@dp.message(CommandStart())
async def on_start(message: Message):
    await message.answer(f"Привет! Пришли 2 ссылки:\n"
                         f"1 — ссылка на профиль (с id_token)\n"
                         f"2 — ссылка с токеном нового аккаунта (user token)")


@dp.message()
async def handle_tokens(message: Message):
    urls = re.findall(r'https://durak\.rstgames\.com/\S+', message.text)
    if len(urls) != 2:
        await message.answer("❌ Пожалуйста, пришлите ровно 2 ссылки.")
        return

    play_url, user_url = urls

    await message.answer("🔍 Получаю токены...")

    profile_token = await extract_token_from_play_url(play_url)
    if not profile_token:
        await message.answer("❌ Не удалось получить profileToken из первой ссылки.")
        return

    user_token_match = re.search(r'token=([a-zA-Z0-9\.\-_]+)', user_url)
    if not user_token_match:
        await message.answer("❌ Не удалось извлечь userToken из второй ссылки.")
        return

    user_token = user_token_match.group(1)

    await message.answer("🔄 Отправляю запрос на перенос профиля...")

    status, text = await send_transfer_request(profile_token, user_token)

    if status == 200:
        await message.answer("✅ Профиль успешно перенесён!")
    else:
        escaped = html.escape(text)
        await message.answer(f"❌ Ошибка переноса (код {status}):\n<pre>{escaped}</pre>")


if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
