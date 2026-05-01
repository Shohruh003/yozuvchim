from __future__ import annotations

import html
import secrets
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ...config import SETTINGS, logger
from ...database import AsyncSessionLocal, Ticket, get_all_admin_ids

router = Router()


class TicketWizard(StatesGroup):
    message = State()


SUPPORT_MANAGED_DOCS = [
    "🎓 Diplom ishi",
    "🔬 Dissertatsiya",
    "📖 O'quv qo'llanma",
    "📝 Imtihonga yordam",
    "💬 Adminga murojaat",
]


TG_MAX = 4096  # Telegram message text limit


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
    return "(Matn yuborilmadi. Iltimos, xabaringizni matn ko‘rinishida yozing.)"


def _short(s: str, n: int = 60) -> str:
    s = s or ""
    return (s[: n - 1] + "…") if len(s) > n else s


def _chunk_for_tg(text: str, limit: int = TG_MAX) -> list[str]:
    """
    Telegram limitidan oshmasligi uchun matnni bo'laklash.
    (oddiy split; xohlasangiz keyinroq paragraph bo'yicha ham qilamiz)
    """
    if not text:
        return [""]
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


@router.message(F.text.in_(SUPPORT_MANAGED_DOCS))
async def start_support_wiz(message: Message, state: FSMContext) -> None:
    uid = message.from_user.id if message.from_user else 0
    logger.info("Support wizard started uid=%s subject=%s", uid, message.text)

    await state.clear()
    await state.update_data(subject=message.text or "Murojaat")
    await state.set_state(TicketWizard.message)

    await message.answer(
        f"🛠️ <b>{html.escape(message.text or '')}</b> bo'yicha batafsil yozing.\n"
        "Admin tez orada javob beradi.",
        parse_mode="HTML",
    )


@router.message(TicketWizard.message)
async def process_ticket(message: Message, state: FSMContext, bot: Bot) -> None:
    uid = message.from_user.id if message.from_user else 0
    raw_text = _safe_text(message)

    logger.info("Processing ticket uid=%s preview=%s", uid, _short(raw_text, 30))

    data = await state.get_data()
    subject = (data.get("subject") or "Murojaat").strip()

    # 6 ta belgili token, collision juda past; xohlasangiz 8 qiling
    tick_id = secrets.token_hex(3).upper()  # 6 hex chars

    # DB save
    try:
        async with AsyncSessionLocal() as session:
            ticket = Ticket(
                user_id=uid,
                ticket_id=tick_id,
                subject=subject,
                message=raw_text,
                status="open",
            )
            session.add(ticket)
            await session.commit()
    except Exception as e:
        logger.exception("Ticket DB save failed uid=%s: %s", uid, e)
        await message.answer(
            "❌ Murojaatni saqlashda xatolik bo‘ldi. Iltimos qayta urinib ko‘ring.",
        )
        await state.clear()
        return

    await message.answer(
        f"✅ Murojaatingiz yuborildi! ID: <code>#{html.escape(tick_id)}</code>.\n"
        "Tez orada javob beramiz.",
        parse_mode="HTML",
    )

    # Admin notify (callback data qisqa bo'lsin)
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(text="✍️ Javob berish", callback_data=f"adm:reply:{uid}:{tick_id}")
    kb = kb_builder.as_markup()

    admin_text = (
        f"📩 <b>Yangi Murojaat (#{html.escape(tick_id)})</b>\n"
        f"User: <code>{html.escape(str(uid))}</code>\n"
        f"Mavzu: {html.escape(subject)}\n\n"
        f"Xabar:\n{html.escape(raw_text)}"
    )

    # Telegram 4096 limit -> chunklab yuboramiz
    for adm in get_all_admin_ids():
        try:
            chunks = _chunk_for_tg(admin_text, TG_MAX)
            # birinchi xabarga keyboard qo'yamiz, qolganlariga qo'ymaymiz
            await bot.send_message(adm, chunks[0], reply_markup=kb, parse_mode="HTML")
            for c in chunks[1:]:
                await bot.send_message(adm, c, parse_mode="HTML")
        except Exception as e:
            logger.error("Failed to notify admin=%s: %s", adm, e)

    await state.clear()
