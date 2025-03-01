from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import time
import uuid
from app.core.chains.conversation_chain import ConversationChain
from app.utils.logger import qa_logger

router = APIRouter()

# 存储会话实例
conversation_chains: Dict[str, ConversationChain] = {}

class ChatRequest(BaseModel):
    question: str
    kb_type: str
    session_id: str = ""

class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    session_id: str

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """处理聊天请求"""
    start_time = time.time()
    session_id = request.session_id or str(uuid.uuid4())
    error = None
    
    try:
        # 获取或创建会话实例
        if session_id not in conversation_chains:
            qa_logger.log_info(f"创建新会话: {session_id}, 知识库类型: {request.kb_type}")
            conversation_chains[session_id] = ConversationChain(kb_type=request.kb_type)
        
        chain = conversation_chains[session_id]
        
        # 记录请求信息
        qa_logger.log_info(f"收到问题 - 会话: {session_id}, 问题: {request.question}")
        
        # 获取回答
        response = await chain.get_response(request.question)
        
        # 计算响应时间
        response_time = time.time() - start_time
        
        # 记录问答交互
        qa_logger.log_qa_interaction(
            session_id=session_id,
            question=request.question,
            answer=response["answer"],
            kb_type=request.kb_type,
            sources=response["sources"],
            response_time=response_time,
            metadata={
                "token_count": len(request.question) + len(response["answer"]),  # 简单的token计数
                "source_count": len(response["sources"])
            }
        )
        
        return ChatResponse(
            answer=response["answer"],
            sources=response["sources"],
            session_id=session_id
        )
        
    except Exception as e:
        error = str(e)
        qa_logger.log_error(f"处理问题时出错 - 会话: {session_id}, 错误: {error}")
        
        # 记录失败的问答交互
        qa_logger.log_qa_interaction(
            session_id=session_id,
            question=request.question,
            answer="",
            kb_type=request.kb_type,
            sources=[],
            response_time=time.time() - start_time,
            error=error
        )
        
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clear_context")
async def clear_context(session_id: str):
    """清除会话上下文"""
    try:
        if session_id in conversation_chains:
            conversation_chains[session_id].clear_memory()
            qa_logger.log_info(f"清除会话上下文: {session_id}")
            return {"message": "上下文已清除"}
        return {"message": "会话不存在"}
    except Exception as e:
        error_msg = f"清除上下文时出错 - 会话: {session_id}, 错误: {str(e)}"
        qa_logger.log_error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg) 