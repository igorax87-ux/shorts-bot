import asyncio
import httpx
import random
import math
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import imageio
import numpy as np

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

TOPICS = [
    {"type": "card_day", "title": "🃏 Карта дня"},
    {"type": "numerology", "title": "🔢 Нумерология дня"},
    {"type": "tarot_spread", "title": "🔮 Расклад Таро"},
    {"type": "zodiac", "title": "⭐ Послание звёзд"},
]

# Mystical color palettes
PALETTES = [
    {"bg": (15, 5, 40), "accent": (180, 100, 255), "text": (220, 200, 255), "star": (255, 220, 150)},
    {"bg": (5, 20, 40), "accent": (100, 180, 255), "text": (200, 220, 255), "star": (255, 255, 200)},
    {"bg": (30, 5, 30), "accent": (255, 100, 200), "text": (255, 210, 240), "star": (255, 230, 150)},
    {"bg": (5, 30, 20), "accent": (100, 255, 180), "text": (200, 255, 230), "star": (255, 255, 180)},
]

TAROT_CARDS = [
    "Дурак", "Маг", "Верховная Жрица", "Императрица", "Император",
    "Иерофант", "Влюблённые", "Колесница", "Сила", "Отшельник",
    "Колесо Фортуны", "Справедливость", "Повешенный", "Смерть",
    "Умеренность", "Дьявол", "Башня", "Звезда", "Луна", "Солнце",
    "Суд", "Мир"
]


async def get_groq_text(topic_type: str, groq_key: str) -> dict:
    prompts = {
        "card_day": (
            "Ты Таро-мастер. Вытяни одну карту Таро и дай послание на сегодня. "
            "Ответь ТОЛЬКО в формате JSON без markdown:\n"
            "{\"card\": \"название карты\", \"title\": \"Карта дня\", "
            "\"text\": \"послание 2-3 коротких предложения\", "
            "\"cta\": \"Бесплатный расклад и карта дня каждый день — ссылка в описании! 🔮\"}"
        ),
        "numerology": (
            f"Сегодня {datetime.now().strftime('%d.%m.%Y')}. Посчитай число дня (сложи все цифры до однозначного). "
            "Дай нумерологическое послание. "
            "Ответь ТОЛЬКО в формате JSON без markdown:\n"
            "{\"card\": \"Число дня: X\", \"title\": \"Нумерология\", "
            "\"text\": \"послание 2-3 коротких предложения\", "
            "\"cta\": \"Узнай своё число судьбы бесплатно — ссылка в описании! ✨\"}"
        ),
        "tarot_spread": (
            "Сделай мини-расклад Таро на 3 карты: прошлое, настоящее, будущее. "
            "Ответь ТОЛЬКО в формате JSON без markdown:\n"
            "{\"card\": \"3 карты расклада\", \"title\": \"Расклад Таро\", "
            "\"text\": \"краткое толкование 2-3 предложения\", "
            "\"cta\": \"Личный расклад бесплатно — ссылка в описании! 🃏\"}"
        ),
        "zodiac": (
            "Дай мистическое послание звёзд на сегодня — коротко и вдохновляюще. "
            "Ответь ТОЛЬКО в формате JSON без markdown:\n"
            "{\"card\": \"✨ Послание Вселенной\", \"title\": \"Звёзды говорят\", "
            "\"text\": \"послание 2-3 коротких предложения\", "
            "\"cta\": \"Натальная карта и карта дня бесплатно — ссылка в описании! ⭐\"}"
        ),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {groq_key}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompts[topic_type]}],
                "max_tokens": 400,
                "temperature": 0.9,
            }
        )
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        # Clean and parse JSON
        text = text.strip().replace("```json", "").replace("```", "").strip()
        import json
        return json.loads(text)


def draw_stars(draw, width, height, palette, count=80, alpha_img=None):
    """Draw twinkling stars"""
    for _ in range(count):
        x = random.randint(0, width)
        y = random.randint(0, height)
        size = random.choice([1, 1, 1, 2, 2, 3])
        brightness = random.randint(150, 255)
        color = (brightness, brightness, int(brightness * 0.8))
        draw.ellipse([x-size, y-size, x+size, y+size], fill=color)


def draw_mystical_circles(draw, width, height, palette):
    """Draw decorative mystical circles"""
    cx, cy = width // 2, height // 2
    for r in [280, 240, 200]:
        for i in range(0, 360, 15):
            angle = math.radians(i)
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            draw.ellipse([x-2, y-2, x+2, y+2], fill=palette["accent"] + (80,) if len(palette["accent"]) == 3 else palette["accent"])


