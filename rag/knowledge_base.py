"""
Knowledge Base — Votive VA

High-level RAG pipeline:
1. Receive user query
2. Detect if RAG context needed
3. Search knowledge base
4. Format context for LLM
5. Return augmented response
"""

import logging
from typing import Optional

from rag.search import search_and_format

log = logging.getLogger("votive-va-kb")


def get_context(query: str, k: int = 5, max_chars: int = 3000) -> Optional[str]:
    """
    Get RAG context for a query.
    
    Args:
        query: User question
        k: Number of chunks to retrieve
        max_chars: Maximum context length
    
    Returns:
        Formatted context string, or None if no relevant results
    """
    context = search_and_format(query, k=k, max_chars=max_chars)
    
    if not context:
        log.info(f"📭 No RAG context found for: {query}")
        return None
    
    log.info(f"📖 RAG context: {len(context)} chars from search")
    return context


def get_course_info() -> str:
    """
    Get course information (price, schedule, terms).
    
    TODO: Load from data/course_info.md
    """
    # Placeholder — will be populated when course info is available
    return (
        "Thông tin chi tiết về khóa học (học phí, lịch học, điều khoản) "
        "sẽ được cập nhật sớm. Bạn vui lòng để lại thông tin để admin liên hệ tư vấn nhé!"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🪐 Knowledge Base — Test")
    print("=" * 40)
    
    context = get_context("chiêm tinh veda dùng để làm gì")
    print(f"\nContext: {context[:200] if context else '(none)'}...")
    
    print(f"\nCourse info: {get_course_info()}")
