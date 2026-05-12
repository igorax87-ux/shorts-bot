import asyncio
import logging
import os
import tempfile
import aiohttp
import pickle
import random
import json
import subprocess
import shutil
from datetime import datetime

# ── УСТАНОВКА FFMPEG ЕСЛИ НЕТ ────────────────────────────────────────────────
def ensure_ffmpeg():
    if shutil.which("ffmpeg"):
        return True
    logging.info("ffmpeg not found, installing via apt...")
    try:
        subprocess.run(
            ["apt-get", "install", "-y", "-q", "ffmpeg"],
            capture_output=True, timeout=120, check=True
        )
        if shutil.which("ffmpeg"):
            logging.info("ffmpeg installed successfully!")
            return True
    except Exception as e:
        logging.warning(f"apt install failed: {e}")
    # Запасной вариант — imagemagick ffmpeg через pip
    try:
        subprocess.run(
            ["pip", "install", "-q", "imageio[ffmpeg]"],
            capture_output=True, timeout=60, check=True
        )
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        os.environ["PATH"] = os.path.dirname(ffmpeg_path) + ":" + os.environ.get("PATH", "")
        if shutil.which("ffmpeg"):
            logging.info("ffmpeg installed via imageio!")
            return True
    except Exception as e:
        logging.warning(f"imageio ffmpeg failed: {e}")
    logging.warning("ffmpeg unavailable, will use opencv fallback")
    return False

ensure_ffmpeg()
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── ENV ───────────────────────────────────────────────────────────────────────
BOT_TOKEN             = os.getenv("BOT_TOKEN")
GROQ_API_KEY          = os.getenv("GROQ_API_KEY")
ADMIN_ID              = int(os.getenv("ADMIN_ID", "0"))
YOUTUBE_TOKEN         = os.getenv("YOUTUBE_TOKEN")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN")
YOUTUBE_CLIENT_ID     = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
PEXELS_API_KEY        = os.getenv("PEXELS_API_KEY", "cyoihyJPUKMu8nGftkt9Z51s8St0tuXV5GkZ4VIonpeczZpLVgBmWquI")

bot    = Bot(token=BOT_TOKEN)
dp     = Dispatcher()
router = Router()

USED_VIDEOS_FILE = "/tmp/used_pexels_videos.json"

# ── ДАННЫЕ ────────────────────────────────────────────────────────────────────
TAROT_CARDS = [
    "Шут", "Маг", "Верховная Жрица", "Императрица", "Император",
    "Иерофант", "Влюблённые", "Колесница", "Сила", "Отшельник",
    "Колесо Фортуны", "Справедливость", "Повешенный", "Смерть",
    "Умеренность", "Дьявол", "Башня", "Звезда", "Луна", "Солнце",
    "Суд", "Мир"
]

SCHEDULES = [
    {"hour": 9,  "minute": 0,  "type": "card",       "emoji": "🃏", "title": "Карта дня"},
    {"hour": 12, "minute": 0,  "type": "numerology",  "emoji": "🔢", "title": "Нумерология"},
    {"hour": 18, "minute": 0,  "type": "tarot",       "emoji": "🔮", "title": "Расклад Таро"},
    {"hour": 21, "minute": 0,  "type": "stars",       "emoji": "⭐", "title": "Послание звёзд"},
]

# Ключевые слова для Pexels
PEXELS_KEYWORDS = {
    "card":       ["tarot cards mystical dark", "magic candles fortune", "mystical hands occult", "fortune telling fog", "magic ritual dark"],
    "numerology": ["sacred geometry cosmos", "golden numbers universe", "mystical numbers space", "fibonacci spiral light", "cosmic energy glow"],
    "tarot":      ["tarot reading mystic", "crystal ball magic", "witch forest dark", "mystical altar candles", "dark magic ritual"],
    "stars":      ["galaxy stars milky way", "night sky cosmos purple", "nebula universe dark", "aurora borealis night", "starry sky dark"],
}

