from __future__ import annotations

import hashlib
from typing import Iterable, Sequence, Tuple

import os

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

WEB_APP_URL = os.getenv("WEB_APP_URL", "").strip()


# -------------------------
# Constants
# -------------------------
MAIN_MENU_BUTTONS: Tuple[str, ...] = (
    "📚 Kurs ishi", "🎯 Taqdimot", "📄 Maqola", "📌 Tezis",
    "📝 Mustaqil ish", "🎓 Diplom ishi", "🔬 Dissertatsiya", "📖 O'quv qo'llanma",
    "📝 Imtihonga yordam", "👤 Hisobim", "💳 To'lov",
    "💬 Adminga murojaat", "🎁 Taklifnoma", "📝 Narxlar",
)


# -------------------------
# Helpers
# -------------------------
def _clean_channel_username(chan: str) -> str:
    """'@channel' or 'channel' -> 'channel' (no @, trimmed)."""
    c = (chan or "").strip()
    if c.startswith("@"):
        c = c[1:]
    return c.strip()


def _clamp_cols(cols: int, default: int = 2) -> int:
    try:
        c = int(cols)
    except Exception:
        c = default
    return max(1, min(4, c))  # 1..4


def _short_id(value: str, max_len: int = 24) -> str:
    """
    Make callback-safe short id.
    - Telegram callback_data has ~64 bytes limit.
    - If inv_id is long, we hash to 12 chars.
    """
    v = (value or "").strip()
    if not v:
        return "na"
    if len(v) <= max_len:
        return v
    h = hashlib.sha256(v.encode("utf-8")).hexdigest()[:12]
    return f"{v[:8]}_{h}"


def inline_options(
    options: Sequence[Tuple[str, str]],
    prefix: str,
    cols: int = 2,
) -> InlineKeyboardMarkup:
    """Generic inline options builder."""
    builder = InlineKeyboardBuilder()
    for text, val in options:
        builder.button(text=text, callback_data=f"{prefix}:{val}")
    builder.adjust(_clamp_cols(cols))
    return builder.as_markup()


# -------------------------
# Main Menu (Reply KB)
# -------------------------
def main_menu_kb(
    is_admin: bool = False,
    user_id: int | None = None,
    web_app_token: str | None = None,
) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()

    # Web App button — caller passes a fresh one-time token (async generation)
    if WEB_APP_URL.startswith("https://"):
        url = WEB_APP_URL.rstrip("/")
        if web_app_token:
            url = f"{url}/login?token={web_app_token}"
        builder.add(KeyboardButton(text="🌐 Web App ochish", web_app=WebAppInfo(url=url)))

    for text in MAIN_MENU_BUTTONS:
        builder.add(KeyboardButton(text=text))

    if is_admin:
        builder.add(KeyboardButton(text="⚙️ Admin Panel"))

    builder.adjust(2)
    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Bo‘lim tanlang…",
        selective=False,
    )


# -------------------------
# Admin Panel (Inline KB)
# -------------------------
def admin_panel_kb(is_superadmin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Statistika", callback_data="adm:stats")
    builder.button(text="📢 Xabar tarqatish", callback_data="adm:broadcast")
    builder.button(text="⏳ Kutilayotgan to'lovlar", callback_data="adm:pending")
    builder.button(text="💰 Narxlar", callback_data="adm:prices")
    builder.button(text="🎁 Promo-kodlar", callback_data="adm:promo_menu")
    builder.button(text="🛠 Sozlamalar", callback_data="adm:settings")
    builder.button(text="👤 Foydalanuvchi", callback_data="adm:usermgmt")
    if is_superadmin:
        builder.button(text="👥 Adminlar boshqaruvi", callback_data="adm:admins")
    builder.adjust(1)
    return builder.as_markup()


def user_mgmt_kb(user_id: int, is_blocked: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    block_text = "🔓 Blokdan ochish" if is_blocked else "🔒 Bloklash"
    builder.button(text=block_text, callback_data=f"adm:block:{user_id}")
    builder.button(text="💰 Balans", callback_data=f"adm:bal:{user_id}")

    builder.adjust(1)
    return builder.as_markup()


# -------------------------
# Wizard KBs
# -------------------------
def citation_styles_kb() -> InlineKeyboardMarkup:
    return inline_options(
        [
            ("APA Style", "apa"),
            ("Vancouver", "vancouver"),
            ("GOST (Russian standard)", "gost"),
            ("Harvard", "harvard"),
            ("O'AK (Uzbek standard)", "oak"),
            ("Formatlamaslik", "none"),
        ],
        prefix="wiz:cite",
        cols=2,
    )


def university_kb() -> InlineKeyboardMarkup:
    return inline_options(
        [
            ("Milliy Univ (MU)", "nuz"),
            ("Toshkent Davlat Iqtisod (TDIU)", "tsue"),
            ("TATU", "tuit"),
            ("Westminster (WIUT)", "wiut"),
            ("Boshqa (Oddiy)", "other"),
        ],
        prefix="wiz:uni",
        cols=2,
    )


# -------------------------
# Payment review (Admin)
# -------------------------
def payment_review_kb(user_id: int, inv_id: str) -> InlineKeyboardMarkup:
    """
    Payment review callbacks must be short enough for Telegram.
    We shorten inv_id safely if needed.
    """
    inv = _short_id(inv_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=f"adm:payok:{user_id}:{inv}")
    builder.button(text="❌ Rad etish", callback_data=f"adm:payno:{user_id}:{inv}")
    builder.adjust(2)
    return builder.as_markup()


# -------------------------
# Subscription check
# -------------------------
def sub_check_kb(channels: Iterable[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    clean = [_clean_channel_username(ch) for ch in channels]
    clean = [c for c in clean if c]

    if clean:
        for i, chan in enumerate(clean, 1):
            builder.button(text=f"Kanal {i}", url=f"https://t.me/{chan}")
    else:
        # fallback — kanal yo'q bo'lsa ham tekshirish tugmasi chiqsin
        builder.button(text="ℹ️ Kanal ro‘yxati yo‘q", callback_data="noop")

    builder.button(text="🔄 Tekshirish", callback_data="sub:check")
    builder.adjust(1)
    return builder.as_markup()



def get_feedback_keyboard(req_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    # Stars 1 to 5
    buttons = [
        InlineKeyboardButton(text="⭐", callback_data=f"feed:{req_id}:1"),
        InlineKeyboardButton(text="⭐⭐", callback_data=f"feed:{req_id}:2"),
        InlineKeyboardButton(text="⭐⭐⭐", callback_data=f"feed:{req_id}:3"),
        InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data=f"feed:{req_id}:4"),
        InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data=f"feed:{req_id}:5"),
    ]
    # Chunk into rows: 5 stars top, then 4&3, then 2&1
    kb.row(buttons[4])
    kb.row(buttons[3], buttons[2])
    kb.row(buttons[1], buttons[0])
    return kb.as_markup()
