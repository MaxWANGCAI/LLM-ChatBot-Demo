import sys
from pathlib import Path
from elasticsearch import Elasticsearch
import logging

# Add project root directory to Python path
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent
sys.path.append(str(root_dir))

# Now we can import from app
from app.config.settings import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
from app.utils.es_client import es_client
import logging

logger = logging.getLogger(__name__)

def main():
        # 获取配置中的索引前缀
        index_name = settings.ELASTICSEARCH_INDEX_NAME

        # 获取所有匹配索引
        existing_indices = list(es_client.client.indices.get(index=f"{index_name}").keys())
        
        if not existing_indices:
            logger.info(f"没有找到匹配的索引: {index_name}")
            return
            
        # 批量删除索引
        if existing_indices:
            for index_name in existing_indices:
                es_client.client.indices.delete(index=index_name)
                logger.info(f"成功删除索引: {index_name}")

if __name__ == "__main__":
    main()