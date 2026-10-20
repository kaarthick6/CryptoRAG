"""Create deterministic sentence-aware chunks from extracted PDF pages."""

import re

from app.config import get_settings


def split_sentences(text: str) -> list[str]:
    """Split page text after sentence endings while retaining useful content."""
    normalized_text = re.sub(r"\s+", " ", text).strip()
    if not normalized_text:
        return []
    sentence_parts = re.split(r"(?<=[.!?])\s+", normalized_text)
    return [sentence.strip() for sentence in sentence_parts]


def create_chunks(pages: list[dict]) -> list[dict]:
    """Group sentences up to configured size and overlap chunks by sentences."""
    settings = get_settings()
    if (
        settings.chunk_size <= 0
        or settings.chunk_overlap < 0
        or settings.chunk_overlap >= settings.chunk_size
    ):
        raise ValueError("Chunk size must exceed a non-negative overlap")

    chunks = []
    for page in pages:
        sentences = split_sentences(page["text"])
        page_chunks = group_sentences(sentences, settings.chunk_size)
        for chunk_text in page_chunks:
            chunks.append({"page_number": page["page_number"], "text": chunk_text})
    return chunks


def group_sentences(sentences: list[str], chunk_size: int) -> list[str]:
    """Group sentences without splitting a sentence unless it exceeds the limit."""
    chunks = []
    current_sentences = []
    current_length = 0

    for sentence in sentences:
        if len(sentence) > chunk_size:
            if current_sentences:
                chunks.append(" ".join(current_sentences))
                current_sentences = []
                current_length = 0
            chunks.extend(split_long_sentence(sentence, chunk_size))
            continue

        if current_sentences and current_length + len(sentence) + 1 > chunk_size:
            chunks.append(" ".join(current_sentences))
            current_sentences = get_overlap_sentences(current_sentences)
            while current_sentences and (
                sum(len(item) + 1 for item in current_sentences) + len(sentence) + 1
                > chunk_size
            ):
                current_sentences.pop(0)
            current_length = sum(len(item) + 1 for item in current_sentences)

        current_sentences.append(sentence)
        current_length += len(sentence) + 1

    if current_sentences:
        chunks.append(" ".join(current_sentences))
    return chunks


def split_long_sentence(sentence: str, chunk_size: int) -> list[str]:
    """Split an unusually long sentence at word boundaries."""
    words = sentence.split()
    result = []
    current_words = []
    current_length = 0
    for word in words:
        if len(word) > chunk_size:
            if current_words:
                result.append(" ".join(current_words))
                current_words = []
                current_length = 0
            for start in range(0, len(word), chunk_size):
                result.append(word[start : start + chunk_size])
            continue

        if current_words and current_length + len(word) + 1 > chunk_size:
            result.append(" ".join(current_words))
            current_words = []
            current_length = 0
        current_words.append(word)
        current_length += len(word) + 1
    if current_words:
        result.append(" ".join(current_words))
    return result


def get_overlap_sentences(sentences: list[str]) -> list[str]:
    """Keep trailing sentences that fit the configured overlap size."""
    overlap_size = get_settings().chunk_overlap
    overlap = []
    length = 0
    for sentence in reversed(sentences):
        if length + len(sentence) > overlap_size:
            break
        overlap.insert(0, sentence)
        length += len(sentence) + 1
    return overlap
