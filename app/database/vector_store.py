import psycopg2
from typing import List
from config.settings import get_settings
import re
import unidecode

class PostgreSQLVectorStore:
    def __init__(self):
        config = get_settings()
        self.db_url = config.database.db_url
        self.table_name = config.vector_store.table_name
        self.embedding_dimensions = config.vector_store.embedding_dimensions

        self.conn = psycopg2.connect(self.db_url)
        self._create_table()
    
    def _create_table(self):
        with self.conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id SERIAL PRIMARY KEY,
                    content TEXT,
                    embedding VECTOR({self.embedding_dimensions}),
                    tsv_content TSVECTOR
                );
            """)
            self.conn.commit()
            print('creating table in db...............')
            
    def insert_embedding(self, text: str, embedding: List[float]):
        
        normalized = unidecode.unidecode(text)
        tokens = re.findall(r'\b\w+\b', normalized)

        tsv_content = ' '.join(tokens)

        with self.conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {self.table_name} (content, embedding, tsv_content) VALUES (%s, %s, to_tsvector(%s))", (text, embedding, tsv_content))
            self.conn.commit()
            print('save to db................')

    def delete_table(self):
        with self.conn.cursor() as cur:
            cur.execute(
                f"DROP TABLE IF EXISTS {self.table_name}"
            )
            self.conn.commit()
            print('delete table...........')