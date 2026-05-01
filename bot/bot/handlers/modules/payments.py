# bot/handlers/modules/payments.py
from __future__ import annotations

import html
import secrets
from contextlib import suppress
from typing import List, Optional

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ...config import SETTINGS, logger
from ...database import AsyncSessionLocal, Ticket

router = Router()

TG_LIMIT = 4096  # Telegram text limit


# -------------------------
# FSM
# -------------------------
class TicketWizard(StatesGroup):
    subject = State()
    message = State()


# -------------------------
# Subjects that open support wizard
# -------------------------
SUPPORT_MANAGED_DOCS = [
    "🎓 Diplom ishi",
    "🔬 Dissertatsiya",
    "📖 O'quv qo'llanma",
    "📝 Imtihonga yordam",
    "💬 Adminga murojaat",
]


# -------------------------
# Helpers
# -------------------------
def _uid(msg: Message) -> Optional[int]:
    return msg.from_user.id if msg.from_user else None


def _safe_text(msg: Message) -> str:
    """
    Ticket uchun matnni xavfsiz olish:
    - text bo'lsa: text
    - caption bo'lsa: caption
    - bo'lmasa: placeholder
    """
    if msg.text and msg.text.strip():
        return msg.text.strip()
    if msg.caption and msg.caption.strip():
        return msg.caption.strip()
    return (
        "(Matn yuborilmadi)\n"
        "Iltimos, xabaringizni matn ko‘rinishida yozing."
    )


def _short(s: str, n: int = 60) -> str:
    s = s or ""
    return (s[: n - 1] + "…") if len(s) > n else s


def _chunk_for_tg(text: str, limit: int = TG_LIMIT) -> List[str]:
    """
    Telegram limitidan oshmasligi uchun bo'laklash.
    HTML parse_mode ishlatilgani uchun taglar bo'linib ketmasin:
    - Biz faqat headerda tag ishlatamiz
    - Body'ni escape qilingan holatda qo'shamiz
    """
    if not text:
        return [""]
    chunks: List[str] = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + limit])
        i += limit
    return chunks


