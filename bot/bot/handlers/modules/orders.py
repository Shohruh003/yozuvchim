from datetime import datetime
import json
import html
from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, update

from ...config import SETTINGS, logger
from ...database import AsyncSessionLocal, User, Request, DB, is_admin as db_is_admin
from ...keyboards import inline_options, citation_styles_kb, university_kb, MAIN_MENU_BUTTONS
from ...queue_manager import AI_QUEUE

router = Router()

# Menyu tugmalari to'plami — wizard ichida bu matnlar oddiy input sifatida qabul qilinmasligi kerak
_MENU_TEXTS = set(MAIN_MENU_BUTTONS) | {"⚙️ Admin Panel", "⚙️ Admin Menu"}
_NOT_MENU = ~F.text.in_(_MENU_TEXTS)

class DocWizard(StatesGroup):
    authors = State()
    workplace = State()
    email = State()
    language = State()
    title = State()
    university = State()
    major = State()
    subject = State()
    student_name = State()
    advisor = State()
    ppt_style = State()
    ppt_template = State()
    article_level = State()
    citation_style = State()
    udc = State()
    required_languages = State()
    special_requirements = State()
    custom_structure = State()
    length = State()


# Default narxlar — 3 xil format: flat, range, exact
DEFAULT_PRICES = {
    "coursework":  {"1-10": 15000, "11-20": 18000, "21-30": 25000, "31-40": 32000, "41-50": 40000},
    "taqdimot":    {"5": 3000,  "10": 6000,   "15": 10000},
    "article":     {"3": 50000, "5": 80000,   "10": 150000, "15": 250000},
    "independent": {"flat": 5000},
    "thesis":      {"flat": 30000},
}


def _price_format(doc_prices: dict) -> str:
    """Narx formatini aniqlaydi: flat / range / exact."""
    if "flat" in doc_prices:
        return "flat"
    if any("-" in str(k) for k in doc_prices):
        return "range"
    return "exact"


def _calc_price(doc_prices: dict, length: int) -> int | None:
    """Formatga qarab narxni hisoblaydi."""
    fmt = _price_format(doc_prices)
    if fmt == "flat":
        return int(doc_prices["flat"])
    if fmt == "exact":
        val = doc_prices.get(str(length))
        return int(val) if val else None
    # range
    for key, price in doc_prices.items():
        if "-" not in str(key):
            continue
        lo, hi = str(key).split("-", 1)
        if int(lo) <= length <= int(hi):
            return int(price)
    return None


async def get_prices() -> dict:
    """DB dan narxlarni o'qiydi. Topilmasa default qaytaradi."""
    try:
        async with AsyncSessionLocal() as session:
            raw = await DB.get_setting(session, "prices")
            if raw:
                data = json.loads(raw)
                # Eski format tekshiruvi — "per_page"/"base" kalitlari bo'lsa, eskirgan
                for doc_type, dp in data.items():
                    if isinstance(dp, dict) and ("per_page" in dp or "base" in dp):
                        logger.info("Eski narx formati topildi, default ga qaytarilmoqda")
                        await DB.set_setting(session, "prices", json.dumps(DEFAULT_PRICES, ensure_ascii=False))
                        return DEFAULT_PRICES.copy()
                return data
    except Exception as e:
        logger.warning(f"Narxlarni DB dan o'qishda xatolik: {e}")
    return DEFAULT_PRICES.copy()


async def save_prices(prices: dict) -> None:
    """Narxlarni DB ga saqlaydi."""
    async with AsyncSessionLocal() as session:
        await DB.set_setting(session, "prices", json.dumps(prices, ensure_ascii=False))

DOC_TYPE_MAP = {
    "📚 Kurs ishi": "coursework",
    "🎯 Taqdimot": "taqdimot",
    "📄 Maqola": "article",
    "📝 Mustaqil ish": "independent",
    "📌 Tezis": "thesis"
}


@router.message(StateFilter(DocWizard), F.text.in_(_MENU_TEXTS))
async def wiz_menu_button_handler(message: Message, state: FSMContext):
    """Wizard ichida menyu tugmasi bosilsa — rad etadi."""
    data = await state.get_data()
    doc_key = data.get("doc_key", "hujjat")
    await message.answer(
        f"⚠️ <b>Sizda tugallanmagan jarayon bor:</b> {doc_key}\n\n"
        "Avval shu jarayonni yakunlang yoki\n"
        "bekor qilish uchun /start bosing.",
        parse_mode="HTML"
    )


