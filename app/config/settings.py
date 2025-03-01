from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

class Settings(BaseSettings):
    # LLM 配置
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    
    # Elasticsearch 配置
    ELASTICSEARCH_HOST: str = "localhost"
    ELASTICSEARCH_PORT: int = 9200
    ELASTICSEARCH_INDEX_PREFIX: str = "knowledge"
    
    # 检索配置
    TOP_K_RESULTS: int = 3
    VECTOR_SEARCH_WEIGHT: float = 0.5

settings = Settings() 