# bot/handlers/modules/admin.py
from __future__ import annotations

import asyncio
import html
import io
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional
from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message,
    CallbackQuery,
    BufferedInputFile,
    InputMediaPhoto,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func

from ...config import SETTINGS, logger
from ...database import (
    AsyncSessionLocal,
    User,
    Ticket,
    DB,
    Payment,
    Request,
    PromoCode,
    is_admin as db_is_admin,
    is_superadmin as db_is_superadmin,
    get_all_admin_ids,
)
from ...keyboards import admin_panel_kb, user_mgmt_kb

router = Router()

TG_MAX = 4096


# =========================
# State
# =========================
class AdminState(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_reply = State()
    waiting_for_user_search = State()
    waiting_for_bal_amount = State()
    waiting_for_pay_amount = State()
    waiting_for_new_admin_id = State()
    waiting_for_price_value = State()


# =========================
# Helpers
# =========================
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_admin(uid: int) -> bool:
    return db_is_admin(uid)


def _is_superadmin(uid: int) -> bool:
    return db_is_superadmin(uid)


def _chunk(text: str, limit: int = TG_MAX) -> list[str]:
    if not text:
        return [""]
    out = []
    while text:
        out.append(text[:limit])
        text = text[limit:]
    return out


async def _admin_only_msg(message: Message) -> bool:
    uid = message.from_user.id if message.from_user else 0
    if not _is_admin(uid):
        return False
    return True


async def _admin_only_cb(cb: CallbackQuery) -> bool:
    uid = cb.from_user.id if cb.from_user else 0
    if not _is_admin(uid):
        await cb.answer("❌ Ruxsat yo‘q", show_alert=True)
        return False
    return True


async def _send_admin_text(bot: Bot, admin_id: int, text: str, reply_markup=None) -> None:
    """
    Telegram limitidan oshmasin: chunklab yuboradi.
    Birinchi bo‘lakka keyboard qo‘yadi.
    """
    chunks = _chunk(text, TG_MAX)
    await bot.send_message(admin_id, chunks[0], parse_mode="HTML", reply_markup=reply_markup)
    for c in chunks[1:]:
        await bot.send_message(admin_id, c, parse_mode="HTML")


async def _set_setting(session, key: str, value: str) -> None:
    """
    DB.set_setting bor bo‘lsa ishlatadi, bo‘lmasa: jadvalingizga moslab DB ichida yozilgan funksiyani ishlating.
    """
    await DB.set_setting(session, key, value)


async def _get_setting(session, key: str, default: Optional[str] = None) -> Optional[str]:
    try:
        val = await DB.get_setting(session, key)
        return val if val is not None else default
    except Exception:
        return default


# =========================
# Admin Menu
# =========================
@router.message(F.text.in_({"⚙️ Admin Panel", "⚙️ Admin Menu"}))
async def cmd_admin_menu(message: Message) -> None:
    if not await _admin_only_msg(message):
        return
    uid = message.from_user.id if message.from_user else 0
    await message.answer(
        "⚙️ <b>Admin Boshqaruv Paneli</b>",
        reply_markup=admin_panel_kb(_is_superadmin(uid)),
        parse_mode="HTML",
    )


# =========================
# PROMO CODES
# =========================
@router.callback_query(F.data == "adm:promo_menu")
async def cb_admin_promo_menu(cb: CallbackQuery) -> None:
    if not await _admin_only_cb(cb):
        return

    text = (
        "🎁 <b>Promo-kodlar Boshqaruvi</b>\n\n"
        "Yangi kod yaratish:\n"
        "<code>/newpromo KOD SUMMA SANOQ</code>\n"
        "Masalan: <code>/newpromo START2026 5000 100</code>\n\n"
    )

    async with AsyncSessionLocal() as session:
        promos = await session.execute(select(PromoCode).where(PromoCode.uses_left > 0))
        active = promos.scalars().all()
        if active:
            text += "<b>Faol kodlar:</b>\n"
            for p in active:
                text += f"🏷 <code>{html.escape(p.code)}</code>: {int(p.amount):,} so'm ({int(p.uses_left)} ta qoldi)\n"
        else:
            text += "<i>Hozircha faol promo-kod yo‘q.</i>"

    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=admin_panel_kb())
    except TelegramBadRequest:
        pass
    await cb.answer()


@router.message(F.text.startswith("/newpromo"))
async def cmd_new_promo(message: Message) -> None:
    if not await _admin_only_msg(message):
        return

    parts = (message.text or "").split()
    if len(parts) != 4:
        await message.answer("❌ Format: <code>/newpromo CODE SUMMA COUNT</code>", parse_mode="HTML")
        return

    code = parts[1].strip().upper()
    try:
        amount = int(parts[2])
        uses = int(parts[3])
    except ValueError:
        await message.answer("❌ SUMMA va COUNT raqam bo‘lishi kerak.")
        return

    if amount <= 0 or uses <= 0:
        await message.answer("❌ SUMMA va COUNT musbat bo‘lishi kerak.")
        return

    async with AsyncSessionLocal() as session:
        exist = await session.execute(select(PromoCode).where(PromoCode.code == code))
        if exist.scalar_one_or_none():
            await message.answer("❌ Bu promo-kod allaqachon mavjud.")
            return

        pc = PromoCode(code=code, amount=amount, uses_left=uses)
        session.add(pc)
        await session.commit()

    await message.answer(
        f"✅ <b>{html.escape(code)}</b> yaratildi!\n"
        f"Qiymat: <b>{amount:,}</b> so'm\n"
        f"Limit: <b>{uses}</b> ta",
        parse_mode="HTML",
    )


