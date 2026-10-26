import re

# canonical section name -> heading variants (matched against a whole short line)
SECTION_ALIASES: dict[str, list[str]] = {
    "summary": ["summary", "professional summary", "profile", "objective", "career objective", "about me", "about"],
    "experience": ["experience", "work experience", "professional experience", "employment history", "work history", "employment"],
    "projects": ["projects", "personal projects", "key projects", "academic projects", "selected projects"],
    "skills": ["skills", "technical skills", "key skills", "core competencies", "technologies", "tech stack"],
    "education": ["education", "academic background", "qualifications", "academics"],
    "certifications": ["certifications", "certificates", "licenses", "courses"],
    "achievements": ["achievements", "awards", "honors", "accomplishments"],
    # job-description headings
    "responsibilities": ["responsibilities", "key responsibilities", "what you will do", "what you'll do", "duties", "role"],
    "requirements": ["requirements", "qualifications", "what we are looking for", "what we're looking for", "must have", "must-have", "required skills", "who you are"],
    "nice_to_have": ["nice to have", "nice-to-have", "preferred", "preferred qualifications", "bonus"],
    "benefits": ["benefits", "perks", "what we offer", "why join us"],
}
_LOOKUP = {alias: name for name, aliases in SECTION_ALIASES.items() for alias in aliases}


def _heading_name(line: str) -> str | None:
    candidate = re.sub(r"[:\-–—_=#*]+$", "", line.strip()).strip(" :#*").lower()
    if not candidate or len(candidate) > 40:
        return None
    return _LOOKUP.get(candidate)


def split_sections(text: str) -> list[dict[str, str]]:
    """Split text at recognised headings. Text before the first heading is 'header'.
    If nothing is recognised, return a single 'full_text' section."""
    sections: list[dict[str, str]] = []
    current_name = "header"
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            sections.append({"name": current_name, "text": body})

    found = False
    for line in text.split("\n"):
        name = _heading_name(line)
        if name:
            flush()
            current_name, buffer, found = name, [], True
        else:
            buffer.append(line)
    flush()

    if not found:
        return [{"name": "full_text", "text": text.strip()}] if text.strip() else []
    return sections
