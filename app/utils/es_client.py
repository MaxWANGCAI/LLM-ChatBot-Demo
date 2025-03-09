from elasticsearch import Elasticsearch
from app.config.settings import settings
import logging
import json
import traceback

logger = logging.getLogger(__name__)

class ESClient:
    def __init__(self):
        self.client = Elasticsearch(
            f"http://{settings.ELASTICSEARCH_HOST}:{settings.ELASTICSEARCH_PORT}",
            timeout=settings.ELASTICSEARCH_TIMEOUT,
            max_retries=settings.ELASTICSEARCH_MAX_RETRIES,
            retry_on_timeout=settings.ELASTICSEARCH_RETRY_ON_TIMEOUT
        )
        self.index_name = settings.ELASTICSEARCH_INDEX_NAME
    
    def search_similar(self, query_vector: list, role: str = None, top_k: int = 3):
        """搜索相似文档"""
        try:
            query = {
                "script_score": {
                    "query": {
                        "bool": {
                            "must": [{"match_all": {}}]
                        }
                    },
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'embedding')",
                        "params": {"query_vector": query_vector}
                    }
                }
            }

            # 如果指定了角色，添加角色过滤
            if role:
                query["script_score"]["query"]["bool"]["must"].append({
                    "term": {"metadata.role.keyword": role}
                })
    
            # 记录搜索参数
            logger.debug(f"执行向量搜索，参数：index={self.index_name}, size={top_k}, query={json.dumps(query, ensure_ascii=False)}")
    
            response = self.client.search(
                index=self.index_name,
                body={"query": query},
                size=top_k
            )
    
            # 记录搜索结果统计
            total_hits = response["hits"]["total"]["value"]
            max_score = response["hits"]["max_score"] if response["hits"]["hits"] else 0
            logger.info(f"搜索完成：总匹配数={total_hits}, 最高分={max_score:.4f}")
    
            return response["hits"]["hits"]
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"搜索失败: {error_msg}")
            if settings.DEBUG:
                logger.debug(f"详细错误: {traceback.format_exc()}")
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

    def delete_index(self):
        """删除知识库索引"""
        try:
            if self.client.indices.exists(index=self.index_name):
                self.client.indices.delete(index=self.index_name)
                logger.info(f"成功删除索引: {self.index_name}")
            return True
        except Exception as e:
            logger.error(f"删除索引时发生错误: {e}")
            return False

es_client = ESClient()