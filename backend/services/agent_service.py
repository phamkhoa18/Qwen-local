"""
Agentic RAG Service — Multi-step legal reasoning with tool calling
Agent automatically decides: search → verify → cross-reference → answer
"""
import re
import json
from typing import List, Dict, Any, Optional
from backend.config import settings
from backend.services.vector_store import vector_store


# ============ Tools for the Agent ============

def tool_search_law(query: str, top_k: int = 8) -> List[Dict]:
    """Hybrid search for legal documents"""
    if not vector_store.is_loaded:
        return []
    results = vector_store.search(query, top_k)
    sources = []
    for meta, score in results:
        sources.append({
            "content": meta.get("content", ""),
            "title": meta.get("title", ""),
            "article": meta.get("article", ""),
            "score": round(score, 4),
            "doc_type": meta.get("doc_type", "legal"),
        })
    return sources


def tool_search_exact_article(law_name: str, article_num: str) -> List[Dict]:
    """Search for a specific article by keyword (BM25)"""
    query = f"{law_name} Điều {article_num}"
    results = vector_store.search_keyword_only(query, top_k=5)
    sources = []
    for meta, score in results:
        sources.append({
            "content": meta.get("content", ""),
            "title": meta.get("title", ""),
            "article": meta.get("article", ""),
            "score": round(score, 4),
            "doc_type": "legal",
        })
    return sources


def tool_cross_reference(article_text: str) -> List[Dict]:
    """Find related articles that reference or complement the given article"""
    # Extract article numbers mentioned in the text
    refs = re.findall(r'[Đđ]i[eề]u\s+(\d+[a-z]?)', article_text)
    related = []
    seen = set()
    for ref_num in refs[:3]:  # Limit to 3 cross-references
        query = f"Điều {ref_num}"
        results = vector_store.search_keyword_only(query, top_k=2)
        for meta, score in results:
            content = meta.get("content", "")
            if content not in seen:
                seen.add(content)
                related.append({
                    "content": content,
                    "title": meta.get("title", ""),
                    "article": meta.get("article", ""),
                    "score": round(score, 4),
                    "doc_type": "legal",
                    "ref_type": "cross_reference",
                })
    return related


# ============ Intent Classification ============

def classify_intent(query: str) -> str:
    """
    Classify user query intent:
    - LOOKUP: Direct article lookup (e.g., "Điều 173 BLHS")
    - ANALYSIS: Complex legal analysis needing multi-step reasoning
    - GENERAL: Non-legal or simple chat
    """
    query_lower = query.lower()

    # LOOKUP: mentions specific article/law numbers
    lookup_patterns = [
        r'[đd]i[eề]u\s+\d+',
        r'kho[aả]n\s+\d+',
        r'ngh[ịi]\s+[đd][ịi]nh\s+\d+',
        r'lu[aậ]t\s+s[oố]',
        r'thông\s+tư\s+\d+',
    ]
    for pattern in lookup_patterns:
        if re.search(pattern, query_lower):
            return "LOOKUP"

    # ANALYSIS: comparison, analysis, complex questions
    analysis_keywords = [
        'so sánh', 'phân tích', 'khác nhau', 'giống nhau',
        'nếu', 'trường hợp', 'tình huống', 'xử phạt',
        'hình phạt', 'cấu thành', 'tội phạm', 'chuyển hóa',
        'bao nhiêu năm', 'mức phạt', 'có bị', 'có phải',
        'thế nào', 'như thế nào', 'ra sao',
    ]
    match_count = sum(1 for kw in analysis_keywords if kw in query_lower)
    if match_count >= 1:
        return "ANALYSIS"

    # Default: treat as analysis for legal platform
    return "ANALYSIS"


# ============ Agentic RAG ============

