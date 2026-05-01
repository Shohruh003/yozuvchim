# bot/handlers/modules/payments_flow.py
from __future__ import annotations

import html
import secrets
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery

from ...config import SETTINGS, logger
from ...database import AsyncSessionLocal, Payment, get_all_admin_ids
from ...keyboards import payment_review_kb

router = Router()

# {invoice_id: {admin_id: message_id}} — adminga yuborilgan xabar IDlari
payment_admin_msgs: dict[str, dict[int, int]] = {}

class PaymentWizard(StatesGroup):
    waiting_for_screenshot = State()

@router.message(PaymentWizard.waiting_for_screenshot, F.photo | F.document)
async def process_payment_screenshot(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    
    # Generate unique invoice ID
    invoice_id = secrets.token_hex(8).upper()
    file_id = ""
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id

    async with AsyncSessionLocal() as session:
        pay = Payment(
            user_id=uid,
            invoice_id=invoice_id,
            amount=0, # Will be set by admin
            status="pending",
            screenshot_file_id=file_id
        )
        session.add(pay)
        await session.commit()

    await message.answer(
        "✅ <b>Chek qabul qilindi!</b>\n\n"
        "Adminlarimiz uni tez orada tekshirib, hisobingizni to'ldirishadi.\n"
        f"Kvitansiya ID: <code>#{invoice_id}</code>",
        parse_mode="HTML"
    )

    # Notify Admins — xabar IDlarini saqlab qo'yamiz (keyinchalik edit qilish uchun)
    payment_admin_msgs[invoice_id] = {}
    for adm in get_all_admin_ids():
        try:
            sent = await bot.send_message(
                adm,
                f"💰 <b>Yangi to'lov cheki!</b>\n"
                f"User: <code>{uid}</code>\n"
                f"Invoice: <code>{invoice_id}</code>\n"
                f"Tasdiqlash uchun quyidagi tugmalarni bosing:",
                reply_markup=payment_review_kb(uid, invoice_id),
                parse_mode="HTML"
            )
            payment_admin_msgs[invoice_id][adm] = sent.message_id
            # Forward the actual screenshot
            await message.copy_to(chat_id=adm)
        except Exception as e:
            logger.error(f"Failed to notify admin {adm} about payment: {e}", exc_info=True)

    await state.clear()

@router.message(PaymentWizard.waiting_for_screenshot, F.text)
async def process_payment_non_media_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()

    # /start yoki /cancel — state'ni tozalab, o'tkazib yuborish
    if text.startswith("/"):
        await state.clear()
        # Bu handler xabarni "yutib yuboradi", lekin middleware allaqachon
        # state'ni tozalagan, shuning uchun bu faqat xavfsizlik uchun.
        await message.answer(
            "To'lov bekor qilindi. Qayta boshlash uchun /start bosing.",
        )
        return

    await message.answer("⚠️ Iltimos, to'lov chekini rasm (skrinshot) yoki fayl ko'rinishida yuboring.")


@router.message(PaymentWizard.waiting_for_screenshot)
async def process_payment_non_media(message: Message):
    await message.answer("⚠️ Iltimos, to'lov chekini rasm (skrinshot) yoki fayl ko'rinishida yuboring.")
