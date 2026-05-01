# bot/services/image_service.py
"""Unsplash API orqali slaydlar uchun rasm qidirish va yuklab olish."""

from __future__ import annotations

import asyncio
import re
from typing import Optional

import aiohttp

from ..config import SETTINGS, logger


# Unsplash API
UNSPLASH_BASE = "https://api.unsplash.com"
UNSPLASH_TIMEOUT = aiohttp.ClientTimeout(total=10)

# O'zbek/Rus → Inglizcha kalit so'z lug'ati (keng tarqalgan akademik atamalar)
_KEYWORD_MAP = {
    "kirish": "introduction", "xulosa": "conclusion", "rahmat": "thank you",
    "reja": "plan", "maqsad": "goal", "vazifa": "task", "dolzarb": "relevant",
    "taqdimot": "presentation", "natija": "result", "tahlil": "analysis",
    "metod": "method", "tadqiqot": "research", "texnolog": "technology",
    "axborot": "information", "tarmoq": "network", "xavfsiz": "security",
    "dastur": "software", "kompyuter": "computer", "tizim": "system",
    "iqtisod": "economics", "moliya": "finance", "bozor": "market",
    "talim": "education", "ta'lim": "education", "fan": "science",
    "tibbiyot": "medicine", "sog'liq": "health", "huquq": "law",
    "jamiyat": "society", "madaniyat": "culture", "tarix": "history",
    "muhit": "environment", "ekolog": "ecology", "energi": "energy",
    "qurilish": "construction", "arxitektura": "architecture",
    "transport": "transport", "savdo": "trade", "sanoat": "industry",
    "qishloq": "agriculture", "oziq": "food", "suv": "water",
    "введен": "introduction", "заключен": "conclusion", "метод": "method",
    "результат": "result", "анализ": "analysis", "технолог": "technology",
    "безопасн": "security", "экономи": "economics", "образован": "education",
}

# Rasm kerak bo'lmagan slaydlar (titul, reja, rahmat)
_SKIP_PATTERNS = [
    "titul", "title slide", "reja", "outline", "rahmat", "thank",
    "mundarija", "содержан", "спасибо", "plan",
]


def _extract_english_keywords(title: str, topic: str = "") -> str:
    """Slayd sarlavhasidan inglizcha qidiruv so'zi yaratish."""
    text = f"{title} {topic}".lower()

    # Lug'atdan mos kalit so'zlarni topish
    keywords = []
    for uz_key, en_val in _KEYWORD_MAP.items():
        if uz_key in text and en_val not in keywords:
            keywords.append(en_val)

    # Faqat ALL-CAPS texnik atamalar (VPN, IPsec, IT, API, SQL...)
    tech_words = re.findall(r'\b[A-Z][A-Z0-9]{1,10}\b', f"{title} {topic}")
    for w in tech_words:
        if w.lower() not in keywords:
            keywords.append(w)

    if not keywords:
        return "academic presentation technology"

    # Faqat inglizcha so'zlarni qaytarish (o'zbekcha so'zlar Unsplash da ishlamaydi)
    return " ".join(keywords[:3])


def _should_skip_slide(title: str) -> bool:
    """Bu slaydga rasm kerak emasmi?"""
    t = title.lower()
    return any(p in t for p in _SKIP_PATTERNS)


async def fetch_slide_image(query: str, session: aiohttp.ClientSession) -> Optional[bytes]:
    """Unsplash dan rasm qidirish va yuklab olish."""
    api_key = getattr(SETTINGS, "unsplash_api_key", "") or ""
    if not api_key:
        return None

    try:
        url = f"{UNSPLASH_BASE}/search/photos"
        params = {
            "query": query[:100],
            "per_page": 1,
            "orientation": "landscape",
        }
        headers = {"Authorization": f"Client-ID {api_key}"}

        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                logger.warning(f"Unsplash search failed: {resp.status}")
                return None
            data = await resp.json()

        results = data.get("results", [])
        if not results:
            return None

        # regular (1080px) — sifatli, slayd uchun yaxshi
        img_url = results[0].get("urls", {}).get("regular") or results[0].get("urls", {}).get("small")
        if not img_url:
            return None

        async with session.get(img_url) as img_resp:
            if img_resp.status != 200:
                return None
            return await img_resp.read()

    except Exception as e:
        logger.warning(f"Image fetch error for '{query}': {e}")
        return None


async def fetch_images_for_slides(slide_titles: list[str], topic: str = "") -> dict[int, bytes]:
    """Barcha slaydlar uchun rasmlar olish (parallel).

    Args:
        slide_titles: Slayd sarlavhalari ro'yxati
        topic: Asosiy mavzu (inglizcha kalit so'z olish uchun)

    Returns:
        {slayd_index: image_bytes} dict
    """
    api_key = getattr(SETTINGS, "unsplash_api_key", "") or ""
    if not api_key:
        logger.info("Unsplash API key yo'q — rasmlar o'tkazib yuboriladi")
        return {}

    images: dict[int, bytes] = {}

    async with aiohttp.ClientSession(timeout=UNSPLASH_TIMEOUT) as session:
        sem = asyncio.Semaphore(5)

        async def _fetch_one(idx: int, title: str):
            async with sem:
                # Titul, reja, rahmat slaydlarini o'tkazib yuborish
                if _should_skip_slide(title):
                    return
                # Inglizcha kalit so'z yaratish
                query = _extract_english_keywords(title, topic)
                logger.info(f"Slide {idx} image search: '{title}' -> '{query}'")
                img = await fetch_slide_image(query, session)
                if img:
                    images[idx] = img

        tasks = [_fetch_one(i, t) for i, t in enumerate(slide_titles)]
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info(f"Unsplash: {len(images)}/{len(slide_titles)} ta rasm yuklab olindi")
    return images
