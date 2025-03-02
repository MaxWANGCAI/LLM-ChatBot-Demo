from elasticsearch import Elasticsearch
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)

class ESClient:
    def __init__(self):
        self.client = Elasticsearch(
            f"http://{settings.ELASTICSEARCH_HOST}:{settings.ELASTICSEARCH_PORT}",
            timeout=settings.ELASTICSEARCH_TIMEOUT,
            max_retries=settings.ELASTICSEARCH_MAX_RETRIES,
            retry_on_timeout=settings.ELASTICSEARCH_RETRY_ON_TIMEOUT
        )
    
    def search_similar(self, index_name: str, query_vector: list, top_k: int = 3):
        """搜索相似文档"""
        try:
            response = self.client.search(
                index=index_name,
                body={
                    "query": {
                        "script_score": {
                            "query": {"match_all": {}},
                            "script": {
                                "source": "cosineSimilarity(params.query_vector, 'vector') + 1.0",
                                "params": {"query_vector": query_vector}
                            }
                        }
                    },
                    "size": top_k
                }
            )
            return response["hits"]["hits"]
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []

    async def ping(self) -> bool:
        """
        检查Elasticsearch连接是否可用
        
        Returns:
            bool: 连接可用返回True，否则返回False
        """
        try:
            # 使用info()方法替代ping()，但不使用await
            info = self.client.info()
            return True
        except Exception as e:
            logger.error(f"Elasticsearch连接测试失败: {str(e)}")
            return False

es_client = ESClient()