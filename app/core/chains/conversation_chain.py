from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import BaseRetriever, Document
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage
from app.config.settings import settings
from app.utils.es_client import es_client
from app.utils.aliyun_llm import AliyunLLM
from app.utils.logger import qa_logger
from dashscope import TextEmbedding
from typing import List, Dict, Any
from pydantic import Field, BaseModel
import time
import logging

logger = logging.getLogger(__name__)

class CustomRetriever(BaseRetriever, BaseModel):
    kb_type: str = Field(description="知识库类型")
    index_name: str = Field(description="Elasticsearch 索引名称")
    
    def __init__(self, kb_type: str, **kwargs: Any):
        index_name = f"{settings.ELASTICSEARCH_INDEX_PREFIX}_{kb_type}"
        super().__init__(kb_type=kb_type, index_name=index_name, **kwargs)
    
    async def aget_relevant_documents(self, query: str) -> List[Document]:
        """异步获取相关文档"""
        start_time = time.time()
        try:
            # 使用阿里云的 embedding 服务
            embedding_start = time.time()
            response = TextEmbedding.call(
                model="text-embedding-v2",
                input=query,
                api_key=settings.DASHSCOPE_API_KEY
            )
            embedding_time = time.time() - embedding_start
            qa_logger.log_debug(f"生成 embedding 耗时: {embedding_time:.2f}秒")
            
            if response.status_code == 200:
                query_vector = response.output['embeddings'][0]
                
                # 搜索相似文档
                search_start = time.time()
                results = es_client.search_similar(
                    self.index_name,
                    query_vector,
                    settings.TOP_K_RESULTS
                )
                search_time = time.time() - search_start
                qa_logger.log_debug(f"Elasticsearch 搜索耗时: {search_time:.2f}秒")
                
                # 转换为文档格式
                documents = []
                for hit in results:
                    doc = Document(
                        page_content=hit['_source']['content'],
                        metadata=hit['_source']['metadata']
                    )
                    documents.append(doc)
                
                total_time = time.time() - start_time
                qa_logger.log_info(
                    f"文档检索完成 - 总耗时: {total_time:.2f}秒, "
                    f"找到文档数: {len(documents)}, "
                    f"知识库类型: {self.kb_type}"
                )
                return documents
            else:
                qa_logger.log_error(f"获取 embedding 失败: {response.message}")
                return []
        except Exception as e:
            qa_logger.log_error(f"检索文档时出错: {str(e)}")
            return []
    
    def get_relevant_documents(self, query: str) -> List[Document]:
        """同步获取相关文档"""
        start_time = time.time()
        try:
            # 使用阿里云的 embedding 服务
            embedding_start = time.time()
            response = TextEmbedding.call(
                model="text-embedding-v2",
                input=query,
                api_key=settings.DASHSCOPE_API_KEY
            )
            embedding_time = time.time() - embedding_start
            qa_logger.log_debug(f"生成 embedding 耗时: {embedding_time:.2f}秒")
            
            if response.status_code == 200:
                query_vector = response.output['embeddings'][0]
                
                # 搜索相似文档
                search_start = time.time()
                results = es_client.search_similar(
                    self.index_name,
                    query_vector,
                    settings.TOP_K_RESULTS
                )
                search_time = time.time() - search_start
                qa_logger.log_debug(f"Elasticsearch 搜索耗时: {search_time:.2f}秒")
                
                # 转换为文档格式
                documents = []
                for hit in results:
                    doc = Document(
                        page_content=hit['_source']['content'],
                        metadata=hit['_source']['metadata']
                    )
                    documents.append(doc)
                
                total_time = time.time() - start_time
                qa_logger.log_info(
                    f"文档检索完成 - 总耗时: {total_time:.2f}秒, "
                    f"找到文档数: {len(documents)}, "
                    f"知识库类型: {self.kb_type}"
                )
                return documents
            else:
                qa_logger.log_error(f"获取 embedding 失败: {response.message}")
                return []
        except Exception as e:
            qa_logger.log_error(f"检索文档时出错: {str(e)}")
            return []

class ConversationChain:
    def __init__(self, kb_type: str):
        self.kb_type = kb_type
        self.llm = AliyunLLM()
        self.chat_history = ChatMessageHistory()
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            chat_memory=self.chat_history,
            input_key="question",
            output_key="answer"
        )
        self.retriever = CustomRetriever(kb_type=kb_type)
        self.chain = self._create_chain()
        qa_logger.log_info(f"创建新的对话链实例，知识库类型: {kb_type}")
    
    def _create_chain(self) -> ConversationalRetrievalChain:
        """创建对话检索链"""
        return ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=self.retriever,
            memory=self.memory,
            return_source_documents=True,
            verbose=True
        )
    
    async def get_response(self, query: str) -> Dict:
        """获取响应"""
        start_time = time.time()
        try:
            # 记录问题长度
            qa_logger.log_debug(f"问题长度: {len(query)} 字符")
            
            # 使用 ainvoke 替代 acall
            chain_start = time.time()
            response = await self.chain.ainvoke({
                "question": query
            })
            chain_time = time.time() - chain_start
            
            # 记录性能指标
            answer_length = len(response["answer"])
            total_time = time.time() - start_time
            
            qa_logger.log_debug(
                f"性能指标 - "
                f"链处理时间: {chain_time:.2f}秒, "
                f"总响应时间: {total_time:.2f}秒, "
                f"回答长度: {answer_length} 字符"
            )
            
            # 保存对话历史
            self.chat_history.add_user_message(query)
            self.chat_history.add_ai_message(response["answer"])
            
            # 记录对话历史长度
            history_length = len(self.chat_history.messages)
            qa_logger.log_debug(f"当前对话历史长度: {history_length} 条消息")
            
            return {
                "answer": response["answer"],
                "sources": [doc.metadata for doc in response["source_documents"]]
            }
        except Exception as e:
            qa_logger.log_error(f"获取响应时出错: {str(e)}")
            return {
                "answer": "抱歉，处理您的问题时出现错误。",
                "sources": []
            }
    
    def clear_memory(self):
        """清除对话历史"""
        try:
            history_length = len(self.chat_history.messages)
            self.chat_history.clear()
            self.memory.clear()
            qa_logger.log_info(f"对话历史已清除，共清除 {history_length} 条消息")
        except Exception as e:
            qa_logger.log_error(f"清除对话历史时出错: {str(e)}") 