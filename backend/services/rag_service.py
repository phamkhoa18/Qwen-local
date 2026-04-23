"""
RAG Service - Orchestrates retrieval + generation for legal Q&A
Downloads and indexes Vietnamese legal datasets from HuggingFace
"""
import asyncio
from typing import List, Dict, Any, Optional
from backend.config import settings
from backend.services.vector_store import vector_store


class RAGService:
    """Retrieval-Augmented Generation for Vietnamese Legal domain"""

    def __init__(self):
        self._indexing = False
        self._index_progress = {"status": "idle", "current": 0, "total": 0}

    @property
    def is_ready(self) -> bool:
        return vector_store.is_loaded

    @property
    def index_progress(self) -> dict:
        return self._index_progress

    def initialize(self):
        """Load existing vector store on startup"""
        loaded = vector_store.load()
        if not loaded:
            print("[INFO] No vector store found. Use /admin/rag/index to build index.")
        return loaded

    def retrieve(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """Retrieve relevant legal passages for a query"""
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
                "doc_type": meta.get("doc_type", "legal")
            })

        return sources

    def build_rag_prompt(self, user_query: str, sources: List[Dict[str, Any]]) -> str:
        """Build augmented prompt with retrieved legal passages"""
        if not sources:
            return user_query

        context_parts = []
        for i, src in enumerate(sources, 1):
            title = src.get("title", "")
            article = src.get("article", "")
            content = src.get("content", "")
            score = src.get("score", 0)

            header = f"[Nguon {i}]"
            if title:
                header += f" {title}"
            if article:
                header += f" - {article}"
            header += f" (do chinh xac: {score:.0%})"

            context_parts.append(f"{header}\n{content}")

        context_text = "\n\n---\n\n".join(context_parts)

        augmented = f"""TAI LIEU PHAP LUAT THAM KHAO:

{context_text}

---

CAU HOI CUA KIEM SAT VIEN:
{user_query}

Hay tra loi dua tren tai lieu phap luat duoc cung cap o tren. Trich dan chinh xac so dieu, khoan khi tra loi. Neu thong tin khong du, hay noi ro va goi y huong tra cuu them."""

        return augmented

    async def index_dataset(self, max_docs: int = 50000):
        """Download and index Vietnamese legal documents from HuggingFace"""
        if self._indexing:
            return {"status": "already_indexing", "progress": self._index_progress}

        self._indexing = True
        self._index_progress = {"status": "downloading", "current": 0, "total": 0}

        try:
            import requests
            import time

            print(f"[INFO] Loading dataset via REST API: {settings.LEGAL_DATASET}")
            self._index_progress["status"] = "downloading"

            # Collect documents
            texts = []
            metadatas = []
            count = 0
            offset = 0
            batch_size = 100

            print("[INFO] Processing documents...")
            self._index_progress["status"] = "processing"

            while count < max_docs:
                url = f"https://datasets-server.huggingface.co/rows?dataset={settings.LEGAL_DATASET.replace('/', '%2F')}&config=content&split=data&offset={offset}&length={batch_size}"
                
                try:
                    resp = requests.get(url, timeout=30)
                    if resp.status_code != 200:
                        print(f"[WARN] HF API returned {resp.status_code}: {resp.text}")
                        # Fallback to metadata config if content fails
                        if resp.status_code == 404:
                            url = f"https://datasets-server.huggingface.co/rows?dataset={settings.LEGAL_DATASET.replace('/', '%2F')}&config=default&split=train&offset={offset}&length={batch_size}"
                            resp = requests.get(url, timeout=30)
                            if resp.status_code != 200:
                                break
                        else:
                            break
                    
                    data = resp.json()
                    rows = data.get("rows", [])
                    if not rows:
                        break
                        
                    for row in rows:
                        if count >= max_docs:
                            break
                            
                        item = row.get("row", {})
                        
                        text = ""
                        title = ""

                        for field in ["text", "content", "body", "document", "noidung"]:
                            if field in item and item[field]:
                                text = item[field]
                                break

                        for field in ["title", "name", "subject", "ten_van_ban"]:
                            if field in item and item[field]:
                                title = item[field]
                                break

                        if not text or len(text) < 50:
                            continue

                        # Chunk the document
                        chunks = vector_store.chunk_text(text, title=title, doc_type="legal")

                        for chunk in chunks:
                            texts.append(chunk["content"])
                            metadatas.append(chunk)

                        count += 1
                        
                    offset += batch_size
                    if count % 100 == 0:
                        self._index_progress["current"] = count
                        self._index_progress["total"] = max_docs
                        print(f"[INFO] Processed {count}/{max_docs} documents, {len(texts)} chunks")
                        
                    time.sleep(0.5) # Rate limit protection
                    
                except Exception as req_err:
                    print(f"[WARN] Request error: {req_err}")
                    time.sleep(2)
                    continue

            if not texts:
                self._index_progress = {"status": "error", "message": "No documents found"}
                return self._index_progress

            # Embed and index
            print(f"[INFO] Embedding {len(texts)} chunks...")
            self._index_progress["status"] = "embedding"
            self._index_progress["total"] = len(texts)

            # Process in batches to avoid OOM
            batch_size = 5000
            total_added = 0

            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                batch_meta = metadatas[i:i + batch_size]
                added = vector_store.add_documents(batch_texts, batch_meta)
                total_added += added
                self._index_progress["current"] = total_added
                print(f"[INFO] Indexed {total_added}/{len(texts)} chunks")

            # Save to disk
            vector_store.save()

            self._index_progress = {
                "status": "complete",
                "total_documents": count,
                "total_chunks": total_added
            }
            print(f"[OK] Indexing complete: {count} docs, {total_added} chunks")
            return self._index_progress

        except Exception as e:
            self._index_progress = {"status": "error", "message": str(e)}
            print(f"[ERROR] Indexing failed: {e}")
            raise
        finally:
            self._indexing = False

    def add_custom_document(self, title: str, content: str, doc_type: str = "legal") -> int:
        """Add a single custom document to the index"""
        chunks = vector_store.chunk_text(content, title=title, doc_type=doc_type)

        if not chunks:
            return 0

        texts = [c["content"] for c in chunks]
        added = vector_store.add_documents(texts, chunks)
        vector_store.save()
        return added


# Global instance
rag_service = RAGService()
