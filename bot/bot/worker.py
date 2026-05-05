from __future__ import annotations

import asyncio
import re
import secrets
import traceback
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from typing import Optional, Callable, Any

from aiogram import Bot
from aiogram.types import FSInputFile

from .config import SETTINGS, logger
from .database import AsyncSessionLocal, DB, Request
from .services.ai_service import ai_service
from .services.export_service import export_service
from .utils.helpers import html_escape, get_progress_bar, slugify
from .utils.structures import get_structure_for_type, get_presentation_sections
from .queue_manager import AI_QUEUE


# ----------------------------
# Tunables (from SETTINGS)
# ----------------------------
AI_TIMEOUT_SEC = getattr(SETTINGS, "ai_timeout_sec", 240)
EXPORT_TIMEOUT_SEC = getattr(SETTINGS, "export_timeout_sec", 60)
MAX_RETRIES = getattr(SETTINGS, "max_retries", 2)
RETRY_BACKOFF_SEC = getattr(SETTINGS, "retry_backoff_sec", 2)

RESULTS_CHANNEL = getattr(SETTINGS, "results_channel", None)
RESULTS_CHANNEL_URL = getattr(SETTINGS, "results_channel_url", "")
ADMIN_IDS = list(getattr(SETTINGS, "admin_ids", []))

# Active tasks — for cancellation support
_active_tasks: dict[int, asyncio.Task] = {}


def cancel_request_task(req_id: int) -> bool:
    """Cancel a running request task. Returns True if task was found and cancelled."""
    task = _active_tasks.get(req_id)
    if task and not task.done():
        task.cancel()
        return True
    return False


# ----------------------------
# Helpers
# ----------------------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def make_dl_link(bot_username: str, token: str) -> str:
    u = quote((bot_username or "").strip().lstrip("@"), safe="")
    t = quote(token or "", safe="")
    return f"https://t.me/{u}?start=dl_{t}"


def _generate_cell_value(header: str) -> str:
    """Generate realistic placeholder value based on column header."""
    import random
    h = (header or "").lower()
    # M±SD format
    if "m±" in h or "m+" in h or "(m" in h or "sd" in h:
        if "sm" in h or "(cm" in h or "uzunlik" in h or "balandlik" in h:
            base = random.uniform(150, 200)
            sd = random.uniform(5, 15)
            return f"{base:.1f}±{sd:.1f}"
        if "soni" in h or "marta" in h or "rep" in h:
            base = random.uniform(15, 35)
            sd = random.uniform(2, 6)
            return f"{base:.1f}±{sd:.1f}"
        if "min" in h or "daqiqa" in h:
            return f"{random.randint(3,7)}:{random.randint(10,55):02d}±0:{random.randint(10,40):02d}"
        # Default time in seconds
        base = random.uniform(5, 25)
        sd = random.uniform(0.3, 3)
        return f"{base:.2f}±{sd:.2f}"
    # Percentage
    if "%" in h or "o'sish" in h or "ozgarish" in h or "o'zgarish" in h or "din" in h or "natija" in h:
        sign = random.choice(["+", "-", "+"])
        return f"{sign}{random.uniform(2, 25):.1f}%"
    # p-value
    if h.strip() == "p" or "p-" in h or "p (" in h or "mezon" in h or "ahamiy" in h or "signif" in h:
        return random.choice(["<0.05", "<0.01", ">0.05", "<0.001"])
    # t-criterion
    if "t-" in h or "t mezon" in h:
        return f"{random.uniform(1.5, 4.5):.2f}"
    # Group columns - shouldn't be empty but just in case
    if "guruh" in h or "group" in h:
        return random.choice(["Tajriba", "Nazorat"])
    # Default: numeric value
    return f"{random.uniform(10, 100):.1f}"


