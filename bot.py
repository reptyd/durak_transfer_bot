import re
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from aiohttp import ClientSession

BOT_TOKEN = "7957577211:AAHZ4XRF35VKC_trcbxF1Lw5kSwS3PlfG88"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties())
dp = Dispatcher()


def extract_tokens(text):
    token_pattern = r"(?:profile|user)?token=([\w\-_.]+)"
    return re.findall(token_pattern, text)


@dp.message(F.text)
async def handle_tokens(message: Message):
    tokens = extract_tokens(message.text)
    if len(tokens) < 2:
        await message.reply("⚠️ Отправьте *две* ссылки, содержащие токены (одна от профиля, другая от нового аккаунта).")
        return

    token1, token2 = tokens[:2]

    # Попробуем оба варианта — какой из них profile, какой user
    pairs = [
        {"sourceProfileToken": token1, "targetUserToken": token2},
        {"sourceProfileToken": token2, "targetUserToken": token1}
    ]

    for i, payload in enumerate(pairs, start=1):
        async with ClientSession() as session:
            async with session.post("https://durak.rstgames.com/api/v1/account/transfer", json=payload) as resp:
                status = resp.status
                text = await resp.text()

        if status == 200:
            await message.reply("✅ Профиль успешно перенесён!")
            return
        elif status != 404:
            await message.reply(f"❌ Ошибка переноса (код {status}):\n{text}")
            return

    await message.reply("❌ Не удалось перенести. Вероятно, один из токенов устарел или невалиден.")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
