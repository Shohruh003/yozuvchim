from datetime import datetime
import html
import os
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.exceptions import TelegramBadRequest

from ...config import SETTINGS, logger
from ...database import AsyncSessionLocal, User, DB, Request, is_admin as db_is_admin, get_all_admin_ids
from ...keyboards import main_menu_kb, sub_check_kb
from sqlalchemy import select

router = Router()



async def is_subscribed(bot: Bot, user_id: int) -> bool:
    if not SETTINGS.required_channels:
        return True
    try:
        for ch in SETTINGS.required_channels:
            member = await bot.get_chat_member(ch, user_id)
            if member.status in ("left", "kicked"):
                return False
        return True
    except Exception as e:
        logger.warning("Channel membership check failed for user %s: %s", user_id, e)
        return False

# NOTE: cmd_start is registered on the PARENT router in __init__.py for highest priority
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    
    is_admin = db_is_admin(message.from_user.id)
    
    async with AsyncSessionLocal() as session:
        user = await DB.get_user(session, message.from_user.id)
        
        if not user:
            user = User(id=message.from_user.id, full_name=message.from_user.full_name, username=message.from_user.username)
            if referrer_id and referrer_id != message.from_user.id:
                user.referred_by_id = referrer_id
                # Update referrer's balance AND count
                await DB.update_balance(session, referrer_id, 1000)
                # FIXED: Increment referral count
                referrer = await DB.get_user(session, referrer_id)
                if referrer:
                    referrer.referral_count += 1
                try:
                    await bot.send_message(
                        referrer_id, 
                        f"🎁 <b>Yangi hamkor!</b>\n"
                        f"Do'stingiz <code>{html.escape(message.from_user.full_name)}</code> qo'shildi.\n"
                        f"Hisobingizga <b>1,000 so'm</b> qo'shildi.",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning("Failed to notify referrer %s: %s", referrer_id, e)
            session.add(user)
            await session.commit()

        # Maintenance Check
        if not is_admin:
            m_mode = await DB.get_setting(session, "maintenance_mode")
            if m_mode == "on":
                await message.answer("🛠 <b>Botda texnik ishlar olib borilmoqda.</b>\n\nIltimos, birozdan so'ng urinib ko'ring.", parse_mode="HTML")
                return

    
    if not is_admin:
        if user and user.is_blocked:
            await message.answer("❌ Siz botdan foydalanishdan chetlatilgansiz.")
            return

        if not await is_subscribed(bot, message.from_user.id):
            await message.answer("⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:", 
                                 reply_markup=sub_check_kb(SETTINGS.required_channels))
            return

    welcome_text = "Assalomu alaykum! Akademik botga xush kelibsiz."
    if user and user.academic_context:
        ctx = user.academic_context
        welcome_text += f"\n\n🎓 <b>Sizning ma'lumotlaringiz:</b>\nOTM: {html.escape(ctx.get('uni', '-'))}\nYo'nalish: {html.escape(ctx.get('major', '-'))}"
    
    welcome_text += "\n\nQuyidagi tugmalardan birini tanlang:"

    from ...login_tokens import make_token
    web_token = await make_token(message.from_user.id)
    await message.answer(
        welcome_text,
        reply_markup=main_menu_kb(is_admin, user_id=message.from_user.id, web_app_token=web_token),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "sub:check")
async def callback_sub_check(cb: CallbackQuery, bot: Bot):
    if await is_subscribed(bot, cb.from_user.id):
        try:
            await cb.message.edit_text("✅ Rahmat! Barchasi joyida. Menu tanlang:")
        except TelegramBadRequest:
            pass
        from ...login_tokens import make_token
        web_token = await make_token(cb.from_user.id)
        await cb.message.answer(
            "Asosiy menu:",
            reply_markup=main_menu_kb(db_is_admin(cb.from_user.id), user_id=cb.from_user.id, web_app_token=web_token),
        )
    else:
        await cb.answer("❌ Hali ham hamma kanallarga a'zo emassiz!", show_alert=True)



@router.message(F.text == "🎁 Taklifnoma")
async def cmd_referrals(message: Message, bot: Bot):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    async with AsyncSessionLocal() as session:
        u = await DB.get_user(session, message.from_user.id)
        
        # Gamification Logic
        count = u.referral_count
        earnings = count * 1000
        
        rank = "🌱 Yangi a'zo"
        next_goal = 5
        if count >= 5: rank, next_goal = "🥉 Faol", 20
        if count >= 20: rank, next_goal = "🥈 Lider", 50
        if count >= 50: rank, next_goal = "🥇 Elchi", 100
        if count >= 100: rank, next_goal = "👑 Legend", 1000
        
        # Simple progress bar
        progress = min(count / next_goal, 1.0)
        filled = int(progress * 10)
        bar = "🟩" * filled + "⬜️" * (10 - filled)
        
        text = (
            "🎁 <b>Hamkorlik Dasturi</b>\n\n"
            f"🔗 <b>Sizning havolangiz:</b>\n<code>{html.escape(link)}</code>\n\n"
            f"📊 <b>Statistika:</b>\n"
            f"👥 Do'stlar: <b>{count} ta</b>\n"
            f"💰 Daromad: <b>{html.escape(f'{earnings:,}')} so'm</b>\n"
            f"🏆 Unvon: <b>{rank}</b>\n\n"
            f"🎯 <b>Keyingi maqsad ({next_goal} ta):</b>\n"
            f"{bar} {int(progress * 100)}%\n\n"
            "Har bir taklif uchun <b>1,000 so'm</b> oling!"
        )
        await message.answer(text, parse_mode="HTML")

@router.message(F.text == "📝 Narxlar")
async def cmd_prices(message: Message):
    from .orders import get_prices, _price_format

    prices = await get_prices()

    labels = {
        "coursework": "📚 Kurs ishi",
        "taqdimot": "🎯 Taqdimot",
        "article": "📄 Maqola",
        "independent": "📝 Mustaqil ish",
        "thesis": "📌 Tezis",
    }
    bet_label = {"taqdimot": "slayd"}

    text = "📊 <b>Xizmatlar Narxlari</b>\n\n"
    for doc_type, label in labels.items():
        dp = prices.get(doc_type, {})
        unit = bet_label.get(doc_type, "bet")
        fmt = _price_format(dp)
        text += f"<b>{label}:</b>\n"

        if fmt == "flat":
            text += f"  <b>{int(dp['flat']):,}</b> so'm\n"
        elif fmt == "range":
            for k in sorted(dp.keys(), key=lambda x: int(x.split("-")[0])):
                text += f"  {k} {unit} — <b>{int(dp[k]):,}</b> so'm\n"
        else:
            def _sort_key(x):
                try:
                    return int(x.split()[0])
                except (ValueError, IndexError):
                    return 0
            for k in sorted(dp.keys(), key=_sort_key):
                text += f"  {k} {unit} — <b>{int(dp[k]):,}</b> so'm\n"
        text += "\n"

    text += "<i>Boshqa xizmatlar (Diplom, Dissertatsiya) kelishuv asosida.</i>"
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "👤 Hisobim")
async def cmd_me(message: Message):
    async with AsyncSessionLocal() as session:
        u = await DB.get_user(session, message.from_user.id)

        text = (
            f"👤 <b>Profilingiz</b>\n"
            f"🆔 ID: <code>{html.escape(str(u.id))}</code>\n"
            f"💰 Balans: {html.escape(f'{u.balance:,}')} {html.escape(SETTINGS.currency)}\n"
            f"🎁 Takliflar: {html.escape(str(u.referral_count))}\n\n"
            f"💳 <b>Hisobni to'ldirish uchun «💳 To'lov» tugmasini bosing</b>\n"
        )
        await message.answer(text, parse_mode="HTML")