# 35 ЦЕПЛЯЮЩИХ ХУКОВ
HOOKS = [
    "Это послание пришло именно для тебя...",
    "Вселенная шепчет тебе кое-что важное",
    "Стоп. Это не случайно что ты это видишь",
    "Твои ответы уже ждут тебя здесь",
    "Сегодня звёзды говорят только о тебе",
    "Это знак. Читай до конца",
    "Ты это видишь — значит тебе это нужно",
    "Судьба отправила тебе сообщение",
    "Не листай дальше. Это важно",
    "Твои карты открылись прямо сейчас",
    "Что скрывает от тебя Вселенная?",
    "Секрет твоей судьбы раскрыт",
    "Высшие силы говорят именно с тобой",
    "Этот день изменит всё. Смотри",
    "Тёмная тайна твоего пути открыта",
    "Космос послал тебе это сегодня",
    "Твоя судьба разворачивается прямо сейчас",
    "Остановись. Вселенная хочет тебе сказать",
    "Это видение пришло специально для тебя",
    "Магия этого дня раскрывается здесь",
    "Знаешь ли ты что ждёт тебя впереди?",
    "Архангелы шепчут твоё имя сегодня",
    "Скрытое становится явным. Смотри",
    "Твой путь освещается прямо сейчас",
    "Предупреждение от звёзд именно тебе",
    "Энергия этого дня принадлежит тебе",
    "Что таят карты для тебя сегодня?",
    "Молчание небес нарушено ради тебя",
    "Твоя судьба говорит. Слышишь её?",
    "Этот знак появился не случайно",
    "Силы небес собрались ради тебя",
    "Что Луна скрывала от тебя месяцами?",
    "Портал открыт. Твоё послание внутри",
    "Карты не лгут. Особенно сегодня",
    "Вибрации этого дня несут твой ответ",
]

# ── PEXELS ────────────────────────────────────────────────────────────────────
def load_used_videos() -> set:
    try:
        with open(USED_VIDEOS_FILE, 'r') as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_used_videos(used: set):
    try:
        with open(USED_VIDEOS_FILE, 'w') as f:
            json.dump(list(used), f)
    except Exception:
        pass


