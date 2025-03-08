from elasticsearch import Elasticsearch
from dashscope import TextEmbedding
import numpy as np
from datetime import datetime
import pandas as pd
import os
from app.config.settings import settings

class ESManager:
    def __init__(self, host="localhost", port=9200, model_name=None, api_key=None):
        self.es = Elasticsearch(
            f"http://{host}:{port}",
            timeout=30,
            max_retries=3,
            retry_on_timeout=True
        )
        # 从环境变量获取API Key和模型名称
        self.api_key = api_key or os.getenv('DASHSCOPE_API_KEY')
        if not self.api_key:
            raise ValueError("DashScope API key is required")
        self.model_name = model_name or os.getenv('MODEL_NAME', 'text-embedding-v2')
        self.index_name = settings.ELASTICSEARCH_INDEX_NAME

    def _get_embedding(self, text):
        """使用DashScope API获取文本嵌入向量"""
        '''try:
            response = TextEmbedding.call(
                model=self.model_name,
                input=text,
                api_key=self.api_key
            )
            if response.status_code == 200:
                return response.output['embeddings'][0]
            else:
                raise Exception(f"API调用失败: {response.code} - {response.message}")
        except Exception as e:
            raise Exception(f"获取嵌入向量失败: {str(e)}")'''
        retun [0.1]*1536 # to delete after test

    def _batch_get_embeddings(self, texts, batch_size=32):
        """批量获取文本嵌入向量"""
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            '''try:
                response = TextEmbedding.call(
                    model=self.model_name,
                    input=batch_texts,
                    api_key=self.api_key
                )
                if response.status_code == 200:
                    all_embeddings.extend(response.output['embeddings'])
                else:
                    raise Exception(f"API调用失败: {response.code} - {response.message}")
            except Exception as e:
                raise Exception(f"批量获取嵌入向量失败: {str(e)}")'''
            all_embeddings.extend(np.full((len(batch_texts),1536),0.1)) # to delete after test
        return all_embeddings

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
                    "dims": 1536,  # text-embedding-v2 维度
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
        embedding = self._get_embedding(content)
        
        doc = {
            "content": content,
            "embedding": embedding,
            "metadata": metadata or {},
            "timestamp": datetime.now()
        }
        
        return self.es.index(index=self.index_name, document=doc)

    def hybrid_search(self, query: str, top_k=5, vector_weight=0.5, role=None):
        """混合召回：结合BM25和向量搜索，支持按角色过滤"""
        query_vector = self._get_embedding(query)
        
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
        """批量添加文档，确保元数据完整性"""
        if not documents:
            return None
        
        # 数据验证
        validated_documents = []
        for doc in documents:
            if not isinstance(doc, dict) or 'content' not in doc:
                print(f"警告：跳过无效文档: {doc}")
                continue
                
            # 确保metadata是一个字典
            metadata = doc.get('metadata', {})
            if not isinstance(metadata, dict):
                metadata = {}
                print(f"警告：文档的metadata不是字典类型，已重置为空字典: {doc}")
            
            validated_documents.append({
                'content': str(doc['content']),
                'metadata': metadata
            })
        
        if not validated_documents:
            print("警告：没有有效的文档需要处理")
            return None
            
        # 批量计算embeddings
        contents = [doc['content'] for doc in validated_documents]
        embeddings = self._batch_get_embeddings(contents)
        
        operations = []
        for doc, embedding in zip(validated_documents, embeddings):
            operations.append({"index": {"_index": self.index_name}})
            operations.append({
                "content": doc['content'],
                "embedding": embedding,
                "metadata": doc['metadata'],
                "timestamp": datetime.now()
            })
        
        if operations:
            try:
                response = self.es.bulk(operations=operations)
                if response.get('errors'):
                    print(f"警告：批量导入过程中出现错误: {response}")
                return response
            except Exception as e:
                print(f"错误：批量导入失败: {str(e)}")
                return None
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
                        # 确保非空值
                        value = row[col]
                        if pd.notna(value):
                            metadata[col] = str(value) if not isinstance(value, (int, float, bool)) else value
            
            # 验证内容不为空
            if not content.strip():
                print(f"警告：跳过空内容的行")
                continue
                
            documents.append({
                'content': content,
                'metadata': metadata
            })
            
            # 每1000条数据批量处理一次
            if len(documents) >= 1000:
                self.bulk_add_documents(documents)
                documents = []
        
        # 处理剩余的数据
        if not documents:
            print("警告：没有有效的文档需要导入")
            return None
            
        return self.bulk_add_documents(documents)