async def _fix_empty_table_cells(content: str, topic: str, language: str) -> str:
    """Detect markdown tables with empty cells and fill them."""
    lines = content.split("\n")
    result_lines = []
    i = 0

    while i < len(lines):
        ln = lines[i]
        # Detect start of table: line with multiple pipes
        if "|" in ln and ln.count("|") >= 2:
            # Collect all consecutive table lines
            table_lines = []
            j = i
            while j < len(lines) and ("|" in lines[j] and lines[j].strip()):
                table_lines.append(lines[j])
                j += 1

            if len(table_lines) >= 2:
                # Find separator row index
                sep_idx = -1
                for idx, tl in enumerate(table_lines):
                    if re.match(r"^[ \t]*\|?[\-\|\s:]+\|?[ \t]*$", tl.strip()) and "-" in tl:
                        sep_idx = idx
                        break

                # Get header cells
                header_cells = []
                if sep_idx >= 1:
                    header_cells = [c.strip() for c in table_lines[sep_idx - 1].strip("|").split("|")]
                elif table_lines:
                    header_cells = [c.strip() for c in table_lines[0].strip("|").split("|")]

                num_cols = len(header_cells)
                start_data = max(1, sep_idx + 1) if sep_idx >= 0 else 1

                # Fill empty cells programmatically — pad short rows to match header width
                empty_count = 0
                total_data_cells = 0
                for idx in range(start_data, len(table_lines)):
                    tl = table_lines[idx]
                    cells = [c.strip() for c in tl.strip("|").split("|")]
                    # Pad with empty strings if row is shorter than header
                    while len(cells) < num_cols:
                        cells.append("")
                    # Truncate if longer (rare)
                    cells = cells[:num_cols]
                    new_cells = []
                    for c_idx, c in enumerate(cells):
                        total_data_cells += 1
                        if not c:
                            empty_count += 1
                            header = header_cells[c_idx] if c_idx < len(header_cells) else ""
                            new_cells.append(_generate_cell_value(header))
                        else:
                            new_cells.append(c)
                    table_lines[idx] = "| " + " | ".join(new_cells) + " |"

                logger.info(f"Table: {len(table_lines)} rows, filled {empty_count}/{total_data_cells} empty cells")
                has_empty = False  # already filled programmatically

                if has_empty:
                    logger.info("Regenerating table with AI...")
                    table_text = "\n".join(table_lines)
                    # Try up to 2 times
                    for attempt in range(2):
                        try:
                            fix_prompt = (
                                f"You are a research data assistant. Topic: {topic}\n\n"
                                f"TASK: Below is a markdown table with EMPTY cells. "
                                f"You MUST fill EVERY single empty cell with realistic numeric research data.\n\n"
                                f"RULES:\n"
                                f"1. Use M±SD format for measurements (e.g., 5.84±0.31, 175.3±8.2)\n"
                                f"2. Use percentages for change (+15.2%, -8.7%)\n"
                                f"3. Use p-values for significance (<0.05, <0.01, >0.05)\n"
                                f"4. Numbers must be realistic for the topic context\n"
                                f"5. NEVER leave any cell empty — every cell MUST have a value\n"
                                f"6. Keep exact same column structure and row count\n"
                                f"7. Output ONLY the markdown table, no extra text, no explanation\n\n"
                                f"INPUT TABLE (with empty cells):\n{table_text}\n\n"
                                f"FILLED TABLE (all cells filled with numbers):"
                            )
                            fixed = await ai_service._call_ai(fix_prompt, temperature=0.6)
                            logger.info(f"AI fix attempt {attempt+1}: {fixed[:300]}")

                            fixed_lines = [l for l in fixed.split("\n") if "|" in l and l.count("|") >= 2]

                            # Validate: check if fixed table still has empty cells
                            still_empty = False
                            sep_idx2 = -1
                            for idx, fl in enumerate(fixed_lines):
                                if re.match(r"^[ \t]*\|?[\-\|\s:]+\|?[ \t]*$", fl.strip()) and "-" in fl:
                                    sep_idx2 = idx
                                    break
                            start2 = max(1, sep_idx2 + 1) if sep_idx2 >= 0 else 1
                            empty2 = 0
                            total2 = 0
                            for fl in fixed_lines[start2:]:
                                cells = [c.strip() for c in fl.strip("|").split("|")]
                                for c in cells:
                                    total2 += 1
                                    if not c:
                                        empty2 += 1
                            if total2 > 0 and empty2 / total2 > 0.1:
                                still_empty = True

                            if fixed_lines and len(fixed_lines) >= 2 and not still_empty:
                                logger.info(f"Table filled successfully with {len(fixed_lines)} rows")
                                result_lines.extend(fixed_lines)
                                i = j
                                break
                            else:
                                logger.warning(f"Attempt {attempt+1}: still empty ({empty2}/{total2})")
                        except Exception as e:
                            logger.warning(f"Table fix attempt {attempt+1} failed: {e}")
                    else:
                        # Both attempts failed, keep original
                        result_lines.extend(table_lines)
                        i = j
                        continue
                    continue

                result_lines.extend(table_lines)
                i = j
                continue

        result_lines.append(ln)
        i += 1

    return "\n".join(result_lines)


