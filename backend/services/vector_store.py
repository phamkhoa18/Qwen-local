"""
Vector Store using FAISS + vietlegal-harrier-0.6b embeddings
Handles document indexing and similarity search for legal RAG
"""
import os
import json
import numpy as np
import faiss
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from backend.config import settings

# Global model reference
_embedding_model = None


def get_embedding_model():
    """Lazy-load the sentence-transformers embedding model"""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        print(f"[INFO] Loading embedding model: {settings.EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        print(f"[OK] Embedding model loaded ({settings.EMBEDDING_DIM}-dim)")
    return _embedding_model


class VectorStore:
    """FAISS-based vector store for legal document retrieval"""

    def __init__(self):
        self.index: Optional[faiss.IndexFlatIP] = None
        self.metadata: List[Dict[str, Any]] = []
        self.store_path = Path(settings.VECTOR_STORE_PATH)
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.index_file = self.store_path / "index.faiss"
        self.meta_file = self.store_path / "metadata.json"

    @property
    def is_loaded(self) -> bool:
        return self.index is not None and self.index.ntotal > 0

    @property
    def total_chunks(self) -> int:
        return self.index.ntotal if self.index else 0

    def load(self) -> bool:
        """Load existing index from disk"""
        try:
            if self.index_file.exists() and self.meta_file.exists():
                self.index = faiss.read_index(str(self.index_file))
                with open(self.meta_file, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                print(f"[OK] Vector store loaded: {self.index.ntotal} chunks")
                return True
        except Exception as e:
            print(f"[WARN] Failed to load vector store: {e}")
        return False

    def save(self):
        """Save index to disk"""
        if self.index:
            faiss.write_index(self.index, str(self.index_file))
            with open(self.meta_file, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, ensure_ascii=False)
            print(f"[OK] Vector store saved: {self.index.ntotal} chunks")

    def chunk_text(self, text: str, title: str = "", doc_type: str = "legal") -> List[Dict[str, Any]]:
        """Split text into chunks, preferring article boundaries for legal docs"""
        chunks = []

        if doc_type == "legal":
            # Try to split by Vietnamese legal article patterns
            article_pattern = r'((?:Dieu|[DdĐđ]i[eề]u)\s+\d+[a-z]?\.?\s*[^\n]*)'
            articles = re.split(article_pattern, text)

            current_chunk = ""
            current_article = ""

            for part in articles:
                part = part.strip()
                if not part:
                    continue

                # Check if this is an article header
                if re.match(article_pattern, part):
                    current_article = part
                    if current_chunk and len(current_chunk) > 50:
                        chunks.append({
                            "content": current_chunk.strip(),
                            "title": title,
                            "article": current_article,
                            "doc_type": doc_type
                        })
                    current_chunk = part + "\n"
                else:
                    current_chunk += part + "\n"
                    # If chunk is too large, split it
                    if len(current_chunk) > settings.CHUNK_SIZE:
                        chunks.append({
                            "content": current_chunk.strip(),
                            "title": title,
                            "article": current_article,
                            "doc_type": doc_type
                        })
                        current_chunk = ""

            if current_chunk and len(current_chunk.strip()) > 50:
                chunks.append({
                    "content": current_chunk.strip(),
                    "title": title,
                    "article": current_article,
                    "doc_type": doc_type
                })

        # Fallback: simple chunking
        if not chunks:
            words = text.split()
            for i in range(0, len(words), settings.CHUNK_SIZE - settings.CHUNK_OVERLAP):
                chunk_words = words[i:i + settings.CHUNK_SIZE]
                if len(chunk_words) > 20:
                    chunks.append({
                        "content": " ".join(chunk_words),
                        "title": title,
                        "article": "",
                        "doc_type": doc_type
                    })

        return chunks

    def add_documents(self, texts: List[str], metadatas: List[Dict[str, Any]]) -> int:
        """Embed and add documents to the index"""
        if not texts:
            return 0

        model = get_embedding_model()

        # Encode passages (no instruction prefix for passages)
        embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)
        embeddings = np.array(embeddings, dtype=np.float32)

        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings)

        if self.index is None:
            self.index = faiss.IndexFlatIP(settings.EMBEDDING_DIM)

        self.index.add(embeddings)
        self.metadata.extend(metadatas)

        return len(texts)

    def search(self, query: str, top_k: int = None) -> List[Tuple[Dict[str, Any], float]]:
        """Search for similar documents using the query"""
        if not self.is_loaded:
            return []

        if top_k is None:
            top_k = settings.TOP_K

        model = get_embedding_model()

        # Encode query with instruction prefix (Harrier model requirement)
        query_with_instruction = f"{settings.EMBEDDING_INSTRUCTION}{query}"
        query_embedding = model.encode([query_with_instruction])
        query_embedding = np.array(query_embedding, dtype=np.float32)
        faiss.normalize_L2(query_embedding)

        scores, indices = self.index.search(query_embedding, min(top_k, self.index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self.metadata) and score >= settings.SIMILARITY_THRESHOLD:
                results.append((self.metadata[idx], float(score)))

        return results

    def clear(self):
        """Clear the entire index"""
        self.index = None
        self.metadata = []
        if self.index_file.exists():
            os.remove(self.index_file)
        if self.meta_file.exists():
            os.remove(self.meta_file)


# Global instance
vector_store = VectorStore()
