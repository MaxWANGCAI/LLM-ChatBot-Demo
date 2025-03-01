import pandas as pd
from typing import List, Dict
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from app.config.settings import settings
from app.utils.es_client import es_client
import logging

logger = logging.getLogger(__name__)

class KnowledgeBaseLoader:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(openai_api_key=settings.OPENAI_API_KEY)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )
    
    def load_csv(self, file_path: str) -> List[Dict]:
        """加载 CSV 文件并处理为文档列表"""
        try:
            df = pd.read_csv(file_path)
            documents = []
            for _, row in df.iterrows():
                # 假设 CSV 文件包含 'content' 和 'metadata' 列
                doc = {
                    'content': row['content'],
                    'metadata': row.get('metadata', {})
                }
                documents.append(doc)
            return documents
        except Exception as e:
            logger.error(f"Error loading CSV file {file_path}: {e}")
            raise
    
    def process_documents(self, documents: List[Dict], kb_type: str):
        """处理文档并存入 Elasticsearch"""
        try:
            index_name = f"{settings.ELASTICSEARCH_INDEX_PREFIX}_{kb_type}"
            es_client.create_index(index_name)
            
            for doc in documents:
                # 分割文本
                texts = self.text_splitter.split_text(doc['content'])
                
                # 为每个文本块生成向量
                for text in texts:
                    vector = self.embeddings.embed_query(text)
                    
                    # 构建文档
                    es_doc = {
                        'content': text,
                        'vector': vector,
                        'metadata': doc['metadata']
                    }
                    
                    # 存入 Elasticsearch
                    es_client.index_document(index_name, es_doc)
                    
            logger.info(f"Successfully processed and indexed documents for {kb_type}")
        except Exception as e:
            logger.error(f"Error processing documents: {e}")
            raise

    def init_knowledge_base(self):
        """初始化所有知识库"""
        for kb_type, file_path in settings.KNOWLEDGE_BASE_PATHS.items():
            try:
                documents = self.load_csv(file_path)
                self.process_documents(documents, kb_type)
                logger.info(f"Successfully initialized {kb_type} knowledge base")
            except Exception as e:
                logger.error(f"Error initializing {kb_type} knowledge base: {e}")
                continue

kb_loader = KnowledgeBaseLoader() 