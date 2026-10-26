import re
from collections import Counter

BULLET_CHARS = "•●▪■◦○‣∙·➢➤✓✔►–—*"
_PAGE_NUM_RE = re.compile(r"^(page\s*)?\d+(\s*(of|/)\s*\d+)?$", re.IGNORECASE)
_BULLET_RE = re.compile(rf"^[{re.escape(BULLET_CHARS)}]\s*(?=\S)")
_LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"}


def _strip_repeated_lines(pages: list[list[str]]) -> list[list[str]]:
    """Drop short lines that appear on most pages (running headers/footers) and page numbers."""
    if len(pages) >= 3:
        counts: Counter[str] = Counter()
        for lines in pages:
            counts.update({ln.lower() for ln in lines if ln and len(ln) <= 80})
        threshold = max(3, len(pages) // 2 + 1)
        repeated = {ln for ln, n in counts.items() if n >= threshold}
    else:
        repeated = set()
    return [
        [ln for ln in lines if not _PAGE_NUM_RE.match(ln) and ln.lower() not in repeated]
        for lines in pages
    ]


def clean_pages(pages: list[str]) -> str:
    cleaned_pages: list[list[str]] = []
    for page in pages:
        for src, dst in _LIGATURES.items():
            page = page.replace(src, dst)
        page = page.replace(" ", " ").replace("\r\n", "\n").replace("\r", "\n")
        lines = []
        for raw in page.split("\n"):
            line = re.sub(r"[ \t]+", " ", raw).strip()
            line = _BULLET_RE.sub("- ", line)
            lines.append(line)
        cleaned_pages.append(lines)

    cleaned_pages = _strip_repeated_lines(cleaned_pages)
    text = "\n".join("\n".join(lines) for lines in cleaned_pages)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
