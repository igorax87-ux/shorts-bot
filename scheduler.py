import asyncio
import logging
import os
import json
import tempfile
import subprocess
import aiohttp
import pickle
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

YOUTUBE_TOKEN = os.getenv("YOUTUBE_TOKEN")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN")
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

TAROT_CARDS = [
    "Шут", "Маг", "Верховная Жрица", "Императрица", "Император",
    "Иерофант", "Влюблённые", "Колесница", "Сила", "Отшельник",
    "Колесо Фортуны", "Справедливость", "Повешенный", "Смерть",
    "Умеренность", "Дьявол", "Башня", "Звезда", "Луна", "Солнце",
    "Суд", "Мир"
]

SCHEDULES = [
    {"hour": 9,  "minute": 0,  "type": "card",      "emoji": "🃏", "title": "Карта дня"},
    {"hour": 12, "minute": 0,  "type": "numerology", "emoji": "🔢", "title": "Нумерология"},
    {"hour": 18, "minute": 0,  "type": "tarot",      "emoji": "🔮", "title": "Расклад Таро"},
    {"hour": 21, "minute": 0,  "type": "stars",      "emoji": "⭐", "title": "Послание звёзд"},
]


async def ask_groq(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
        "temperature": 0.9
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers, json=data
        ) as resp:
            result = await resp.json()
            if "choices" not in result:
                error_msg = result.get("error", {}).get("message", str(result))
                raise Exception(f"Groq error: {error_msg}")
            return result["choices"][0]["message"]["content"]


def wrap_text_to_lines(text, max_chars=32):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = (current + " " + word).strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def create_single_frame(text: str, title: str) -> str:
    """Создаёт ОДНУ PNG картинку с текстом — быстро!"""
    width, height = 1080, 1920
    img = Image.new('RGB', (width, height), color=(10, 5, 25))
    draw = ImageDraw.Draw(img)

    # Градиент фон
    for y in range(height):
        ratio = y / height
        r = int(15 + ratio * 25)
        g = int(5 + ratio * 8)
        b = int(50 + ratio * 35)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Звёзды (фиксированные, не анимированные — для статичного кадра)
    import random
    rng = random.Random(42)
    for _ in range(200):
        x = rng.randint(0, width)
        y = rng.randint(0, height)
        brightness = rng.randint(120, 255)
        size = rng.randint(1, 3)
        draw.ellipse([x-size, y-size, x+size, y+size],
                     fill=(brightness, brightness, brightness))

    # Декоративный круг
    cx, cy = width // 2, 900
    for radius in [300, 280, 260]:
        draw.ellipse([cx-radius, cy-radius, cx+radius, cy+radius],
                     outline=(120, 60, 180), width=1)

    # Шрифты
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        font_text  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 50)
        font_cta   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
    except Exception:
        font_title = ImageFont.load_default()
        font_text  = font_title
        font_cta   = font_title

    # Заголовок
    draw.text((width // 2, 160), title,
              font=font_title, fill=(220, 180, 255), anchor="mm",
              stroke_width=2, stroke_fill=(80, 0, 120))

    # Разделитель
    draw.line([(100, 240), (width - 100, 240)], fill=(150, 80, 200), width=2)

    # Основной текст
    lines = wrap_text_to_lines(text, max_chars=30)
    y_pos = 320
    for line in lines:
        draw.text((width // 2, y_pos), line,
                  font=font_text, fill=(255, 240, 255), anchor="mm",
                  stroke_width=1, stroke_fill=(50, 0, 80))
        y_pos += 65
        if y_pos > height - 350:
            break

    # CTA блок снизу
    cta_y = height - 280
    draw.rounded_rectangle([60, cta_y - 20, width - 60, cta_y + 200],
                            radius=20, fill=(30, 15, 60),
                            outline=(150, 80, 200), width=2)
    draw.text((width // 2, cta_y + 20),  "✨ Бесплатные расклады каждый день",
              font=font_cta, fill=(200, 160, 255), anchor="mm")
    draw.text((width // 2, cta_y + 90),  "🔮 @numer_taro_bot",
              font=font_cta, fill=(255, 220, 100), anchor="mm")
    draw.text((width // 2, cta_y + 160), "👇 Ссылка в описании канала",
              font=font_cta, fill=(200, 200, 255), anchor="mm")

    # Сохраняем PNG
    png_path = tempfile.mktemp(suffix='.png')
    img.save(png_path)
    return png_path


def create_video(content_type: str, text: str, title: str) -> str:
    """Создаёт MP4 через ffmpeg из одного PNG — занимает ~5 секунд"""
    png_path = create_single_frame(text, title)
    output_path = tempfile.mktemp(suffix='.mp4')

    # ffmpeg: берёт одну картинку и делает из неё 30-секундное видео
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", png_path,
        "-t", "30",
        "-vf", "scale=1080:1920",
        "-c:v", "libx264",
        "-crf", "23",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    os.remove(png_path)

    if result.returncode != 0:
        raise Exception(f"ffmpeg error: {result.stderr}")

    return output_path


def upload_to_youtube(video_path: str, title: str, description: str) -> str:
    creds = Credentials(
        token=YOUTUBE_TOKEN,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token"
    )
    youtube = build('youtube', 'v3', credentials=creds)
    request_body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': ['таро', 'нумерология', 'гороскоп', 'эзотерика', 'расклад', 'shorts'],
            'categoryId': '22'
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False
        }
    }
    media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
    response = youtube.videos().insert(
        part='snippet,status',
        body=request_body,
        media_body=media
    ).execute()
    return f"https://youtube.com/shorts/{response['id']}"


async def generate_and_send(content_type: str, title: str):
    try:
        prompts = {
            "card":       f"Напиши мистическое послание карты Таро на сегодня. Карта: {np.random.choice(TAROT_CARDS)}. 4-5 предложений. Мистический стиль.",
            "numerology": f"Сегодня {datetime.now().strftime('%d.%m.%Y')}. Напиши нумерологическое послание числа дня. 4-5 предложений.",
            "tarot":      "Напиши короткий расклад Таро на три карты: прошлое, настоящее, будущее. Кратко и мистично. 4-5 предложений.",
            "stars":      "Напиши мистическое послание звёзд на сегодня. Общий энергетический прогноз. 4-5 предложений.",
        }

        text = await ask_groq(prompts[content_type])
        await bot.send_message(ADMIN_ID, f"🎬 Генерирую видео: {title}...\n⏳ ~10 секунд")

        loop = asyncio.get_event_loop()
        video_path = await loop.run_in_executor(None, create_video, content_type, text, title)

        yt_title = f"{title} | {datetime.now().strftime('%d.%m.%Y')} #shorts #таро #нумерология"
        yt_description = (
            f"{title} на сегодня\n\n"
            "🔮 Хочешь личный расклад?\n"
            "✨ Карта дня БЕСПЛАТНО\n"
            "🔢 Нумерология БЕСПЛАТНО\n"
            "⭐ Натальная карта БЕСПЛАТНО\n\n"
            "👉 @numer_taro_bot\n\n"
            "#таро #нумерология #эзотерика #гороскоп #расклад #shorts"
        )

        cache_key = f"video_{datetime.now().strftime('%H%M%S')}"
        with open(f"/tmp/{cache_key}.pkl", 'wb') as f:
            pickle.dump({'path': video_path, 'title': yt_title, 'description': yt_description}, f)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="📤 Загрузить в YouTube Shorts",
                callback_data=f"upload:{cache_key}"
            )
        ]])

        with open(video_path, 'rb') as video_file:
            await bot.send_video(
                ADMIN_ID,
                video_file,
                caption=f"✅ {title} готово!\n\n📋 Описание:\n{yt_description}",
                reply_markup=keyboard
            )

    except Exception as e:
        logger.error(f"generate_and_send error: {e}")
        await bot.send_message(ADMIN_ID, f"❌ Ошибка генерации: {e}")


