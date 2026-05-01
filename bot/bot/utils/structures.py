"""
Document structures and word count weightings based on the Enterprise System.
Values represent relative weights (hints) for sectional word count calculation.
Formula: section_words = int(total_words * weight / 100)
Note: Weights may sum to more than 100 to ensure high content density.
"""

DOCUMENT_STRUCTURES = {
    "article": [
        ("Abstract", 8),
        ("Keywords", 3),
        ("Introduction", 20),
        ("Literature Review and Methods", 28),
        ("Results and Discussion", 25),
        ("Conclusion", 8),
        ("References", 8),
    ],
    "coursework": [
        ("Sarlavha", 2),
        ("Reja", 5),
        ("Kirish (dolzarblik, maqsad, vazifalar, metodlar)", 15),
        ("1-bob: Nazariy asoslar", 25),
        ("2-bob: Tahlil yoki amaliy qism", 25),
        ("Xulosa", 10),
        ("Foydalanilgan adabiyotlar", 8),
    ],
    "independent": [
        ("Sarlavha", 5),
        ("Reja", 8),
        ("Kirish", 25),
        ("Mavzuning nazariy tahlili", 35),
        ("Amaliy ahamiyati va misollar", 35),
        ("Xulosa va takliflar", 15),
        ("Foydalanilgan adabiyotlar", 8),
    ],
    "thesis": [
        ("Annotatsiya", 15),
        ("Kirish", 20),
        ("Asosiy qism", 35),
        ("Xulosa", 15),
        ("Kalit so'zlar va adabiyotlar", 15),
    ],
}

def get_structure_for_type(doc_type: str, pages: int = 1) -> list[tuple[str, int]]:
    """Returns the list of (section_name, weight) for a given doc_type."""
    base = DOCUMENT_STRUCTURES.get(doc_type, DOCUMENT_STRUCTURES["independent"])
    
    # Conditional logic for coursework: 10-15 pages = add 3rd chapter
    if doc_type == "coursework" and pages >= 10:
        new_struct = base[:5] # Title, Plan, Intro, Ch1, Ch2
        new_struct.append(("3-bob: Tadqiqot natijalari va takliflar", 20))
        new_struct.extend(base[5:]) # Conclusion, Refs
        return new_struct
        
    return base

def get_presentation_sections(num_slides: int) -> list[tuple[str, int]]:
    """Generates a dynamic list of slides for a presentation."""
    # Ensure minimum 5 slides
    if num_slides < 5: 
        num_slides = 5
    
    # Fixed slides: Titul, Reja, Xulosa, Rahmat (4 slides)
    # Remaining: num_slides - 4
    
    sections = [
        ("Titul varag'i", 2), # Weight is for speaker notes target
        ("Reja", 5),
    ]
    
    # Core content slides calculation
    # We add 2 mandatory conceptual slides: Dolzarblik, Maqsad
    # Then the rest are "Core content" slides.
    
    sections.append(("Mavzuning dolzarbligi", 10))
    sections.append(("Maqsad va vazifalar", 10))
    
    core_count = num_slides - 6 # Titul, Reja, Dolzarblik, Maqsad, Xulosa, Rahmat
    
    if core_count > 0:
        for i in range(core_count):
            sections.append((f"{i+1}-asosiy bo'lim", 15))
    
    # Add a data/analysis slide if we have more than 7 slides total
    if num_slides > 7:
        # Swap one core slide for analysis if possible
        if core_count > 0:
            sections[-1] = ("Diagramma va tahlil (Jadval uchun)", 15)
        else:
            sections.append(("Diagramma va tahlil (Jadval uchun)", 15))

    sections.extend([
        ("Xulosa", 10),
        ("E'tiboringiz uchun rahmat", 2)
    ])
    
    # Final check: if we exceed num_slides due to logic, trim or adjust
    # Actually, the logic above is: 2 (start) + 2 (mand) + core_count + 2 (end) = 6 + core_count
    # Since core_count = num_slides - 6, the total is exactly num_slides.
    
    return sections[:num_slides]
