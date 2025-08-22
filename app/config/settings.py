import logging
import os
from datetime import timedelta
from functools import lru_cache
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

def setup_logging():
    logging.basicConfig(filename='example.log', level=logging.DEBUG, encoding='utf-8')

class LLMSettings(BaseModel):
    temparature: float=0.0
    # max_tokens: Optional[int]
    max_tokens: int=2048

class OpenAISettings(LLMSettings):
    api_key: str = Field(default_factory=lambda: os.getenv('OPEN_AI_KEY'))
    generate_model: str = Field(default='gpt-4o')
    embedding_model: str = Field(default='text-embedding-3-small')

class DeepseekSettings(LLMSettings):
    api_key: str = Field(default_factory=lambda: os.getenv('DEEPSEEK_API_KEY'))
    base_url: str = Field(default="https://api.deepseek.com")
    model_name: str = Field(default='deepseek-chat')

class LocalModelSettings(LLMSettings):
    generate_model: str = Field(default='vinai/PhoGPT-4B')
    embedding_model: str = Field(default='dangvantuan/vietnamese-document-embedding')
    # keepitreal/vietnamese-sbert; dangvantuan/vietnamese-embedding; VoVanPhuc/sup-SimCSE-VietNamese-phobert-base; dangvantuan/vietnamese-document-embedding
    # sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
class DatabaseSettings(BaseModel):
    db_url: str = Field(default_factory=lambda: os.getenv('DB_URL'))

class VectorStroreSettings(BaseModel):
    doc_table_name: str = 'document_table'
    chunk_table_name: str = 'chunk_table'
    embedding_dimensions: int = 768
    time_partition_interval: timedelta = timedelta(days=7)

class Settings(BaseModel):
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    deepseek: DeepseekSettings = Field(default_factory=DeepseekSettings)
    local_model: LocalModelSettings = Field(default_factory=LocalModelSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    vector_store: VectorStroreSettings = Field(default_factory=VectorStroreSettings)

@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    setup_logging
    return settings