import pandas as pd
import json
import logging
import csv
from pathlib import Path
from elasticsearch import Elasticsearch
from dashscope import TextEmbedding
from app.config.settings import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_embedding(text):
    """生成文本的向量嵌入"""
    try:
        response = TextEmbedding.call(
            model="text-embedding-v2",
            input=text,
            api_key=settings.DASHSCOPE_API_KEY
        )
        
        if response.status_code == 200:
            return response.output['embeddings'][0]
        else:
            logger.error(f"生成嵌入失败: {response.message}")
            return None
    except Exception as e:
        logger.error(f"生成嵌入时出错: {str(e)}")
        return None

def import_data_from_csv(file_path, index_name):
    """从CSV文件导入数据到Elasticsearch"""
    try:
        # 检查文件是否存在
        path = Path(file_path)
        if not path.exists():
            logger.error(f"文件不存在: {file_path}")
            return False
        
        # 读取CSV文件
        df = pd.read_csv(file_path, quoting=csv.QUOTE_MINIMAL, escapechar='\\')
        logger.info(f"从 {file_path} 读取了 {len(df)} 条记录")
        
        # 连接到Elasticsearch
        es = Elasticsearch(
            f"http://{settings.ELASTICSEARCH_HOST}:{settings.ELASTICSEARCH_PORT}",
            timeout=settings.ELASTICSEARCH_TIMEOUT,
            max_retries=settings.ELASTICSEARCH_MAX_RETRIES,
            retry_on_timeout=settings.ELASTICSEARCH_RETRY_ON_TIMEOUT
        )
        
        # 检查连接
        if not es.ping():
            logger.error("无法连接到Elasticsearch")
            return False
        
        # 检查索引是否存在，如果不存在则创建
        if not es.indices.exists(index=index_name):
            es.indices.create(
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
            logger.info(f"创建索引: {index_name}")
        
        # 导入数据
        success_count = 0
        error_count = 0
        
        for _, row in df.iterrows():
            try:
                # 提取内容和元数据
                content = row['content'].strip()
                
                # 解析和验证元数据
                try:
                    # 尝试解析content字段中的JSON
                    try:
                        content_json = json.loads(content)
                        if isinstance(content_json, dict):
                            content = json.dumps(content_json, ensure_ascii=False)
                    except json.JSONDecodeError:
                        pass
                    
                    metadata = json.loads(row['metadata'])
                    required_fields = ['category', 'source', 'answer', 'role']
                    if not all(field in metadata for field in required_fields):
                        logger.warning(f"跳过记录，元数据缺少必要字段: {required_fields}")
                        error_count += 1
                        continue
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"跳过记录，元数据格式错误: {str(e)}")
                    error_count += 1
                    continue
                
                # 生成嵌入
                # embedding = generate_embedding(content)
                embedding = [0.1]*1536 # to delete after testing
                if embedding is None:
                    logger.warning(f"跳过记录，无法生成嵌入: {content[:50]}...")
                    error_count += 1
                    continue
                
                # 构建文档
                doc = {
                    "content": content,
                    "embedding": embedding,
                    "metadata": metadata
                }
                
                # 索引文档
                es.index(index=index_name, body=doc)
                success_count += 1
                
                # 每100条记录输出一次进度
                if success_count % 100 == 0:
                    logger.info(f"已处理 {success_count} 条记录")
                
            except Exception as e:
                logger.error(f"处理记录时出错: {str(e)}")
                error_count += 1
        
        # 刷新索引
        es.indices.refresh(index=index_name)
        
        logger.info(f"导入完成: 成功 {success_count} 条，失败 {error_count} 条")
        return True if error_count <= 2 else False
        
    except Exception as e:
        logger.error(f"导入数据时出错: {str(e)}")
        return False

def import_all_data():
    """导入所有知识库数据"""
    success = True
    
    for kb_type, file_path in settings.KNOWLEDGE_BASE_PATHS.items():
        index_name = "llm_index"
        logger.info(f"开始导入 {kb_type} 知识库数据到 {index_name}")
        
        if not import_data_from_csv(file_path, index_name):
            logger.error(f"导入 {kb_type} 知识库数据失败")
            success = False
    
    return success

if __name__ == "__main__":
    # 导入所有数据
    if import_all_data():
        print("所有数据导入成功")
    else:
        print("部分或全部数据导入失败，请检查日志")