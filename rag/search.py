"""
RAG Search — Votive VA

Simple keyword + TF-IDF search over knowledge base files.
NO ML libraries, NO API calls, NO FAISS — pure Python!
Perfect for 25-50 chunks (course info, ethics, terms).

For larger corpus (634+ chunks), use FAISS + Gemini embedding.
"""

import os
import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional
from collections import Counter

log = logging.getLogger("votive-va-rag")

DATA_DIR = Path(__file__).parent.parent / "data"

# ── Knowledge base files ───────────────────────────────────
KB_FILES = {
    "course_info": DATA_DIR / "course_info.md",
    "services": DATA_DIR / "services.md",
    "ethics": DATA_DIR / "ethics.md",
    "terms": DATA_DIR / "terms.md",
    "quant": DATA_DIR / "quant_framework.md",
}

# ── Chunk config ───────────────────────────────────────────
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

# Cache
_chunks_cache = None


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if end < len(text):
            last_period = chunk.rfind('.')
            last_newline = chunk.rfind('\n')
            break_point = max(last_period, last_newline)
            if break_point > chunk_size * 0.5:
                chunk = chunk[:break_point + 1]
                end = start + break_point + 1
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    return chunks


def load_chunks() -> List[Dict]:
    """Load and chunk all knowledge base files."""
    global _chunks_cache
    if _chunks_cache is not None:
        return _chunks_cache

    chunks = []
    for name, path in KB_FILES.items():
        if not path.exists():
            log.warning(f"⚠️ File not found: {path}")
            continue
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        file_chunks = split_text(text)
        for i, chunk in enumerate(file_chunks):
            chunks.append({
                "text": chunk,
                "source": name,
                "chunk_id": f"{name}_{i}",
            })
        log.info(f"📄 {name}: {len(file_chunks)} chunks")

    _chunks_cache = chunks
    log.info(f"📊 Total chunks: {len(chunks)}")
    return chunks


def tokenize(text: str) -> List[str]:
    """Vietnamese-aware tokenizer."""
    text = text.lower()
    # Keep Vietnamese diacritics, split on non-alphanumeric
    tokens = re.findall(r'[\w\u00C0-\u1EF9]+', text)
    return tokens


def search(query: str, k: int = 5) -> List[Dict]:
    """
    Keyword + TF-IDF search with n-gram expansion.
    
    Score = weighted by term rarity + n-gram matches.
    """
    chunks = load_chunks()
    if not chunks:
        return []

    query_tokens = set(tokenize(query))
    if not query_tokens:
        return []

    # Build IDF (inverse document frequency)
    doc_freq = Counter()
    for chunk in chunks:
        chunk_tokens = tokenize(chunk["text"])
        for token in chunk_tokens:
            doc_freq[token] += 1

    total_docs = len(chunks)

    # Expand query with bigrams for better matching
    query_bigrams = set()
    words = query.lower().split()
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        query_bigrams.add(bigram)

    scored = []
    for chunk in chunks:
        chunk_tokens = tokenize(chunk["text"])
        chunk_token_set = set(chunk_tokens)
        chunk_text_lower = chunk["text"].lower()

        # TF-IDF score
        score = 0
        for token in query_tokens:
            if token in chunk_token_set:
                tf = chunk_tokens.count(token) / len(chunk_tokens)
                idf = max(1, total_docs / max(1, doc_freq.get(token, 1)))
                # Boost for exact word match
                if token in chunk_text_lower.split():
                    score += tf * idf * 1.5
                else:
                    score += tf * idf

        # Bonus for bigram matches
        for bigram in query_bigrams:
            if bigram in chunk_text_lower:
                score += 2.0  # Strong boost for phrase match

        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: -x[0])
    results = [{"score": round(s, 3), **c} for s, c in scored[:k]]

    log.info(f"🔍 Search: '{query}' → {len(results)} results (top score: {results[0]['score'] if results else 0})")
    return results


def format_context(results: List[Dict], max_chars: int = 3000) -> str:
    """Format search results into context string for LLM."""
    if not results:
        return ""

    lines = []
    total_chars = 0

    for i, chunk in enumerate(results):
        source = chunk.get("source", "unknown")
        text = chunk.get("text", "")
        score = chunk.get("score", 0)

        entry = f"[{i+1}] (nguồn: {source}, độ khớp: {score:.3f})\n{text[:500]}\n"

        if total_chars + len(entry) > max_chars:
            break

        lines.append(entry)
        total_chars += len(entry)

    return "\n".join(lines)


def search_and_format(query: str, k: int = 5, max_chars: int = 3000) -> str:
    """Search and format in one call."""
    results = search(query, k=k)
    return format_context(results, max_chars=max_chars)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("🪐 RAG Search — Test")
    print("=" * 50)

    test_queries = [
        "chiêm tinh veda là gì",
        "nakshatra nghĩa là gì",
        "học phí khóa học",
        "chính sách hoàn tiền",
        "lịch học lớp học",
        "ưu đãi học phí",
        "đạo đức nghề nghiệp",
        "ayurveda là gì",
    ]

    for q in test_queries:
        print(f"\nQuery: {q}")
        results = search(q, k=3)
        print(f"  Results: {len(results)}")
        for r in results[:2]:
            text = r.get("text", "")[:120]
            score = r.get("score", 0)
            print(f"  → [{r.get('source')}] score={score:.3f} {text}...")