@router.message(StateFilter(DocWizard), ~F.text)
async def wiz_non_text_handler(message: Message):
    """Wizard bosqichlarida matn bo'lmagan xabarlarni rad qiladi."""
    await message.answer(
        "⚠️ Iltimos, faqat <b>matn</b> yuboring.\n"
        "Fayl, rasm yoki stiker qabul qilinmaydi.",
        parse_mode="HTML"
    )


@router.message(F.text.in_(DOC_TYPE_MAP.keys()))
async def start_doc_wiz(message: Message, state: FSMContext):
    await state.clear()
    doc_type = DOC_TYPE_MAP[message.text]
    await state.update_data(doc_key=message.text, doc_type=doc_type)

    # Check for active orders
    async with AsyncSessionLocal() as session:
        active_req = await session.execute(select(Request).where(
            Request.user_id == message.from_user.id,
            Request.status.in_(["queued", "processing"])
        ))
        req = active_req.scalar_one_or_none()
        if req:
            cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Buyurtmani bekor qilish", callback_data=f"cancel_order:{req.id}")]
            ])
            await message.answer(
                "⚠️ <b>Sizda hali yakunlanmagan buyurtma mavjud!</b>\n\n"
                "Kutishni xohlamasangiz, bekor qilishingiz mumkin:",
                parse_mode="HTML",
                reply_markup=cancel_kb
            )
            await state.clear()
            return

    # Maqola va Tezis — avval muallif ma'lumotlari so'raladi
    if doc_type in ('article', 'thesis'):
        await state.set_state(DocWizard.authors)
        await message.answer(
            "👥 <b>Mualliflar F.I.Sh ni kiriting</b>\n"
            "<i>Bir nechta bo'lsa, har birini yangi qatordan yozing.</i>\n\n"
            "Masalan:\n<code>Karimov A.B.\nRahimova D.E.</code>",
            parse_mode="HTML"
        )
        return

    await state.set_state(DocWizard.title)
    await message.answer("📝 Mavzu sarlavhasini yozing:")


# --- Muallif ma'lumotlari (Maqola / Tezis) ---
@router.message(DocWizard.authors, F.text, _NOT_MENU)
async def wiz_authors(message: Message, state: FSMContext):
    await state.update_data(authors=message.text.strip())
    await state.set_state(DocWizard.workplace)
    await message.answer(
        "🏢 <b>Ish/o'qish joyini kiriting</b>\n"
        "<i>Masalan: TDIU, Toshkent shahri</i>",
        parse_mode="HTML"
    )

@router.message(DocWizard.workplace, F.text, _NOT_MENU)
async def wiz_workplace(message: Message, state: FSMContext):
    await state.update_data(workplace=message.text.strip())
    await state.set_state(DocWizard.email)
    await message.answer(
        "📧 <b>Email manzilingizni kiriting</b>\n"
        "<i>Masalan: karimov@mail.uz</i>",
        parse_mode="HTML"
    )

@router.message(DocWizard.email, F.text, _NOT_MENU)
async def wiz_email(message: Message, state: FSMContext):
    await state.update_data(author_email=message.text.strip())
    await state.set_state(DocWizard.title)
    await message.answer("📝 Mavzu sarlavhasini yozing:")


@router.message(DocWizard.title, F.text, _NOT_MENU)
async def wiz_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    data = await state.get_data()

    # Universal Language Selection
    await message.answer(
        "🌐 <b>Tilni tanlang:</b>",
        reply_markup=inline_options([
            ("🇺🇿 O'zbek (Lotin)", "uz_lat"),
            ("🇺🇿 O'zbek (Кирилл)", "uz_cyr"),
            ("🇷🇺 Русский", "ru"),
            ("🇬🇧 English", "en")
        ], "wiz:lang"),
        parse_mode="HTML"
    )




