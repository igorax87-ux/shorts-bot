import asyncio
import logging
import os
import json
import tempfile
import aiohttp
import aiofiles
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from moviepy.editor import *
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import textwrap
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
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
        "temperature": 0.9
    }
    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.groq.com/openai/v1/chat/completions", 
                               headers=headers, json=data) as resp:
            result = await resp.json()
            return result["choices"][0]["message"]["content"]

def create_mystical_frame(width, height, frame_num, total_frames):
    img = Image.new('RGB', (width, height), color=(10, 5, 25))
    draw = ImageDraw.Draw(img)
    
    # Градиент фиолетово-синий
    for y in range(height):
        ratio = y / height
        r = int(20 + ratio * 30)
        g = int(5 + ratio * 10)
        b = int(50 + ratio * 40)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # Звёзды
    import random
    rng = random.Random(42)
    for _ in range(150):
        x = rng.randint(0, width)
        y = rng.randint(0, height)
        twinkle = abs(np.sin(frame_num * 0.1 + rng.random() * 10))
        brightness = int(100 + 155 * twinkle)
        size = rng.randint(1, 3)
        draw.ellipse([x-size, y-size, x+size, y+size], 
                    fill=(brightness, brightness, brightness))
    
    # Магический круг снизу
    cx, cy = width // 2, height - 80
    radius = 60 + int(10 * abs(np.sin(frame_num * 0.05)))
    for r in range(radius-2, radius+2):
        alpha = int(150 * abs(np.sin(frame_num * 0.05)))
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(alpha, 50, alpha))
    
    return np.array(img)

def wrap_text_to_lines(text, max_chars=28):
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

