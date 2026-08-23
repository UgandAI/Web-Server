import re


def normalize_text(text: str) -> str:
    """Normalize whitespace while retaining paragraph boundaries."""
    paragraphs = [re.sub(r"\s+", " ", item).strip() for item in re.split(r"\n\s*\n", text)]
    return "\n\n".join(item for item in paragraphs if item)


def chunk_text(text: str, max_words: int = 180, overlap_words: int = 30) -> list[str]:
    """Create stable word-window chunks with bounded overlap."""
    if max_words <= 0 or overlap_words < 0 or overlap_words >= max_words:
        raise ValueError("max_words must be positive and overlap_words must be smaller")
    words = normalize_text(text).split()
    if not words:
        return []
    step = max_words - overlap_words
    chunks = []
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start : start + max_words]))
        if start + max_words >= len(words):
            break
    return chunks
