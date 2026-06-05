"""
RAG Ingest — Build FAISS index using Gemini API (FREE tier)

Step 1: Build index on local machine (Mac)
Step 2: Upload to VPS
Step 3: VPS uses FAISS search only (no ML libraries needed)

Usage: python rag/ingest.py --gemini AIzaSy...qQKY
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict

import numpy as np

log = logging.getLogger("votive-va-ingest")

# ── Paths ──────────────────────────────────────────────────
VA_DIR = Path(__file__).parent.parent
DATA_DIR = VA_DIR / "data"
FAISS_DIR = DATA_DIR / "faiss_index"
FAISS_DIR.mkdir(parents=True, exist_ok=True)

# Horoscope bot corpus (optional — 634 chunks)
HOROSCOPE_CORPUS_DIR = VA_DIR.parent / "horoscope-bot" / "corpus"

# ── Chunk config ───────────────────────────────────────────
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


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


def load_knowledge_files() -> List[Dict]:
    """Load knowledge base markdown files."""
    files = {
        "course_info": DATA_DIR / "course_info.md",
        "ethics": DATA_DIR / "ethics.md",
        "terms": DATA_DIR / "terms.md",
    }
    chunks = []
    for name, path in files.items():
        if not path.exists():
            log.warning(f"⚠️ File not found: {path}")
            continue
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        file_chunks = split_text(text)
        for i, chunk in enumerate(file_chunks):
            chunks.append({"text": chunk, "source": name, "chunk_id": f"{name}_{i}"})
        log.info(f"📄 {name}: {len(file_chunks)} chunks from {len(text)} chars")
    return chunks


def load_horoscope_corpus() -> List[Dict]:
    """Load horoscope bot corpus (634 chunks) — optional."""
    if not HOROSCOPE_CORPUS_DIR.exists():
        log.info("ℹ️ Horoscope corpus not found — skipping")
        return []
    chunks = []
    for source_file in HOROSCOPE_CORPUS_DIR.glob("*.json"):
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            items = data if isinstance(data, list) else data.get("chunks", [])
            for item in items:
                text = item.get("text", item.get("content", ""))
                if text:
                    chunks.append({"text": text, "source": source_file.stem, "chunk_id": f"{source_file.stem}_{len(chunks)}"})
        except Exception as e:
            log.error(f"❌ Error loading {source_file}: {e}")
    log.info(f"📚 Horoscope corpus: {len(chunks)} chunks")
    return chunks


def build_embeddings_gemini(chunks: List[Dict], api_key: str) -> np.ndarray:
    """Build embeddings using Gemini API (FREE tier — 1,500 req/min)."""
    import google.generativeai as genai
    genai.configure(api_key=api_key)

    texts = [c["text"] for c in chunks]
    embeddings_list = []
    batch_size = 100

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=batch,
            task_type="retrieval_document",
        )
        # Handle batch vs single
        if isinstance(result["embedding"], list) and isinstance(result["embedding"][0], list):
            embeddings_list.extend(result["embedding"])
        else:
            embeddings_list.append(result["embedding"])
        log.info(f"  Gemini batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}: {len(batch)} chunks")

    return np.array(embeddings_list, dtype='float32')


def build_faiss_index(chunks: List[Dict], embeddings: np.ndarray):
    """Build and save FAISS index."""
    import faiss
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    index_path = FAISS_DIR / "index.faiss"
    faiss.write_index(index, str(index_path))

    metadata = []
    for i, chunk in enumerate(chunks):
        metadata.append({
            "id": i,
            "text": chunk["text"],
            "source": chunk["source"],
            "chunk_id": chunk.get("chunk_id", f"chunk_{i}"),
        })

    meta_path = FAISS_DIR / "metadata.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    config = {
        "total_chunks": len(chunks),
        "dimension": dimension,
        "index_type": "IndexFlatL2",
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
    }
    with open(FAISS_DIR / "config.json", 'w') as f:
        json.dump(config, f, indent=2)

    log.info(f"✅ FAISS index: {len(chunks)} chunks, {dimension} dimensions")


def main(gemini_api_key: str):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("=" * 60)
    print("🪐 Votive VA — RAG Ingest (Gemini API)")
    print("=" * 60)

    print("\n📄 Loading knowledge files...")
    kb_chunks = load_knowledge_files()
    print(f"   Knowledge base: {len(kb_chunks)} chunks")

    print("\n📚 Loading horoscope corpus...")
    corpus_chunks = load_horoscope_corpus()
    print(f"   Horoscope corpus: {len(corpus_chunks)} chunks")

    all_chunks = kb_chunks + corpus_chunks
    print(f"\n📊 Total: {len(all_chunks)} chunks")

    if not all_chunks:
        print("❌ No chunks found!")
        return

    print("\n🤖 Building embeddings (Gemini API)...")
    embeddings = build_embeddings_gemini(all_chunks, gemini_api_key)
    print(f"   ✅ Embeddings: {embeddings.shape}")

    print("\n💾 Building FAISS index...")
    build_faiss_index(all_chunks, embeddings)

    print("\n✅ RAG Ingest complete!")
    print(f"   Index: {FAISS_DIR / 'index.faiss'}")
    print(f"   Metadata: {FAISS_DIR / 'metadata.json'}")
    print(f"   Config: {FAISS_DIR / 'config.json'}")


if __name__ == "__main__":
    import sys
    if "--gemini" not in sys.argv:
        print("Usage: python rag/ingest.py --gemini AIzaSy...qQKY")
        sys.exit(1)
    idx = sys.argv.index("--gemini")
    if idx + 1 >= len(sys.argv):
        print("❌ Missing API key")
        sys.exit(1)
    main(sys.argv[idx + 1])