@router.callback_query(F.data.startswith("wiz:lang:"))
async def wiz_lang(cb: CallbackQuery, state: FSMContext):
    lang = cb.data.split(":")[2]
    await state.update_data(lang=lang)
    data = await state.get_data()
    doc_type = data['doc_type']

    # Routing based on Doc Type
    if doc_type == "article":
        await ask_length(cb.message, state, cb.from_user.id)
        await cb.answer()
        return

    # Tezis — tildan keyin to'g'ridan-to'g'ri finish (5 bet avtomatik)
    if doc_type == "thesis":
        await state.update_data(length='5')
        await finish_wiz(cb.message, state, cb.from_user.id)
        await cb.answer()
        return

    # For Coursework, Presentation, Independent
    await state.set_state(DocWizard.university)
    
    # Check if context already exists (for returning users)
    async with AsyncSessionLocal() as session:
        user = await DB.get_user(session, cb.from_user.id)
        if user.academic_context:
            await state.update_data(uni=user.academic_context.get('uni'), major=user.academic_context.get('major'))
            # Skip directly to Subject
            await state.set_state(DocWizard.subject)
            await cb.message.edit_text("📚 <b>Fan nomini</b> kiriting:", parse_mode="HTML")
            return

    await cb.message.edit_text("🎓 Mukammal natija uchun OTM nomini yozing:", parse_mode="HTML")


@router.message(DocWizard.university, F.text, _NOT_MENU)
async def wiz_university(message: Message, state: FSMContext):
    await state.update_data(uni=message.text)
    await state.set_state(DocWizard.major)
    await message.answer("📚 Fakultetingiz yoki yo'nalishingizni yozing:")

@router.message(DocWizard.major, F.text, _NOT_MENU)
async def wiz_major(message: Message, state: FSMContext):
    major = message.text
    data = await state.get_data()
    uni = data.get('uni')
    
    async with AsyncSessionLocal() as session:
        user = await DB.get_user(session, message.from_user.id)
        user.academic_context = {"uni": uni, "major": major}
        await session.commit()
    
    await state.set_state(DocWizard.subject)
    await message.answer("📚 <b>Fan nomini</b> kiriting (bu matn mazmuni uchun muhim):", parse_mode="HTML")

@router.message(DocWizard.subject, F.text, _NOT_MENU)
async def wiz_subject(message: Message, state: FSMContext):
    await state.update_data(subject=message.text)
    
    data = await state.get_data()
    if not data.get('doc_type'):
        # State tozalangan — foydalanuvchi /start bosgan bo'lishi mumkin
        await state.clear()
        return
    if data['doc_type'] == 'taqdimot':
        await state.set_state(DocWizard.ppt_style)
        await message.answer(
            "🎨 <b>Taqdimot uslubini tanlang:</b>",
            reply_markup=inline_options([
                ("🏛 Akademik (Jiddiy)", "akademik"),
                ("💼 Biznes (Zamonaviy)", "biznes"),
                ("🎨 Kreativ (Erkin)", "kreativ")
            ], "wiz:style"),
            parse_mode="HTML"
        )
        return

    # Coursework, Mustaqil ish, Tezis — avval talaba ismini, keyin advisor so'raydi
    await state.set_state(DocWizard.student_name)
    await message.answer("👤 <b>Ismingiz</b> (F.I.Sh):", parse_mode="HTML")

@router.callback_query(F.data.startswith("wiz:art_type:"))
async def wiz_art_type(cb: CallbackQuery, state: FSMContext):
    await state.update_data(article_type=cb.data.split(":")[2])
    # Articles skip advisor/citation style prompts based on user request
    await ask_length(cb.message, state, cb.from_user.id)
    await cb.answer()

@router.callback_query(F.data.startswith("wiz:style:"))
async def wiz_ppt_style(cb: CallbackQuery, state: FSMContext):
    await state.update_data(ppt_style=cb.data.split(":")[2])
    await state.set_state(DocWizard.ppt_template)
    await cb.message.answer(
        "🖼 <b>Slayd fon shablonini tanlang:</b>",
        reply_markup=inline_options([
            ("🔵 Navy (To'q ko'k)", "navy"),
            ("🟢 Green (Yashil)", "green"),
            ("🔴 Burgundy (Qizg'ish)", "burgundy"),
            ("⚫ Charcoal (Tech)", "charcoal"),
            ("🟤 Maroon (Jigarrang)", "maroon"),
        ], "wiz:tpl"),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("wiz:tpl:"))
