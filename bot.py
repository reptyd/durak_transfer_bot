import re
import logging
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.utils.markdown import hquote

BOT_TOKEN = 'ВАШ_ТОКЕН'

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

API_TRANSFER = 'https://durak.rstgames.com/api/v1/account/transfer'
API_PROFILE = 'https://durak.rstgames.com/api/v1/user/me'


async def extract_profile_token(id_token: str) -> str | None:
    headers = {
        "Authorization": f"Bearer {id_token}"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(API_PROFILE, headers=headers) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get("profileToken")


@dp.message()
async def handle_links(message: Message):
    text = message.text.strip()

    # Ссылки
    id_token_match = re.search(r'durak\.rstgames\.com\/play\/\?[^ ]*id_token=([^&\s]+)', text)
    user_token_match = re.search(r'durak\.rstgames\.com\/link\/user\?token=([a-zA-Z0-9_\-]+)', text)

    if not (id_token_match and user_token_match):
        return  # ждём обе ссылки

    id_token = id_token_match.group(1)
    user_token = user_token_match.group(1)

    await message.answer("⏳ Получаю profileToken...")

    profile_token = await extract_profile_token(id_token)

    if not profile_token:
        await message.answer("❌ Не удалось получить profileToken. Возможно, токен устарел или недействителен.")
        return

    payload = {
        "sourceProfileToken": profile_token,
        "targetUserToken": user_token
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(API_TRANSFER, json=payload) as resp:
            status = resp.status
            content = await resp.text()

    if status == 200:
        await message.answer("✅ Профиль успешно перенесён.")
    else:
        clean_text = re.sub(r'<[^>]+>', '', content)
        await message.answer(f"❌ Ошибка переноса (код {status}):\n{hquote(clean_text)}", parse_mode=ParseMode.HTML)


async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