class AgentRAGService:
    """Multi-step agentic RAG for legal Q&A"""

    def process(self, query: str, messages: List[Dict] = None) -> Dict[str, Any]:
        """
        Run agentic RAG pipeline:
        1. Classify intent
        2. Execute appropriate search strategy
        3. Cross-reference if needed
        4. Build augmented prompt with structured context

        Returns: {"sources": [...], "augmented_prompt": str, "intent": str, "steps": [...]}
        """
        intent = classify_intent(query)
        all_sources = []
        steps = []
        seen_contents = set()

        def add_unique_sources(new_sources: List[Dict], step_name: str):
            added = 0
            for src in new_sources:
                content_key = src.get("content", "")[:200]
                if content_key not in seen_contents:
                    seen_contents.add(content_key)
                    all_sources.append(src)
                    added += 1
            steps.append({"step": step_name, "found": added})

        if intent == "LOOKUP":
            # Step 1: Exact keyword search first
            sources = tool_search_law(query, top_k=5)
            add_unique_sources(sources, "Tra cứu trực tiếp (Hybrid Search)")

            # Step 2: Cross-reference from found articles
            if all_sources:
                best = all_sources[0]
                xrefs = tool_cross_reference(best.get("content", ""))
                add_unique_sources(xrefs, "Tham chiếu chéo điều luật liên quan")

        elif intent == "ANALYSIS":
            # Step 1: Primary search
            sources = tool_search_law(query, top_k=8)
            add_unique_sources(sources, "Tìm kiếm ngữ nghĩa + từ khóa (Hybrid)")

            # Step 2: Extract legal terms and search deeper
            legal_terms = self._extract_legal_terms(query)
            for term in legal_terms[:2]:
                extra = tool_search_law(term, top_k=3)
                add_unique_sources(extra, f"Tìm kiếm bổ sung: '{term}'")

            # Step 3: Cross-reference top results
            if all_sources:
                for src in all_sources[:2]:
                    xrefs = tool_cross_reference(src.get("content", ""))
                    add_unique_sources(xrefs, "Tham chiếu chéo")

        # Build structured prompt
        augmented = self._build_agent_prompt(query, all_sources, intent, steps)

        return {
            "sources": all_sources,
            "augmented_prompt": augmented,
            "intent": intent,
            "steps": steps,
            "total_sources": len(all_sources),
        }

    def _extract_legal_terms(self, query: str) -> List[str]:
        """Extract key legal terms from query for deeper search"""
        terms = []
        # Extract crime names (tội + noun phrase)
        crime_matches = re.findall(r't[oộ]i\s+[\w\s]{3,30}', query.lower())
        terms.extend(crime_matches)

        # Extract law references
        law_matches = re.findall(r'(?:bộ luật|luật|nghị định|thông tư)[\s\w]{3,30}', query.lower())
        terms.extend(law_matches)

        return terms[:3]

    def _build_agent_prompt(self, query: str, sources: List[Dict], intent: str, steps: List[Dict]) -> str:
        """Build structured prompt with agent-gathered context"""
        if not sources:
            return query

        # Build step summary
        step_log = " → ".join([f"{s['step']} ({s['found']} kết quả)" for s in steps])

        # Build source context
        context_parts = []
        for i, src in enumerate(sources[:10], 1):  # Max 10 sources
            title = src.get("title", "")
            article = src.get("article", "")
            content = src.get("content", "")
            score = src.get("score", 0)
            ref_type = src.get("ref_type", "")

            header = f"[Nguồn {i}]"
            if title:
                header += f" {title}"
            if article:
                header += f" — {article}"
            if ref_type:
                header += f" (tham chiếu chéo)"
            header += f" [score: {score}]"

            context_parts.append(f"{header}\n{content}")

        context_text = "\n\n---\n\n".join(context_parts)

        augmented = f"""HỆ THỐNG TRA CỨU TỰ ĐỘNG (Agentic RAG):
Phân loại câu hỏi: {intent}
Các bước đã thực hiện: {step_log}
Tổng nguồn tìm thấy: {len(sources)}

═══════════════════════════════════════════
TÀI LIỆU PHÁP LUẬT ĐÃ TRUY XUẤT:
═══════════════════════════════════════════

{context_text}

═══════════════════════════════════════════
CÂU HỎI CỦA NGƯỜI DÙNG:
{query}
═══════════════════════════════════════════

HƯỚNG DẪN TRẢ LỜI:
1. DỰA TRÊN CÁC TÀI LIỆU PHÁP LUẬT ĐÃ TRUY XUẤT Ở TRÊN để trả lời
2. TRÍCH DẪN CHÍNH XÁC số Điều, Khoản, Điểm khi đề cập
3. Nếu tài liệu không đủ thông tin, NÓI RÕ và gợi ý hướng tra cứu thêm
4. Phân tích có cấu trúc, logic, chuyên nghiệp
5. Kết thúc bằng TÓM TẮT và KHUYẾN NGHỊ nếu phù hợp"""

        return augmented


# Global instance
agent_rag = AgentRAGService()
