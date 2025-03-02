from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TypedDict

class Document(TypedDict):
    """文档数据结构"""
    id: str
    content: str
    title: str
    score: float
    vector_score: Optional[float]
    keyword_score: Optional[float]
    rerank_score: Optional[float]

class BaseRetriever(ABC):
    """基础检索器接口"""
    
    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 10, **kwargs) -> List[Document]:
        """检索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            **kwargs: 额外的检索参数
            
        Returns:
            List[Document]: 检索结果列表，每个文档包含id、content、title和相关分数
        
        Raises:
            ValueError: 当查询参数无效时
            RuntimeError: 当检索过程发生错误时
        """
        pass
    
    @abstractmethod
    async def rerank(self, query: str, documents: List[Document], top_k: int = 3) -> List[Document]:
        """重排序检索结果
        
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
        pass 