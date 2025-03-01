from elasticsearch import Elasticsearch
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)

class ESClient:
    def __init__(self):
        self.client = Elasticsearch(
            f"http://{settings.ELASTICSEARCH_HOST}:{settings.ELASTICSEARCH_PORT}"
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

es_client = ESClient() 