def create_video(content_type: str, text: str, title: str) -> str:
    width, height = 1080, 1920
    fps = 24
    duration = 30
    total_frames = fps * duration
    
    output_path = tempfile.mktemp(suffix='.mp4')
    
    frames = []
    for i in range(total_frames):
        frame = create_mystical_frame(width, height, i, total_frames)
        img = Image.fromarray(frame)
        draw = ImageDraw.Draw(img)
        
        # Заголовок
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 65)
            font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
            font_cta = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
        except:
            font_title = ImageFont.load_default()
            font_text = font_title
            font_cta = font_title
        
        # Иконка типа контента
        emojis = {"card": "🃏", "numerology": "🔢", "tarot": "🔮", "stars": "⭐"}
        emoji = emojis.get(content_type, "🔮")
        
        # Заголовок вверху
        draw.text((width//2, 180), title, font=font_title, 
                 fill=(220, 180, 255), anchor="mm",
                 stroke_width=2, stroke_fill=(80, 0, 120))
        
        # Разделитель
        line_y = 250
        draw.line([(100, line_y), (width-100, line_y)], fill=(150, 80, 200), width=2)
        
        # Основной текст
        lines = wrap_text_to_lines(text, max_chars=26)
        start_y = 400
        visible_lines = int((i / total_frames) * len(lines)) + 1
        
        for j, line in enumerate(lines[:visible_lines]):
            y_pos = start_y + j * 70
            if y_pos < height - 300:
                alpha = min(255, int(255 * (i - j * (total_frames/len(lines))) / 20)) if i > j * (total_frames/len(lines)) else 255
                draw.text((width//2, y_pos), line, font=font_text,
                         fill=(255, 240, 255), anchor="mm",
                         stroke_width=1, stroke_fill=(50, 0, 80))
        
        # CTA снизу
        cta_y = height - 250
        pulse = abs(np.sin(i * 0.1))
        cta_color = (int(200 + 55*pulse), int(150 + 50*pulse), 255)
        draw.text((width//2, cta_y), "✨ Бесплатные расклады", font=font_cta,
                 fill=cta_color, anchor="mm",
                 stroke_width=2, stroke_fill=(50, 0, 80))
        draw.text((width//2, cta_y + 70), "Карта дня • Нумерология • Таро", font=font_cta,
                 fill=(200, 200, 255), anchor="mm")
        draw.text((width//2, cta_y + 140), "👇 Ссылка в описании канала", font=font_cta,
                 fill=(255, 220, 100), anchor="mm",
                 stroke_width=2, stroke_fill=(80, 50, 0))
        
        frames.append(np.array(img))
    
    clip = ImageSequenceClip(frames, fps=fps)
    clip.write_videofile(output_path, fps=fps, codec='libx264', 
                        audio=False, logger=None,
                        ffmpeg_params=['-crf', '28'])
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
    
    video_id = response['id']
    return f"https://youtube.com/shorts/{video_id}"

async def generate_and_send(content_type: str, title: str):
    prompts = {
        "card": f"Напиши мистическое послание карты Таро '{np.random.choice(TAROT_CARDS)}' на сегодня. 5-7 предложений. Мистический стиль. В конце скажи что в боте есть бесплатные расклады.",
        "numerology": "Напиши мистическое послание о числе дня по нумерологии. Укажи число и его значение. 5-7 предложений. В конце скажи про бесплатный расчёт в боте.",
        "tarot": "Напиши короткий расклад Таро на три карты: прошлое, настоящее, будущее. Кратко и мистично. В конце — приглашение на бесплатный расклад в боте.",
        "stars": "Напиши мистическое послание звёзд на сегодня. Общий энергетический прогноз. 5-7 предложений. Упомяни бесплатную натальную карту в боте."
    }
    
    text = await ask_groq(prompts[content_type])
    
    await bot.send_message(ADMIN_ID, f"🎬 Генерирую видео: {title}...")
    
    loop = asyncio.get_event_loop()
    video_path = await loop.run_in_executor(None, create_video, content_type, text, title)
    
    yt_title = f"{title} | {datetime.now().strftime('%d.%m.%Y')} #shorts #таро #нумерология"
    yt_description = f"""{title} на сегодня

🔮 Хочешь личный расклад?
✨ Карта дня БЕСПЛАТНО
🔢 Нумерология БЕСПЛАТНО  
⭐ Натальная карта БЕСПЛАТНО

👉 @numer_taro_bot

#таро #нумерология #эзотерика #гороскоп #расклад #shorts"""

    # Кнопка загрузки в YouTube
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="📤 Загрузить в YouTube", 
            callback_data=f"upload_yt:{content_type}:{datetime.now().strftime('%H%M%S')}"
        )
    ]])
    
    # Сохраняем видео и текст для загрузки
    import pickle
    cache_key = f"video_{datetime.now().strftime('%H%M%S')}"
    with open(f"/tmp/{cache_key}.pkl", 'wb') as f:
        pickle.dump({
            'path': video_path, 
            'title': yt_title, 
            'description': yt_description
        }, f)
    
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
            caption=f"✅ {title} готово!\n\n📋 Описание скопируй:\n{yt_description}",
            reply_markup=keyboard
        )

@router.callback_query(F.data.startswith("upload:"))
async def handle_upload(callback: CallbackQuery):
    cache_key = callback.data.split(":")[1]
    await callback.answer("Загружаю в YouTube...")
    
    try:
        import pickle
        with open(f"/tmp/{cache_key}.pkl", 'rb') as f:
            data = pickle.load(f)
        
        await callback.message.answer("⏳ Загружаю в YouTube... это займёт 1-2 минуты")
        
        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(
            None, upload_to_youtube, data['path'], data['title'], data['description']
        )
        
        await callback.message.answer(f"🎉 Загружено в YouTube!\n\n🔗 {url}")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка загрузки: {e}\n\nЗагрузи видео вручную через YouTube Studio")

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
    await message.answer("🎬 Генерирую тестовое видео... займёт ~2 минуты")
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
    await bot.send_message(ADMIN_ID, 
        "✅ Shorts бот запущен!\n\n"
        "Напиши /test чтобы сразу получить видео с кнопкой 📤 Загрузить в YouTube"
    )
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
