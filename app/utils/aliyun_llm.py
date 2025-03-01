from typing import Any, List, Optional, Dict
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun
import json
import requests
from app.config.settings import settings
import logging
from dashscope import Generation

logger = logging.getLogger(__name__)

class AliyunLLM(LLM):
    """阿里云通义千问模型封装"""
    
    api_key: str = ""
    
    def __init__(self):
        super().__init__()
        self.api_key = settings.DASHSCOPE_API_KEY
    
    @property
    def _llm_type(self) -> str:
        return "aliyun"
    
    def _call(self, prompt: str, stop: Optional[List[str]] = None, run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> str:
        try:
            response = Generation.call(
                model='qwen-turbo',
                prompt=prompt,
                api_key=self.api_key,
                **kwargs
            )
            
            if response.status_code == 200:
                return response.output.text
            else:
                logger.error(f"Error from Aliyun API: {response.message}")
                return "抱歉，处理您的请求时出现错误。"
        except Exception as e:
            logger.error(f"Error calling Aliyun API: {e}")
            return "抱歉，系统出现错误。"
    
    async def _acall(self, prompt: str, stop: Optional[List[str]] = None, run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> str:
        """异步调用"""
        return self._call(prompt, stop, run_manager, **kwargs)
    
    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Get the identifying parameters."""
        return {
            "model": "qwen-turbo"
        } 