from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Tuple
from contextlib import suppress

import aiohttp

from ..config import SETTINGS, logger
from .validation_utils import (
    validate_word_count,
    detect_hallucinated_data,
    validate_references,
    get_word_range_for_pages
)


class AIServiceError(RuntimeError):
    """Raised when AI provider returns an error or unexpected response."""


@dataclass(frozen=True, slots=True)
class AIConfig:
    base_url: str
    api_key: str
    model: str
    timeout_sec: int = 240
    max_retries: int = 2
    backoff_sec: int = 2
    max_tokens: int = 8000


def _env_bool(v: str, default: bool = False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


class AIService:
    """
    Production-grade DeepSeek (OpenAI-compatible) AI service.

    Key improvements vs your code:
    - Single transport (aiohttp only)
    - Persistent ClientSession (connection pooling)
    - timeout + retry + exponential backoff
    - safe JSON parsing + status checks
    - special instructions are actually injected
    - safer citation policy (avoid forcing fake DOI)
    """

    def __init__(self, cfg: Optional[AIConfig] = None):
        base_url = (getattr(SETTINGS, "deepseek_base_url", "") or "https://api.deepseek.com").rstrip("/")
        api_key = getattr(SETTINGS, "deepseek_api_key", "") or ""
        model = getattr(SETTINGS, "deepseek_model", "deepseek-chat") or "deepseek-chat"

        self.cfg = cfg or AIConfig(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_sec=int(getattr(SETTINGS, "ai_timeout_sec", 240)),
            max_retries=int(getattr(SETTINGS, "max_retries", 2)),
            backoff_sec=int(getattr(SETTINGS, "retry_backoff_sec", 2)),
            max_tokens=8000,
        )

        # Secondary (Failover) config
        self.secondary_cfg = AIConfig(
            base_url=SETTINGS.secondary_ai_base_url,
            api_key=SETTINGS.secondary_ai_api_key,
            model=SETTINGS.secondary_ai_model,
            timeout_sec=int(getattr(SETTINGS, "ai_timeout_sec", 240)),
            max_retries=1,
            backoff_sec=2,
            max_tokens=8000,
        )

        # Optional: strict references toggle
        self.strict_references = _env_bool(getattr(SETTINGS, "strict_references", "0"), default=False)

        self.system_prompt = (
            "You are an academic article generation engine with strict word-volume control.\n\n"
            "ABSOLUTE RULES:\n\n"
            "1) OUTPUT RULE\n"
            "- Output ONLY the final academic article text.\n"
            "- Do NOT output explanations, comments, instructions, templates, or meta-text.\n"
            "- Do NOT output section-by-section word counts.\n"
            "- Do NOT output intermediate drafts.\n\n"
            "2) LANGUAGE RULE\n"
            "- Write ONLY in the selected language.\n"
            "- Do NOT mix languages in the body text.\n"
            "- If multilingual output is explicitly requested, only Title/Abstract/Keywords may be multilingual.\n\n"
            "3) STRUCTURE RULE (MANDATORY ORDER)\n"
            "Title\nAbstract\nKeywords\nIntroduction\nLiterature Review\nMaterials and Methods\nResults\nDiscussion\nConclusion\nReferences\n\n"
            "4) WORD VOLUME RULE (CRITICAL)\n"
            "- Total word count = Abstract + Introduction + Literature Review + Methods + Results + Discussion + Conclusion.\n"
            "- References are excluded from counting.\n"
            "- You MUST reach the target word range before finishing.\n"
            "- If total words are below the target, you MUST internally expand sections until the target is reached.\n"
            "- You are NOT allowed to finish early.\n\n"
            "5) PAGE → WORD TARGETS (for DOCX: 14pt, 1.5 spacing, ~230 words/page)\n"
            "UZ/RU: 3 pages = 500–690 words, 5 pages = 690–1150 words, 10 pages = 1840–2300 words, 15 pages = 2990–3450 words.\n"
            "EN: 3 pages = 500–690 words, 5 pages = 690–1150 words, 10 pages = 1840–2300 words, 15 pages = 2990–3450 words.\n\n"
            "6) LEVEL LOGIC\n"
            "LOCAL_OAK: descriptive, national context, moderate academic style.\n"
            "SCOPUS_Q3Q4: evidence-based, structured argumentation, academic tone.\n"
            "SCOPUS_Q1Q2: novelty, deep theoretical analysis, comparative discussion, critical synthesis.\n\n"
            "7) DATA INTEGRITY\n"
            "- Do NOT invent statistics, sample sizes, p-values, Cronbach alpha, or institutions unless provided.\n"
            "- If real data is not provided, write a theoretical/review article without fake numbers.\n"
            "- Do NOT invent fake DOI links.\n\n"
            "8) OUTPUT RULES\n"
            "- NEVER include 'WORD COUNT REPORT', word statistics, target ranges, or 'Status: PASS/FAIL' in your output.\n"
            "- Output ONLY the academic content. No meta-information."
        )

        self._session: Optional[aiohttp.ClientSession] = None
        self._limiter = asyncio.Semaphore(int(getattr(SETTINGS, "ai_concurrency_limit", 5)))

    ARTICLE_TARGET_RANGES = {
        "uz": {3: (500, 690), 5: (690, 1150), 10: (1840, 2300), 15: (2990, 3450)},
        "ru": {3: (500, 690), 5: (690, 1150), 10: (1840, 2300), 15: (2990, 3450)},
        "en": {3: (500, 690), 5: (690, 1150), 10: (1840, 2300), 15: (2990, 3450)},
    }

    ARTICLE_LEVEL_WEIGHTS = {
        "LOCAL_OAK": {
            "Abstract": (0.06, 0.08),
            "Introduction": (0.18, 0.22),
            "Literature Review": (0.18, 0.22),
            "Methods": (0.12, 0.16),
            "Results": (0.10, 0.14),
            "Discussion": (0.12, 0.16),
            "Conclusion": (0.04, 0.06),
        },
        "SCOPUS_Q3Q4": {
            "Abstract": (0.07, 0.09),
            "Introduction": (0.16, 0.20),
            "Literature Review": (0.20, 0.24),
            "Methods": (0.14, 0.18),
            "Results": (0.12, 0.16),
            "Discussion": (0.14, 0.18),
            "Conclusion": (0.04, 0.06),
        },
        "SCOPUS_Q1Q2": {
            "Abstract": (0.08, 0.10),
            "Introduction": (0.14, 0.18),
            "Literature Review": (0.22, 0.28),
            "Methods": (0.16, 0.20),
            "Results": (0.12, 0.16),
            "Discussion": (0.16, 0.22),
            "Conclusion": (0.04, 0.06),
        },
    }

    # ----------------------------
    # Session lifecycle
    # ----------------------------
    async def start(self) -> None:
        if self._session and not self._session.closed:
            return
        timeout = aiohttp.ClientTimeout(total=self.cfg.timeout_sec)
        self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ----------------------------
    # Public API
    # ----------------------------
    async def generate_content(
        self,
        topic: str,
        doc_type: str,
        lang: str,
        cite_style: str = "none",
        length: int = 1,
    ) -> str:
        special = self._get_special_instr(doc_type, cite_style, length)
        # 14pt TNR + 1.5 interval DOCX = ~230 so'z/bet; minus 2 bet overhead (title+TOC)
        pages = max(1, int(length or 1))
        content_pages = max(1, pages - 2) if doc_type not in ("article", "thesis", "taqdimot") else pages
        word_count = content_pages * 230

        # Language instruction
        lang_instruction = {
            "uz": "MUHIM TIL: Butun matn FAQAT O'ZBEK TILIDA yozilishi kerak!",
            "en": "CRITICAL LANGUAGE: The ENTIRE text MUST be written in ENGLISH ONLY!",
            "ru": "ВАЖНЫЙ ЯЗЫК: Весь текст должен быть написан ТОЛЬКО НА РУССКОМ ЯЗЫКЕ!"
        }.get((lang or "uz").lower(), "")

        stealth_instr = (
            "You are acting as a human academic researcher revising your own manuscript draft.\n"
            "CRITICAL ANTI-DETECTION RULES:\n"
            "1. MUST pass AI detectors (Antigravity, Turnitin, GPTZero). Write like a REAL human student.\n"
            "2. Sentence Variety: mix short (5-8 words) and long (20-30 words) sentences randomly. NEVER use uniform length.\n"
            "3. AVOID these AI patterns: 'Furthermore', 'Moreover', 'It is worth noting', 'In conclusion', 'Additionally', 'It is important to note'. Use natural transitions instead.\n"
            "4. Natural Imperfections: occasionally use slightly informal phrasing, vary paragraph lengths (2-8 sentences), sometimes start with 'But' or 'And'.\n"
            "5. NO LISTS unless explicitly needed. Write in flowing prose paragraphs, not bullet-point style.\n"
            "6. AVOID perfectly balanced structures (don't write 3 equal paragraphs, don't repeat same sentence pattern).\n"
            "7. Use SPECIFIC examples, names, dates — not vague generalizations like 'many researchers' or 'various studies'.\n"
            "8. Hedged language: 'ko'rinishicha', 'ehtimol', 'mumkin', 'may suggest', 'appears to indicate'."
        )

        prompt = (
            f"{stealth_instr}\n\n"
            f"MAVZU: {topic}\n"
            f"{lang_instruction}\n"
            f"TIL: {lang}\n"
            f"TURI: {doc_type}\n"
            f"HAJM: kamida {word_count} so'z bo'lishi SHART. (MANDATORY: AT LEAST {word_count} WORDS)\n"
            f"{special}\n"
            "MUHIM: Faqat sof akademik matnni qaytaring. Markdown belgilarisiz (#, *, **)."
        )

        temperature = 0.8 if doc_type == "rewrite" else 0.5
        return await self._call_ai(prompt, temperature=temperature)

    async def generate_plan(self, topic: str, doc_type: str, length: int, lang: str = "uz") -> str:
        length = max(1, int(length or 1))
        lang = (lang or "uz").lower()

        # Article: 7 sections (IMRAD based)
        if doc_type == "article":
            if lang == "ru":
                return (
                    "1. Аннотация\n2. Ключевые слова\n3. Введение\n"
                    "4. Обзор литературы и методология\n5. Результаты и обсуждение\n"
                    "6. Заключение\n7. Список литературы"
                )
            elif lang == "en":
                return (
                    "1. Abstract\n2. Keywords\n3. Introduction\n"
                    "4. Literature Review and Methods\n5. Results and Discussion\n"
                    "6. Conclusion\n7. References"
                )
            else:  # uz
                return (
                    "1. Annotatsiya\n2. Kalit so'zlar\n3. Kirish\n"
                    "4. Adabiyotlar tahlili va metodlar\n5. Natijalar va muhokama\n"
                    "6. Xulosa\n7. Foydalanilgan adabiyotlar"
                )
        # Thesis: fixed sections — no AI call needed
        if doc_type == "thesis":
            if lang == "ru":
                return "1. Аннотация\n2. Введение\n3. Основная часть\n4. Заключение\n5. Ключевые слова и литература"
            elif lang == "en":
                return "1. Abstract\n2. Introduction\n3. Main Body\n4. Conclusion\n5. Keywords and References"
            else:
                return "1. Annotatsiya\n2. Kirish\n3. Asosiy qism\n4. Xulosa\n5. Kalit so'zlar va adabiyotlar"

        # Coursework: Bob (chapter) structure — 2 bob (<=30 pages) or 3 bob (>30 pages)
        if doc_type == "coursework":
            num_bobs = 2 if length <= 30 else 3

            if lang == "ru":
                bob2 = "II.Глава. [?]\n2.1. [?]\n2.2. [?]\n2.3. [?]"
                bob3 = "\nIII.Глава. [?]\n3.1. [?]\n3.2. [?]\n3.3. [?]" if num_bobs >= 3 else ""
                cn = num_bobs + 2
                tpl = f"1. Введение\nI.Глава. {topic}\n1.1. [?]\n1.2. [?]\n1.3. [?]\n{bob2}{bob3}\n{cn}. Заключение\n{cn+1}. Список литературы"
                prompt = (
                    f"ТЕМА: «{topic}»\nОБЪЁМ: {length} стр.\n\n"
                    f"Составьте план курсовой работы. Замените каждый [?] КОНКРЕТНЫМ названием ПО ТЕМЕ (3-7 слов).\n\n"
                    f"ВАЖНЫЕ ПРАВИЛА:\n"
                    f"- I.Глава — это НАЗВАНИЕ ТЕМЫ, НЕ МЕНЯТЬ!\n"
                    f"- II.Глава — напишите СВЯЗАННУЮ тему (развитие/совершенствование основной темы)\n"
                    + (f"- III.Глава — ещё одна связанная тема\n" if num_bobs >= 3 else "")
                    + f"- Подразделы (1.1, 1.2, 1.3, 2.1, 2.2, 2.3) — конкретные аспекты по теме\n\n"
                    f"ШАБЛОН:\n{tpl}\n\nВерните ТОЛЬКО список. Структуру НЕ менять. ВСЁ на РУССКОМ."
                )
            elif lang == "en":
                bob2 = "Chapter II. [?]\n2.1. [?]\n2.2. [?]\n2.3. [?]"
                bob3 = "\nChapter III. [?]\n3.1. [?]\n3.2. [?]\n3.3. [?]" if num_bobs >= 3 else ""
                cn = num_bobs + 2
                tpl = f"1. Introduction\nChapter I. {topic}\n1.1. [?]\n1.2. [?]\n1.3. [?]\n{bob2}{bob3}\n{cn}. Conclusion\n{cn+1}. References"
                prompt = (
                    f"TOPIC: «{topic}»\nPAGES: {length}\n\n"
                    f"Create a coursework plan. Replace each [?] with a SPECIFIC title about the topic (3-7 words).\n\n"
                    f"IMPORTANT RULES:\n"
                    f"- Chapter I title = THE TOPIC NAME, do NOT change it!\n"
                    f"- Chapter II = a RELATED topic (development/improvement of the main topic)\n"
                    + (f"- Chapter III = another related topic\n" if num_bobs >= 3 else "")
                    + f"- Subsections (1.1, 1.2, 1.3, 2.1, 2.2, 2.3) = specific aspects of the topic\n\n"
                    f"TEMPLATE:\n{tpl}\n\nReturn ONLY the list. Do NOT change structure. ALL in ENGLISH."
                )
            else:  # uz
                bob2 = "II.Bob. [?]\n2.1. [?]\n2.2. [?]\n2.3. [?]"
                bob3 = "\nIII.Bob. [?]\n3.1. [?]\n3.2. [?]\n3.3. [?]" if num_bobs >= 3 else ""
                cn = num_bobs + 2
                tpl = f"1. Kirish\nI.Bob. {topic}\n1.1. [?]\n1.2. [?]\n1.3. [?]\n{bob2}{bob3}\n{cn}. Xulosa\n{cn+1}. Foydalanilgan adabiyotlar"
                prompt = (
                    f"MAVZU: «{topic}»\nBET: {length}\n\n"
                    f"Kurs ishi rejasi tuzing. Har bir [?] o'rniga MAVZUGA OID aniq sarlavha yozing (3-7 so'z).\n\n"
                    f"MUHIM QOIDALAR:\n"
                    f"- I.Bob sarlavhasi AYNAN mavzu nomi — O'ZGARTIRMANG!\n"
                    f"- II.Bob sarlavhasi — mavzuni TAKOMILLASHTIRISH/RIVOJLANTIRISH yo'llari haqida bo'lsin\n"
                    + (f"- III.Bob sarlavhasi — mavzuga oid yana bir tegishli yo'nalish\n" if num_bobs >= 3 else "")
                    + f"- Kichik bo'limlar (1.1, 1.2, 1.3, 2.1, 2.2, 2.3) — mavzuning aniq jihatlari\n\n"
                    f"SHABLON:\n{tpl}\n\nFaqat ro'yxat qaytaring. Strukturani o'zgartirmang."
                )
            return await self._call_ai(prompt, temperature=0.4)

        # Presentation: AI generates topic-specific slide titles
        if doc_type == "taqdimot":
            num_slides = max(length, 5)
            mc = max(num_slides - 6, 1)
            mid = "\n".join(f"{i+5}. [?]" for i in range(mc))
            if lang == "ru":
                tpl = f"1. Титульный слайд\n2. План презентации\n3. Актуальность темы\n4. Цели и задачи\n{mid}\n{mc+5}. Заключение\n{mc+6}. Спасибо за внимание"
                prompt = (
                    f"ТЕМА: {topic}\nСЛАЙДЫ: {num_slides}\n\n"
                    f"Составьте план презентации. Замените каждый [?] названием слайда ПО ТЕМЕ «{topic}» (3-7 слов).\n\n"
                    f"ШАБЛОН:\n{tpl}\n\nВерните ТОЛЬКО список. Структуру НЕ менять."
                )
            elif lang == "en":
                tpl = f"1. Title Slide\n2. Presentation Outline\n3. Topic Relevance\n4. Objectives and Tasks\n{mid}\n{mc+5}. Conclusion\n{mc+6}. Thank You"
                prompt = (
                    f"TOPIC: {topic}\nSLIDES: {num_slides}\n\n"
                    f"Create a presentation plan. Replace each [?] with a slide title about «{topic}» (3-7 words).\n\n"
                    f"TEMPLATE:\n{tpl}\n\nReturn ONLY the list. Do NOT change structure. ALL in ENGLISH."
                )
            else:
                tpl = f"1. Titul slayd\n2. Taqdimot rejasi\n3. Mavzuning dolzarbligi\n4. Maqsad va vazifalar\n{mid}\n{mc+5}. Xulosa\n{mc+6}. E'tiboringiz uchun rahmat"
                prompt = (
                    f"MAVZU: {topic}\nSLAYDLAR: {num_slides}\n\n"
                    f"Taqdimot rejasi tuzing. Har bir [?] o'rniga «{topic}» MAVZUSIGA OID slayd sarlavhasi yozing (3-7 so'z).\n\n"
                    f"SHABLON:\n{tpl}\n\nFaqat ro'yxat qaytaring. Strukturani o'zgartirmang."
                )
            return await self._call_ai(prompt, temperature=0.4)

        # All other types (independent, diploma, dissertation, manual, etc.)
        # Main section count scales with page length
        if doc_type in ("diploma", "dissertation"):
            mc = max(3, min(length // 6 + 2, 6))
        else:  # independent, manual, etc.
            mc = max(2, min((length + 1) // 3, 5))

        mid = "\n".join(f"{i}. [?]" for i in range(2, 2 + mc))
        cn = 2 + mc  # conclusion number
        rn = cn + 1  # refs number

        if lang == "ru":
            if doc_type == "manual":
                tpl = f"1. Введение\n{mid}\n{cn}. Контрольные вопросы и задания\n{rn}. Рекомендуемая литература"
            else:
                tpl = f"1. Введение\n{mid}\n{cn}. Заключение и рекомендации\n{rn}. Список литературы"
            prompt = (
                f"ТЕМА: {topic}\nОБЪЁМ: {length} стр.\n\n"
                f"Составьте план. Замените каждый [?] КОНКРЕТНЫМ названием раздела ПО ТЕМЕ «{topic}» (3-7 слов).\n\n"
                f"ШАБЛОН:\n{tpl}\n\nВерните ТОЛЬКО список. Структуру НЕ менять. ВСЁ на РУССКОМ."
            )
        elif lang == "en":
            if doc_type == "manual":
                tpl = f"1. Introduction\n{mid}\n{cn}. Review Questions and Assignments\n{rn}. Recommended References"
            else:
                tpl = f"1. Introduction\n{mid}\n{cn}. Conclusion and Recommendations\n{rn}. References"
            prompt = (
                f"TOPIC: {topic}\nPAGES: {length}\n\n"
                f"Create a plan. Replace each [?] with a SPECIFIC section title about «{topic}» (3-7 words).\n\n"
                f"TEMPLATE:\n{tpl}\n\nReturn ONLY the list. Do NOT change structure. ALL in ENGLISH."
            )
        else:
            if doc_type == "manual":
                tpl = f"1. Kirish\n{mid}\n{cn}. Nazorat savollari va topshiriqlar\n{rn}. Tavsiya etilgan adabiyotlar"
            else:
                tpl = f"1. Kirish\n{mid}\n{cn}. Xulosa va takliflar\n{rn}. Foydalanilgan adabiyotlar"
            prompt = (
                f"MAVZU: {topic}\nBET: {length}\n\n"
                f"Reja tuzing. Har bir [?] o'rniga «{topic}» MAVZUSIGA OID aniq sarlavha yozing (3-7 so'z).\n\n"
                f"SHABLON:\n{tpl}\n\nFaqat ro'yxat qaytaring. Strukturani o'zgartirmang."
            )
        return await self._call_ai(prompt, temperature=0.4)

    async def generate_section(
        self,
        topic: str,
        section_title: str,
        context: str,
        doc_type: str,
        cite_style: str,
        lang: str = "uz",
        target_words: int = 330,  # CHANGED: Exact word target
        section_index: int = 1,
        total_sections: int = 1,
        meta: dict = None,
    ) -> str:
        # Use structured metadata from meta_json
        meta = meta or {}
        real_topic = topic or "Mavzusiz ish"
        
        uni = meta.get("uni", "")
        major = meta.get("major", "")
        subject = meta.get("subject", "")
        advisor = meta.get("advisor", "")
        ppt_style = meta.get("ppt_style", "akademik")
        article_level = meta.get("article_level", "LOCAL_OAK")
        udc = meta.get("udc", "")
        required_langs = meta.get("required_languages", "")
        refs_style = refs_style if (refs_style := meta.get("references_style")) else cite_style

        style_instr = ""
        if ppt_style == "akademik":
            style_instr = "USLUB: Rasmiy, ilmiy, terminlar bilan."
        elif ppt_style == "biznes":
            style_instr = "USLUB: Lo'nda, ishontiruvchi, biznes ohangida."
        elif ppt_style == "kreativ":
            style_instr = "USLUB: Yengilroq, qiziqarli, ammo akademik chegarada."

        tier_instr = ""
        if article_level == "LEVEL_SCOPUS_HIGH":
            tier_instr = "DARAJA: Xalqaro yuqori sifatli jurnal (Q1-Q2) talabi. O'ta yuqori ilmiy aniqlik."
        elif article_level == "LEVEL_SCOPUS_MID":
            tier_instr = "DARAJA: Scopus/WoS Q3-Q4 darajasidagi jurnal talabi."
        
        additional_ctx = ""
        if uni: additional_ctx += f"OTM: {uni}. "
        if major: additional_ctx += f"Yo'nalish: {major}. "
        if subject: additional_ctx += f"Fan: {subject}. "
        if advisor: additional_ctx += f"Ilmiy rahbar: {advisor}. "
        if udc: additional_ctx += f"UO'K: {udc}. "
        if required_langs: additional_ctx += f"Annotatsiya/Kalit so'zlar uchun tillar: {required_langs}. "
        if refs_style: additional_ctx += f"Iqtibos uslubi: {refs_style}. "

        # ADDED: Language enforcement map
        lang_instruction = {
            "uz": "MUHIM TIL: Butun matn FAQAT O'ZBEK TILIDA yozilishi kerak! (Uzbek language only)",
            "en": "CRITICAL LANGUAGE: The ENTIRE text MUST be written in ENGLISH ONLY! All content, explanations, and text must be in English.",
            "ru": "ВАЖНЫЙ ЯЗЫК: Весь текст должен быть написан ТОЛЬКО НА РУССКОМ ЯЗЫКЕ! (Russian only)"
        }.get((lang or "uz").lower(), "")

        # Presentation special
        if doc_type == "taqdimot":
            # Special handling for conclusion slides
            _sl = (section_title or "").lower()
            is_conclusion = any(k in _sl for k in ["xulosa", "conclu", "заключ"])
            is_thanks = any(k in _sl for k in ["rahmat", "thank", "спасибо", "e'tiboringiz"])

            if is_conclusion:
                prompt = (
                    f"Siz professional taqdimot tayyorlovchi mutaxassissiz.\n"
                    f"MAVZU: {real_topic}\n"
                    f"{lang_instruction}\n"
                    f"SLAYD: Xulosa (oxirgi slayd)\n\n"
                    "VAZIFA: Mavzuga bag'ishlangan haqiqiy XULOSA yozing — o'rganilgan natijalarni, "
                    "olingan ma'lumotlarni va muhim tushunchalarni yakunlang.\n\n"
                    "FORMAT:\n"
                    "- 4-5 ta bullet — HAR BIR bullet 10-15 so'zli to'liq xulosa gap bo'lsin (nafaqat sarlavha!)\n"
                    "- Har bullet mavzuni tahlil qilgan holda aniq fikr bildirsin\n"
                    "- Takrorlanadigan mavzu sarlavhalari EMAS — yangi xulosa fikrlari bo'lsin\n\n"
                    "NAMUNA (mavzu: Kiber hujumlar):\n"
                    "- Kiber hujumlar zamonaviy axborot tizimlari uchun eng jiddiy tahdid hisoblanadi\n"
                    "- Himoyaning texnik, tashkiliy va huquqiy jihatlari birgalikda amal qilishi kerak\n"
                    "- Kadrlarni muntazam o'qitish hujumlarning 70% oldini oladi\n"
                    "- Milliy kiber xavfsizlik strategiyasi davlat ustuvor vazifasiga aylanmog'i zarur\n\n"
                    "Speaker notes: [80-120 so'z xulosa tushuntirishi]\n\n"
                    "MUHIM: Sarlavhalar ro'yxati EMAS — to'liq xulosa gaplar yozing!"
                )
                return await self._call_ai(prompt, temperature=0.6)

            if is_thanks:
                # No content needed for thanks slide — just return minimal
                return "- E'tiboringiz uchun rahmat\n\nSpeaker notes: Tinglanganingiz uchun rahmat. Savollar bo'lsa, javob berishga tayyorman."

            prompt = (
                f"Siz professional taqdimot tayyorlovchi mutaxassissiz.\n"
                f"MAVZU: {real_topic}\n"
                f"{style_instr}\n"
                f"{lang_instruction}\n"
                f"SLAYD MAVZUSI: {section_title}\n"
                f"JARAYON: {section_index}/{total_sections}-slayd.\n"
                f"KONTEKST: {context}\n\n"
                "VAZIFA: Ushbu slayd uchun MA'NOLI MATNLI BULLETLAR tayyorlang.\n\n"
                "FORMAT:\n"
                "- Sarlavha yoki meta-label YOZMANG\n"
                "- 4-5 ta bullet point yozing\n"
                "- Har bir bullet 10-18 so'zli TO'LIQ JUMLA bo'lsin — fakt, tahlil yoki aniq fikr ifodalasin\n"
                "- Sarlavha yoki kalit so'zlar EMAS — to'liq ma'noli gaplar\n"
                "- Keyin 'Speaker notes:' deb ma'ruzachi matni yozing (80-120 so'z)\n\n"
                "NAMUNA (Kiber xavfsizlik mavzusida):\n"
                "- Kiber hujumlarning soni so'nggi 5 yilda 300% ga oshdi, bu jiddiy tahdidni ko'rsatadi\n"
                "- Phishing hujumlari barcha buzilishlarning 80% dan ortig'ini tashkil qiladi\n"
                "- Ko'p faktorli autentifikatsiya hisob ma'lumotlari o'g'irlanishini 99% kamaytiradi\n"
                "- Xodimlarning muntazam o'qitilishi insoniy omildagi xatoliklarning oldini oladi\n\n"
                "Speaker notes: [80-120 so'z batafsil tushuntirish]\n\n"
                "MUHIM: Qisqa kalit so'z emas — to'liq MA'NOLI gaplar yozing!"
            )
            return await self._call_ai(prompt, temperature=0.7)

        article_enhancement = self._article_enhancement(doc_type, section_title, level=article_level)

        stealth_persona = (
            "PERSONA: Human student/researcher writing their own work.\n"
            "ANTI-AI-DETECTION RULES (CRITICAL):\n"
            "- MUST pass GPTZero, Turnitin, Antigravity AI detectors.\n"
            "- NEVER use: 'Furthermore', 'Moreover', 'Additionally', 'It is worth noting', 'In light of'.\n"
            "- Mix sentence lengths randomly: short (5-8 words), medium (12-18), long (20-30). NO uniform pattern.\n"
            "- Vary paragraph sizes: some 2 sentences, some 5-8 sentences. NOT all equal.\n"
            "- Use hedged language: 'ko'rinishicha', 'ehtimol', 'could suggest', 'appears to'.\n"
            "- Write like a real student — slightly imperfect, natural flow, occasional informal tone.\n"
            "- Include specific examples with real names/dates, not vague 'many researchers say'.\n"
            "- De-idealize statistics (use 47.3% not 50%, 1847 not 'about 2000')."
        )

        is_final = section_index >= total_sections
        is_metadata = section_index <= 4 # Title, Abstract, etc.

        target_range_val = "[total_target_range]"
        if "TARGET_RANGE:" in context:
            target_range_val = context.split("TARGET_RANGE:")[1].strip().split("\n")[0]

        # WORD COUNT REPORT removed — was leaking into final documents

        # Quality Requirements by Level
        quality_instr = ""
        if doc_type == "article":
            if article_level == "SCOPUS_Q1Q2":
                quality_instr = "SCOPUS Q1-Q2 REQUIREMENTS: NOVELTY IS REQUIRED. Advanced methodology, comparative discussion. NO descriptive filler."
            elif article_level == "SCOPUS_Q3Q4":
                quality_instr = "SCOPUS Q3-Q4 REQUIREMENTS: Evidence-based research. Clear methodology. Statistics (p-values) required."
            else:
                quality_instr = "LOCAL OAK REQUIREMENTS: Descriptive, contextual, simple statistics."

        # CHAIN-OF-THOUGHT (CoT) Prompting
        # Faqat oxirgi "Foydalanilgan adabiyotlar" bo'limi — "Adabiyotlar tahlili" emas!
        _st = section_title.lower()
        _st_clean = re.sub(r'^[\d]+[\.\)]\s*', '', _st).strip()
        is_references_section = (
            ("foydalanilgan" in _st_clean and "adabiyot" in _st_clean) or
            ("список" in _st_clean and "литератур" in _st_clean) or
            _st_clean.startswith("references") or
            _st_clean.startswith("список литератур") or
            _st_clean.startswith("foydalanilgan") or
            # Thesis combined: "Kalit so'zlar va adabiyotlar" / "Keywords and References"
            ("kalit" in _st_clean and "adabiyot" in _st_clean) or
            ("keyword" in _st_clean and "reference" in _st_clean) or
            ("ключев" in _st_clean and "литератур" in _st_clean) or
            # Standalone "Adabiyotlar" (without "tahlil" = not Literature Review)
            ("adabiyot" in _st_clean and "tahlil" not in _st_clean) or
            # Standalone "Литература" (without "обзор"/"метод")
            ("литератур" in _st_clean and "обзор" not in _st_clean and "метод" not in _st_clean) or
            "библиограф" in _st_clean
        )

        refs_rule = ""
        if is_references_section:
            refs_rule = "10. REFERENCES LIST — STRICT RULES: Write ONLY a NUMBERED list (1. 2. 3. ...). MINIMUM 5 sources, MAXIMUM 10 sources. NEVER write more than 10! Do NOT write any sub-heading, title, or review text — ONLY numbered entries. Do NOT use bullet points (•, -, *). Start directly with '1. Author...'. STOP after 10th entry! IMPORTANT: Each reference must be SHORT (1-2 lines max). Format: Author(s), Title, Publisher/Journal, Year. Do NOT add descriptions, annotations, or explanations after each reference."
        else:
            refs_rule = "10. REFERENCES: Do NOT include a bibliography or reference list in this section. Only use in-text citations like [1], (Author, Year)."

        cot_instructions = (
            "INSTRUCTIONS:\n"
            "1. You are an academic writing engine producing a SINGLE complete document. This is one part of it.\n"
            "2. Analyze the 'PREVIOUS CONTEXT'. Do NOT repeat explanations. Maintain flow consistency.\n"
            "3. Identify the specific goal of THIS section ('SECTION TITLE').\n"
            "4. Write with depth and analysis. Avoid general descriptions unless it's the Intro.\n"
            "5. NO MARKDOWN: Use plain text ONLY. Never use #, ##, **, or similar symbols. "
            "EXCEPTION: Tables MUST use markdown pipe format: | col | col | — this is required for proper formatting.\n"
            "6. PROHIBITED: No '...', '___', empty templates, or unknown symbols. "
            "EXCEPTION: Table pipes | and separators |---| are allowed and required.\n"
            "6b. TABLE DATA: If writing a table, ALL cells MUST contain actual numeric values (e.g. 5.84±0.31). NEVER leave a cell empty. Generate realistic research data.\n"
            "7. NO FILLER: Avoid redundant sentences. Discussion must NOT repeat Results.\n"
            "8. LANGUAGE: Strictly use the specified language. If multiple languages are requested for metadata (e.g. UZ+RU+EN), apply it ONLY to Title/Abstract/Keywords.\n"
            "9. WORD COUNT: Write at least 90% of the word target. If target is 450, write 400-500 words.\n"
            f"{refs_rule}\n"
            "11. Do NOT include WORD COUNT REPORT or any meta-statistics in your output.\n"
            "12. NEVER end with an empty heading. If you are running out of words, finish the current section properly with content. Do NOT write a new section title if you cannot write its content."
        )

        safe_context = context[-4000:] if context else ""

        prompt = (
            f"ROLE: Senior Academic Editor & Researcher.\n"
            f"TASK: Write a rigorous academic section for a {doc_type}.\n\n"
            f"METADATA:\n"
            f"- Topic: {real_topic}\n"
            f"- Section Title: {section_title}\n"
            f"- Level: {article_level}\n"
            f"- Progress: {section_index}/{total_sections}\n"
            f"- WORD TARGET: {'Write ONLY the required items (keywords list, references list) — no extra text.' if target_words <= 40 else f'approximately {target_words} words. Do NOT exceed {int(target_words * 1.1)} words. Stay within {int(target_words * 0.85)}-{int(target_words * 1.1)} words.'}\n"
            f"- Language: {lang}\n"
            f"- {quality_instr}\n"
            f"- {style_instr}\n"
            f"- {article_enhancement}\n"
            f"- {tier_instr}\n"
            f"- UDC: {udc}\n"
            f"- Multi-lang Req: {required_langs}\n"
            f"- References Style: {refs_style}\n"
            f"- {additional_ctx}\n\n"
            f"PREVIOUS CONTEXT (Internal consistency):\n"
            f"{safe_context}\n\n"
            f"{cot_instructions}\n"
            f"CONTENT TO GENERATE ({section_title}):\n"
            "Write the academic text now. No AI chatter."
        )
        
        return await self._call_ai(prompt, temperature=0.6)

    async def verify_citations(self, content: str, cite_style: str, lang: str = "uz") -> str:
        """
        Specialized step to ensure citation health.
        """
        lang = (lang or "uz").lower()
        if lang == "ru":
            p_text = "Проверьте цитаты и список литературы в этом тексте:"
            p_rule1 = f"1. Все цитаты должны соответствовать стилю {cite_style}."
            p_rule2 = "2. Убедитесь, что каждая внутритекстовая цитата есть в списке."
            p_rule4 = "4. Год источников должен быть 2019-2025."
            p_rule5 = "5. По возможности используйте ссылки DOI."
            p_final = "Верните только исправленный текст."
        elif lang == "en":
            p_text = "Verify citations and references in this text:"
            p_rule1 = f"1. All citations must match {cite_style} style."
            p_rule2 = "2. Ensure every in-text citation is in the references list."
            p_rule4 = "4. Sources must be primarily from 2019-2025."
            p_rule5 = "5. Provide DOI links where possible."
            p_final = "Return ONLY the edited text."
        else: # uz
            p_text = "Ushbu akademik matndagi iqtiboslarni va 'Foydalanilgan adabiyotlar' ro'yxatini tekshiring:"
            p_rule1 = f"1. Barcha iqtiboslar {cite_style} uslubiga mosligini tekshiring."
            p_rule2 = "2. Har bir iqtibos ro'yxatda mavjudligini tasdiqlang."
            p_rule4 = "4. Manbalar yili 2019-2025 oralig'ida bo'lsin."
            p_rule5 = "5. Manbalar iloji boricha DOI havolalari bilan berilsin."
            p_final = "Faqat tahrirlangan matnni qaytaring."

        prompt = (
            f"{p_text}\n"
            f"{p_rule1}\n"
            f"{p_rule2}\n"
            "3. Nomuvofiqlikni tuzating.\n"
            f"{p_rule4}\n"
            f"{p_rule5}\n"
            f"{p_final}\n\n"
            f"TEXT:\n{content}"
        )
        return await self._call_ai(prompt, temperature=0.3)

    async def critique_content(self, content: str, lang: str = "uz", target_pages: int = 0) -> str:
        """Enhanced critique with validation checks."""
        if not content: return ""
        lang = (lang or "uz").lower()
        if len(content) > 20000:
            logger.warning("Content too large for critique (%d).", len(content))
            return content

        # Validation checks
        if target_pages > 0:
            min_w, max_w = get_word_range_for_pages(target_pages, lang)
            is_valid, actual, msg = validate_word_count(content, min_w, max_w)
            logger.info(f"Word count validation: {msg}")
            
            if not is_valid:
                logger.warning(f"Word count FAIL: {actual} words (target: {min_w}-{max_w})")
        
        # Anti-hallucination check
        warnings = detect_hallucinated_data(content)
        if warnings:
            logger.warning(f"Hallucination warnings: {', '.join(warnings)}")
        
        # Reference validation
        ref_valid, ref_warnings = validate_references(content)
        if not ref_valid:
            logger.warning(f"Reference warnings: {', '.join(ref_warnings)}")

        instr = {
            "uz": "Siz akademik muharrirsiz. AI xususiyatlarini (chatter, **, *, ` belgilar) olib tashlang, uslubni va imloni tuzating. MUHIM: Matnni KENGAYTIRMANG. Faqat tahrirlab, tuzating. So'zlar sonini oshirmang. QOIDA: ## bilan boshlanadigan bo'lim sarlavhalarini AYNAN SHU HOLATDA SAQLANG (masalan: '## Kirish' → '## Kirish'). ## belgilarini O'CHIRMANG!",
            "ru": "Вы академический редактор. Удалите артефакты ИИ (**, *, `), исправьте стиль и орфографию. ВАЖНО: НЕ расширяйте текст. Только редактируйте. Не увеличивайте количество слов. ПРАВИЛО: Заголовки разделов, начинающиеся с ##, СОХРАНЯЙТЕ КАК ЕСТЬ (например: '## Введение' → '## Введение'). НЕ удаляйте символы ##!",
            "en": "You are an academic editor. Remove AI chatter and markdown artifacts (**, *, `), fix style and grammar. CRITICAL: Do NOT expand or add content. Only edit. Keep the same word count or less. RULE: PRESERVE section headings that start with ## EXACTLY as they are (e.g. '## Introduction' → '## Introduction'). Do NOT remove ## markers!"
        }.get(lang, "You are an academic editor. Fix style and remove AI chatter. Do NOT expand text. PRESERVE ## section headings.")

        prompt = f"{instr}\n\nTEXT:\n{content}"
        try:
            return await self._call_ai(prompt, temperature=0.3)
        except Exception as e:
            logger.error(f"Critique failed: {e}")
            return content

    # ----------------------------
    # Internal
    # ----------------------------
    async def _call_ai(self, prompt: str, temperature: float = 0.5) -> str:
        """
        AI Call with Provider Failover, Concurrency Limit, and Redis Caching.
        """
        await self.start()
        
        # Phase 3: Caching Strategy
        import hashlib
        cache_key = f"ai_cache:{hashlib.md5(f'{prompt}:{temperature}'.encode()).hexdigest()}"
        
        # Try to get from Redis (using the global AI_QUEUE's redis instance if available)
        from ..queue_manager import AI_QUEUE
        if AI_QUEUE._mode == "redis" and AI_QUEUE._redis:
            try:
                cached = await AI_QUEUE._redis.get(cache_key)
                if cached:
                    logger.info(f"AI Cache Hit: {cache_key}")
                    return cached
            except Exception as e:
                logger.warning(f"AI Cache Get Error: {e}")

        async with self._limiter:
            # 1. Try Primary
            try:
                res = await self._execute_ai_call(self.cfg, prompt, temperature)
                
                # Cache the successful result for 24 hours
                if AI_QUEUE._mode == "redis" and AI_QUEUE._redis:
                    try:
                        await AI_QUEUE._redis.setex(cache_key, 86400, res)
                        logger.info(f"AI Cache Save: {cache_key}")
                    except Exception as e:
                        logger.warning(f"AI Cache Set Error: {e}")
                
                return res
            except Exception as e:
                logger.warning("Primary AI failed: %s. Attempting failover...", e)
                
                # 2. Try Secondary if configured
                if self.secondary_cfg.api_key:
                    try:
                        return await self._execute_ai_call(self.secondary_cfg, prompt, temperature)
                    except Exception as e2:
                        logger.error("Secondary AI also failed: %s", e2)
                        raise AIServiceError(f"Both AI providers failed. Last error: {e2}")
                else:
                    raise AIServiceError(f"Primary AI failed and no secondary configured: {e}")

    async def _execute_ai_call(self, cfg: AIConfig, prompt: str, temperature: float) -> str:
        url = f"{cfg.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {cfg.api_key}"}

        payload = {
            "model": cfg.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": float(temperature),
            "max_tokens": int(cfg.max_tokens),
        }

        last_err: Optional[Exception] = None

        for attempt in range(cfg.max_retries + 1):
            try:
                assert self._session is not None

                async with self._session.post(url, headers=headers, json=payload) as resp:
                    raw_text = await resp.text()

                    if resp.status >= 400:
                        raise AIServiceError(f"HTTP {resp.status}: {raw_text[:800]}")

                    data: Optional[Dict[str, Any]] = None
                    with suppress(Exception):
                        data = await resp.json()

                    if not isinstance(data, dict):
                        raise AIServiceError(f"Invalid JSON response: {raw_text[:800]}")

                    # DeepSeek/OpenAI compatible: {"choices":[{"message":{"content":"..."}}], ...}
                    choices = data.get("choices")
                    if not choices or not isinstance(choices, list):
                        raise AIServiceError(f"No choices in response: {str(data)[:800]}")

                    msg = choices[0].get("message") if isinstance(choices[0], dict) else None
                    content = (msg or {}).get("content") if isinstance(msg, dict) else None
                    if not content:
                        raise AIServiceError(f"Empty content: {str(data)[:800]}")

                    return str(content).strip()

            except asyncio.CancelledError:
                raise
            except Exception as e:
                last_err = e
                if attempt >= cfg.max_retries:
                    break
                backoff = cfg.backoff_sec * (2 ** attempt)
                logger.warning(
                    "AI call failed (attempt %s/%s): %s | retry in %ss",
                    attempt + 1,
                    cfg.max_retries + 1,
                    e,
                    backoff,
                )
                await asyncio.sleep(backoff)

        raise AIServiceError(f"AI call failed after retries: {last_err}")

    def _extract_topic_meta(self, topic: str) -> tuple[str, str, str, str]:
        real_topic = (topic or "").split("|")[0].strip() or "Mavzusiz ish"
        additional_ctx = ""
        style_instr = ""
        tier_instr = ""

        if "|" not in (topic or ""):
            return real_topic, additional_ctx, style_instr, tier_instr

        parts = [p.strip() for p in topic.split("|") if p.strip()]
        if parts:
            real_topic = parts[0]

        additional_ctx = " ".join(parts[1:])

        for p in parts[1:]:
            if "Style:" in p:
                s = p.split(":", 1)[1].strip().lower()
                if s == "akademik":
                    style_instr = "USLUB: Rasmiy, ilmiy, terminlar bilan."
                elif s == "biznes":
                    style_instr = "USLUB: Lo'nda, ishontiruvchi, biznes ohangida."
                elif s == "kreativ":
                    style_instr = "USLUB: Yengilroq, qiziqarli, ammo akademik chegarada."
            if "Tier:" in p:
                t = p.split(":", 1)[1].strip().lower()
                if t == "international":
                    tier_instr = (
                        "DARAJA: Xalqaro jurnal talabi.\n"
                "Talab: aniq metodologiya, natijalar, cheklovlar, ilmiy terminlar."
                    )

        return real_topic, additional_ctx, style_instr, tier_instr

    async def analyze_article_type(self, title: str) -> str:
        """Taklif 7: Dynamic Weighting."""
        prompt = (
            f"Mavzu: {title}\n"
            "Ushbu maqola qaysi turga kirishini aniqlang:\n"
            "- EXPERIMENTAL (Tajriba, laboratoriya, so'rovnoma)\n"
            "- REVIEW (Nazariy tahlil, adabiyotlar sharhi)\n"
            "- CASE_STUDY (Muayyan ob'ekt/tashkilot tahlili)\n"
            "Faqat bir so'z qaytaring."
        )
        res = await self._call_ai(prompt, temperature=0.2)
        res = res.strip().upper()
        if "EXPERIMENTAL" in res: return "EXPERIMENTAL"
        if "CASE" in res: return "CASE_STUDY"
        return "REVIEW"

    async def get_research_foundation(self, title: str, lang: str) -> dict:
        """Taklif 9 & 10: Concept Drift & Terminology Lock."""
        prompt = (
            f"MAVZU: {title}\n"
            f"TIL: {lang}\n"
            "Vazifa: Ushbu ilmiy maqola uchun fundament yaratib bering (JSON formatda):\n"
            "1. core_question (Asosiy tadqiqot savoli)\n"
            "2. hypotheses (3 ta gipoteza ro'yxati)\n"
            "3. key_terms (5-7 ta asosiy ilmiy termin va ularning ma'nosi)\n"
            "Faqat JSON qaytaring."
        )
        res = await self._call_ai(prompt, temperature=0.3)
        try:
            import json
            if "```json" in res: res = res.split("```json")[1].split("```")[0]
            data = json.loads(res.strip())
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            if not isinstance(data, dict):
                data = {"core_question": title, "hypotheses": [], "key_terms": {}}
            return data
        except Exception as e:
            logger.error(f"Failed to parse research foundation JSON: {e}")
            return {"core_question": title, "hypotheses": [], "key_terms": {}}

    def _article_enhancement(self, doc_type: str, section_title: str, level: str = "LOCAL_OAK") -> str:
        s = (section_title or "").lower()

        # Thesis enhancements
        if doc_type == "thesis":
            if any(x in s for x in ["annotatsiya", "abstract", "аннотац"]):
                return "ANNOTATSIYA: Muammo va natijalar qisqa bayoni. 100-150 so'z. FAQAT shu bo'limni yoz."
            if any(x in s for x in ["kirish", "intro", "введен"]):
                return "KIRISH: Mavzuning dolzarbligi, muammo, maqsad. FAQAT shu bo'limni yoz."
            if any(x in s for x in ["asosiy", "main", "основн"]):
                return "ASOSIY QISM: Muammo tahlili, tadqiqot metodi, natijalar. Eng katta bo'lim. FAQAT shu bo'limni yoz."
            if any(x in s for x in ["xulosa", "conclu", "заключ"]):
                return "XULOSA: Yakuniy fikrlar va tavsiyalar. FAQAT shu bo'limni yoz."
            if any(x in s for x in ["kalit", "keyword", "ключев", "adabiyot", "literat"]):
                return (
                    "KALIT SO'ZLAR VA ADABIYOTLAR:\n"
                    "Avval kalit so'zlar (5-8 ta, vergul bilan ajratilgan).\n"
                    "Keyin adabiyotlar ro'yxati (3-5 ta, raqamlangan: 1. 2. 3.). MAKSIMUM 5 TA!\n"
                    "Har bir adabiyot QISQA bo'lsin (1-2 qator): Muallif, Sarlavha, Nashriyot, Yil. Izoh/tavsif YOZMA!\n"
                    "FAQAT shu bo'limni yoz."
                )
            return ""

        # ALL doc types: references section enhancement
        if doc_type != "article":
            s_clean = re.sub(r'^[\d]+[\.\)]\s*', '', s).strip()
            if ("adabiyot" in s_clean and "tahlil" not in s_clean) or \
               s_clean.startswith("references") or s_clean.startswith("recommend") or \
               ("список" in s_clean and "литератур" in s_clean) or \
               ("литератур" in s_clean and "обзор" not in s_clean and "метод" not in s_clean) or \
               "библиограф" in s_clean or ("foydalanilgan" in s_clean):
                return (
                    "REFERENCES/ADABIYOTLAR: Write ONLY a NUMBERED list (1. 2. 3. ...). "
                    "MINIMUM 5, MAXIMUM 10 sources! Do NOT write more than 10! "
                    "Do NOT write any sub-heading, title, or review text — ONLY numbered entries. "
                    "Do NOT use bullet points (•, -, *). Start directly with '1. Author...'. "
                    "Each reference must be SHORT (1-2 lines max): Author(s), Title, Publisher/Journal, Year. "
                    "Do NOT add descriptions, annotations, or explanations after each reference. "
                    "This is the FINAL section."
                )
            return ""

        level = level or "LOCAL_OAK"

        # IMRAD Rules (uz/en/ru keywords)
        if any(x in s for x in ["annotatsiya", "abstract", "аннотац"]):
            return "ANNOTATSIYA/ABSTRACT: Tadqiqot muammosi, maqsadi, metodi va asosiy natijalar qisqa bayoni. 150-200 so'z. FAQAT shu bo'limni yoz, boshqa bo'limga o'tma."
        elif any(x in s for x in ["kalit", "keyword", "ключев"]):
            return "KALIT SO'ZLAR/KEYWORDS: 8-12 ta kalit so'z, vergul bilan ajratilgan. Mavzuning eng muhim tushunchalarini aks ettirsin. FAQAT kalit so'zlarni yoz, boshqa hech narsa yozma."
        elif any(x in s for x in ["kirish", "intro", "введение"]):
            return "KIRISH: Mavzuning dolzarbligi, muammo, tadqiqot maqsadi. 5-8 ta manbaga murojaat."
        elif ("tahlil" in s and "metod" in s) or ("literature" in s and "method" in s) or ("литератур" in s and "метод" in s):
            return "ADABIYOTLAR TAHLILI VA METODLAR: Nazariy asoslar + tadqiqot usullari. Adabiyotlar RO'YXATINI bu yerda YOZMA — faqat tahlil va in-text citation [1] ishlatish."
        elif ("natija" in s and "muhokama" in s) or ("result" in s and "discuss" in s) or ("результат" in s and "обсужд" in s):
            return "NATIJALAR VA MUHOKAMA: Natijalar tahlili + oldingi tadqiqotlar bilan solishtirish. Jadvallar bo'lsin."
        elif any(x in s for x in ["xulosa", "conclu", "заключение"]):
            return "XULOSA: Asosiy xulosalar va amaliy tavsiyalar."
        elif ("foydalanilgan" in s and "adabiyot" in s) or s.strip().startswith("references") or ("список" in s and "литератур" in s):
            return "REFERENCES/ADABIYOTLAR: Write ONLY a numbered list (1. 2. 3. ...), 5-10 sources (MAXIMUM 10!), 70% from last 5 years. Do NOT write any sub-heading or title text — ONLY numbered entries. Do NOT use bullet points (•, -, *). This is the FINAL section."

        return f"Apply {level} academic rigor."

    def _get_special_instr(self, doc_type: str, cite_style: str, length: int) -> str:
        length = max(1, int(length or 1))
        word_count = length * 300
        cite_style = (cite_style or "none").strip()

        if doc_type == "article":
            return (
                f"Ilmiy maqola yoz. Hajm: ~{word_count} so'z (~{length} bet, 1 bet ~250 so'z).\n"
                "Struktura qattiq rioya qilinishi kerak va BARCHA bo'limlarni to'liq yoz:\n\n"
                "1. Annotatsiya (qisqa xulosa, 150-200 so'z, muammo va natijalarni qamrab olgan).\n"
                "2. Kalit so'zlar (8-12 ta).\n"
                "3. Kirish (mavzuning dolzarbligi, muammo ta'rifi, maqsad va vazifalar).\n"
                "4. Adabiyotlar tahlili va metodlar (nazariy asoslar, adabiyotlar tahlili, tadqiqot metodlari batafsil).\n"
                "5. Natijalar va muhokama bo'limida JADVAL MAJBURIY.\n"
                "JADVAL QOIDALARI (QATTIQ BAJAR):\n"
                "- Jadval sarlavhasi jadvaldan OLDIN: '1-Jadval. [sarlavha]'\n"
                "- Jadval markdown formatida: | ustun | ustun | ...\n"
                "- Separator qatori: |-----|-----|----|\n"
                "- BARCHA katak RAQAMLI MA'LUMOT bilan to'ldirilsin — BO'SH KATAK YO'Q!\n"
                "- Mavzuga mos real ilmiy qiymatlar yaz (M±SD formatida)\n"
                "- Jadval max 5-6 ustun, 6-10 qator bo'lsin\n"
                "NAMUNA:\n"
                "1-Jadval. Tajriba va nazorat guruhlarining ko'rsatkichlari (M±SD)\n"
                "| Ko'rsatkich | Tajriba B | Tajriba Y | Nazorat B | Nazorat Y | p |\n"
                "|------------|-----------|-----------|-----------|-----------|---|\n"
                "| 30 m yugurish (s) | 5.84±0.31 | 5.52±0.28 | 5.91±0.33 | 5.83±0.30 | <0.05 |\n"
                "| Uzunlikka sakrash (sm) | 175.3±8.2 | 185.6±7.9 | 174.8±8.5 | 177.1±8.3 | <0.05 |\n"
                "| Muvozanat (s) | 18.2±3.1 | 25.6±2.8 | 18.5±3.3 | 19.2±3.1 | >0.05 |\n"
                "6. Xulosa (yakuniy natijalar, takliflar va kelajakdagi ishlar).\n"
                f"7. Foydalanilgan adabiyotlar (5-10 manba, {cite_style} uslubida, raqamlangan: 1. 2. 3. Maksimum 10 ta!).\n\n"
                f"Qattiq rioya qil: Agar {word_count} so'zdan oshsa, qisqartir, lekin barcha bo'limlarni to'liq saqla.\n"
                "Har bir bo'limni mutanosib taqsimla: Kirish va Xulosa 10-15% hajm, "
                "Asosiy qism (Adabiyotlar tahlili, Metodlar, Natijalar) 70%.\n"
                "Ilmiy uslubda yoz, yangi natijalar va real manbalar bilan.\n"
                "To'liq matnni yoz, hech qaysi bo'limni o'tkazib yuborma.\n"
                "SARLAVHALAR tanlangan tilda yozilsin (REFERENCES emas, Foydalanilgan adabiyotlar).\n"
            )

        if doc_type == "coursework":
            return (
                "KURS ISHI (O'AK STANDARTI):\n\n"
                "═══════════════════════════════════════════════════════════════\n"
                "STRUKTURA (MAJBURIY - 8 bo'lim):\n"
                "═══════════════════════════════════════════════════════════════\n\n"
                "1️⃣ TITUL VARAQ (Title page)\n"
                "   - OTM nomi\n"
                "   - Fakultet va kafedra\n"
                "   - Ish turi va mavzusi\n"
                "   - Talaba F.I.Sh va guruhi\n"
                "   - Ilmiy rahbar F.I.Sh va unvoni\n"
                "   - Shahar va yil\n\n"
                "2️⃣ MUNDARIJA (Table of contents)\n"
                "   - Barcha bo'limlar sahifa raqamlari bilan\n"
                "   - Kirish, boblar, xulosa, adabiyotlar, ilovalar\n\n"
                "3️⃣ KIRISH (Introduction - 2-3 bet) - ENG MUHIM BO'LIM!\n"
                "   MAJBURIY elementlar:\n"
                "   ✓ DOLZARBLIK (Relevance):\n"
                "     - Mavzuning zamonaviy ahamiyati\n"
                "     - Nima uchun bu mavzu muhim?\n"
                "     - Statistik kontekst (agar mavjud bo'lsa)\n"
                "     ❌ Xato: 'Bu mavzu dolzarb'\n"
                "     ✅ To'g'ri: 'Raqamli iqtisodiyot O'zbekiston YaIMning 15% ni tashkil etadi (2024), shuning uchun...'\n\n"
                "   ✓ MAQSAD (Objective - 1 gap):\n"
                "     - Aniq va o'lchanuvchi\n"
                "     - Nima erishmoqchisiz?\n"
                "     ❌ Xato: 'Mavzuni o'rganish'\n"
                "     ✅ To'g'ri: 'Raqamli iqtisodiyotning kichik biznesga ta'sirini tahlil qilish va rivojlantirish yo'llarini aniqlash'\n\n"
                "   ✓ VAZIFALAR (Tasks - 4-6 ta):\n"
                "     - Konkret, bajarilishi mumkin bo'lgan vazifalar\n"
                "     - Har biri maqsadga erishishga yordam beradi\n"
                "     Namuna:\n"
                "     1. Raqamli iqtisodiyot tushunchasini nazariy jihatdan o'rganish\n"
                "     2. O'zbekistonda raqamli iqtisodiyot holatini tahlil qilish\n"
                "     3. Kichik biznesda raqamli texnologiyalar qo'llanilishini tadqiq etish\n"
                "     4. Muammolarni aniqlash va yechim yo'llarini taklif qilish\n\n"
                "   ✓ TADQIQOT OBYEKTI VA PREDMETI:\n"
                "     - Obyekt: Nima o'rganiladi? (masalan: O'zbekiston kichik biznesi)\n"
                "     - Predmet: Qaysi jihati o'rganiladi? (masalan: raqamli texnologiyalar ta'siri)\n\n"
                "   ✓ AMALIY AHAMIYATI:\n"
                "     - Natijalar qayerda qo'llanilishi mumkin?\n"
                "     - Kim foydalanadi?\n"
                "     Namuna: 'Tadqiqot natijalari kichik biznes rahbarlari va davlat organlari tomonidan raqamlashtirish strategiyasini ishlab chiqishda foydalanilishi mumkin.'\n\n"
                "4️⃣ I BOB. NAZARIY QISM (Theoretical part)\n"
                "   - 2-3 ta paragraf (1.1, 1.2, 1.3)\n"
                "   - Asosiy tushunchalar va ta'riflar\n"
                "   - Xorijiy va mahalliy adabiyotlar tahlili\n"
                "   - Nazariy asoslar\n"
                "   - Har paragraf 3-5 bet\n\n"
                "5️⃣ II BOB. AMALIY/TAHLILIY QISM (Practical/Analytical part)\n"
                "   - 2-3 ta paragraf (2.1, 2.2, 2.3)\n"
                "   - Hozirgi holat tahlili\n"
                "   - Statistik ma'lumotlar (jadvallar, grafiklar)\n"
                "   - Muammolar va ularning sabablari\n"
                "   - Taklif va tavsiyalar\n"
                "   - Har paragraf 3-5 bet\n\n"
                "6️⃣ XULOSA (Conclusion - 1-2 bet)\n"
                "   - Asosiy xulosalar (vazifalar bo'yicha)\n"
                "   - Erishilgan natijalar\n"
                "   - Tavsiyalar\n"
                "   - Kelajakda rivojlantirish yo'nalishlari\n\n"
                "7️⃣ FOYDALANILGAN ADABIYOTLAR (References):\n"
                "   TALABLAR:\n"
                "   ✓ Jami: 5-10 ta manba (MAKSIMUM 10 ta!)\n"
                "   ✓ Xorijiy: kamida 3-5 ta\n"
                "   ✓ Yangilik: 50% oxirgi 5 yil ichida (2020-2025)\n"
                "   ✓ Turlar: kitoblar, maqolalar, qonunlar, internet manbalar\n"
                f"   ✓ Format: {cite_style} uslubida\n\n"
                "   Namuna:\n"
                "   1. Karimov I.A. O'zbekiston XXI asr bo'sag'asida. - T.: O'zbekiston, 2020. - 315 b.\n"
                "   2. Smith J. Digital Economy Trends. - London: Academic Press, 2023. - 245 p.\n"
                "   3. www.stat.uz - O'zbekiston Statistika qo'mitasi rasmiy sayti\n\n"
                "8️⃣ ILOVALAR (Appendices - agar kerak bo'lsa)\n"
                "   - Jadvallar\n"
                "   - Grafiklar\n"
                "   - So'rovnomalar\n"
                "   - Hujjatlar\n\n"
                "═══════════════════════════════════════════════════════════════\n"
                "TEXNIK TALABLAR:\n"
                "═══════════════════════════════════════════════════════════════\n"
                f"✓ Umumiy hajm: 25-40 bet (~{word_count}+ so'z)\n"
                "✓ Shrift: Times New Roman 14\n"
                "✓ Interval: 1.5\n"
                "✓ Margin: 2-2.5 sm (barcha tomondan)\n"
                "✓ Sahifa raqami: Pastki o'ng burchakda\n"
                "✓ Abzas: 1.25 sm\n"
                "✓ Format: Word (.docx), A4\n\n"
                "═══════════════════════════════════════════════════════════════\n"
                "MUHIM QOIDALAR:\n"
                "═══════════════════════════════════════════════════════════════\n"
                "❌ QILMANG:\n"
                "  - Internetdan to'g'ridan-to'g'ri ko'chirish\n"
                "  - Umumiy, noaniq gaplar ('Bu mavzu dolzarb')\n"
                "  - Eski adabiyotlar (faqat eski)\n"
                "  - Maqsadsiz kirish\n\n"
                "✅ QILING:\n"
                "  - Aniq va o'lchanuvchi fikrlar\n"
                "  - Ilmiy uslubda yozish\n"
                "  - Zamonaviy manbalardan foydalanish\n"
                "  - Jadval va grafiklar bilan boyitish\n"
                "  - Har bir fikrni manba bilan asoslash\n"
            )


        if doc_type == "thesis":
            return (
                "Tezis tayyorla. Hajm: 750-1250 so'z (3-5 bet, mavzudan kelib chiqib).\n"
                "Struktura qattiq rioya qilinishi kerak va BARCHA bo'limlarni to'liq yoz:\n\n"
                "1. Annotatsiya (muammo va natijalar qisqa, 100-150 so'z).\n"
                "2. Kirish (mavzuning dolzarbligi va maqsad).\n"
                "3. Asosiy qism (tezislar shaklida: muammo tahlili, metod, natijalar, 3-5 asosiy punkt).\n"
                "4. Xulosa (yakuniy fikrlar va takliflar).\n"
                "5. Kalit so'zlar (5-8 ta) va foydalanilgan adabiyotlar (5-10 manba, raqamlangan: 1. 2. 3.).\n\n"
                "Qattiq rioya qil: 1250 so'zdan oshmasin, lekin barcha bo'limlarni to'liq saqla.\n"
                "Har bir bo'limni mutanosib taqsimla: Asosiy qism 50-60% hajm.\n"
                "Konferensiya uchun mos, qisqa va aniq yoz.\n"
                "Hech qaysi bo'limni o'tkazib yuborma.\n"
                "Faqat HOZIRGI so'ralgan bo'limni yoz, boshqasini yozMA.\n"
                "SARLAVHALAR tanlangan tilda bo'lsin.\n"
            )

        if doc_type == "independent":
            return (
                "MUSTAQIL ISH (Akademik format):\n\n"
                "1. Kirish (Mavzuning dolzarbligi)\n"
                "2. Asosiy qism (Mavzu mazmunini ochib berish, 2-3 ta tahliliy bo'lim)\n"
                "3. Xulosa (O'z fikri va xulosalari)\n"
                "4. Foydalanilgan adabiyotlar (5-10 ta, raqamlangan: 1. 2. 3. Maksimum 10 ta!)\n\n"
                "TALABLAR: Tushunarli, akademik tilda, mavzuni to'liq yoritgan holda yozing.\n"
            )

        if doc_type in ("diploma", "dissertation"):
            return (
                f"{doc_type.upper()} (YUQORI ILMIY DARAJA):\n\n"
                "1. Kirish (Muammo, Maqsad, Vazifalar, Yangilik, Amaliy qiymat)\n"
                "2. Nazariy Bob (Chuqur adabiyotlar tahlili)\n"
                "3. Tahliliy Bob (Statistik va amaliy tahlil)\n"
                "4. Takliflar Bobi (Yangi yechimlar va tavsiyalar)\n"
                "5. Xulosa va Foydalanilgan adabiyotlar (5-10 ta, raqamlangan: 1. 2. 3. Maksimum 10 ta!)\n\n"
                "TALABLAR: O'ta yuqori akademik daraja, original tadqiqot.\n"
            )

        if doc_type == "manual":
             return (
                "O'QUV QO'LLANMA (Darslik formati):\n\n"
                "1. Mavzuga kirish va uslubiyot\n"
                "2. Nazariy tushuntirish va misollar\n"
                "3. Nazorat savollari va topshiriqlar\n"
                "4. Tavsiya etilgan adabiyotlar (5-10 ta, raqamlangan: 1. 2. 3. Maksimum 10 ta!)\n\n"
                "TALABLAR: Pedagogik uslubda, sodda va tushunarli tilda, o'quvchi uchun foydali bo'lishi kerak.\n"
            )

        if doc_type == "taqdimot":
            return (
                f"TAQDIMOT (PowerPoint formati - {length} slayd):\n\n"
                "═══════════════════════════════════════════════════════════════\n"
                "SLAYDLAR TUZILISHI (8-15 slayd):\n"
                "═══════════════════════════════════════════════════════════════\n\n"
                "MAJBURIY SLAYDLAR:\n\n"
                "1️⃣ SARLAVHA SLAYDI (Title slide)\n"
                "   - Mavzu nomi\n"
                "   - Talaba F.I.Sh va guruhi\n"
                "   - Ilmiy rahbar\n"
                "   - OTM nomi\n"
                "   - Yil\n\n"
                "2️⃣ REJA (Outline)\n"
                "   - Taqdimot rejalari (3-5 band)\n"
                "   - Qisqa va aniq\n\n"
                "3️⃣ DOLZARBLIK (Relevance)\n"
                "   - Nima uchun bu mavzu muhim?\n"
                "   - 3-4 ta bullet point\n"
                "   - Raqamlar yoki faktlar (agar bo'lsa)\n\n"
                "4️⃣ MAQSAD VA VAZIFALAR (Objectives & Tasks)\n"
                "   - Maqsad: 1 ta aniq gap\n"
                "   - Vazifalar: 4-5 ta bullet\n\n"
                "5-7️⃣ ASOSIY QISM (Main content - 3-6 slayd)\n"
                "   Har slayd:\n"
                "   - Aniq sarlavha\n"
                "   - 4-6 ta bullet point YOKI\n"
                "   - 1 ta jadval/sxema/grafik\n"
                "   - Minimal matn, maksimal vizual\n\n"
                "   Tavsiya etiladigan slaydlar:\n"
                "   • Nazariy asoslar (sxema bilan)\n"
                "   • Hozirgi holat tahlili (jadval/grafik)\n"
                "   • Muammolar (diagramma)\n"
                "   • Yechimlar (sxema)\n\n"
                "8️⃣ NATIJALAR (Results)\n"
                "   - Asosiy topilmalar\n"
                "   - Raqamlar va foizlar\n"
                "   - Grafik yoki jadval\n\n"
                "9️⃣ XULOSA (Conclusion)\n"
                "   - 3-4 ta asosiy xulosa\n"
                "   - Tavsiyalar\n"
                "   - Kelajak istiqbollari\n\n"
                "🔟 RAHMAT SLAYDI (Thank you slide)\n"
                "   - 'E'tiboringiz uchun rahmat!'\n"
                "   - Savollar uchun tayyorman\n"
                "   - Kontakt ma'lumotlari (email)\n\n"
                "═══════════════════════════════════════════════════════════════\n"
                "DIZAYN TALABLARI:\n"
                "═══════════════════════════════════════════════════════════════\n\n"
                "✓ SHRIFT:\n"
                "  - Sarlavha: 32-36\n"
                "  - Matn: 24-28\n"
                "  - Turi: Arial, Calibri, Times New Roman\n\n"
                "✓ RANG SXEMASI:\n"
                "  - Fon: Och ranglar (oq, och ko'k, och kulrang)\n"
                "  - Matn: To'q ranglar (qora, to'q ko'k)\n"
                "  - Kontrast: Yuqori (o'qish oson bo'lishi uchun)\n"
                "  ❌ Xato: Qizil fonda yashil matn\n"
                "  ✅ To'g'ri: Oq fonda qora matn\n\n"
                "✓ MATN HAJMI:\n"
                "  - Har slaydda: 5-6 qator (maksimum)\n"
                "  - Har qatorda: 6-8 so'z (maksimum)\n"
                "  - Qisqa jumla yoki bullet point\n"
                "  ❌ Xato: Uzun paragraflar\n"
                "  ✅ To'g'ri: Qisqa bullet points\n\n"
                "✓ VIZUAL ELEMENTLAR:\n"
                "  - Rasmlar: Sifatli, mazmunli\n"
                "  - Jadvallar: Oddiy, tushunarli\n"
                "  - Grafiklar: Rangli, izohli\n"
                "  - Sxemalar: Aniq, mantiqiy\n"
                "  - Animatsiya: Minimal (chalg'itmasin)\n\n"
                "═══════════════════════════════════════════════════════════════\n"
                "HAR SLAYD FORMATI:\n"
                "═══════════════════════════════════════════════════════════════\n\n"
                "--- SLAYD X: [Sarlavha] ---\n\n"
                "SLAYDDA KO'RSATILADIGAN MATN:\n"
                "• Birinchi asosiy fikr\n"
                "• Ikkinchi asosiy fikr\n"
                "• Uchinchi asosiy fikr\n"
                "• [Agar kerak bo'lsa: jadval/grafik tavsifi]\n\n"
                "SPEAKER NOTES (Nutq uchun - 50-80 so'z):\n"
                "[Bu yerda siz slaydni tushuntirishda aytadigan batafsil matnni yozing. "
                "Bu matn slaydda ko'rinmaydi, lekin sizga taqdimot paytida yordam beradi. "
                "Har bir bullet pointni kengaytiring, misollar keltiring, raqamlarni tushuntiring.]\n\n"
                "═══════════════════════════════════════════════════════════════\n"
                "MUHIM QOIDALAR:\n"
                "═══════════════════════════════════════════════════════════════\n\n"
                "❌ QILMANG:\n"
                "  - Ko'p matn yozish\n"
                "  - Mayda shrift ishlatish\n"
                "  - Dizaynsiz oddiy slaydlar\n"
                "  - Faqat matn, vizual yo'q\n"
                "  - Ortiqcha animatsiya\n\n"
                "✅ QILING:\n"
                "  - Qisqa va lo'nda\n"
                "  - Sxema, jadval, grafik qo'shing\n"
                "  - Har slayd bitta g'oya\n"
                "  - Professional dizayn\n"
                "  - Speaker notes yozing\n"
                "  - Vizual elementlar bilan boyiting\n\n"
                "ESLATMA: Slaydda faqat asosiy fikrlar, batafsil tushuntirish speaker notes da!\n"
            )

        if doc_type == "rewrite":
            return f"REWRITE: akademik parafraza, mazmun saqlansin. Hajm {word_count}+ so'z."

        return f"AKADEMIK MATN: {word_count}+ so'z. Iqtibos: {cite_style}"


# Singleton
ai_service = AIService()