@router.message(F.text == "💳 To'lov")
async def cmd_payment(message: Message, state: FSMContext):
    current = await state.get_state()
    if current:
        await state.clear()
    from .payments_flow import PaymentWizard
    await state.set_state(PaymentWizard.waiting_for_screenshot)
    text = (
        "💳 <b>Hisobni to'ldirish</b>\n\n"
        f"Karta raqam: <code>{html.escape(SETTINGS.card_details)}</code>\n"
        f"Egasining ismi: <b>{html.escape(SETTINGS.card_holder)}</b>\n\n"
        "To'lov qilganingizdan so'ng, chekni (skrinshot) shu yerga yuboring.\n"
        "Adminlar tasdiqlagach, balansingiz to'ldiriladi."
    )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text.startswith("/promo "))
async def cmd_use_promo(message: Message):
    try:
        code = message.text.split()[1].upper()
    except IndexError:
        await message.answer("⚠️ Format: /promo KOD")
        return
    
    from ...database import PromoCode
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        # Check promo
        res = await session.execute(select(PromoCode).where(PromoCode.code == code))
        pc = res.scalar_one_or_none()
        
        if not pc:
            await message.answer("❌ Promokod topilmadi.")
            return
            
        if pc.uses_left <= 0:
            await message.answer("❌ Promokod muddati tugagan.")
            return

        # Decrement and Add Balance
        pc.uses_left -= 1
        await DB.update_balance(session, message.from_user.id, pc.amount)
        
        await message.answer(f"✅ <b>Tabriklaymiz!</b>\n\nSizga {pc.amount} so'm bonus berildi.", parse_mode="HTML")

@router.message()
async def catch_all(message: Message):
    """Catch-all: noma'lum xabarlarni menu tanlashga yo'naltiradi."""
    # Ignore if in specific states (wizards handle those)
    # Ignore bots
    if message.from_user and message.from_user.is_bot:
        return

    from ...login_tokens import make_token
    web_token = await make_token(message.from_user.id)
    await message.answer(
        "Iltimos, quyidagi tugmalardan birini tanlang:",
        reply_markup=main_menu_kb(
            db_is_admin(message.from_user.id),
            user_id=message.from_user.id,
            web_app_token=web_token,
        ),
    )