async def get_pexels_video(content_type: str):
    """Скачивает уникальное видео с Pexels. Возвращает путь или None."""
    used_ids = load_used_videos()
    keywords = PEXELS_KEYWORDS.get(content_type, PEXELS_KEYWORDS["stars"])
    keyword  = random.choice(keywords)
    headers  = {"Authorization": PEXELS_API_KEY}

    try:
        async with aiohttp.ClientSession() as session:
            params = {"query": keyword, "orientation": "portrait", "size": "medium", "per_page": 20}
            async with session.get("https://api.pexels.com/videos/search",
                                   headers=headers, params=params) as resp:
                if resp.status != 200:
                    logger.warning(f"Pexels API status: {resp.status}")
                    return None
                data = await resp.json()

            videos = data.get("videos", [])
            if not videos:
                return None

            fresh = [v for v in videos if str(v["id"]) not in used_ids]
            if not fresh:
                used_ids = set()   # сбрасываем историю
                fresh = videos

            video    = random.choice(fresh)
            video_id = str(video["id"])

            files = video.get("video_files", [])
            # Берём вертикальные файлы, иначе любые
            portrait = [f for f in files if f.get("width", 0) < f.get("height", 1)]
            pool = portrait if portrait else files
            # Среднее качество чтобы не слишком большое
            pool.sort(key=lambda x: x.get("width", 0) * x.get("height", 0))
            chosen = pool[len(pool) // 2] if len(pool) > 1 else pool[0]

            video_url = chosen.get("link")
            if not video_url:
                return None

            tmp_path = tempfile.mktemp(suffix='.mp4')
            async with session.get(video_url) as vresp:
                if vresp.status != 200:
                    return None
                with open(tmp_path, 'wb') as f:
                    f.write(await vresp.read())

            used_ids.add(video_id)
            save_used_videos(used_ids)
            logger.info(f"Pexels OK: id={video_id} query='{keyword}'")
            return tmp_path

    except Exception as e:
        logger.warning(f"Pexels error: {e}")
        return None

# ── ТЕКСТ НА ПРОЗРАЧНОМ PNG ───────────────────────────────────────────────────
def create_text_overlay_image(hook: str, text: str, title: str) -> str:
    W, H = 1080, 1920
    # Финальное изображение БЕЗ прозрачности (RGB) — чёрный фон
    final = Image.new('RGB', (W, H), (8, 4, 22))

    # Градиентный тёмный overlay
    grad = Image.new('RGBA', (W, H))
    gd   = ImageDraw.Draw(grad)
    for y in range(H):
        alpha = int(200 * (y / H))
        gd.line([(0, y), (W, y)], fill=(0, 0, 15, alpha))
    final.paste(grad.convert('RGB'), mask=grad.split()[3])

    draw = ImageDraw.Draw(final)

    # Шрифты — ищем что есть в системе
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    ]
    font_path = next((p for p in candidates if os.path.exists(p)), None)

    def fnt(size):
        if font_path:
            return ImageFont.truetype(font_path, size)
        return ImageFont.load_default()

    f_hook  = fnt(74)   # крупный цепляющий хук
    f_title = fnt(60)   # заголовок
    f_body  = fnt(46)   # основной текст
    f_cta   = fnt(42)   # CTA блок снизу

    def shadow_text(d, xy, txt, font, color, shadow=(0, 0, 0), off=4):
        x, y = xy
        d.text((x + off, y + off), txt, font=font, fill=shadow, anchor="mm")
        d.text((x, y),             txt, font=font, fill=color,  anchor="mm")

    def wrap(t, max_c=26):
        words = t.split()
        lines, cur = [], ""
        for w in words:
            if len(cur) + len(w) + 1 <= max_c:
                cur = (cur + " " + w).strip()
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    # ── ХУК — жёлтый, крупный, цепляющий ──
    y = 160
    for line in wrap(hook, 22):
        shadow_text(draw, (W // 2, y), line, f_hook, (255, 225, 60))
        y += 86

    # Линия-разделитель
    draw.line([(80, y + 15), (W - 80, y + 15)], fill=(180, 80, 255), width=3)

    # ── Заголовок — фиолетовый ──
    shadow_text(draw, (W // 2, y + 70), title, f_title, (210, 155, 255))
    draw.line([(80, y + 115), (W - 80, y + 115)], fill=(180, 80, 255), width=2)

    # ── Основной текст — белый ──
    ty = y + 185
    for line in wrap(text, 30)[:7]:
        shadow_text(draw, (W // 2, ty), line, f_body, (255, 245, 255))
        ty += 62
        if ty > H - 430:
            break

    # ── CTA блок снизу ──
    cta_y = H - 340
    draw.rounded_rectangle([50, cta_y - 20, W - 50, cta_y + 270],
                            radius=28,
                            fill=(12, 0, 40),
                            outline=(170, 70, 255),
                            width=3)

    shadow_text(draw, (W // 2, cta_y + 30),
                "Бесплатный расклад каждый день", f_cta, (190, 140, 255))
    shadow_text(draw, (W // 2, cta_y + 115),
                "@numer_taro_bot", f_cta, (255, 215, 60))
    shadow_text(draw, (W // 2, cta_y + 200),
                "Ссылка в описании", f_cta, (170, 215, 255))

    png_path = tempfile.mktemp(suffix='.png')
    final.save(png_path, 'PNG')
    return png_path

# ── СБОРКА ВИДЕО ЧЕРЕЗ FFMPEG ─────────────────────────────────────────────────
def build_video_ffmpeg(bg_path, overlay_png, out_path) -> bool:
    try:
        if bg_path and os.path.exists(bg_path):
            # Шаг 1: перекодируем Pexels видео в совместимый формат
            bg_fixed = tempfile.mktemp(suffix='_fixed.mp4')
            fix = subprocess.run([
                "ffmpeg", "-y", "-i", bg_path,
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
                "-pix_fmt", "yuv420p", "-an", "-t", "30", bg_fixed
            ], capture_output=True, text=True, timeout=90)

            if fix.returncode == 0 and os.path.exists(bg_fixed) and os.path.getsize(bg_fixed) > 1000:
                # Шаг 2: накладываем текст поверх
                cmd = [
                    "ffmpeg", "-y",
                    "-i", bg_fixed,
                    "-i", overlay_png,
                    "-filter_complex", "[0:v][1:v]overlay=0:0[out]",
                    "-map", "[out]",
                    "-t", "30",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "28",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
                    out_path
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                try: os.remove(bg_fixed)
                except: pass
                if r.returncode == 0:
                    return True
                logger.error(f"overlay failed: {r.stderr[-300:]}")
            else:
                logger.warning(f"bg fix failed: {fix.stderr[-300:]}")

        # Запасной вариант: красивый тёмный фон через ffmpeg (без Pexels)
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=0x08041a:size=1080x1920:rate=24",
            "-i", overlay_png,
            "-filter_complex", "[0:v][1:v]overlay=0:0[out]",
            "-map", "[out]",
            "-t", "30",
            "-c:v", "libx264", "-preset", "fast", "-crf", "28",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
            out_path
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            logger.error(f"ffmpeg fallback failed: {r.stderr[-300:]}")
            return False
        return True
    except Exception as e:
        logger.error(f"ffmpeg exception: {e}")
        return False


def build_video_opencv(overlay_png, out_path) -> bool:
    """Запасной вариант без ffmpeg."""
    try:
        import cv2
        img = Image.open(overlay_png).convert('RGB')
        frame_bgr = np.array(img)[:, :, ::-1].copy()
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(out_path, fourcc, 24, (1080, 1920))
        for _ in range(720):
            writer.write(frame_bgr)
        writer.release()
        return os.path.exists(out_path) and os.path.getsize(out_path) > 1000
    except Exception as e:
        logger.error(f"opencv error: {e}")
        return False


async def create_video(content_type: str, text: str, title: str) -> str:
    hook = random.choice(HOOKS)

    bg_video = await get_pexels_video(content_type)

    loop = asyncio.get_event_loop()
    overlay_png = await loop.run_in_executor(
        None, create_text_overlay_image, hook, text, title
    )

    out_path = tempfile.mktemp(suffix='.mp4')
    ok = await loop.run_in_executor(None, build_video_ffmpeg, bg_video, overlay_png, out_path)

    if not ok:
        logger.warning("ffmpeg failed → opencv fallback")
        ok = await loop.run_in_executor(None, build_video_opencv, overlay_png, out_path)

    # Чистим временные файлы
    for tmp in [overlay_png, bg_video]:
        if tmp and os.path.exists(tmp):
            try: os.remove(tmp)
            except Exception: pass

    if not ok:
        raise Exception("Не удалось создать видео")

    # Проверяем размер — Telegram лимит 50MB
    size_mb = os.path.getsize(out_path) / 1024 / 1024
    logger.info(f"Video size: {size_mb:.1f} MB")
    if size_mb > 45:
        compressed = tempfile.mktemp(suffix='.mp4')
        cmd = ["ffmpeg", "-y", "-i", out_path,
               "-c:v", "libx264", "-crf", "36", "-preset", "fast",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", compressed]
        subprocess.run(cmd, capture_output=True, timeout=90)
        if os.path.exists(compressed):
            os.remove(out_path)
            out_path = compressed

    return out_path

# ── GROQ ──────────────────────────────────────────────────────────────────────
async def ask_groq(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
        "temperature": 0.9,
    }
    async with aiohttp.ClientSession() as s:
        async with s.post("https://api.groq.com/openai/v1/chat/completions",
                          headers=headers, json=payload) as resp:
            result = await resp.json()
            if "choices" not in result:
                raise Exception(result.get("error", {}).get("message", str(result)))
            return result["choices"][0]["message"]["content"]

# ── YOUTUBE ───────────────────────────────────────────────────────────────────
def upload_to_youtube(video_path: str, title: str, description: str) -> str:
    creds   = Credentials(
        token=YOUTUBE_TOKEN,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token"
    )
    youtube = build('youtube', 'v3', credentials=creds)
    body    = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': ['таро', 'нумерология', 'гороскоп', 'эзотерика',
                     'расклад', 'shorts', 'картадня', 'мистика', 'предсказание'],
            'categoryId': '22'
        },
        'status': {'privacyStatus': 'public', 'selfDeclaredMadeForKids': False}
    }
    media   = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
    resp    = youtube.videos().insert(part='snippet,status', body=body, media_body=media).execute()
    return f"https://youtube.com/shorts/{resp['id']}"

# ── ГЕНЕРАЦИЯ И ОТПРАВКА ──────────────────────────────────────────────────────
async def generate_and_send(content_type: str, title: str):
    card = random.choice(TAROT_CARDS)
    prompts = {
        "card":
            f"Карта Таро на сегодня — {card}. Напиши мистическое послание. "
            "2-3 коротких предложения максимум. Только кириллица. Мистически и лично.",
        "numerology":
            f"Сегодня {datetime.now().strftime('%d.%m.%Y')}. Нумерологическое послание числа дня. "
            "2-3 предложения максимум. Только кириллица.",
        "tarot":
            "Расклад Таро: прошлое, настоящее, будущее — по одному короткому предложению. "
            "Только кириллица. Кратко и мистично.",
        "stars":
            "Энергетический прогноз звёзд на сегодня. 2-3 предложения максимум. "
            "Только кириллица. Мистически.",
    }
    try:
        text = await ask_groq(prompts[content_type])
        await bot.send_message(ADMIN_ID, f"🎬 Генерирую видео: {title}...\n⏳ ~45 секунд")

        video_path = await create_video(content_type, text, title)

        yt_title = f"{title} | {datetime.now().strftime('%d.%m.%Y')} #shorts #таро #нумерология"
        yt_desc  = (
            f"{title} на сегодня\n\n"
            "🔮 Хочешь личный расклад?\n"
            "✨ Карта дня БЕСПЛАТНО\n"
            "🔢 Нумерология БЕСПЛАТНО\n"
            "⭐ Натальная карта БЕСПЛАТНО\n\n"
            "👉 Бот в Telegram: @numer_taro_bot\n\n"
            "#таро #нумерология #эзотерика #гороскоп #расклад #shorts "
            "#картадня #предсказание #мистика #послание"
        )

        cache_key = f"video_{datetime.now().strftime('%H%M%S')}"
        with open(f"/tmp/{cache_key}.pkl", 'wb') as f:
            pickle.dump({'path': video_path, 'title': yt_title, 'description': yt_desc}, f)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📤 Загрузить в YouTube Shorts",
                                 callback_data=f"upload:{cache_key}")
        ]])

        video_file = FSInputFile(video_path)
        await bot.send_document(
            ADMIN_ID, video_file,
            caption=f"✅ {title} готово!\n\n📋 Описание:\n{yt_desc}",
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error(f"generate_and_send error: {e}")
        await bot.send_message(ADMIN_ID, f"❌ Ошибка генерации: {e}")

# ── HANDLERS ──────────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("upload:"))
async def handle_upload(callback: CallbackQuery):
    key = callback.data.split(":")[1]
    await callback.answer("Загружаю в YouTube...")
    try:
        with open(f"/tmp/{key}.pkl", 'rb') as f:
            data = pickle.load(f)
        await callback.message.answer("⏳ Загружаю в YouTube... 1-2 минуты")
        loop = asyncio.get_event_loop()
        url  = await loop.run_in_executor(
            None, upload_to_youtube, data['path'], data['title'], data['description']
        )
        await callback.message.answer(f"🎉 Загружено!\n\n🔗 {url}")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка загрузки: {e}\n\nЗагрузи вручную через YouTube Studio")


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
        "/test — тестовое видео прямо сейчас\n"
        "/stats — сколько Pexels видео использовано"
    )


@router.message(Command("test"))
async def cmd_test(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🎬 Генерирую тестовое видео с Pexels фоном... ~45 сек")
    await generate_and_send("tarot", "🔮 Расклад Таро")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    used = load_used_videos()
    await message.answer(f"📊 Использовано уникальных Pexels видео: {len(used)}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
async def main():
    dp.include_router(router)
    scheduler = AsyncIOScheduler(timezone="Europe/Kiev")
    for s in SCHEDULES:
        scheduler.add_job(
            generate_and_send, 'cron',
            hour=s["hour"], minute=s["minute"],
            args=[s["type"], f"{s['emoji']} {s['title']}"]
        )
    scheduler.start()
    logger.info("✅ SHORTS SCHEDULER STARTED!")
    await bot.send_message(
        ADMIN_ID,
        "✅ Shorts бот запущен!\n\n"
        "Напиши /test — видео с живым Pexels фоном придёт за ~45 сек 🚀\n"
        "35 разных хуков, уникальные фоны, без повторений!"
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
