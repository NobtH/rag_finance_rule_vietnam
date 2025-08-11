import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from config.settings import get_settings
from embedding.encoder import Encoder
import re
import unicodedata

class HybridRetriever:
    def __init__(self, top_k=10, rrf_k=30, alpha=0.5):
        settings = get_settings()
        self.db_url = settings.database.db_url
        self.table_name = settings.vector_store.table_name
        self.conn = psycopg2.connect(self.db_url)
        self.embedder = Encoder()
        self.top_k = top_k
        self.rrf_k = rrf_k
        self.alpha = alpha
        
        
    def remove_vietnamese_tone(self, text):
        return ''.join(c for c in unicodedata.normalize('NFD', text)
                    if unicodedata.category(c) != 'Mn')

    def _rrf_fusion(self, faiss_rank, bm25_rank):
        
        all_idx = set(faiss_rank) | set(bm25_rank)
        scores = {}
        for idx in all_idx:
            r1 = faiss_rank.index(idx) if idx in faiss_rank else self.top_k
            r2 = bm25_rank.index(idx) if idx in bm25_rank else self.top_k
            print(r1, r2)
            scores[idx] = 1 / (self.rrf_k + r1) + 1 / (self.rrf_k + r2)
        return scores

    def retrieve(self, query: str):
        print(f"\n🔍 Truy vấn: {query}")
        
        # 1. Thực hiện tìm kiếm ngữ nghĩa (Semantic Search)
        # Gửi truy vấn tìm kiếm embedding và lấy top N kết quả
        query_embedding = self.embedder.get_embedding(query)
        semantic_sql = f"""
            SELECT id, content, embedding <#> %s::vector AS semantic_score
            FROM {self.table_name}
            ORDER BY semantic_score
            LIMIT %s
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(semantic_sql, (query_embedding, self.top_k * 3))
            semantic_results = cur.fetchall()

        # 2. Thực hiện tìm kiếm từ khóa (BM25)
        # Gửi truy vấn tìm kiếm từ khóa và lấy top N kết quả
        query_plain = self.remove_vietnamese_tone(query)
        # query_plain = query
        print(query_plain)

        bm25_sql = f"""
            SELECT id, content, ts_rank(tsv_content, plainto_tsquery('simple', %s)) AS bm25_score
            FROM {self.table_name}
            WHERE tsv_content @@ plainto_tsquery('simple', %s)
            ORDER BY bm25_score DESC
            LIMIT %s
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(bm25_sql, (query_plain, query_plain, self.top_k * 3))
            bm25_results = cur.fetchall()

        # 3. Kết hợp kết quả từ hai loại tìm kiếm
        semantic_rank = [row['id'] for row in semantic_results]
        bm25_rank = [row['id'] for row in bm25_results]
        
        # Sử dụng RRF fusion để tính điểm cuối cùng
        fused_scores = self._rrf_fusion(semantic_rank, bm25_rank)

        # 4. Tạo danh sách kết quả cuối cùng
        all_results = {row['id']: {'content': row['content']} for row in semantic_results}
        all_results.update({row['id']: {'content': row['content']} for row in bm25_results})
        
        final_results = []
        for idx, score in fused_scores.items():
            final_results.append({
                "cid": idx,  # Sử dụng ID làm CID
                "content": all_results[idx]['content'],
                "score": score
            })

        # 5. Sắp xếp và trả về
        final_results.sort(key=lambda x: x["score"], reverse=True)
        
        if not final_results:
            print('Không tìm thấy kết quả')
        
        return final_results[:self.top_k]


    