async def wiz_ppt_template(cb: CallbackQuery, state: FSMContext):
    await state.update_data(ppt_template=cb.data.split(":")[2])
    await ask_length(cb.message, state, cb.from_user.id)
    await cb.answer()

@router.message(DocWizard.student_name, F.text, _NOT_MENU)
async def wiz_student_name(message: Message, state: FSMContext):
    await state.update_data(student_name=message.text)
    await state.set_state(DocWizard.advisor)
    await message.answer("👨‍🏫 <b>Ilmiy rahbaringiz</b> (F.I.Sh):", parse_mode="HTML")

@router.message(DocWizard.advisor, F.text, _NOT_MENU)
async def wiz_advisor(message: Message, state: FSMContext):
    await state.update_data(advisor=message.text)
    data = await state.get_data()

    # Mustaqil ish — iqtibos kerak emas, to'g'ri hajmga o'tadi
    if data.get('doc_type') == 'independent':
        await ask_length(message, state, message.from_user.id)
        return

    await message.answer("📖 Iqtiboslar uslubini tanlang:", reply_markup=citation_styles_kb())

@router.callback_query(F.data.startswith("wiz:cite:"))
async def wiz_cite(cb: CallbackQuery, state: FSMContext):
    await state.update_data(citation_style=cb.data.split(":")[2])
    
    data = await state.get_data()
    if data.get('doc_type') == 'article':
        # Article flow ends here (Length was asked at start)
        await finish_wiz(cb.message, state, cb.from_user.id)
    else:
        # Others flow to Length
        await ask_length(cb.message, state, cb.from_user.id)
    
    await cb.answer()

async def ask_length(message: Message, state: FSMContext, user_id: int = None):
    data = await state.get_data()
    doc_type = data.get('doc_type')
    prices = await get_prices()
    doc_prices = prices.get(doc_type, {})
    fmt = _price_format(doc_prices)

    # Flat — hajm so'ralmasdan to'g'ridan-to'g'ri finish
    if fmt == "flat":
        await state.update_data(length='1')
        uid = user_id or message.chat.id
        await finish_wiz(message, state, uid)
        return

    await state.set_state(DocWizard.length)
    unit = "slayd" if doc_type == "taqdimot" else "bet"

    if fmt == "range":
        # Diapazon tugmalari: "1-10 bet (15,000)"
        opts = []
        for key in sorted(doc_prices.keys(), key=lambda k: int(k.split("-")[0])):
            lo, hi = key.split("-", 1)
            price = int(doc_prices[key])
            label = f"{lo}-{hi} {unit} ({price:,} so'm)"
            opts.append((label, key))
        opts.append(("✏️ Boshqa (qo'lda)", "custom"))
        text = f"📏 Hajmni tanlang ({unit}):"
    else:
        # Exact — aniq betlar tugmasi
        opts = []
        for pages in sorted(doc_prices.keys(), key=lambda k: int(k)):
            price = int(doc_prices[pages])
            label = f"{pages} {unit} ({price:,} so'm)"
            opts.append((label, pages))
        text = "🖼 Slaydlar sonini tanlang:" if doc_type == "taqdimot" else "📏 Hajmi (betlarda):"

    await message.answer(text, reply_markup=inline_options(opts, "wiz:len", cols=1))

