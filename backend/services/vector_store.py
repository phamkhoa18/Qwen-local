"""
Hybrid Vector Store — FAISS + BM25 with RRF Fusion
Combines semantic search (vectors) with keyword search (BM25)
for significantly improved legal document retrieval accuracy
"""
import os
import json
import pickle
import math
import numpy as np
import faiss
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
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


# ============ BM25 Implementation ============

def _tokenize_vi(text: str) -> List[str]:
    """Simple Vietnamese tokenizer: lowercase + split on non-alphanumeric"""
    text = text.lower()
    text = re.sub(r'[^\w\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', ' ', text)
    return [w for w in text.split() if len(w) > 1]


class BM25Index:
    """Okapi BM25 index for keyword search"""

    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.corpus: List[List[str]] = []
        self.doc_len: List[int] = []
        self.avgdl: float = 0
        self.df: Dict[str, int] = {}  # document frequency
        self.n_docs: int = 0

    @property
    def is_loaded(self) -> bool:
        return self.n_docs > 0

    def build(self, texts: List[str]):
        """Build BM25 index from texts"""
        self.corpus = [_tokenize_vi(t) for t in texts]
        self.n_docs = len(self.corpus)
        self.doc_len = [len(d) for d in self.corpus]
        self.avgdl = sum(self.doc_len) / max(self.n_docs, 1)

        # Compute document frequency
        self.df = {}
        for doc in self.corpus:
            for term in set(doc):
                self.df[term] = self.df.get(term, 0) + 1

    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Search and return (doc_index, score) pairs"""
        if not self.is_loaded:
            return []

        query_tokens = _tokenize_vi(query)
        scores = []

        for i, doc in enumerate(self.corpus):
            score = 0.0
            tf_map = Counter(doc)
            dl = self.doc_len[i]

            for term in query_tokens:
                if term not in self.df:
                    continue
                tf = tf_map.get(term, 0)
                if tf == 0:
                    continue
                df = self.df[term]
                idf = math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1)
                tf_norm = (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
                score += idf * tf_norm

            if score > 0:
                scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def save(self, path: str):
        with open(path, 'wb') as f:
            pickle.dump({
                'corpus': self.corpus, 'doc_len': self.doc_len,
                'avgdl': self.avgdl, 'df': self.df, 'n_docs': self.n_docs,
            }, f)

    def load(self, path: str) -> bool:
        try:
            with open(path, 'rb') as f:
                data = pickle.load(f)
            self.corpus = data['corpus']
            self.doc_len = data['doc_len']
            self.avgdl = data['avgdl']
            self.df = data['df']
            self.n_docs = data['n_docs']
            return True
        except Exception:
            return False


# ============ Hybrid Vector Store ============

class VectorStore:
    """FAISS + BM25 hybrid vector store for legal document retrieval"""

    def __init__(self):
        self.index: Optional[faiss.IndexFlatIP] = None
        self.metadata: List[Dict[str, Any]] = []
        self.bm25 = BM25Index()
        self.store_path = Path(settings.VECTOR_STORE_PATH)
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.index_file = self.store_path / "index.faiss"
        self.meta_file = self.store_path / "metadata.json"
        self.bm25_file = self.store_path / "bm25.pkl"

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

                # Load or rebuild BM25
                if self.bm25_file.exists():
                    self.bm25.load(str(self.bm25_file))
                    print(f"[OK] BM25 index loaded: {self.bm25.n_docs} docs")
                else:
                    print("[INFO] Building BM25 index from existing metadata...")
                    texts = [m.get("content", "") for m in self.metadata]
                    self.bm25.build(texts)
                    self.bm25.save(str(self.bm25_file))
                    print(f"[OK] BM25 index built: {self.bm25.n_docs} docs")

                # Eager load embedding model
                print("[INFO] Eager loading embedding model...")
                get_embedding_model()

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
            self.bm25.save(str(self.bm25_file))
            print(f"[OK] Vector store saved: {self.index.ntotal} chunks (FAISS + BM25)")

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
        """Embed and add documents to both FAISS and BM25 indexes"""
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

        # Rebuild BM25 with all documents
        all_texts = [m.get("content", "") for m in self.metadata]
        self.bm25.build(all_texts)

        return len(texts)

    def _rrf_fusion(self, vector_results: List[Tuple[int, float]], bm25_results: List[Tuple[int, float]], top_k: int) -> List[Tuple[int, float]]:
        """Reciprocal Rank Fusion: merge vector and BM25 rankings"""
        k = settings.RRF_K
        scores: Dict[int, float] = {}

        for rank, (idx, _) in enumerate(vector_results):
            scores[idx] = scores.get(idx, 0) + settings.VECTOR_WEIGHT / (k + rank + 1)

        for rank, (idx, _) in enumerate(bm25_results):
            scores[idx] = scores.get(idx, 0) + settings.BM25_WEIGHT / (k + rank + 1)

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    def search(self, query: str, top_k: int = None) -> List[Tuple[Dict[str, Any], float]]:
        """Hybrid search: FAISS vector + BM25 keyword with RRF fusion"""
        if not self.is_loaded:
            return []

        if top_k is None:
            top_k = settings.TOP_K

        # Fetch more candidates for fusion
        fetch_k = min(top_k * 3, self.index.ntotal)

        # === FAISS Vector Search ===
        model = get_embedding_model()
        query_with_instruction = f"{settings.EMBEDDING_INSTRUCTION}{query}"
        query_embedding = model.encode([query_with_instruction])
        query_embedding = np.array(query_embedding, dtype=np.float32)
        faiss.normalize_L2(query_embedding)

        scores_vec, indices_vec = self.index.search(query_embedding, fetch_k)
        vector_results = [
            (int(idx), float(score))
            for score, idx in zip(scores_vec[0], indices_vec[0])
            if idx >= 0 and idx < len(self.metadata) and score >= settings.SIMILARITY_THRESHOLD
        ]

        # === BM25 Keyword Search ===
        bm25_results = []
        if self.bm25.is_loaded:
            bm25_results = self.bm25.search(query, fetch_k)

        # === RRF Fusion ===
        if bm25_results:
            fused = self._rrf_fusion(vector_results, bm25_results, top_k)
            results = []
            for idx, rrf_score in fused:
                if idx < len(self.metadata):
                    results.append((self.metadata[idx], rrf_score))
            return results
        else:
            # Fallback to vector-only if BM25 not available
            return [(self.metadata[idx], score) for idx, score in vector_results[:top_k]]

    def search_keyword_only(self, query: str, top_k: int = 10) -> List[Tuple[Dict[str, Any], float]]:
        """BM25 keyword search only — for exact article lookup"""
        if not self.bm25.is_loaded:
            return []
        results = self.bm25.search(query, top_k)
        return [(self.metadata[idx], score) for idx, score in results if idx < len(self.metadata)]

    def clear(self):
        """Clear the entire index"""
        self.index = None
        self.metadata = []
        self.bm25 = BM25Index()
        for f in [self.index_file, self.meta_file, self.bm25_file]:
            if f.exists():
                os.remove(f)


# Global instance
vector_store = VectorStore()
