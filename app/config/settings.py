from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

class Settings(BaseSettings):
    # 应用服务配置
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # LLM 配置
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    
    # Elasticsearch 配置
    ELASTICSEARCH_HOST: str = os.getenv("ELASTICSEARCH_HOST", "localhost")
    ELASTICSEARCH_PORT: int = int(os.getenv("ELASTICSEARCH_PORT", "9200"))
    ELASTICSEARCH_INDEX_PREFIX: str = "knowledge"
    ELASTICSEARCH_TIMEOUT: int = int(os.getenv("ELASTICSEARCH_TIMEOUT", "30"))
    ELASTICSEARCH_MAX_RETRIES: int = int(os.getenv("ELASTICSEARCH_MAX_RETRIES", "3"))
    ELASTICSEARCH_RETRY_ON_TIMEOUT: bool = True
    
    # 检索配置
    TOP_K_RESULTS: int = 3
    VECTOR_SEARCH_WEIGHT: float = 0.5

    # 文本分割配置
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # 知识库文件路径配置
    KNOWLEDGE_BASE_PATHS: dict = {
        "legal": "data/production/legal_kb.csv",
        "business": "data/production/business_kb.csv",
        "customer": "data/production/customer_kb.csv"
    }

settings = Settings()