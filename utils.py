import re


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks by approximate token count (1 token ≈ 4 chars)."""
    char_size = chunk_size * 4
    char_overlap = overlap * 4

    chunks = []
    start = 0
    while start < len(text):
        end = start + char_size
        chunks.append(text[start:end].strip())
        start += char_size - char_overlap

    return [c for c in chunks if c]
