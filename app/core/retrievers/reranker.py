from typing import List, Dict, Any, Optional
import dashscope
from dashscope.api_entities.api_request_exception import ApiRequestException
from app.core.retrievers.base_retriever import Document
from app.config.settings import settings
from app.utils.logger import qa_logger

class DashScopeReranker:
    """DashScope重排序器实现"""
    
    def __init__(self, model: str = "rerank-v1", api_key: Optional[str] = None):
        """初始化重排序器
        
        Args:
            model: 模型名称
            api_key: API密钥，如果为None则从settings获取
            
        Raises:
            ValueError: 当API密钥未设置时
        """
        self.model = model
        self.api_key = api_key or settings.DASHSCOPE_API_KEY
        
        if not self.api_key:
            raise ValueError("DashScope API密钥未设置")
            
        dashscope.api_key = self.api_key
    
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
            
        try:
            # 准备重排序输入
            pairs = []
            for doc in documents:
                if not doc.get("content"):
                    qa_logger.log_warning(f"文档 {doc.get('id', 'unknown')} 缺少content字段")
                    continue
                    
                pairs.append({
                    "query": query,
                    "passage": doc["content"],
                    "doc_id": doc["id"]
                })
                
            if not pairs:
                qa_logger.log_warning("没有有效的文档用于重排序")
                return documents[:top_k]
            
            # 调用DashScope重排序API
            response = await dashscope.rerank.call(
                model=self.model,
                pairs=pairs,
                top_k=min(top_k, len(pairs))
            )
            
            if response.status_code == 200:
                # 处理重排序结果
                reranked_docs: List[Document] = []
                for result in response.output["results"][:top_k]:
                    # 找到原始文档
                    try:
                        original_doc = next(
                            doc for doc in documents 
                            if doc["id"] == result["doc_id"]
                        )
                    except StopIteration:
                        qa_logger.log_error(f"找不到ID为 {result['doc_id']} 的原始文档")
                        continue
                        
                    # 更新得分并保留其他信息
                    reranked_doc = original_doc.copy()
                    reranked_doc["score"] = result["score"]
                    reranked_doc["rerank_score"] = result["score"]
                    reranked_docs.append(reranked_doc)
                
                return reranked_docs
            else:
                qa_logger.log_error(f"DashScope重排序API调用失败: {response.code} - {response.message}")
                raise RuntimeError(f"DashScope重排序API调用失败: {response.code} - {response.message}")
                
        except ApiRequestException as e:
            qa_logger.log_error(f"DashScope API请求错误: {str(e)}")
            raise RuntimeError(f"DashScope API请求错误: {str(e)}")
        except Exception as e:
            qa_logger.log_error(f"重排序过程发生错误: {str(e)}")
            raise RuntimeError(f"重排序过程发生错误: {str(e)}") 