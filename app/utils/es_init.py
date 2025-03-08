from elasticsearch import Elasticsearch
import logging
from app.config.settings import settings

logger = logging.getLogger(__name__)

def create_index(es_client, index_name):
    """创建 Elasticsearch 索引"""
    try:
        if not es_client.indices.exists(index=index_name):
            es_client.indices.create(
                index=index_name,
                body={
                    "mappings": {
                        "properties": {
                            "content": {"type": "text"},
                            "embedding": {"type": "dense_vector", "dims": 1536},
                            "metadata": {"type": "object"}
                        }
                    }
                }
            )
            logger.info(f"索引 {index_name} 创建成功")
            return True
        else:
            logger.info(f"索引 {index_name} 已存在")
            return True
    except Exception as e:
        logger.error(f"创建索引 {index_name} 失败: {str(e)}")
        return False

def init_elasticsearch_indices():
    """初始化所有必要的 Elasticsearch 索引"""
    try:
        es_client = Elasticsearch(
            f"http://{settings.ELASTICSEARCH_HOST}:{settings.ELASTICSEARCH_PORT}",
            timeout=settings.ELASTICSEARCH_TIMEOUT,
            max_retries=settings.ELASTICSEARCH_MAX_RETRIES,
            retry_on_timeout=settings.ELASTICSEARCH_RETRY_ON_TIMEOUT
        )
        
        # 检查 Elasticsearch 连接
        if not es_client.ping():
            logger.error("无法连接到 Elasticsearch")
            return False
        
        # 创建统一索引
        index_name = settings.ELASTICSEARCH_INDEX_NAME
        success = create_index(es_client, index_name)
        
        return success
    except Exception as e:
        logger.error(f"初始化 Elasticsearch 索引失败: {str(e)}")
        return False

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 初始化索引
    if init_elasticsearch_indices():
        print("所有索引初始化成功")
    else:
        print("索引初始化失败，请检查日志")