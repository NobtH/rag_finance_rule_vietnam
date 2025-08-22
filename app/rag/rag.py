from retriever.hybrid_retriever import HybridRetriever
from embedding.encoder import Encoder
from database.vector_store import PostgreSQLVectorStore
import tqdm
import pandas as pd
from generator.generator import Generator


class RAG:
    def __init__(self, corpus_path = 'data/corpus.csv'):
        self.vector_store = PostgreSQLVectorStore()
        self.embedder = Encoder()
        self.retriever = HybridRetriever()
        self.generator = Generator()
        self.corpus_path = corpus_path

    def document_embedding(self, batch_size: int = 1):
        df = pd.read_csv(self.corpus_path)
        for i in tqdm.tqdm(range(0, len(df), batch_size)):
            batch = df.iloc[i:i + batch_size]
            texts = (batch['topic'] + '. ' + batch['text']).tolist()
            metadata = batch['metadata']
            embeddings = self.embedder.get_embedding(texts)

            for row, embbed in zip(batch.itertuples(), embeddings):
                text = row.topic + '.\n' + row.text
                self.vector_store.insert_embedding(text, embbed, metadata)
        print("Document embedded")

    def search(self, text):
        return self.retriever.retrieve(text)

    def delete_table(self):
        self.vector_store.delete_table()

    def generate_answer(self, question, context):
        return self.generator.generate_answer(question, context)