def wrap_text(text, font, max_width, draw):
    """Wrap text to fit width"""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = current + " " + word if current else word
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def create_frame(content: dict, palette: dict, frame_num: int, total_frames: int, width=1080, height=1920):
    """Create one video frame"""
    img = Image.new("RGB", (width, height), palette["bg"])
    draw = ImageDraw.Draw(img)

    # Animated star twinkle offset
    random.seed(frame_num // 5)
    draw_stars(draw, width, height, palette, count=120)

    # Gradient overlay top and bottom
    for y in range(200):
        alpha = int(180 * (1 - y / 200))
        draw.line([(0, y), (width, y)], fill=tuple(min(255, c + 20) for c in palette["bg"]))
    for y in range(height - 200, height):
        alpha = int(180 * ((y - (height - 200)) / 200))
        draw.line([(0, y), (width, y)], fill=tuple(min(255, c + 20) for c in palette["bg"]))

    # Pulsing circle animation
    pulse = math.sin(frame_num * 0.15) * 20
    cx, cy = width // 2, height // 2

    # Outer decorative rings
    for r, op in [(320 + pulse, 40), (280 + pulse, 60), (240 + pulse, 80)]:
        for angle_deg in range(0, 360, 10):
            angle = math.radians(angle_deg)
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            size = 2
            draw.ellipse([x-size, y-size, x+size, y+size], fill=palette["accent"])

    # Center glow circle
    for r in range(150, 0, -10):
        alpha_val = int(30 * (r / 150))
        glow_color = tuple(min(255, c + alpha_val) for c in palette["bg"])
        draw.ellipse([cx-r, cy-r*1.1, cx+r, cy+r*1.1], fill=glow_color)

    # Load fonts - use default if custom not available
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 38)
        font_cta = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except:
        font_large = ImageFont.load_default()
        font_medium = font_large
        font_small = font_large
        font_cta = font_large

    # TITLE at top
    title = content.get("title", "Таро")
    bbox = draw.textbbox((0, 0), title, font=font_large)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, 120), title, font=font_large, fill=palette["accent"])

    # Decorative line under title
    draw.line([(width//2 - 200, 220), (width//2 + 200, 220)], fill=palette["accent"], width=2)

    # CARD NAME in center
    card = content.get("card", "")
    card_lines = wrap_text(card, font_medium, width - 100, draw)
    card_y = cy - 80
    for line in card_lines:
        bbox = draw.textbbox((0, 0), line, font=font_medium)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) // 2, card_y), line, font=font_medium, fill=palette["star"])
        card_y += 70

    # MAIN TEXT
    text = content.get("text", "")
    text_lines = wrap_text(text, font_small, width - 120, draw)
    text_y = cy + 120
    for line in text_lines:
        bbox = draw.textbbox((0, 0), line, font=font_small)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) // 2, text_y), line, font=font_small, fill=palette["text"])
        text_y += 55

    # CTA box at bottom
    cta = content.get("cta", "")
    cta_lines = wrap_text(cta, font_cta, width - 80, draw)

    # CTA background
    cta_y = height - 280
    box_h = len(cta_lines) * 60 + 40
    draw.rounded_rectangle(
        [40, cta_y - 20, width - 40, cta_y + box_h],
        radius=20,
        fill=tuple(min(255, c + 30) for c in palette["bg"])
    )
    draw.rounded_rectangle(
        [40, cta_y - 20, width - 40, cta_y + box_h],
        radius=20,
        outline=palette["accent"],
        width=2
    )

    for line in cta_lines:
        bbox = draw.textbbox((0, 0), line, font=font_cta)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) // 2, cta_y), line, font=font_cta, fill=palette["accent"])
        cta_y += 58

    # Selena signature
    sign = "🔮 Селена • Потомственная гадалка"
    try:
        bbox = draw.textbbox((0, 0), sign, font=font_small)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) // 2, height - 80), sign, font=font_small, fill=palette["text"])
    except:
        pass

    return np.array(img)


async def generate_video(topic: dict, groq_key: str, output_path: str):
    """Generate one Shorts video"""
    print(f"Generating video: {topic['title']}...")

    content = await get_groq_text(topic["type"], groq_key)
    palette = random.choice(PALETTES)

    fps = 24
    duration = 30  # 30 seconds
    total_frames = fps * duration

    frames = []
    for i in range(total_frames):
        frame = create_frame(content, palette, i, total_frames)
        frames.append(frame)
        if i % 24 == 0:
            print(f"  Frame {i}/{total_frames}")

    # Write video
    writer = imageio.get_writer(output_path, fps=fps, codec='libx264', quality=7)
    for frame in frames:
        writer.append_data(frame)
    writer.close()

    print(f"Video saved: {output_path}")
    return content


if __name__ == "__main__":
    import sys
    topic = TOPICS[int(sys.argv[1]) if len(sys.argv) > 1 else 0]
    groq_key = os.getenv("GROQ_API_KEY", "")
    asyncio.run(generate_video(topic, groq_key, f"test_{topic['type']}.mp4"))