def _admin_ticket_kb(user_id: int, ticket_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✍️ Javob berish", callback_data=f"adm:reply:{user_id}:{ticket_id}")
    b.button(text="✅ Yopish", callback_data=f"adm:close:{user_id}:{ticket_id}")
    b.adjust(2)
    return b.as_markup()


async def _create_ticket_unique_id(max_tries: int = 7) -> str:
    """
    Unique ticket_id yaratish:
    - avval random token
    - collision bo'lsa qayta urinish
    (Asosiy himoya DB unique constraint + IntegrityError)
    """
    for _ in range(max_tries):
        # 8 hex char (token_hex(4) => 8 chars)
        return secrets.token_hex(4).upper()
    return secrets.token_hex(4).upper()


async def _save_ticket(uid: int, subject: str, text: str) -> str:
    """
    Ticketni DBga saqlaydi (collision bo'lsa retry).
    Ticket model: ticket_id UNIQUE bo'lgani uchun IntegrityError bo'lishi mumkin.
    """
    for attempt in range(7):
        tid = await _create_ticket_unique_id()
        try:
            async with AsyncSessionLocal() as session:
                session.add(
                    Ticket(
                        user_id=uid,
                        ticket_id=tid,
                        subject=subject,
                        message=text,
                        status="open",
                    )
                )
                await session.commit()
            return tid
        except IntegrityError:
            logger.warning("Ticket id collision tid=%s attempt=%s", tid, attempt + 1)
            continue
    raise RuntimeError("Ticket ID yaratib bo‘lmadi (collision).")


async def _notify_admins(bot: Bot, uid: int, subject: str, ticket_id: str, raw_text: str, original_msg: Optional[Message] = None) -> None:
    """
    Adminlarga ticket yuborish (uzun bo'lsa chunklab).
    """
    kb = _admin_ticket_kb(uid, ticket_id)

    header = (
        f"📩 <b>Yangi murojaat (#{html.escape(ticket_id)})</b>\n"
        f"User: <code>{html.escape(str(uid))}</code>\n"
        f"Mavzu: <b>{html.escape(subject)}</b>\n"
        f"Status: <code>open</code>\n"
        "— — —\n"
    )
    body = f"Xabar:\n{html.escape(raw_text)}"

    # 1 xabarga kb, qolganiga kb yo'q
    full = header + body
    chunks = _chunk_for_tg(full, TG_LIMIT)

    for adm in getattr(SETTINGS, "admin_ids", []):
        try:
            # Send Header + Text
            await bot.send_message(adm, chunks[0], reply_markup=kb, parse_mode="HTML")
            for c in chunks[1:]:
                await bot.send_message(adm, c, parse_mode="HTML")
            
            # FIXED: Forward original media if exists
            if original_msg:
                # We use copy_to to avoid "Forwarded from..." header if possible, or just copy
                await original_msg.copy_to(chat_id=adm)
        except Exception as e:
            logger.error("Failed to notify admin=%s: %s", adm, e)


# -------------------------
# Start support wizard
# -------------------------
@router.message(F.text.in_(SUPPORT_MANAGED_DOCS))
async def start_support_wiz(message: Message, state: FSMContext) -> None:
    uid = _uid(message)
    if not uid:
        await message.answer("❌ Foydalanuvchi aniqlanmadi. Qayta urinib ko‘ring.")
        return

    subject = (message.text or "Murojaat").strip()
    logger.info("Support wizard started uid=%s subject=%s", uid, subject)

    await state.clear()
    await state.update_data(subject=subject)
    await state.set_state(TicketWizard.message)

    await message.answer(
        f"🛠️ <b>{html.escape(subject)}</b> bo'yicha batafsil yozing.\n\n"
        "✅ Qancha aniq yozsangiz, shuncha tez yechim topiladi.\n"
        "📎 Rasm/skrinsot bo‘lsa — yuboring va izohini MATNda yozing.",
        parse_mode="HTML",
    )


# -------------------------
# Receive ticket message
# -------------------------
@router.message(TicketWizard.message)
async def process_ticket(message: Message, state: FSMContext, bot: Bot) -> None:
    uid = _uid(message)
    if not uid:
        await message.answer("❌ Foydalanuvchi aniqlanmadi. Qayta urinib ko‘ring.")
        await state.clear()
        return

    data = await state.get_data()
    subject = (data.get("subject") or "Murojaat").strip()
    raw_text = _safe_text(message)

    logger.info("Processing ticket uid=%s subject=%s preview=%s", uid, subject, _short(raw_text, 40))

    # DB save
    try:
        ticket_id = await _save_ticket(uid, subject, raw_text)
    except Exception as e:
        logger.exception("Ticket DB save failed uid=%s: %s", uid, e)
        await message.answer(
            "❌ Murojaatni saqlashda xatolik bo‘ldi. Iltimos, qayta urinib ko‘ring."
        )
        await state.clear()
        return

    await message.answer(
        f"✅ Murojaatingiz yuborildi!\n"
        f"🆔 ID: <code>#{html.escape(ticket_id)}</code>\n\n"
        "Tez orada javob beramiz.",
        parse_mode="HTML",
    )

    # Notify admins
    await _notify_admins(bot, uid, subject, ticket_id, raw_text, message)

    await state.clear()


# -------------------------
# Optional: admin close ticket (if you have handler elsewhere you can remove this)
# -------------------------
@router.callback_query(F.data.startswith("adm:close:"))
async def admin_close_ticket(call: CallbackQuery) -> None:
    if not call.from_user:
        return

    if call.from_user.id not in getattr(SETTINGS, "admin_ids", set()):
        await call.answer("Ruxsat yo‘q.", show_alert=True)
        return

    parts = (call.data or "").split(":")
    # adm:close:{uid}:{ticket_id}
    if len(parts) != 4:
        await call.answer("Callback xato.", show_alert=True)
        return

    ticket_id = (parts[3] or "").strip()

    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))
            t = res.scalar_one_or_none()
            if not t:
                await call.answer("Ticket topilmadi.", show_alert=True)
                return
            t.status = "closed"
            await session.commit()

        await call.answer("Yopildi ✅")
        with suppress(Exception):
            await call.message.answer(
                f"✅ Ticket yopildi: <code>#{html.escape(ticket_id)}</code>",
                parse_mode="HTML",
            )
    except Exception as e:
        logger.exception("Close ticket failed tid=%s: %s", ticket_id, e)
        await call.answer("Xatolik.", show_alert=True)