@router.callback_query(F.data.startswith("upload:"))
async def handle_upload(callback: CallbackQuery):
    cache_key = callback.data.split(":")[1]
    await callback.answer("Загружаю в YouTube...")
    try:
        with open(f"/tmp/{cache_key}.pkl", 'rb') as f:
            data = pickle.load(f)
        await callback.message.answer("⏳ Загружаю в YouTube... 1-2 минуты")
        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(
            None, upload_to_youtube, data['path'], data['title'], data['description']
        )
        await callback.message.answer(f"🎉 Загружено!\n\n🔗 {url}")
    except Exception as e:
        await callback.message.answer(
            f"❌ Ошибка загрузки: {e}\n\nЗагрузи вручную через YouTube Studio"
        )


@router.message(Command("start"))
async def cmd_start(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "🔮 Shorts бот запущен!\n\n"
        "📅 Расписание:\n"
        "09:00 — 🃏 Карта дня\n"
        "12:00 — 🔢 Нумерология\n"
        "18:00 — 🔮 Расклад Таро\n"
        "21:00 — ⭐ Послание звёзд\n\n"
        "/test — тестовое видео прямо сейчас"
    )


@router.message(Command("test"))
async def cmd_test(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🎬 Генерирую тестовое видео... ~10 секунд")
    await generate_and_send("tarot", "🔮 Расклад Таро")


async def main():
    dp.include_router(router)

    scheduler = AsyncIOScheduler(timezone="Europe/Kiev")
    for s in SCHEDULES:
        scheduler.add_job(
            generate_and_send,
            'cron',
            hour=s["hour"],
            minute=s["minute"],
            args=[s["type"], f"{s['emoji']} {s['title']}"]
        )
    scheduler.start()

    logger.info("✅ SHORTS SCHEDULER STARTED!")
    await bot.send_message(
        ADMIN_ID,
        "✅ Shorts бот запущен!\n\nНапиши /test — видео придёт за 10 секунд 🚀"
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
