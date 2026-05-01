from datetime import datetime
import html

def format_currency(amount: int, currency: str = "UZS") -> str:
    return f"{amount:,} {currency}"

def html_escape(text: str) -> str:
    """Safely escape text for Telegram HTML parse mode."""
    return html.escape(str(text))

def get_progress_bar(percentage: int, width: int = 10) -> str:
    """Create a visual progress bar string."""
    filled = int(width * percentage / 100)
    return "█" * filled + "░" * (width - filled)

def slugify(text: str) -> str:
    """Create a safe filename from text."""
    # Remove non-alphanumeric (except underscores) and replace spaces
    import re
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '_', text).strip('_')
    return text[:50] # Limit length

def get_uni_header(uni_code: str) -> str:
    headers = {
        "nuz": "O'ZBEKISTON MILLIY UNIVERSITETI\nFAKULTET: ________________\nGURUH: ________________",
        "tsue": "TOSHKENT DAVLAT IQTISODIYOT UNIVERSITETI\nFAKULTET: ________________\nGURUH: ________________",
        "tuit": "TOSHKENT AXBOROT TEXNOLOGIYALARI UNIVERSITETI\nKAFEDRA: ________________\nGURUH: ________________",
        "wiut": "WESTMINSTER INTERNATIONAL UNIVERSITY IN TASHKENT\nCOURSE: ________________\nID: ________________",
        "other": "OLIY TA'LIM, FAN VA INNOVATSIYALAR VAZIRLIGI\nOTM NOMI: ____________________"
    }
    return headers.get(uni_code, "TITUL VARAG'I")

def clean_markdown(text: str) -> str:
    return text.replace("**", "").replace("__", "").replace("#", "").strip()