# =========================
# SETTINGS / MAINTENANCE
# =========================
@router.callback_query(F.data == "adm:settings")
async def cb_admin_settings(cb: CallbackQuery) -> None:
    if not await _admin_only_cb(cb):
        return

    async with AsyncSessionLocal() as session:
        m_mode = await _get_setting(session, "maintenance_mode", "off")

    is_on = (str(m_mode).lower() == "on")
    status = "🔴 YOQILGAN" if is_on else "🟢 O'CHIRILGAN"
    action = "off" if is_on else "on"
    btn_text = "🟢 O'chirish" if is_on else "🔴 Yoqish"

    kb = InlineKeyboardBuilder()
    kb.button(text=f"Texnik Xizmat: {btn_text}", callback_data=f"adm:maint:{action}")
    kb.button(text="🔙 Orqaga", callback_data="adm:back")

    try:
        await cb.message.edit_text(
            "🛠 <b>Bot Sozlamalari</b>\n\n"
            f"Texnik Xizmat Rejimi: {status}\n"
            "<i>(Bu rejimda faqat adminlar botdan foydalana oladi)</i>",
            parse_mode="HTML",
            reply_markup=kb.as_markup(),
        )
    except TelegramBadRequest:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("adm:maint:"))
async def cb_admin_maint_toggle(cb: CallbackQuery) -> None:
    if not await _admin_only_cb(cb):
        return

    action = cb.data.split(":")[2].strip().lower()
    if action not in {"on", "off"}:
        await cb.answer("❌ Noto‘g‘ri buyruq", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        await _set_setting(session, "maintenance_mode", action)

    await cb.answer("✅ Sozlama o'zgartirildi!")
    await cb_admin_settings(cb)


@router.callback_query(F.data == "adm:back")
async def cb_admin_back(cb: CallbackQuery) -> None:
    if not await _admin_only_cb(cb):
        return
    # delete fail bo'lsa ham yiqilmasin
    try:
        await cb.message.delete()
    except Exception:
        pass
    uid = cb.from_user.id if cb.from_user else 0
    await cb.message.answer(
        "⚙️ <b>Admin Boshqaruv Paneli</b>",
        reply_markup=admin_panel_kb(_is_superadmin(uid)),
        parse_mode="HTML",
    )
    await cb.answer()


# =========================
# STATS
# =========================
@router.callback_query(F.data == "adm:stats")
async def cb_stats(cb: CallbackQuery, bot: Bot) -> None:
    if not await _admin_only_cb(cb):
        return
    await cb.answer()
    await _send_stats(cb.message, bot)


@router.message(F.text == "📊 Stats")
async def msg_stats(message: Message, bot: Bot) -> None:
    if not await _admin_only_msg(message):
        return
    await _send_stats(message, bot)


async def _send_stats(message: Message, bot: Bot) -> None:
    from PIL import Image, ImageDraw, ImageFont

    sts_msg = await message.answer("🔄 Statistika yuklanmoqda...")

    async with AsyncSessionLocal() as session:
        user_count = (await session.execute(select(func.count(User.id)))).scalar() or 0
        block_count = (
            await session.execute(select(func.count(User.id)).where(User.is_blocked.is_(True)))
        ).scalar() or 0

        now = _now_utc()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)
        month_start = today_start - timedelta(days=30)

        def rev_since(dt: datetime):
            return select(func.sum(Payment.amount)).where(
                Payment.status == "approved",
                Payment.created_at >= dt,
            )

        rev_today = (await session.execute(rev_since(today_start))).scalar() or 0
        rev_week = (await session.execute(rev_since(week_start))).scalar() or 0
        rev_month = (await session.execute(rev_since(month_start))).scalar() or 0
        rev_total = (
            await session.execute(select(func.sum(Payment.amount)).where(Payment.status == "approved"))
        ).scalar() or 0

        # order breakdown
        breakdown = await session.execute(
            select(Request.doc_type, func.count(Request.id)).group_by(Request.doc_type)
        )
        order_stats = breakdown.all()

        # last 7 days chart data
        dates: list[str] = []
        revs_k: list[float] = []
        users_new: list[int] = []

        for i in range(6, -1, -1):
            d = today_start - timedelta(days=i)
            next_d = d + timedelta(days=1)

            day_rev = (
                await session.execute(
                    select(func.sum(Payment.amount)).where(
                        Payment.status == "approved",
                        Payment.created_at >= d,
                        Payment.created_at < next_d,
                    )
                )
            ).scalar() or 0

            day_users = (
                await session.execute(
                    select(func.count(User.id)).where(
                        User.created_at >= d,
                        User.created_at < next_d,
                    )
                )
            ).scalar() or 0

            dates.append(d.strftime("%d.%m"))
            revs_k.append(float(day_rev) / 1000.0)
            users_new.append(int(day_users))

    # --- PIL bilan bar chart ---
    W, H = 800, 500
    bg = (30, 30, 46)
    bar_color = (114, 137, 218)
    line_color = (255, 183, 77)
    text_color = (255, 255, 255)
    grid_color = (60, 60, 80)

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except Exception:
        font = ImageFont.load_default()
        font_title = font
        font_small = font

    draw.text((W // 2 - 150, 15), "Oxirgi 7 kunlik statistika", fill=text_color, font=font_title)

    left, right, top, bottom = 70, W - 70, 60, H - 60
    chart_h = bottom - top
    chart_w = right - left

    for i in range(5):
        y = top + i * (chart_h // 4)
        draw.line([(left, y), (right, y)], fill=grid_color, width=1)

    max_rev = max(revs_k) if max(revs_k) > 0 else 1
    max_users = max(users_new) if max(users_new) > 0 else 1
    bar_gap = chart_w // len(dates)
    bar_w = bar_gap - 12

    for i, (date, rev, users) in enumerate(zip(dates, revs_k, users_new)):
        x = left + i * bar_gap + bar_gap // 2
        bar_h = int((rev / max_rev) * (chart_h - 40)) if max_rev > 0 else 0
        draw.rectangle([x - bar_w // 2, bottom - bar_h, x + bar_w // 2, bottom], fill=bar_color)
        if rev > 0:
            draw.text((x - 10, bottom - bar_h - 18), f"{rev:.0f}k", fill=bar_color, font=font_small)
        draw.text((x - 14, bottom + 8), date, fill=text_color, font=font_small)

    points = []
    for i, users in enumerate(users_new):
        x = left + i * bar_gap + bar_gap // 2
        y = bottom - int((users / max_users) * (chart_h - 40)) if max_users > 0 else bottom
        points.append((x, y))
        draw.ellipse([x - 5, y - 5, x + 5, y + 5], fill=line_color)
        if users > 0:
            draw.text((x - 4, y - 20), str(users), fill=line_color, font=font_small)

    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill=line_color, width=3)

    draw.rectangle([left + 10, top + 5, left + 25, top + 18], fill=bar_color)
    draw.text((left + 30, top + 3), "Tushum (ming so'm)", fill=text_color, font=font_small)
    draw.ellipse([left + 200, top + 8, left + 212, top + 20], fill=line_color)
    draw.text((left + 218, top + 3), "Yangi userlar", fill=text_color, font=font_small)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    # --- PIL bilan pie chart ---
    labels = [str(o[0] or "noma'lum") for o in order_stats]
    sizes = [int(o[1]) for o in order_stats]
    buf_pie: Optional[io.BytesIO] = None

    if sum(sizes) > 0:
        PIE_SIZE = 500
        img2 = Image.new("RGB", (PIE_SIZE, PIE_SIZE), bg)
        draw2 = ImageDraw.Draw(img2)
        draw2.text((PIE_SIZE // 2 - 100, 15), "Buyurtmalar taqsimoti", fill=text_color, font=font_title)

        colors = [
            (114, 137, 218), (255, 183, 77), (67, 181, 129), (240, 71, 71),
            (255, 115, 250), (69, 207, 254), (254, 231, 92), (184, 107, 255),
        ]
        total = sum(sizes)
        cx, cy, r = PIE_SIZE // 2, PIE_SIZE // 2 + 30, 150
        start_angle = 0

        for i, (label, size) in enumerate(zip(labels, sizes)):
            angle = (size / total) * 360
            color = colors[i % len(colors)]
            draw2.pieslice(
                [cx - r, cy - r, cx + r, cy + r],
                start=start_angle, end=start_angle + angle,
                fill=color, outline=bg, width=2,
            )
            ly = PIE_SIZE - 80 + (i // 4) * 20
            lx = 20 + (i % 4) * 120
            pct = size / total * 100
            draw2.rectangle([lx, ly, lx + 10, ly + 10], fill=color)
            draw2.text((lx + 14, ly - 2), f"{label} {pct:.0f}%", fill=text_color, font=font_small)
            start_angle += angle

        buf_pie = io.BytesIO()
        img2.save(buf_pie, format="PNG")
        buf_pie.seek(0)

    text = (
        "📊 <b>Bot Statistikasi</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{int(user_count)}</b> (Blokda: {int(block_count)})\n\n"
        "💰 <b>Moliyaviy ko'rsatkichlar:</b>\n"
        f"Bugun: <b>{int(rev_today):,}</b> so'm\n"
        f"Bu hafta: <b>{int(rev_week):,}</b> so'm\n"
        f"Bu oy: <b>{int(rev_month):,}</b> so'm\n"
        f"Jami: <b>{int(rev_total):,}</b> so'm"
    )

    try:
        await sts_msg.delete()
    except Exception:
        pass

    media = [
        InputMediaPhoto(
            media=BufferedInputFile(buf.read(), filename="stats.png"),
            caption=text,
            parse_mode="HTML",
        )
    ]
    if buf_pie:
        media.append(InputMediaPhoto(media=BufferedInputFile(buf_pie.read(), filename="orders_pie.png")))

    await message.answer_media_group(media=media)


# =========================
# BROADCAST (tarqatish)
# =========================
@router.callback_query(F.data == "adm:broadcast")
async def cb_broadcast(cb: CallbackQuery, state: FSMContext) -> None:
    if not await _admin_only_cb(cb):
        return
    await cb.answer()
    await state.set_state(AdminState.waiting_for_broadcast)
    await cb.message.answer(
        "📢 <b>Xabar tarqatish rejimi</b>\n\n"
        "Xabarni yuboring (matn/rasm/video). Men uni barcha foydalanuvchilarga tarqataman.\n"
        "Bekor qilish: <code>/cancel</code>",
        parse_mode="HTML",
    )


@router.message(F.text == "📢 Xabar tarqatish")
async def msg_broadcast(message: Message, state: FSMContext) -> None:
    if not await _admin_only_msg(message):
        return
    await state.set_state(AdminState.waiting_for_broadcast)
    await message.answer(
        "📢 <b>Xabar tarqatish rejimi</b>\n\n"
        "Xabarni yuboring (matn/rasm/video). Men uni barcha foydalanuvchilarga tarqataman.\n"
        "Bekor qilish: <code>/cancel</code>",
        parse_mode="HTML",
    )


@router.message(AdminState.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot) -> None:
    if not await _admin_only_msg(message):
        return

    if (message.text or "").strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi.")
        return

    await state.clear()
    progress_msg = await message.answer("⏳ Tarqatish boshlandi...")

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(User.id))
        user_ids = list(res.scalars().all())

    # parallel safe sending (semaphore)
    sem = asyncio.Semaphore(15)  # 10-20 atrofida yaxshi
    ok = 0
    fail = 0

    async def _send_one(uid: int) -> None:
        nonlocal ok, fail
        async with sem:
            try:
                await message.copy_to(uid)
                ok += 1
            except Exception:
                fail += 1
            # kichik delay floodni kamaytiradi
            await asyncio.sleep(0.02)

    # batch gather
    tasks = [_send_one(uid) for uid in user_ids]
    # gather in chunks to avoid huge memory spikes
    CHUNK = 500
    for i in range(0, len(tasks), CHUNK):
        await asyncio.gather(*tasks[i : i + CHUNK])

    await progress_msg.edit_text(
        "✅ <b>Tarqatish yakunlandi.</b>\n\n"
        f"✅ Yetib bordi: <b>{ok}</b>\n"
        f"❌ Bloklagan/Xato: <b>{fail}</b>",
        parse_mode="HTML",
    )


# =========================
# BLOCK / UNBLOCK (commands)
# =========================
@router.message(F.text.startswith("/block "))
async def cmd_block(message: Message) -> None:
    if not await _admin_only_msg(message):
        return
    try:
        uid = int(message.text.split(maxsplit=1)[1])
    except Exception:
        await message.answer("❌ Format: /block USER_ID")
        return

    async with AsyncSessionLocal() as session:
        await DB.toggle_block(session, uid, True)

    await message.answer(f"✅ User <code>{html.escape(str(uid))}</code> bloklandi.", parse_mode="HTML")


@router.message(F.text.startswith("/unblock "))
async def cmd_unblock(message: Message) -> None:
    if not await _admin_only_msg(message):
        return
    try:
        uid = int(message.text.split(maxsplit=1)[1])
    except Exception:
        await message.answer("❌ Format: /unblock USER_ID")
        return

    async with AsyncSessionLocal() as session:
        await DB.toggle_block(session, uid, False)

    await message.answer(f"✅ User <code>{html.escape(str(uid))}</code> blokdan chiqarildi.", parse_mode="HTML")


# =========================
# Ticket reply (support)
# =========================
@router.callback_query(F.data.startswith("adm:reply:"))
async def admin_reply_start(cb: CallbackQuery, state: FSMContext) -> None:
    if not await _admin_only_cb(cb):
        return

    # adm:reply:<uid>:<tick_id>
    parts = cb.data.split(":")
    if len(parts) != 4:
        await cb.answer("❌ Noto‘g‘ri callback", show_alert=True)
        return

    uid = parts[2]
    tick_id = parts[3]

    await state.update_data(reply_uid=uid, reply_tick_id=tick_id)
    await state.set_state(AdminState.waiting_for_reply)

    await cb.message.answer(
        f"✍️ User <code>{html.escape(uid)}</code> (Ticket <code>#{html.escape(tick_id)}</code>) uchun javob yozing:",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminState.waiting_for_reply)
async def admin_send_reply(message: Message, state: FSMContext, bot: Bot) -> None:
    if not await _admin_only_msg(message):
        return

    data = await state.get_data()
    try:
        uid = int(str(data.get("reply_uid", "0")))
    except Exception:
        uid = 0
    tick_id = str(data.get("reply_tick_id", "")).strip()

    text = (message.text or "").strip()
    if not text:
        await message.answer("⚠️ Javob matnini yuboring.")
        return

    try:
        await bot.send_message(
            uid,
            "👨‍💻 <b>Admin javobi</b>\n"
            f"Ticket: <code>#{html.escape(tick_id)}</code>\n\n"
            f"{html.escape(text)}",
            parse_mode="HTML",
        )
        await message.answer("✅ Javob yuborildi.")
    except Exception as e:
        await message.answer(f"❌ Yuborishda xato: {html.escape(str(e))}")

    await state.clear()


# =========================
# USER MANAGEMENT
# =========================
@router.callback_query(F.data == "adm:usermgmt")
async def cb_admin_usermgmt_intro(cb: CallbackQuery, state: FSMContext) -> None:
    if not await _admin_only_cb(cb):
        return
    await state.set_state(AdminState.waiting_for_user_search)
    await cb.message.answer("🔍 Qidirilayotgan User ID ni yuboring:")
    await cb.answer()


@router.message(AdminState.waiting_for_user_search)
async def process_user_search(message: Message) -> None:
    if not await _admin_only_msg(message):
        return

    try:
        uid = int((message.text or "").strip())
    except Exception:
        await message.answer("❌ User ID raqam bo‘lishi kerak.")
        return

    async with AsyncSessionLocal() as session:
        u = await DB.get_user(session, uid)
        if not u:
            await message.answer(f"❌ User <code>{html.escape(str(uid))}</code> topilmadi.", parse_mode="HTML")
            return

        created = getattr(u, "created_at", None)
        created_str = created.strftime("%d.%m.%Y %H:%M") if created else "-"

        text = (
            "👤 <b>Foydalanuvchi Ma'lumotlari</b>\n"
            f"🆔 ID: <code>{html.escape(str(u.id))}</code>\n"
            f"👤 Username: @{html.escape(u.username or 'yo‘q')}\n"
            f"✍️ Ism: {html.escape(u.full_name or '-')}\n"
            f"💰 Balans: <b>{int(getattr(u, 'balance', 0)):,}</b> so'm\n"
            f"🚫 Bloklangan: <b>{'Ha' if u.is_blocked else 'Yo‘q'}</b>\n"
            f"📅 Qo'shilgan: {html.escape(created_str)}"
        )
        await message.answer(text, reply_markup=user_mgmt_kb(u.id, u.is_blocked), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm:block:"))
async def cb_admin_block(cb: CallbackQuery) -> None:
    if not await _admin_only_cb(cb):
        return

    parts = cb.data.split(":")
    if len(parts) != 3:
        await cb.answer("❌ Noto‘g‘ri callback", show_alert=True)
        return

    uid = int(parts[2])

    async with AsyncSessionLocal() as session:
        u = await DB.get_user(session, uid)
        if not u:
            await cb.answer("❌ User topilmadi", show_alert=True)
            return
        u.is_blocked = not u.is_blocked
        await session.commit()

    await cb.answer(f"✅ Status o'zgardi: {'Bloklandi' if u.is_blocked else 'Ochildi'}")
    try:
        await cb.message.edit_reply_markup(reply_markup=user_mgmt_kb(u.id, u.is_blocked))
    except Exception:
        pass


# =========================
# BALANCE CHANGE
# =========================
@router.callback_query(F.data.startswith("adm:bal:"))
async def cb_admin_bal_start(cb: CallbackQuery, state: FSMContext) -> None:
    if not await _admin_only_cb(cb):
        return
    uid = cb.data.split(":")[2]
    await state.update_data(target_uid=uid)
    await state.set_state(AdminState.waiting_for_bal_amount)
    await cb.message.answer(
        f"💰 User <code>{html.escape(uid)}</code> uchun balans o'zgarishini yozing:\n"
        "<i>Masalan: 50000 yoki -20000</i>",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminState.waiting_for_bal_amount)
async def process_admin_bal(message: Message, state: FSMContext, bot: Bot) -> None:
    if not await _admin_only_msg(message):
        return

    data = await state.get_data()
    uid = int(str(data.get("target_uid", "0")))

    try:
        # Robust parsing: remove spaces, commas, dots
        clean_text = (message.text or "").strip().replace(" ", "").replace(",", "").replace(".", "")
        amount = int(clean_text)
    except Exception:
        await message.answer("❌ Raqam yuboring (masalan: 50000 yoki -20000).")
        return

    async with AsyncSessionLocal() as session:
        u = await DB.get_user(session, uid)
        if not u:
            await message.answer("❌ User topilmadi")
            await state.clear()
            return

        await DB.update_balance(session, uid, amount)
        # DB.update_balance commit qilishi mumkin; lekin ishonch uchun:
        await session.refresh(u)

    await message.answer(
        f"✅ Balans o'zgartirildi: <b>{amount:+,}</b> so'm.\n"
        f"Yangi balans: <b>{int(u.balance):,}</b> so'm",
        parse_mode="HTML",
    )

    try:
        await bot.send_message(
            uid,
            f"💰 Hisobingiz {amount:+,} so'mga o'zgartirildi.\n"
            f"Hozirgi balans: {int(u.balance):,} so'm",
        )
    except Exception:
        pass

    await state.clear()


# =========================
# PAYMENT APPROVAL
# =========================
@router.callback_query(F.data.startswith("adm:payok:"))
async def cb_payok(call: CallbackQuery, state: FSMContext) -> None:
    if not await _admin_only_cb(call):
        return

    parts = call.data.split(":")
    # adm:payok:{user_id}:{inv}
    if len(parts) != 4:
        await call.answer("Callback xato", show_alert=True)
        return

    uid = parts[2]
    inv = parts[3]

    # Avval to'lov hali pending ekanini tekshir
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(Payment).where(Payment.invoice_id == inv)
        )
        p = res.scalar_one_or_none()
        if not p or p.status != "pending":
            await call.answer("⚠️ Bu to'lov allaqachon ko'rib chiqilgan!", show_alert=True)
            with suppress(Exception):
                await call.message.edit_reply_markup(reply_markup=None)
            return

    await state.update_data(target_uid=uid, inv_id=inv)
    await state.set_state(AdminState.waiting_for_pay_amount)

    await call.message.answer(
        f"💳 User <code>{html.escape(uid)}</code> uchun to'lov summasini kiriting:\n"
        f"(Invoice: <code>{html.escape(inv)}</code>)",
        parse_mode="HTML"
    )
    await call.answer()


@router.message(AdminState.waiting_for_pay_amount)
async def process_payment_amount(message: Message, state: FSMContext, bot: Bot) -> None:
    if not await _admin_only_msg(message):
        return

    data = await state.get_data()
    uid = int(data.get("target_uid", 0))
    inv = data.get("inv_id")

    try:
        # Robust parsing
        clean_text = (message.text or "").strip().replace(" ", "").replace(",", "").replace(".", "")
        amount = int(clean_text)
    except Exception:
        await message.answer("❌ Raqam yuboring (masalan: 50000).")
        return

    if amount <= 0:
        await message.answer("❌ Summa 0 dan baland bo'lishi kerak.")
        return

    async with AsyncSessionLocal() as session:
        # 1. Update user balance
        success = await DB.update_balance(session, uid, amount)
        if not success:
            await message.answer("❌ Foydalanuvchi topilmadi.")
            await state.clear()
            return
        
        # 2. Find and update the SPECIFIC pending payment
        res = await session.execute(
            select(Payment).where(
                Payment.user_id == uid,
                Payment.invoice_id == inv, # FIXED: filter by specific invoice
                Payment.status == "pending"
            )
        )
        p = res.scalar_one_or_none()
        
        if p:
            p.status = "approved"
            p.amount = amount
            await session.commit()

    await message.answer(f"✅ To'lov tasdiqlandi: <b>{amount:,}</b> so'm qo'shildi.", parse_mode="HTML")

    try:
        await bot.send_message(
            uid,
            f"✅ <b>To'lovingiz tasdiqlandi!</b>\n\n"
            f"Hisobingizga <b>{amount:,}</b> so'm qo'shildi.\n"
            f"Hozirgi balansni 👤 Hisobim bo'limida ko'rishingiz mumkin.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    # Boshqa adminlarning eski xabarini edit qilamiz (tugmalarni o'chirib status yozamiz)
    acting_admin = message.from_user.id if message.from_user else 0
    from .payments_flow import payment_admin_msgs
    admin_msgs = payment_admin_msgs.pop(inv, {})
    for adm, msg_id in admin_msgs.items():
        if adm != acting_admin:
            with suppress(Exception):
                await bot.edit_message_text(
                    chat_id=adm,
                    message_id=msg_id,
                    text=f"💰 <b>To'lov cheki</b>\n"
                         f"User: <code>{html.escape(str(uid))}</code>\n"
                         f"Invoice: <code>{html.escape(inv)}</code>\n\n"
                         f"✅ <b>Tasdiqlandi</b> — {amount:,} so'm\n"
                         f"Admin <code>{acting_admin}</code> tomonidan ko'rib chiqildi.",
                    parse_mode="HTML"
                )

    await state.clear()


@router.callback_query(F.data.startswith("adm:payno:"))
async def cb_payno(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not await _admin_only_cb(call):
        return

    parts = call.data.split(":")
    # adm:payno:{user_id}:{inv}
    uid = int(parts[2])
    inv = parts[3]

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(Payment).where(
                Payment.user_id == uid,
                Payment.invoice_id == inv, # FIXED: Filter by specific invoice
                Payment.status == "pending"
            )
        )
        p = res.scalar_one_or_none()
        if p:
            p.status = "rejected"
            await session.commit()

    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"❌ To'lov rad etildi (User: {uid}).")

    try:
        await bot.send_message(uid, "❌ <b>To'lovingiz rad etildi.</b>\n\nIltimos, chekni to'g'ri yuborganingizni tekshiring yoki adminga murojaat qiling.", parse_mode="HTML")
    except Exception:
        pass

    # Boshqa adminlarning eski xabarini edit qilamiz
    acting_admin = call.from_user.id if call.from_user else 0
    from .payments_flow import payment_admin_msgs
    admin_msgs = payment_admin_msgs.pop(inv, {})
    for adm, msg_id in admin_msgs.items():
        if adm != acting_admin:
            with suppress(Exception):
                await bot.edit_message_text(
                    chat_id=adm,
                    message_id=msg_id,
                    text=f"💰 <b>To'lov cheki</b>\n"
                         f"User: <code>{html.escape(str(uid))}</code>\n"
                         f"Invoice: <code>{html.escape(inv)}</code>\n\n"
                         f"❌ <b>Rad etildi</b>\n"
                         f"Admin <code>{acting_admin}</code> tomonidan ko'rib chiqildi.",
                    parse_mode="HTML"
                )

    await call.answer()


# =========================
# PENDING PAYMENTS
# =========================
@router.callback_query(F.data.startswith("adm:pending"))
async def cb_admin_pending_payments(cb: CallbackQuery, bot: Bot) -> None:
    if not await _admin_only_cb(cb):
        return
    
    parts = cb.data.split(":")
    offset = int(parts[2]) if len(parts) > 2 else 0
    limit = 5 # Show 5 at a time
    
    async with AsyncSessionLocal() as session:
        # Get total count
        count_res = await session.execute(select(func.count(Payment.user_id)).where(Payment.status == "pending"))
        total = count_res.scalar() or 0
        
        # Get slice
        res = await session.execute(
            select(Payment).where(Payment.status == "pending")
            .order_by(Payment.created_at.desc())
            .offset(offset).limit(limit)
        )
        pending = res.scalars().all()

    if not pending and offset == 0:
        await cb.answer("✅ Kutilayotgan to'lovlar yo'q.", show_alert=True)
        return

    # Delete original menu message to avoid clutter
    with suppress(Exception):
        await cb.message.delete()

    await cb.message.answer(
        f"⏳ <b>Kutilayotgan to'lovlar ({offset+1}-{offset+len(pending)} / {total}):</b>", 
        parse_mode="HTML"
    )
    
    from ...keyboards import payment_review_kb
    for p in pending:
        text = (
            f"💰 <b>To'lov kvitansiyasi</b>\n"
            f"User: <code>{p.user_id}</code>\n"
            f"Invoice: <code>{p.invoice_id}</code>\n"
            f"Sana: {p.created_at.strftime('%d.%m.%Y %H:%M')}"
        )
        try:
            if p.screenshot_file_id:
                await bot.send_photo(
                    cb.from_user.id, p.screenshot_file_id,
                    caption=text, reply_markup=payment_review_kb(p.user_id, p.invoice_id),
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    cb.from_user.id, text,
                    reply_markup=payment_review_kb(p.user_id, p.invoice_id),
                    parse_mode="HTML"
                )
        except Exception:
            pass

    # Navigation buttons
    kb = InlineKeyboardBuilder()
    if offset + limit < total:
        kb.button(text="➡️ Keyingi 5 ta", callback_data=f"adm:pending:{offset + limit}")
    if offset > 0:
        kb.button(text="⬅️ Oldingi 5 ta", callback_data=f"adm:pending:{max(0, offset - limit)}")
    
    kb.button(text="🔙 Admin Panel", callback_data="adm:back")
    kb.adjust(2)
    
    await cb.message.answer("Boshqaruv:", reply_markup=kb.as_markup())
    await cb.answer()


# =========================
# ADMIN MANAGEMENT (Superadmin only)
# =========================
async def _superadmin_only_cb(cb: CallbackQuery) -> bool:
    uid = cb.from_user.id if cb.from_user else 0
    if not _is_superadmin(uid):
        await cb.answer("❌ Faqat superadmin uchun", show_alert=True)
        return False
    return True


@router.callback_query(F.data == "adm:admins")
async def cb_admin_list(cb: CallbackQuery) -> None:
    if not await _superadmin_only_cb(cb):
        return

    async with AsyncSessionLocal() as session:
        db_admins = await DB.list_admins(session)

    text = "👥 <b>Adminlar boshqaruvi</b>\n\n"
    text += "👑 <b>Superadminlar (.env):</b>\n"
    for sid in SETTINGS.admin_ids:
        text += f"  • <code>{sid}</code> (o'chirib bo'lmaydi)\n"

    if db_admins:
        text += "\n🛡 <b>Qo'shilgan adminlar:</b>\n"
        for u in db_admins:
            name = u.full_name or u.username or str(u.id)
            text += f"  • <code>{u.id}</code> — {html.escape(name)}\n"
    else:
        text += "\n<i>Qo'shimcha admin hali qo'shilmagan.</i>\n"

    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Admin qo'shish", callback_data="adm:admins:add")
    if db_admins:
        for u in db_admins:
            name = u.full_name or u.username or str(u.id)
            kb.button(
                text=f"🗑 {html.escape(name)[:20]}",
                callback_data=f"adm:admins:rm:{u.id}",
            )
    kb.button(text="🔙 Orqaga", callback_data="adm:back")
    kb.adjust(1)

    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    except TelegramBadRequest:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data == "adm:admins:add")
async def cb_admin_add_start(cb: CallbackQuery, state: FSMContext) -> None:
    if not await _superadmin_only_cb(cb):
        return
    await state.set_state(AdminState.waiting_for_new_admin_id)
    await cb.message.answer(
        "➕ Yangi adminning <b>Telegram ID</b> sini yuboring:\n"
        "<i>(User oldin botga /start bosgan bo'lishi kerak)</i>",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminState.waiting_for_new_admin_id)
async def process_new_admin_id(message: Message, state: FSMContext) -> None:
    uid = message.from_user.id if message.from_user else 0
    if not _is_superadmin(uid):
        await state.clear()
        return

    try:
        new_admin_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ Telegram ID raqam bo'lishi kerak.")
        return

    if _is_admin(new_admin_id):
        await message.answer("⚠️ Bu foydalanuvchi allaqachon admin.")
        await state.clear()
        return

    try:
        async with AsyncSessionLocal() as session:
            await DB.add_admin(session, new_admin_id)
    except ValueError as e:
        await message.answer(f"❌ {e}")
        await state.clear()
        return

    await message.answer(
        f"✅ <b>Yangi admin qo'shildi!</b>\n"
        f"ID: <code>{new_admin_id}</code>",
        parse_mode="HTML",
    )
    await state.clear()


@router.callback_query(F.data.startswith("adm:admins:rm:"))
async def cb_admin_remove(cb: CallbackQuery) -> None:
    if not await _superadmin_only_cb(cb):
        return

    parts = cb.data.split(":")
    try:
        target_id = int(parts[3])
    except (IndexError, ValueError):
        await cb.answer("❌ Noto'g'ri ID", show_alert=True)
        return

    if _is_superadmin(target_id):
        await cb.answer("❌ Superadminni o'chirib bo'lmaydi!", show_alert=True)
        return

    try:
        async with AsyncSessionLocal() as session:
            await DB.remove_admin(session, target_id)
    except ValueError as e:
        await cb.answer(str(e), show_alert=True)
        return

    await cb.answer("✅ Admin o'chirildi!")
    # Refresh the list
    await cb_admin_list(cb)


# =========================
# PRICE MANAGEMENT
# =========================
_DOC_TYPE_LABELS = {
    "coursework": "📚 Kurs ishi",
    "taqdimot": "🎯 Taqdimot",
    "article": "📄 Maqola",
    "independent": "📝 Mustaqil ish",
    "thesis": "📌 Tezis",
}


def _sort_price_keys(keys):
    """Narx kalitlarini to'g'ri tartibda saralaydi (flat, range, exact)."""
    def sort_key(k):
        if k == "flat":
            return 0
        if "-" in str(k):
            return int(str(k).split("-")[0])
        try:
            return int(str(k).split()[0])
        except (ValueError, IndexError):
            return 0
    return sorted(keys, key=sort_key)


def _format_price_display(dp: dict, unit: str = "bet") -> str:
    """Narxlarni formatga qarab chiroyli ko'rsatadi."""
    from .orders import _price_format
    fmt = _price_format(dp)
    lines = []
    if fmt == "flat":
        lines.append(f"  Yagona narx: {int(dp['flat']):,} so'm")
    elif fmt == "range":
        for k in _sort_price_keys(dp.keys()):
            lines.append(f"  {k} {unit} = {int(dp[k]):,} so'm")
    else:
        for k in _sort_price_keys(dp.keys()):
            lines.append(f"  {k} {unit} = {int(dp[k]):,} so'm")
    return "\n".join(lines)


@router.callback_query(F.data == "adm:prices")
async def cb_admin_prices(cb: CallbackQuery) -> None:
    if not await _admin_only_cb(cb):
        return

    from .orders import get_prices
    prices = await get_prices()
    bet_label = {"taqdimot": "slayd"}

    text = "💰 <b>Narxlar Boshqaruvi</b>\n\n"
    for doc_type, label in _DOC_TYPE_LABELS.items():
        dp = prices.get(doc_type, {})
        unit = bet_label.get(doc_type, "bet")
        text += f"<b>{label}:</b>\n"
        text += _format_price_display(dp, unit)
        text += "\n\n"

    text += "O'zgartirish uchun tur tanlang:"

    kb = InlineKeyboardBuilder()
    for doc_type, label in _DOC_TYPE_LABELS.items():
        kb.button(text=label, callback_data=f"adm:price_edit:{doc_type}")
    kb.button(text="🔙 Orqaga", callback_data="adm:back")
    kb.adjust(2)

    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    except TelegramBadRequest:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("adm:price_edit:"))
async def cb_admin_price_edit(cb: CallbackQuery, state: FSMContext) -> None:
    if not await _admin_only_cb(cb):
        return

    doc_type = cb.data.split(":")[2]
    label = _DOC_TYPE_LABELS.get(doc_type, doc_type)
    unit = {"taqdimot": "slayd"}.get(doc_type, "bet")

    from .orders import get_prices
    prices = await get_prices()
    dp = prices.get(doc_type, {})

    text = f"💰 <b>{label} narxini o'zgartirish</b>\n\n"
    text += "Hozirgi narxlar:\n"
    text += _format_price_display(dp, unit)

    text += (
        "\n\n<b>Yangi narxlarni yozing:</b>\n\n"
        "📌 <b>Yagona narx:</b>\n"
        "<code>flat=30000</code>\n\n"
        "📏 <b>Diapazon:</b>\n"
        "<code>1-10=15000\n11-20=18000\n21-30=25000</code>\n\n"
        "🔢 <b>Aniq bet:</b>\n"
        "<code>3=5000\n5=7000\n10=12000</code>\n\n"
        "<i>Yangi format yozsangiz, eski narxlar o'chib yangilanadi.</i>"
    )

    await state.update_data(price_doc_type=doc_type)
    await state.set_state(AdminState.waiting_for_price_value)
    await cb.message.answer(text, parse_mode="HTML")
    await cb.answer()


@router.message(AdminState.waiting_for_price_value)
async def process_price_update(message: Message, state: FSMContext) -> None:
    if not await _admin_only_msg(message):
        return

    data = await state.get_data()
    doc_type = data.get("price_doc_type")
    if not doc_type:
        await message.answer("❌ Xatolik. Qaytadan urinib ko'ring.")
        await state.clear()
        return

    from .orders import get_prices, save_prices

    raw = (message.text or "").strip()
    if not raw:
        await message.answer("❌ Bo'sh xabar. Narxni yozing.")
        return

    # Parse: "flat=30000", "1-10=15000", "3=5000" formatlarni qabul qiladi
    updated = {}
    for line in raw.splitlines():
        line = line.strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip().lower()
        val = val.strip().replace(" ", "").replace(",", "")
        try:
            updated[key] = int(val)
        except ValueError:
            await message.answer(f"❌ '{key}={val}' — noto'g'ri raqam.")
            return

    if not updated:
        await message.answer("❌ Format: <code>flat=30000</code> yoki <code>5=7000</code>", parse_mode="HTML")
        return

    # Yangi format yuborilsa — butunlay almashtiradi (eski kalitlar o'chiriladi)
    prices = await get_prices()
    prices[doc_type] = updated
    await save_prices(prices)

    label = _DOC_TYPE_LABELS.get(doc_type, doc_type)
    unit = {"taqdimot": "slayd"}.get(doc_type, "bet")
    await message.answer(
        f"✅ <b>{label}</b> narxlari yangilandi!\n\n"
        f"{_format_price_display(updated, unit)}",
        parse_mode="HTML",
    )
    await state.clear()
