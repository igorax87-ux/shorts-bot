import asyncio
import os
import logging
from datetime import datetime
from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Dispatcher
from video_generator import generate_video, TOPICS

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6297994568"))

SCHEDULE_HOURS = [9, 12, 18, 21]

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🎬 *Бот для YouTube Shorts запущен!*\n\n"
        "Буду присылать готовые видео в:\n"
        "• 09:00 🃏 Карта дня\n"
        "• 12:00 🔢 Нумерология\n"
        "• 18:00 🔮 Расклад Таро\n"
        "• 21:00 ⭐ Послание звёзд\n\n"
        "Каждое видео готово к публикации в YouTube Shorts! ✅",
        parse_mode="Markdown"
    )
    # Save chat_id for future use
    logging.info(f"Admin started bot, chat_id: {message.chat.id}")


@router.message(Command("test"))
async def cmd_test(message: Message):
    """Test command to generate video immediately"""
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🎬 Генерирую тестовое видео... (займёт ~2 минуты)")
    await generate_and_send(message.bot, message.chat.id, 0)


async def send_video(bot: Bot, chat_id: int, video_path: str, caption: str):
    with open(video_path, "rb") as f:
        await bot.send_video(chat_id, f, caption=caption, supports_streaming=True, parse_mode="Markdown")
    os.remove(video_path)


async def generate_and_send(bot: Bot, chat_id: int, topic_index: int):
    topic = TOPICS[topic_index % len(TOPICS)]
    output_path = f"/tmp/shorts_{topic['type']}_{datetime.now().strftime('%H%M')}.mp4"

    try:
        content = await generate_video(topic, GROQ_API_KEY, output_path)
        caption = (
            f"📹 *{topic['title']}*\n\n"
            f"🃏 {content.get('card', '')}\n\n"
            f"📝 *Описание для YouTube:*\n"
            f"━━━━━━━━━━━━━━\n"
            f"{content.get('text', '')}\n\n"
            f"🔮 Бесплатные расклады, карта дня, натальная карта — @numer_taro_bot\n"
            f"━━━━━━━━━━━━━━\n"
            f"#таро #расклад #гадание #нумерология #эзотерика #shorts"
        )
        await send_video(bot, chat_id, output_path, caption)
        logging.info(f"Video sent: {topic['title']}")
    except Exception as e:
        logging.error(f"Error: {e}")
        await bot.send_message(chat_id, f"❌ Ошибка генерации видео: {e}")


async def scheduler_loop(bot: Bot):
    video_counter = 0
    sent_hours = set()

    while True:
        now = datetime.now()
        current_hour = now.hour

        if current_hour in SCHEDULE_HOURS and current_hour not in sent_hours:
            logging.info(f"Time to post! Hour: {current_hour}")
            await generate_and_send(bot, ADMIN_ID, video_counter)
            video_counter += 1
            sent_hours.add(current_hour)

        if current_hour == 0:
            sent_hours.clear()

        await asyncio.sleep(60)


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logging.info("✅ SHORTS SCHEDULER STARTED!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
