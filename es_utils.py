from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
import numpy as np
from datetime import datetime
import pandas as pd

class ESManager:
    def __init__(self, host="localhost", port=9200, model_name="all-MiniLM-L6-v2", use_gpu=False):
        self.es = Elasticsearch(
            f"http://{host}:{port}",
            timeout=30,
            max_retries=3,
            retry_on_timeout=True
        )
        self.model = SentenceTransformer(model_name)
        if use_gpu:
            self.model = self.model.to('cuda')  # 如果有GPU，使用GPU加速
        self.index_name = "llm_index"

    def create_index(self):
        """创建或更新索引配置"""
        settings = {
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "refresh_interval": "30s",
                "auto_expand_replicas": "0-0"
            },
            "analysis": {
                "analyzer": {
                    "text_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "stop", "snowball"]
                    }
                }
            }
        }
        
        mappings = {
            "properties": {
                "content": {
                    "type": "text",
                    "analyzer": "text_analyzer",
                    "fields": {
                        "keyword": {
                            "type": "keyword",
                            "ignore_above": 256
                        }
                    }
                },
                "embedding": {
                    "type": "dense_vector",
                    "dims": 384,  # all-MiniLM-L6-v2 维度
                    "index": True,
                    "similarity": "cosine"
                },
                "metadata": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "text"},
                        "category": {"type": "keyword"},
                        "role": {"type": "keyword"},
                        "source": {"type": "keyword"}
                    }
                },
                "timestamp": {
                    "type": "date"
                }
            }
        }
        
        if not self.es.indices.exists(index=self.index_name):
            self.es.indices.create(index=self.index_name, settings=settings, mappings=mappings)

    def add_document(self, content, metadata=None):
        """添加文档到ES"""
        embedding = self.model.encode(content)
        
        doc = {
            "content": content,
            "embedding": embedding.tolist(),
            "metadata": metadata or {},
            "timestamp": datetime.now()
        }
        
        return self.es.index(index=self.index_name, document=doc)

    def hybrid_search(self, query: str, top_k=5, vector_weight=0.5, role=None):
        """混合召回：结合BM25和向量搜索，支持按角色过滤"""
        query_vector = self.model.encode(query).tolist()
        
        # 构建基础查询
        must_conditions = [
            {
                "match": {
                    "content": {
                        "query": query,
                        "boost": 1 - vector_weight  # BM25权重
                    }
                }
            }
        ]
        
        # 如果指定了角色，添加角色过滤
        if role:
            must_conditions.append({
                "term": {
                    "metadata.role": role
                }
            })
        
        # 构建混合查询
        hybrid_query = {
            "bool": {
                "must": must_conditions,
                "should": [
                    {
                        "script_score": {
                            "query": {"match_all": {}},
                            "script": {
                                "source": f"cosineSimilarity(params.query_vector, 'embedding') * {vector_weight}",
                                "params": {"query_vector": query_vector}
                            }
                        }
                    }
                ]
            }
        }
        
        response = self.es.search(
            index=self.index_name,
            query=hybrid_query,
            size=top_k
        )
        
        return response["hits"]["hits"]

    def bulk_add_documents(self, documents):
        """批量添加文档"""
        if not documents:
            return None
            
        # 批量计算embeddings
        contents = [doc["content"] for doc in documents]
        embeddings = self.model.encode(contents, batch_size=32, show_progress_bar=True)
        
        operations = []
        for doc, embedding in zip(documents, embeddings):
            operations.append({"index": {"_index": self.index_name}})
            operations.append({
                "content": doc["content"],
                "embedding": embedding.tolist(),
                "metadata": doc.get("metadata", {}),
                "timestamp": datetime.now()
            })
        
        if operations:
            return self.es.bulk(operations=operations)
        return None

    def import_from_csv(self, csv_path, content_column, metadata_columns=None, metadata_defaults=None):
        """从CSV文件导入数据，支持默认元数据"""
        df = pd.read_csv(csv_path)
        documents = []
        
        for _, row in df.iterrows():
            content = str(row[content_column])
            
            # 构建元数据
            metadata = metadata_defaults.copy() if metadata_defaults else {}
            if metadata_columns:
                for col in metadata_columns:
                    if col in row:
                        metadata[col] = str(row[col])
            
            documents.append({
                "content": content,
                "metadata": metadata
            })
            
            # 每1000条数据批量处理一次
            if len(documents) >= 1000:
                self.bulk_add_documents(documents)
                documents = []
        
        # 处理剩余的数据
        if documents:
            self.bulk_add_documents(documents) 