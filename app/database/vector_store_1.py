import psycopg2
from config.settings import get_settings
import json
import unidecode
import re
import os
from typing import List
from embedding.encoder import Encoder


def load_stopwords(filepath="vietnamese-stopwords.txt"):
    with open(filepath, "r", encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}

STOPWORDS_VI = load_stopwords()

def remove_stopwords(text):
    words = re.findall(r'\b\w+\b', text.lower())  
    return ' '.join([w for w in words if w not in STOPWORDS_VI])

class PSQLVectorStore:
    def __init__(self):
        config = get_settings()
        self.db_url = config.database.db_url
        self.doc_table_name = config.vector_store.doc_table_name
        self.chunk_table_name = config.vector_store.chunk_table_name
        self.embedding_dimensions = config.vector_store.embedding_dimensions
        self.embedder = Encoder()

        self.conn = psycopg2.connect(self.db_url)
        self.create_doc_table()
        self.create_embedding_table()

    def create_doc_table(self):
        with self.conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.doc_table_name} (
                    id SERIAL PRIMARY KEY,
                    file_name TEXT,
                    title TEXT,
                    description TEXT,
                    expiration_date DATE,
                    effective_date DATE,
                    status TEXT,
                    document_type TEXT,
                    category TEXT,
                    keywords TEXT[],
                    keywords_tsvector TSVECTOR
                )
            """)
            self.conn.commit()
            print('Creating doc table..........')

    def create_embedding_table(self):
        with self.conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.chunk_table_name} (
                    id SERIAL PRIMARY KEY,
                    doc_id INTEGER REFERENCES {self.doc_table_name}(id) ON DELETE CASCADE, 
                    content TEXT,
                    embedding VECTOR({self.embedding_dimensions}),
                    tsvector TSVECTOR
                )
            """)
            self.conn.commit()
            print('Creating embeddings table.........')

    def insert_doc_table(self, metadata_path):
        if not os.path.exists(metadata_path):
            print(f"Metadata file not found: {metadata_path}")
            return

        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            def safe_get(key):
                val = data.get(key)
                if val in ("", None, [], {}):
                    return None
                return val

            file_name = safe_get('original_filename')
            title = safe_get('title')
            description = safe_get('description')
            expiration_date = safe_get('expiration_date')
            effective_date = safe_get('effective_date')
            status = safe_get('status')
            document_type = safe_get('document_type')
            category = safe_get('category')

            # Ghép nguyên văn keywords từ topic, topic_or, topic_and, tags
            keywords_list = []
            for key in ['topic', 'topic_or', 'topic_and', 'tags']:
                val = safe_get(key)
                if val is None:
                    continue
                if isinstance(val, list):
                    keywords_list.extend(val)  # giữ nguyên không remove stopwords
                else:
                    keywords_list.append(val)

            keywords_array = keywords_list if keywords_list else None
            
            # Create tsvector from keywords_list
            tsv_keywords = ' '.join(keywords_list) if keywords_list else None

            # Insert - cột keywords lưu nguyên text array
            with self.conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.doc_table_name} 
                    (file_name, title, description, expiration_date, effective_date, status, document_type, category, keywords, keywords_tsvector)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, to_tsvector('simple', %s))
                """, (
                    file_name, title, description, expiration_date, effective_date,
                    status, document_type, category, keywords_array, tsv_keywords,
                ))
                self.conn.commit()

            print(f"Saved document {metadata_path} to database.")

        except Exception as e:
            print(f"Error inserting {metadata_path}:", e)
    
    def insert_embedding(self, content: str, embedding: List[float], doc_id: int):

        tsv_content = ' '.join(re.findall(r'\b\w+\b', content))

        with self.conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {self.chunk_table_name} (content, doc_id, embedding, tsvector) VALUES (%s, %s, %s, to_tsvector('simple', %s))", 
                (content, doc_id, embedding, tsv_content)
            )
            self.conn.commit()
            print('Save embedding to database................')

    def delete_table(self, tablename):
        print(f'Deleting {tablename}..........................')
        with self.conn.cursor() as cur:
            cur.execute(f"""
                DROP TABLE IF EXISTS {tablename} CASCADE
            """)
            self.conn.commit()

    def keyword_search(self, question, limit_docs=5, limit_chunks=10):
        """
        1. Tìm kiếm keyword trong metadata trước
        2. Lọc ra doc_id liên quan
        3. Tìm chunk phù hợp nhất trong các doc_id đó
        """
        search_query = remove_stopwords(question)
        print(search_query)

        with self.conn.cursor() as cur:
            cur.execute(f"""
                SELECT id, filename
                FROM {self.doc_table_name}
                WHERE %s ILIKE ANY(SELECT '%' || unnest(keywords)) 
            """, search_query)
            docs = cur.fetchall()

        with self.conn.cursor() as cur:
            # ===== Tìm doc_id liên quan dựa trên metadata keywords =====
            cur.execute(f"""
                SELECT id, file_name, ts_rank(keywords_tsvector, to_tsquery('simple', %s), 2) AS bm25_score
                FROM {self.doc_table_name}
                WHERE keywords_tsvector @@ to_tsquery('simple', %s)
                ORDER BY bm25_score DESC
                LIMIT %s
            """, (search_query.replace(' ', ' | '), search_query.replace(' ', ' | '), limit_docs))
            docs = cur.fetchall()

            if not docs:
                print("No related documents found.")
                return []

            doc_ids = [str(doc[0]) for doc in docs]

            # ===== Tìm chunks liên quan trong các doc_id đã lọc =====
            cur.execute(f"""
                SELECT c.id, c.content, c.doc_id, d.file_name, ts_rank(c.tsvector, to_tsquery('simple', %s), 2) AS bm25_score
                FROM {self.chunk_table_name} c
                JOIN {self.doc_table_name} d ON c.doc_id = d.id
                WHERE c.doc_id = ANY(%s::int[])
                AND c.tsvector @@ to_tsquery('simple', %s)
                ORDER BY bm25_score DESC
                LIMIT %s
            """, (search_query.replace(' ', ' | '), doc_ids, search_query.replace(' ', ' | '), limit_chunks))
            chunks = cur.fetchall()

        return {
            "matched_docs": docs,
            "matched_chunks": chunks
        }

    def semantic_search(self, question, limits_chunks=10):
        """return top chunk, rank and their score"""
        question_embedding = self.embedder.get_embedding(question)
        with self.conn.cursor() as cur:
            cur.execute(f"""
                SELECT c.id, c.content
                FROM {self.chunk_table_name} c
                ORDER BY c.embedding <#> %s::vector
                LIMIT %s
            """, (question_embedding, limits_chunks))
            chunks = cur.fetchall()

        return {
            "matched_chunks": chunks
        }
        
