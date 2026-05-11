import asyncio
import os
import logging
from datetime import datetime
from aiogram import Bot
from video_generator import generate_video, TOPICS

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6297994568"))

# Публикация в 9:00, 12:00, 18:00, 21:00
SCHEDULE_HOURS = [9, 12, 18, 21]


async def send_video_to_admin(bot: Bot, video_path: str, caption: str):
    with open(video_path, "rb") as f:
        await bot.send_video(
            ADMIN_ID,
            f,
            caption=caption,
            supports_streaming=True
        )
    os.remove(video_path)


async def generate_and_send(bot: Bot, topic_index: int):
    topic = TOPICS[topic_index % len(TOPICS)]
    output_path = f"/tmp/shorts_{topic['type']}_{datetime.now().strftime('%H%M')}.mp4"

    try:
        content = await generate_video(topic, GROQ_API_KEY, output_path)
        caption = (
            f"📹 *Готовое Shorts видео!*\n\n"
            f"📌 Тема: {topic['title']}\n"
            f"🃏 {content.get('card', '')}\n\n"
            f"👆 Опубликуй в YouTube Shorts\n"
            f"📝 Описание к видео:\n"
            f"━━━━━━━━━━━━━━\n"
            f"{content.get('text', '')}\n\n"
            f"🔮 Бесплатные расклады, карта дня, натальная карта — @numer_taro_bot\n"
            f"━━━━━━━━━━━━━━\n"
            f"#таро #расклад #гадание #нумерология #эзотерика #shorts"
        )
        await send_video_to_admin(bot, output_path, caption)
        logging.info(f"Video sent: {topic['title']}")
    except Exception as e:
        logging.error(f"Error generating video: {e}")
        await bot.send_message(ADMIN_ID, f"❌ Ошибка генерации видео {topic['title']}: {e}")


async def scheduler_loop(bot: Bot):
    video_counter = 0
    sent_hours = set()

    while True:
        now = datetime.now()
        current_hour = now.hour

        if current_hour in SCHEDULE_HOURS and current_hour not in sent_hours:
            logging.info(f"Time to post! Hour: {current_hour}")
            await generate_and_send(bot, video_counter)
            video_counter += 1
            sent_hours.add(current_hour)

        # Reset sent_hours at midnight
        if current_hour == 0:
            sent_hours.clear()

        await asyncio.sleep(60)  # Check every minute


async def main():
    bot = Bot(token=BOT_TOKEN)
    logging.info("✅ SHORTS SCHEDULER STARTED!")

    # Send startup message
    await bot.send_message(
        ADMIN_ID,
        "🎬 *Бот для Shorts запущен!*\n\n"
        "Буду присылать видео в:\n"
        "• 09:00 🃏 Карта дня\n"
        "• 12:00 🔢 Нумерология\n"
        "• 18:00 🔮 Расклад Таро\n"
        "• 21:00 ⭐ Послание звёзд\n\n"
        "Каждое видео готово к публикации в YouTube Shorts!",
        parse_mode="Markdown"
    )

    await scheduler_loop(bot)


if __name__ == "__main__":
    asyncio.run(main())