@router.callback_query(F.data.startswith("wiz:len:"))
async def wiz_len_callback(cb: CallbackQuery, state: FSMContext):
    raw_length = cb.data.split(":")[2]  # "5", "1-10", yoki "custom"

    # "Boshqa" tugmasi — qo'lda bet soni kiritish
    if raw_length == "custom":
        await state.set_state(DocWizard.length)
        await cb.message.edit_text(
            "✏️ <b>Necha bet yozilsin?</b>\n"
            "<i>Butun son kiriting (masalan: 25)</i>",
            parse_mode="HTML"
        )
        await cb.answer()
        return

    # Range tanlanganda — yuqori chegarani length sifatida saqlash
    if "-" in raw_length:
        length = raw_length.split("-")[1]
    else:
        length = raw_length
    await state.update_data(length=length, length_key=raw_length)
    data = await state.get_data()
    doc_type = data.get('doc_type')

    if doc_type == "article":
        await state.set_state(DocWizard.article_level)
        await cb.message.edit_text(
            "🎓 <b>Maqola darajasini tanlang:</b>",
            reply_markup=inline_options([
                ("🟢 LOCAL_OAK (Milliy)", "LOCAL_OAK"),
                ("🟡 SCOPUS_Q3Q4 (O'rta)", "SCOPUS_Q3Q4"),
                ("🔴 SCOPUS_Q1Q2 (Yuqori)", "SCOPUS_Q1Q2")
            ], "wiz:art_lvl", cols=1),
            parse_mode="HTML"
        )
    else:
        await finish_wiz(cb.message, state, cb.from_user.id)
    await cb.answer()


@router.message(DocWizard.length, F.text, _NOT_MENU)
async def wiz_custom_length(message: Message, state: FSMContext):
    """Qo'lda kiritilgan bet sonini tekshiradi va davom ettiradi."""
    raw = message.text.strip()
    if not raw.isdigit() or int(raw) < 1:
        await message.answer(
            "⚠️ Iltimos, <b>butun son</b> kiriting (masalan: 25)",
            parse_mode="HTML"
        )
        return

    length = int(raw)
    await state.update_data(length=str(length), length_key=str(length))
    data = await state.get_data()
    doc_type = data.get('doc_type')

    if doc_type == "article":
        await state.set_state(DocWizard.article_level)
        await message.answer(
            "🎓 <b>Maqola darajasini tanlang:</b>",
            reply_markup=inline_options([
                ("🟢 LOCAL_OAK (Milliy)", "LOCAL_OAK"),
                ("🟡 SCOPUS_Q3Q4 (O'rta)", "SCOPUS_Q3Q4"),
                ("🔴 SCOPUS_Q1Q2 (Yuqori)", "SCOPUS_Q1Q2")
            ], "wiz:art_lvl", cols=1),
            parse_mode="HTML"
        )
    else:
        await finish_wiz(message, state, message.from_user.id)