def use_sectional_generation(doc_type: str, length_val: int) -> bool:
    """Decides whether to generate the document page-by-page or in a single AI call."""
    if doc_type in ("article", "thesis", "coursework", "diploma", "dissertation", "manual", "independent", "taqdimot"):
        return True
    return length_val >= 2


async def safe_edit(status_msg, text: str) -> None:
    if not status_msg: return
    with suppress(Exception):
        await status_msg.edit_text(text, parse_mode="HTML")


async def safe_delete(msg) -> None:
    if not msg: return
    with suppress(Exception):
        await msg.delete()


async def retry_async(fn: Callable[..., Any], *args, timeout_sec: int, retries: int = MAX_RETRIES, **kwargs):
    last_exc: Optional[BaseException] = None
    for attempt in range(retries + 1):
        try:
            return await asyncio.wait_for(fn(*args, **kwargs), timeout=timeout_sec)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            last_exc = e
            if attempt >= retries: break
            backoff = RETRY_BACKOFF_SEC * (2 ** attempt)
            logger.warning("Retrying %s in %ss (attempt %s/%s): %s", fn.__name__, backoff, attempt+1, retries, e)
            await asyncio.sleep(backoff)
    raise last_exc


def parse_plan_sections(plan_text: str, length_str: str = "1", doc_type: str = "") -> list[str]:
    lines = [ln.strip() for ln in (plan_text or "").splitlines()]
    sections: list[str] = []
    try: total_pages = int(length_str or 1)
    except Exception as e:
        logger.error(f"Error parsing total_pages in parse_plan_sections: {e}")
        total_pages = 1
    # Raqamlar (1. 2.1.) + Bob/Глава/Chapter (I.Bob. II.Глава. Chapter I.)
    pattern = re.compile(r"^(\d+(\.\d+)*\.?|[IVX]+\.\s*[Bb]ob\.?|[IVX]+\.\s*[Гг]лав\w*\.?|Chapter\s+[IVX]+\.?|[\-\*\u2022])\s+(.*)")
    # Kurs ishi va diploma uchun sub-seksiyalar (2.1, 2.2) har doim kerak
    allow_subsections = doc_type in ("coursework", "diploma", "dissertation")
    for ln in lines:
        if not ln: continue
        match = pattern.match(ln)
        if match:
            num = match.group(1)
            if not allow_subsections and total_pages < 10 and "." in num.rstrip("."):
                continue
            sections.append(ln)
    if not sections and any(len(ln) > 10 for ln in lines):
        for ln in lines:
            if 5 < len(ln) < 100: sections.append(ln)
    return sections


def _strip_leading_heading(content: str, section_name: str, doc_title: str = "") -> str:
    """Remove duplicate heading / document title at the start of AI-generated content.

    The AI sometimes prepends lines like:
        Zamonaviy xesh funksiyalarini qurish usullarining tahlili   ← doc title
        Kirish                                                       ← section name
        <actual content>
    Or rephrased variants of the title. This function strips up to 4 such lines.
    """
    import re

    def _normalize(text: str) -> str:
        t = re.sub(r"^#{1,4}\s*", "", text.strip())      # strip markdown headings
        t = re.sub(r"^\d+(\.\d+)*\.?\s*", "", t)          # strip numbering
        t = re.sub(r"[*_`\"']", "", t)                     # strip bold/italic markers
        return t.strip().lower()

    def _words(text: str) -> set:
        return set(re.findall(r"[a-zA-Zа-яА-ЯёЁўЎқҚғҒҳҲo']+", text.lower()))

    section_norm = _normalize(section_name)
    title_norm = _normalize(doc_title) if doc_title else ""
    title_words = _words(title_norm) if title_norm else set()

    def _is_junk_line(line: str) -> bool:
        norm = _normalize(line)
        if not norm:
            return True  # blank line
        # matches the section name
        if section_norm and (
            norm == section_norm
            or section_norm.startswith(norm)
            or norm.startswith(section_norm)
        ):
            return True
        # matches the document title (exact or prefix)
        if title_norm and (
            norm == title_norm
            or title_norm.startswith(norm)
            or norm.startswith(title_norm)
        ):
            return True
        # fuzzy: if line shares 50%+ words with the title, it's a rephrased title
        if title_words and len(title_words) >= 3:
            line_words = _words(norm)
            overlap = title_words & line_words
            if len(overlap) >= len(title_words) * 0.5 and len(line_words) <= len(title_words) * 2:
                return True
        return False

    lines = content.lstrip("\n").split("\n")
    stripped = 0
    # Strip at most 4 leading junk lines (title + heading + possible blanks)
    while stripped < 4 and stripped < len(lines) and _is_junk_line(lines[stripped]):
        stripped += 1

    if stripped == 0:
        return content
    return "\n".join(lines[stripped:]).lstrip("\n")


