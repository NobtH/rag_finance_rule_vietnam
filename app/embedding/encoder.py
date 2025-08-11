import os
import openai 
from typing import List
from dotenv import load_dotenv
from config.settings import get_settings
from sentence_transformers import SentenceTransformer

class Encoder:
    def __init__(self):
        config = get_settings()
        self.model_name = config.local_model.embedding_model
        print('loading model................')
        self.model = SentenceTransformer(self.model_name, trust_remote_code=True)

    def get_embedding(self, text: str) -> List[float]:
        
        embeddings = self.model.encode(text, show_progress_bar=True, convert_to_numpy=True)
        print('embedding.................')
        print(len(embeddings))

        return embeddings.tolist()