@router.callback_query(F.data.startswith("wiz:art_lvl:"))
async def wiz_art_lvl_callback(cb: CallbackQuery, state: FSMContext):
    await state.update_data(article_level=cb.data.split(":")[2])
    await state.set_state(DocWizard.citation_style)
    await cb.message.edit_text(
        "📚 <b>Referens uslubini tanlang:</b>",
        reply_markup=inline_options([
            ("APA 7", "apa7"),
            ("IEEE", "ieee"),
            ("Vancouver (med)", "vancouver")
        ], "wiz:cite"),
        parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(F.data.startswith("wiz:cite:"))
async def wiz_cite_callback(cb: CallbackQuery, state: FSMContext):
    await state.update_data(citation_style=cb.data.split(":")[2])
    
    # Transition to Optional Metadata for Articles
    await state.set_state(DocWizard.udc)
    await cb.message.edit_text(
        "📝 <b>UO'K (UDC) kodini kiriting:</b>\n"
        "<i>(Masalan: 37.013.43). Agar kerak bo'lmasa 'O'tkazib yuborish' tugmasini bosing.</i>",
        reply_markup=inline_options([("⏭ O'tkazib yuborish", "skip_udc")], "wiz:udc"),
        parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(DocWizard.udc, F.data == "wiz:udc:skip_udc")
@router.message(DocWizard.udc, F.text, _NOT_MENU)
async def wiz_udc_handler(event: Message | CallbackQuery, state: FSMContext):
    if isinstance(event, Message):
        await state.update_data(udc=event.text.strip())
        message = event
    else:
        await state.update_data(udc=None)
        message = event.message

    await state.set_state(DocWizard.required_languages)
    await message.answer(
        "🌐 <b>Qo'shimcha tillar (Annotatsiya va Kalit so'zlari uchun):</b>\n"
        "<i>Faqat asosiy til bo'lsa 'O'tkazib yuborish'ni bosing. Agar bir nechta bo'lsa kiriting (masalan: UZ+RU+EN).</i>",
        reply_markup=inline_options([("⏭ O'tkazib yuborish", "skip_req_langs")], "wiz:req_langs"),
        parse_mode="HTML"
    )
    if isinstance(event, CallbackQuery): await event.answer()

@router.callback_query(DocWizard.required_languages, F.data == "wiz:req_langs:skip_req_langs")
@router.message(DocWizard.required_languages, F.text, _NOT_MENU)
async def wiz_req_langs_handler(event: Message | CallbackQuery, state: FSMContext):
    if isinstance(event, Message):
        await state.update_data(required_languages=event.text.strip().upper())
        message = event
    else:
        await state.update_data(required_languages=None)
        message = event.message

    await state.set_state(DocWizard.special_requirements)
    await message.answer(
        "📝 <b>Maxsus talablaringiz bormi?</b>\n"
        "<i>(Masalan: Ma'lum bir metodika bo'yicha yozish, ma'lum bir manbalardan foydalanish). Agar yo'q bo'lsa 'O'tkazib yuborish'ni bosing.</i>",
        reply_markup=inline_options([("⏭ O'tkazib yuborish", "skip_spec")], "wiz:spec"),
        parse_mode="HTML"
    )
    if isinstance(event, CallbackQuery): await event.answer()

@router.callback_query(DocWizard.special_requirements, F.data == "wiz:spec:skip_spec")
@router.message(DocWizard.special_requirements, F.text, _NOT_MENU)
async def wiz_spec_handler(event: Message | CallbackQuery, state: FSMContext):
    if isinstance(event, Message):
        await state.update_data(special_requirements=event.text.strip())
        message = event
    else:
        await state.update_data(special_requirements=None)
        message = event.message

    await state.set_state(DocWizard.custom_structure)
    await message.answer(
        "📋 <b>Tayyor rejangiz bormi?</b>\n"
        "<i>Agar bo'lsa kiriting, aks holda bot o'zi reja tuzadi. Skip uchun 'O'tkazib yuborish'ni bosing.</i>",
        reply_markup=inline_options([("⏭ O'tkazib yuborish", "skip_struct")], "wiz:struct"),
        parse_mode="HTML"
    )
    if isinstance(event, CallbackQuery): await event.answer()

@router.callback_query(DocWizard.custom_structure, F.data == "wiz:struct:skip_struct")
@router.message(DocWizard.custom_structure, F.text, _NOT_MENU)
async def wiz_struct_handler(event: Message | CallbackQuery, state: FSMContext):
    if isinstance(event, Message):
        await state.update_data(custom_structure=event.text.strip())
        message = event
    else:
        await state.update_data(custom_structure=None)
        message = event.message

    await finish_wiz(message, state, event.from_user.id)
    if isinstance(event, CallbackQuery): await event.answer()


async def finish_wiz(message: Message, state: FSMContext, user_id: int):
    data = await state.get_data()
    if 'doc_type' not in data:
        await message.answer("⚠️ Xatolik: Sessiya muddati tugagan. Qaytadan boshlang.")
        await state.clear()
        return

    length = int(data.get('length', 1))
    doc_type = data['doc_type']

    # DB dan narxlarni olish
    prices = await get_prices()

    async with AsyncSessionLocal() as session:
        u = await DB.get_user(session, user_id)

        is_admin = db_is_admin(user_id)

        # Narx hisoblash — flat / range / exact formatga qarab
        doc_prices = prices.get(doc_type, {})
        total_price = _calc_price(doc_prices, length) or 5000

        # Free trial: birinchi marta 10 betgacha bepul (faqat 1 marta)
        FREE_TRIAL_TYPES = ("independent", "coursework", "article", "thesis")
        is_free_trial = False
        if not is_admin and not u.has_used_free_trial and doc_type in FREE_TRIAL_TYPES:
            if doc_type in ("independent", "thesis") or length <= 10:
                is_free_trial = True
                total_price = 0
                u.has_used_free_trial = True

        if not is_admin and not is_free_trial:
            if u.balance < total_price:
                from .payments_flow import PaymentWizard
                text = (
                    f"⚠️ <b>Mablag' yetarli emas!</b>\n\n"
                    f"Mavzu: <code>{html.escape(data.get('title', ''))}</code>\n"
                    f"Hajm: <code>{length} bet</code>\n\n"
                    f"<b>Narxi: {f'{total_price:,}': >10} so'm</b>\n"
                    f"Hisobingiz: {f'{u.balance:,}': >10} so'm\n"
                    f"Yetmayapti: {f'{total_price - u.balance:,}': >10} so'm\n\n"
                    "💳 <b>Hisobni to'ldirish uchun:</b>\n"
                    f"Karta: <code>{html.escape(SETTINGS.card_details)}</code>\n"
                    f"Egasi: <b>{html.escape(SETTINGS.card_holder)}</b>\n\n"
                    "To'lov qilganingizdan so'ng, <b>chekni (skrinshot) shu yerga yuboring</b>.\n"
                    "Admin tasdiqlashi bilan balansingiz to'ldiriladi."
                )
                await message.answer(text, parse_mode="HTML")
                await state.clear()
                await state.set_state(PaymentWizard.waiting_for_screenshot)
                return
            u.balance -= total_price

        if is_free_trial:
            await message.answer(
                "🎉 <b>Birinchi bepul sinov!</b>\n"
                "Bu buyurtma siz uchun bepul. Keyingi buyurtmalar uchun balans to'ldirish kerak bo'ladi.",
                parse_mode="HTML"
            )

        # Preparing Metadata
        title = data.get('title', 'Mavzusiz')
        
        meta = {
            "subject": data.get('subject'),
            "student_name": data.get('student_name'),
            "advisor": data.get('advisor'),
            "uni": data.get('uni'),
            "major": data.get('major'),
            "ppt_style": data.get('ppt_style'),
            "ppt_template": data.get('ppt_template'),
            "article_level": data.get('article_level'),
            "udc": data.get('udc'),
            "required_languages": data.get('required_languages'),
            "authors": data.get('authors'),
            "workplace": data.get('workplace'),
            "author_email": data.get('author_email'),
            "academic_context": u.academic_context # snapshot of user context
        }

        req = Request(
            user_id=user_id, 
            doc_type=doc_type, 
            title=title,
            language=data.get('lang', 'uz'), 
            length=str(length),
            price=total_price,
            citation_style=data.get('citation_style', 'none'),
            requirements_text=data.get('special_requirements', ""),
            custom_structure=data.get('custom_structure', ""),
            status="queued",
            quality_score=0.0,
            meta_json={k: v for k, v in meta.items() if v is not None},
            is_free=is_free_trial,
            is_deleted=False
        )

        session.add(req)
        await session.commit()
    
    try:
        await AI_QUEUE.put(req.id)
        await message.answer(f"🚀 Buyurtma #{req.id} qabul qilindi. Kuting...")
    except Exception as e:
        logger.error(f"Queuing Error for request #{req.id}: {e}")
        async with AsyncSessionLocal() as session:
            await DB.mark_request_error(session, req.id, f"Navbatga qo'shishda xatolik: {str(e)}")
        await message.answer("❌ <b>Tizimda navbat bilan bog'liq xatolik yuz berdi.</b>\n\nIltimos, birozdan so'ng qayta urinib ko'ring yoki adminga murojaat qiling.", parse_mode="HTML")
    
    await state.clear()


@router.callback_query(F.data.startswith("cancel_order:"))
async def cancel_order_cb(cb: CallbackQuery):
    req_id = int(cb.data.split(":")[1])
    async with AsyncSessionLocal() as session:
        req = await DB.get_request(session, req_id)
        if not req or req.user_id != cb.from_user.id:
            await cb.answer("Buyurtma topilmadi.", show_alert=True)
            return
        if req.status not in ("queued", "processing"):
            await cb.answer("Bu buyurtma allaqachon yakunlangan.", show_alert=True)
            return
        req.status = "error"
        req.error_log = "Foydalanuvchi tomonidan bekor qilindi"
        await session.commit()

    # Cancel running task immediately
    from ...worker import cancel_request_task
    cancel_request_task(req_id)

    await cb.message.edit_text("✅ Buyurtma bekor qilindi. Endi yangi buyurtma berishingiz mumkin.", parse_mode="HTML")