async def process_one_request(req_id: int, bot: Bot):
    """Processes a single AI request with full lifecycle management."""
    user_id = 0
    status_msg = None
    
    try:
        async with AsyncSessionLocal() as session:
            db_req = await DB.get_request(session, req_id)
            if not db_req or db_req.status != "queued":
                await AI_QUEUE.ack(req_id)
                return
            
            # Lock the request
            db_req.status = "processing"
            db_req.locked_at = now_utc()
            user_id = db_req.user_id
            await session.commit()

        # 1. Initialization
        language = db_req.language or "uz"
        # uz_lat / uz_cyr → uz (AI faqat uz/en/ru biladi)
        if language.startswith("uz"):
            language = "uz"
        doc_type = db_req.doc_type
        title_clean = db_req.title or "Hujjat"
        length_str = db_req.length or "1"
        cite_style = db_req.citation_style or "APA"
        meta = db_req.meta_json or {}
        meta["language"] = language  # export_service uchun til ma'lumoti

        status_msg = await bot.send_message(
            user_id, 
            f"🚀 <b>Buyurtmangiz boshlandi!</b>\n"
            f"Mavzu: <code>{html_escape(title_clean)}</code>\n\n"
            f"[{get_progress_bar(0)}] 0%",
            parse_mode="HTML"
        )
        
        # 2. Plan Generation
        await safe_edit(status_msg, f"📝 <b>Reja tuzilmoqda...</b>\n[{get_progress_bar(10)}] 10%")
        
        custom_plan = db_req.custom_structure
        if custom_plan and len(custom_plan.strip()) > 10:
            logger.info(f"Using custom structure for request #{req_id}")
            plan_text = custom_plan
        else:
            plan_text = await retry_async(ai_service.generate_plan, title_clean, doc_type, int(length_str or 1), lang=language, timeout_sec=AI_TIMEOUT_SEC)
        
        # Add special requirements to metadata if present
        if db_req.requirements_text:
            meta["special_requirements"] = db_req.requirements_text
        
        # 3. Content Generation
        full_content = ""
        sections = parse_plan_sections(plan_text, length_str, doc_type=doc_type)
        total = len(sections)
        
        if total > 0 and use_sectional_generation(doc_type, int(length_str or 1)):
            # Foundation
            foundation = await retry_async(ai_service.get_research_foundation, title_clean, language, timeout_sec=AI_TIMEOUT_SEC)
            
            # --- Oddiy bet-asosli budjet ---
            # 14pt Times New Roman + 1.5 interval = ~250 so'z/bet DOCX da
            WPP = 230  # words per page (real DOCX capacity with 14pt + 1.5 spacing + headings)
            pages = int(length_str or 1)
            # Titul sahifa + Mundarija = 2 bet overhead (article/thesis/taqdimot da yo'q)
            if doc_type in ("article", "thesis", "taqdimot"):
                content_pages = pages
            else:
                content_pages = max(1, pages - 2)  # title page + TOC
            total_target_words = content_pages * WPP
            target_range_str = str(total_target_words)

            for i, section_name in enumerate(sections, 1):
                s_low = section_name.lower()

                if doc_type == "article":
                    # Maqola: 7 bo'lim (article has no title page/TOC overhead)
                    is_annot = any(x in s_low for x in ["annotatsiya", "abstract", "аннотац"])
                    is_kw = any(x in s_low for x in ["kalit", "keyword", "ключев"])
                    is_refs = ("foydalanilgan" in s_low and "adabiyot" in s_low) or s_low.strip().startswith("references") or ("список" in s_low and "литератур" in s_low) or ("adabiyot" in s_low and "tahlil" not in s_low)

                    if is_kw:
                        current_target = 35  # kalit so'zlar: faqat 8-12 ta so'z, word count bosimi bo'lmasin
                    elif is_annot:
                        current_target = int(min(1.0, content_pages * 0.1) * WPP)
                    elif is_refs:
                        current_target = int(min(1.0, content_pages * 0.1) * WPP)
                    else:
                        fixed = min(1.0, content_pages * 0.1) + 0.5 + min(1.0, content_pages * 0.1)
                        normal_pages = (content_pages - fixed) / 4
                        current_target = int(normal_pages * WPP)

                elif doc_type == "thesis":
                    # Tezis: 5 bo'lim — jami 5-6 bet bo'lishi kerak
                    is_kw = any(x in s_low for x in ["kalit", "keyword", "ключев"])
                    is_xulosa = any(x in s_low for x in ["xulosa", "conclu", "заключ"])
                    is_asosiy = any(x in s_low for x in ["asosiy", "main", "основн"])
                    if is_kw or is_xulosa:
                        current_target = int(0.3 * WPP)  # ~0.3 bet
                    elif is_asosiy:
                        current_target = int(1.5 * WPP)  # ~1.5 bet
                    else:
                        current_target = int(0.6 * WPP)  # ~0.6 bet

                elif doc_type == "coursework":
                    # Kurs ishi: Bob struktura
                    is_kirish = any(x in s_low for x in ["kirish", "intro", "введен"])
                    is_xulosa = any(x in s_low for x in ["xulosa", "conclu", "заключ"])
                    is_refs = ("adabiyot" in s_low and "tahlil" not in s_low) or \
                              s_low.strip().startswith("references") or \
                              ("список" in s_low and "литератур" in s_low) or \
                              ("foydalanilgan" in s_low)
                    is_bob = any(x in s_low for x in ["bob.", "глав", "chapter "])
                    is_subsection = bool(re.match(r'^\d+\.\d+', s_low.strip()))

                    if is_refs:
                        current_target = int(0.5 * WPP)  # adabiyotlar ~0.5 bet
                    elif is_kirish:
                        current_target = int(1.0 * WPP)  # kirish ~1 bet
                    elif is_xulosa:
                        current_target = int(1.0 * WPP)  # xulosa ~1 bet
                    elif is_bob:
                        current_target = int(0.8 * WPP)  # bob kirish ~0.8 bet
                    elif is_subsection:
                        # Kichik bo'limlar — qolgan betlarni teng taqsimlash
                        num_subs = sum(1 for s in sections if re.match(r'^\d+\.\d+', s.strip()))
                        num_bobs = sum(1 for s in sections if any(x in s.lower() for x in ["bob.", "глав", "chapter "]))
                        fixed_pages = 1.0 + 1.0 + 0.5 + (num_bobs * 0.8)  # kirish + xulosa + refs + bob intros
                        remaining = max(1, content_pages - fixed_pages)
                        per_sub = remaining / max(1, num_subs)
                        current_target = int(per_sub * WPP)
                    else:
                        current_target = int(total_target_words / total)

                else:
                    current_target = int(total_target_words / total)
                
                await safe_edit(status_msg, f"✍️ <b>{html_escape(section_name)}</b> yozilmoqda...\n[{get_progress_bar(10 + int(i/total * 60))}] {10 + int(i/total * 60)}%")
                
                # Phase 2: Memory Guard Rail for large docs
                if len(full_content) > 100000:
                    logger.warning(f"Large document detected ({len(full_content)} chars). Trimming context for next section.")
                    context_summary = full_content[-10000:]
                else:
                    context_summary = full_content[-8000:] if len(full_content) > 8000 else full_content
                
                context_plus = f"FOUNDATION: {foundation.get('core_question')}\nCONTEXT:\n{context_summary}\nTARGET_RANGE: {target_range_str}"
                
                sect_content = await retry_async(
                    ai_service.generate_section,
                    title_clean, section_name, context_plus, doc_type, cite_style, language,
                    target_words=current_target, section_index=i, total_sections=total, meta=meta,
                    timeout_sec=AI_TIMEOUT_SEC
                )
                
                if doc_type == "taqdimot":
                    full_content += f"\n\n--- SLAYD {i}: {section_name} ---\n{sect_content}"
                else:
                    # Strip duplicate heading / title from AI response
                    cleaned = _strip_leading_heading(sect_content, section_name, doc_title=title_clean)
                    # Kurs ishi: subseksiyalar ### (Heading 3), qolganlari ## (Heading 2)
                    if doc_type == "coursework" and re.match(r'^\d+\.\d+', section_name.strip()):
                        full_content += f"\n\n### {section_name}\n\n{cleaned}"
                    else:
                        full_content += f"\n\n## {section_name}\n\n{cleaned}"

                # Progress update in DB
                async with AsyncSessionLocal() as session:
                    upd_req = await DB.get_request(session, req_id)
                    if upd_req:
                        upd_req.current_step = i
                        await session.commit()
        else:
            # Single pass
            full_content = await retry_async(ai_service.generate_content, title_clean, doc_type, language, cite_style, int(length_str or 1), timeout_sec=AI_TIMEOUT_SEC)

        # 3.5 Clean AI artifacts from content
        full_content = re.sub(r'WORD\s*COUNT\s*REPORT:.*?(?=\n\n|\Z)', '', full_content, flags=re.IGNORECASE | re.DOTALL)
        full_content = re.sub(r'(Total\s+words.*?Status:\s*\w+)', '', full_content, flags=re.IGNORECASE | re.DOTALL)

        # 3.6 Fix tables with empty cells (AI sometimes leaves cells blank)
        if doc_type == "article":
            full_content = await _fix_empty_table_cells(full_content, title_clean, language)

        # 4. Critique & Finalize with Validation
        if doc_type != "taqdimot":
            # Save section headings before critique (AI may strip ## markers)
            _heading_lines = [ln.strip() for ln in full_content.splitlines() if re.match(r'^#{1,3}\s+', ln.strip())]

            await safe_edit(status_msg, f"🔍 <b>Tahrir va tekshirish...</b>\n[{get_progress_bar(85)}] 85%")
            try:
                full_content = await retry_async(
                    ai_service.critique_content,
                    full_content,
                    lang=language,
                    target_pages=int(length_str or 1),
                    timeout_sec=AI_TIMEOUT_SEC
                )
            except (TimeoutError, Exception) as e:
                logger.warning(f"Critique skipped (timeout/error): {e}")

            # Restore ## heading markers if critique stripped them
            if _heading_lines:
                for h_line in _heading_lines:
                    # Extract the heading text without ## prefix
                    h_text = re.sub(r'^#{1,3}\s+', '', h_line).strip()
                    if not h_text:
                        continue
                    # Check if this heading lost its ## prefix after critique
                    # Look for the heading text as a standalone line without ## prefix
                    pattern = re.compile(
                        r'^(?!#)(\s*)(' + re.escape(h_text) + r')\s*$',
                        re.MULTILINE
                    )
                    # Only restore if the original ## heading is no longer present
                    if h_line not in full_content:
                        full_content = pattern.sub(h_line, full_content, count=1)

        # 5. Export
        await safe_edit(status_msg, f"📄 <b>Fayl tayyorlanmoqda...</b>\n[{get_progress_bar(95)}] 95%")
        out_dir = Path(SETTINGS.data_dir) / str(user_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{slugify(title_clean or 'doc')}_{req_id}.docx"
        if doc_type == "taqdimot": filename = filename.replace(".docx", ".pptx")
        file_path = out_dir / filename
        
        success = False
        if doc_type == "taqdimot":
            success = await retry_async(export_service.to_pptx, title_clean, full_content, file_path, meta=meta, slide_images={}, timeout_sec=EXPORT_TIMEOUT_SEC)
        else:
            success = await retry_async(export_service.to_docx, title_clean, full_content, file_path, doc_type=doc_type, meta=meta, timeout_sec=EXPORT_TIMEOUT_SEC)

        if success:
            # 6. Delivery
            me = await bot.get_me()
            token = secrets.token_urlsafe(16)
            expires_at = now_utc() + timedelta(days=1)
            dl_link = make_dl_link(me.username, token)
            
            # Delivery message
            caption = (
                f"✅ <b>Tayyor! #{req_id}</b>\n\n"
                f"📝 Mavzu: {html_escape(title_clean)}\n"
                f"🧬 Tur: <code>{doc_type.upper()}</code>\n"
                f"📏 Hajm: <code>{length_str} bet</code>\n"
                f"✒️ Uslub: <code>{(cite_style or 'none').upper()}</code>\n\n"
                f"🔗 <a href='{dl_link}'>Yuklab olish (Fayl)</a>\n"
                f"🤖 @{me.username}"
            )
            if RESULTS_CHANNEL_URL:
                caption += f"\n📢 <a href='{RESULTS_CHANNEL_URL}'>Bot natijalari kanali</a>"

            from .keyboards import get_feedback_keyboard
            await bot.send_document(
                user_id,
                FSInputFile(str(file_path)),
                caption=caption + "\n\n<i>Natija qanday bo'ldi? Baholang:</i>",
                parse_mode="HTML",
                reply_markup=get_feedback_keyboard(req_id)
            )
            await safe_delete(status_msg)

            # ─── Forward a copy to the results channel/group (audit log) ───
            if RESULTS_CHANNEL:
                with suppress(Exception):
                    user_label = f"<a href='tg://user?id={user_id}'>#{user_id}</a>"
                    audit_caption = (
                        f"📁 <b>Yangi natija — #{req_id}</b>\n\n"
                        f"👤 Foydalanuvchi: {user_label}\n"
                        f"📝 Mavzu: {html_escape(title_clean)}\n"
                        f"🧬 Tur: <code>{doc_type.upper()}</code>\n"
                        f"📏 Hajm: <code>{length_str} bet</code>\n"
                        f"⏱ Sana: {now_utc().strftime('%Y-%m-%d %H:%M UTC')}"
                    )
                    await bot.send_document(
                        RESULTS_CHANNEL,
                        FSInputFile(str(file_path)),
                        caption=audit_caption,
                        parse_mode="HTML",
                    )

            # 7. Mark Success in DB
            async with AsyncSessionLocal() as session:
                db_req = await DB.get_request(session, req_id)
                if db_req:
                    db_req.status = "done"
                    db_req.completed_at = now_utc()
                    db_req.result_path = str(file_path)
                    db_req.download_token = token
                    db_req.expires_at = expires_at
                    db_req.result_text = full_content[:1000]
                    await session.commit()
            
            await AI_QUEUE.ack(req_id)
        else:
            raise RuntimeError("Export failed")

    except asyncio.CancelledError:
        # User cancelled — clean up silently, don't send file
        logger.info(f"Request #{req_id} was cancelled by user.")
        await safe_delete(status_msg)
        await AI_QUEUE.ack(req_id)
        return
    except Exception as e:
        logger.error(f"Worker process error [Req {req_id}]: {e}", exc_info=True)
        async with AsyncSessionLocal() as session:
            err_req = await DB.get_request(session, req_id)
            if err_req:
                err_req.status = "error"
                err_req.error_log = str(e)
                await session.commit()
        
        if user_id:
            msg = "❌ <b>Texnik xatolik yuz berdi.</b>"
            if "Timeout" in str(e) or "deadline" in str(e).lower():
                msg = "⏱️ <b>AI javob berish vaqti tugadi.</b> Iltimos, qayta urinib ko'ring yoki mavzuni lo'ndaroq yozing."
            elif "Connection" in str(e) or "HTTP" in str(e):
                msg = "🌐 <b>Tarmoq xatoligi.</b> AI servisi bilan bog'lanib bo'lmadi. Birozdan so'ng qayta urinib ko'ring."
            elif "Rate limit" in str(e).lower():
                msg = "⏳ <b>Sorovlar soni cheklangan.</b> Iltimos, bir oz kutib keyin urinib ko'ring."
            
            with suppress(Exception):
                await bot.send_message(user_id, f"{msg}\n\nAgar muammo davom etsa, adminga murojaat qiling.")
        
        await AI_QUEUE.nack(req_id)

async def worker(bot: Bot):
    """Main worker loop."""
    logger.info("Worker started.")
    while True:
        try:
            req_id = await AI_QUEUE.get()
            if req_id:
                task = asyncio.create_task(process_one_request(req_id, bot))
                _active_tasks[req_id] = task
                task.add_done_callback(lambda t, rid=req_id: _active_tasks.pop(rid, None))
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            await asyncio.sleep(5)
