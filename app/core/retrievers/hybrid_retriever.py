from typing import List, Dict, Any, Optional, Protocol
from elasticsearch import AsyncElasticsearch, NotFoundError, TransportError
from app.core.retrievers.base_retriever import BaseRetriever, Document
from app.core.retrievers.reranker import DashScopeReranker
from app.utils.logger import qa_logger

class EmbeddingModel(Protocol):
    """向量模型接口"""
    async def encode(self, text: str) -> List[float]:
        """将文本编码为向量"""
        ...

class HybridRetriever(BaseRetriever):
    """混合检索器实现"""
    
    def __init__(
        self, 
        es_client: AsyncElasticsearch,
        index_name: str,
        embedding_model: EmbeddingModel,
        reranker: Optional[DashScopeReranker] = None,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3
    ):
        """初始化混合检索器
        
        Args:
            es_client: Elasticsearch客户端
            index_name: 索引名称
            embedding_model: 向量模型
            reranker: 重排序器实例
            vector_weight: 向量检索得分权重
            keyword_weight: 关键词检索得分权重
        """
        self.es_client = es_client
        self.index_name = index_name
        self.embedding_model = embedding_model
        self.reranker = reranker or DashScopeReranker()
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        
    async def retrieve(self, query: str, top_k: int = 3, **kwargs) -> List[Document]:
        """混合检索实现
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            **kwargs: 额外参数
                min_score: 最小分数阈值
                
        Returns:
            List[Document]: 检索结果列表
            
        Raises:
            ValueError: 当查询为空或top_k小于1时
            RuntimeError: 当检索过程发生错误时
        """
        if not query.strip():
            raise ValueError("查询文本不能为空")
        if top_k < 1:
            raise ValueError("top_k必须大于0")
            
        min_score = kwargs.get("min_score", 0.0)
        
        try:
            # 向量检索
            query_vector = await self.embedding_model.encode(query)
            vector_results = await self.es_client.search(
                index=self.index_name,
                body={
                    "size": top_k * 2,
                    "query": {
                        "script_score": {
                            "query": {"match_all": {}},
                            "script": {
                                "source": "cosineSimilarity(params.query_vector, 'vector') + 1.0",
                                "params": {"query_vector": query_vector}
                            }
                        }
                    },
                    "_source": ["content", "title"]
                }
            )
            
            # 关键词检索
            keyword_results = await self.es_client.search(
                index=self.index_name,
                body={
                    "size": top_k,
                    "query": {
                        "multi_match": {
                            "query": query,
                            "fields": ["content", "title^2"],
                            "type": "most_fields"
                        }
                    },
                    "_source": ["content", "title"]
                }
            )
            
            # 合并结果
            all_docs: List[Document] = []
            seen_ids = set()
            
            # 处理向量检索结果
            for hit in vector_results["hits"]["hits"]:
                if hit["_id"] not in seen_ids:
                    doc: Document = {
                        "id": hit["_id"],
                        "content": hit["_source"]["content"],
                        "title": hit["_source"].get("title", ""),
                        "score": hit["_score"] * self.vector_weight,
                        "vector_score": hit["_score"],
                        "keyword_score": None,
                        "rerank_score": None
                    }
                    all_docs.append(doc)
                    seen_ids.add(hit["_id"])
            
            # 处理关键词检索结果
            for hit in keyword_results["hits"]["hits"]:
                if hit["_id"] not in seen_ids:
                    doc: Document = {
                        "id": hit["_id"],
                        "content": hit["_source"]["content"],
                        "title": hit["_source"].get("title", ""),
                        "score": hit["_score"] * self.keyword_weight,
                        "vector_score": None,
                        "keyword_score": hit["_score"],
                        "rerank_score": None
                    }
                    all_docs.append(doc)
                    seen_ids.add(hit["_id"])
                else:
                    # 更新已存在文档的关键词得分
                    for doc in all_docs:
                        if doc["id"] == hit["_id"]:
                            doc["keyword_score"] = hit["_score"]
                            # 更新综合得分
                            vector_score = doc["vector_score"] or 0
                            doc["score"] = vector_score * self.vector_weight + hit["_score"] * self.keyword_weight
                            break
            
            # 重排序
            if len(all_docs) > top_k:
                return await self.rerank(query, all_docs, top_k)
            return all_docs[:top_k]
            
        except NotFoundError:
            qa_logger.log_error(f"索引 {self.index_name} 不存在")
            raise RuntimeError(f"索引 {self.index_name} 不存在")
        except Exception as e:
            qa_logger.log_error(f"混合检索过程发生错误: {str(e)}")
            raise RuntimeError(f"混合检索过程发生错误: {str(e)}")
            
    async def rerank(self, query: str, documents: List[Document], top_k: int = 3) -> List[Document]:
        """重排序实现
        
        Args:
            query: 查询文本
            documents: 待重排序的文档列表
            top_k: 返回结果数量
            
        Returns:
            List[Document]: 重排序后的结果列表
            
        Raises:
            ValueError: 当输入参数无效时
            RuntimeError: 当重排序过程发生错误时
        """
        if not query.strip():
            raise ValueError("查询文本不能为空")
        if not documents:
            return []
        if top_k < 1:
            raise ValueError("top_k必须大于0")
            
        return await self.reranker.rerank(query, documents, top_k) 