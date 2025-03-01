from app.core.chains.conversation_chain import ConversationChain
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class Assistant:
    def __init__(self, kb_type: str):
        self.kb_type = kb_type
        self.conversation_chain = ConversationChain(kb_type)
    
    async def get_response(self, query: str) -> Dict:
        """获取助手响应"""
        try:
            response = await self.conversation_chain.get_response(query)
            return response
        except Exception as e:
            logger.error(f"Error in assistant response: {e}")
            return {
                "answer": "抱歉，系统出现错误，请稍后再试。",
                "sources": []
            }
    
    def clear_context(self):
        """清除对话上下文"""
        self.conversation_chain.clear_memory()

class LegalAssistant(Assistant):
    def __init__(self):
        super().__init__("legal")

class BusinessAssistant(Assistant):
    def __init__(self):
        super().__init__("business")

class CustomerServiceAssistant(Assistant):
    def __init__(self):
        super().__init__("customer") 