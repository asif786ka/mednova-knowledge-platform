"""
Recursive, structure-aware chunking with overlap.

Splits on the strongest available boundary (markdown headings, then paragraphs, then
sentences) and packs pieces up to ~chunk_size characters with chunk_overlap carry-over. This
keeps semantically coherent sections together, which improves retrieval precision versus a
naive fixed-window split.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from app.config import settings

_HEADING_RE = re.compile(r"^#{1,6}\s.*$", re.MULTILINE)
_SENT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    source: str
    text: str
    section: str
    char_start: int
    char_end: int


def _current_heading(text: str, pos: int) -> str:
    heading = ""
    for m in _HEADING_RE.finditer(text):
        if m.start() <= pos:
            heading = m.group().lstrip("# ").strip()
        else:
            break
    return heading


def _split_paragraphs(text: str) -> List[str]:
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_document(document_id: str, source: str, text: str,
                   chunk_size: int | None = None,
                   overlap: int | None = None) -> List[Chunk]:
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap
    paragraphs = _split_paragraphs(text)

    chunks: List[Chunk] = []
    buf = ""
    buf_start = 0
    cursor = 0
    idx = 0

    def flush(end_pos: int):
        nonlocal buf, idx
        if not buf.strip():
            return
        section = _current_heading(text, buf_start)
        chunks.append(Chunk(
            chunk_id=f"{document_id}::chunk::{idx}",
            document_id=document_id,
            source=source,
            text=buf.strip(),
            section=section,
            char_start=buf_start,
            char_end=end_pos,
        ))
        idx += 1

    for para in paragraphs:
        p_pos = text.find(para, cursor)
        if p_pos == -1:
            p_pos = cursor
        cursor = p_pos + len(para)

        # oversized paragraph -> sentence-pack it
        pieces = [para]
        if len(para) > chunk_size:
            pieces = _SENT_RE.split(para)

        for piece in pieces:
            if not buf:
                buf_start = p_pos
            if len(buf) + len(piece) + 1 <= chunk_size:
                buf = f"{buf} {piece}".strip()
            else:
                flush(cursor)
                tail = buf[-overlap:] if overlap and len(buf) > overlap else ""
                buf = f"{tail} {piece}".strip()
                buf_start = max(p_pos - len(tail), 0)
    flush(cursor)
    return chunks
