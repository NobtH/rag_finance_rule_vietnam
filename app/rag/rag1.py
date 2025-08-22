from database.vector_store_1 import PSQLVectorStore
from embedding.encoder import Encoder
import tqdm
import json
import os
from database.vector_store_1 import remove_stopwords
from config.settings import get_settings
from chunking.chunking import *

class RAG:
    def __init__(self, data_path='data/markdown/'):
        self.config = get_settings()
        self.vector_store = PSQLVectorStore()
        self.embedder = Encoder()
        self.chunker = Chunking()
        self.data_path = data_path

    def collect_metadata_files(self):
        """Duyệt toàn bộ thư mục data_dir và lấy tất cả file .json"""
        metadata_files = []
        print('collect metadata')
        for dirpath, _, filenames in os.walk(self.data_path):
            for filename in filenames:
                if filename.lower().endswith(".json"):
                    metadata_files.append(os.path.join(dirpath, filename))
        print(len(metadata_files))
        return metadata_files

    def document_embedding(self):
        """
        1. Tìm toàn bộ file metadata JSON trong data_dir
        2. Insert vào doc_table
        3. (Chưa tính embedding)
        """
        metadata_files = self.collect_metadata_files()
        print(f"📄 Found {len(metadata_files)} metadata files.")

        for path in tqdm.tqdm(metadata_files, desc="Inserting metadata"):
            try:
                # Đọc metadata
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Nếu không có category -> lấy tên thư mục cha
                if not data.get("category"):
                    data["category"] = os.path.basename(os.path.dirname(path))
                self.vector_store.insert_doc_table(path)

            except Exception as e:
                print(f"⚠️ Error processing {path}: {e}")

        print("✅ All metadata inserted to database.")

    def chunk_and_embediing(self):
        metadata_files = self.collect_metadata_files()

        for path in tqdm.tqdm(metadata_files, desc='Chunking and saving embedding to db'):
            try:
                with self.vector_store.conn.cursor() as cur:
                    cur.execute(f"""
                        SELECT id FROM {self.config.vector_store.doc_table_name} 
                        WHERE file_name = %s ORDER BY id DESC LIMIT 1
                    """, (os.path.basename(path).replace('.pdf.json', '.pdf'),))
                    doc_id = cur.fetchone()[0]

                md_path = path.replace('.pdf.json', '.md')

                if not os.path.exists(md_path):
                    print(f"Cannot find markdown file: {md_path}")
                    continue

                chunks = self.chunker.chunk_single_md_file(md_path)

                if chunks:
                    for chunk in chunks:
                        text_content = chunk['text']

                        embedding = self.embedder.get_embedding(text_content)

                        self.vector_store.insert_embedding(
                            content=text_content,
                            embedding=embedding,
                            doc_id=doc_id
                        )
            except Exception as e:
                print(f'Bug in insert embedding: {e}')
        print("✅ Inserted all chunks and embeddings")