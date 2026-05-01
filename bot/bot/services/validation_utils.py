"""
Word Count Validation and Anti-Hallucination Utilities for AI Service
"""
import re
from typing import Dict, Tuple, Optional


def count_words(text: str) -> int:
    """
    Count words in text, excluding common markdown and formatting artifacts.
    """
    if not text:
        return 0
    
    # Remove markdown artifacts
    clean = re.sub(r'```[a-zA-Z]*\n?.*?```', '', text, flags=re.DOTALL)
    clean = re.sub(r'[#*_`~\[\]{}]', '', clean)
    clean = re.sub(r'https?://\S+', '', clean)  # Remove URLs
    
    # Count words
    words = clean.split()
    return len([w for w in words if len(w) > 0])


def extract_word_count_report(content: str) -> Optional[Dict[str, any]]:
    """
    Extract word count report from generated content.
    
    Returns dict with keys: total, target_min, target_max, status
    """
    pattern = r'WORD COUNT REPORT:.*?Total.*?:?\s*(\d+).*?Target.*?:?\s*(\d+)[–-](\d+).*?Status.*?:?\s*(PASS|FAIL)'
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
    
    if match:
        return {
            'total': int(match.group(1)),
            'target_min': int(match.group(2)),
            'target_max': int(match.group(3)),
            'status': match.group(4).upper()
        }
    return None


def validate_word_count(content: str, target_min: int, target_max: int) -> Tuple[bool, int, str]:
    """
    Validate if content meets word count requirements.
    
    Returns: (is_valid, actual_count, message)
    """
    # Try to extract from report first
    report = extract_word_count_report(content)
    if report:
        actual = report['total']
        is_valid = report['status'] == 'PASS'
        msg = f"AI Report: {actual} words ({report['status']})"
        return is_valid, actual, msg
    
    # Fallback: count manually
    actual = count_words(content)
    is_valid = target_min <= actual <= target_max
    status = "PASS" if is_valid else "FAIL"
    msg = f"Manual Count: {actual} words ({status}, target: {target_min}-{target_max})"
    
    return is_valid, actual, msg


def detect_hallucinated_data(content: str) -> list[str]:
    """
    Detect potentially hallucinated data in academic content.
    
    Returns list of warnings.
    """
    warnings = []
    
    # Check for suspiciously perfect p-values
    perfect_p = re.findall(r'p\s*[=<]\s*0\.0+1\b', content, re.IGNORECASE)
    if perfect_p:
        warnings.append(f"Suspicious perfect p-values found: {len(perfect_p)} instances")
    
    # Check for unrealistic sample sizes
    sample_sizes = re.findall(r'n\s*=\s*(\d+)', content, re.IGNORECASE)
    if sample_sizes:
        for n in sample_sizes:
            if int(n) > 100000:
                warnings.append(f"Unrealistically large sample size: n={n}")
    
    # Check for placeholder text
    placeholders = ['XXX', 'Lorem ipsum', 'Sample text', '...', '___']
    for ph in placeholders:
        if ph in content:
            warnings.append(f"Placeholder text detected: '{ph}'")
    
    # Check for AI chatter phrases
    ai_phrases = [
        "bu bo'limda", "mana maqola", "umid qilamanki", 
        "here is the", "I hope this", "as requested"
    ]
    for phrase in ai_phrases:
        if phrase.lower() in content.lower():
            warnings.append(f"AI chatter detected: '{phrase}'")
    
    return warnings


def validate_references(content: str) -> Tuple[bool, list[str]]:
    """
    Validate references section for common issues.
    
    Returns: (is_valid, warnings)
    """
    warnings = []
    
    # Extract references section
    ref_match = re.search(r'(REFERENCES|ADABIYOTLAR|СПИСОК ЛИТЕРАТУРЫ).*$', content, re.IGNORECASE | re.DOTALL)
    if not ref_match:
        return False, ["No references section found"]
    
    ref_section = ref_match.group(0)
    
    # Count references
    ref_count = len(re.findall(r'^\s*\d+\.', ref_section, re.MULTILINE))
    if ref_count < 5:
        warnings.append(f"Too few references: {ref_count} (minimum 5 recommended)")
    
    # Check for DOIs
    doi_count = len(re.findall(r'doi:', ref_section, re.IGNORECASE))
    if doi_count == 0:
        warnings.append("No DOI links found in references")
    
    # Check for recent years (2019-2025)
    years = re.findall(r'\b(20\d{2})\b', ref_section)
    recent_years = [y for y in years if 2019 <= int(y) <= 2025]
    if years and len(recent_years) / len(years) < 0.5:
        warnings.append(f"Less than 50% of references are recent (2019-2025)")
    
    is_valid = len(warnings) == 0
    return is_valid, warnings


def get_word_range_for_pages(pages: int, language: str = "uz") -> Tuple[int, int]:
    """
    Get word count range for given page count and language.
    
    Args:
        pages: Number of pages
        language: Language code (uz, ru, en)
    
    Returns:
        (min_words, max_words)
    """
    lang = language.lower()
    
    # DOCX real capacity: 14pt TNR + 1.5 spacing + headings ≈ 200-260 words/page
    min_per_page, max_per_page = 200, 260

    return pages * min_per_page, pages * max_per_page
