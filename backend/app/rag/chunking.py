"""Splits source text into retrieval-sized chunks.

Markdown documentation is split on ## section headers first, so a chunk
never straddles two unrelated topics (e.g. "Known issues" never gets
merged into "What's in it"). Any section still longer than MAX_CHARS
after that is further split with a sliding window. This is a small
hand-rolled splitter rather than a library (e.g. langchain's text
splitters) because the source documents here are short (a few hundred
words) and a transparent, easily-explained implementation is more
valuable in a prototype than a general-purpose one.
"""
import re

MAX_CHARS = 800
OVERLAP_CHARS = 100

_HEADER_RE = re.compile(r"^#{1,6}\s+.*$", re.MULTILINE)


def _split_sections(text: str) -> list[str]:
    """Split markdown on headings, keeping each heading with its body."""
    matches = list(_HEADER_RE.finditer(text))
    if not matches:
        return [text]

    sections = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(preamble)

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append(text[start:end].strip())

    return [s for s in sections if s]


def _sliding_window(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = end - overlap
    return chunks


def chunk_text(text: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Chunk a document: split by markdown section, then by size."""
    chunks: list[str] = []
    for section in _split_sections(text.strip()):
        chunks.extend(_sliding_window(section, max_chars, overlap))
    return [c for c in chunks if c.strip()]
