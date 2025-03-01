import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

class QALogger:
    """问答系统日志记录器"""
    
    def __init__(self):
        # 创建日志目录
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # 创建应用日志记录器
        self.app_logger = logging.getLogger("qa_app")
        self.app_logger.setLevel(logging.INFO)
        
        # 创建问答日志记录器
        self.qa_logger = logging.getLogger("qa_metrics")
        self.qa_logger.setLevel(logging.INFO)
        
        # 设置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # 应用日志处理器（按日期滚动）
        app_handler = logging.FileHandler(
            f"logs/app_{datetime.now().strftime('%Y%m%d')}.log"
        )
        app_handler.setFormatter(formatter)
        self.app_logger.addHandler(app_handler)
        
        # 问答日志处理器（按日期滚动）
        qa_handler = logging.FileHandler(
            f"logs/qa_{datetime.now().strftime('%Y%m%d')}.log"
        )
        qa_handler.setFormatter(formatter)
        self.qa_logger.addHandler(qa_handler)
    
    def log_qa_interaction(
        self,
        session_id: str,
        question: str,
        answer: str,
        kb_type: str,
        sources: list,
        response_time: float,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录一次问答交互
        
        Args:
            session_id: 会话ID
            question: 用户问题
            answer: 系统回答
            kb_type: 知识库类型
            sources: 引用的知识库来源
            response_time: 响应时间（秒）
            error: 错误信息（如果有）
            metadata: 其他元数据
        """
        qa_record = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "kb_type": kb_type,
            "question": question,
            "answer": answer,
            "sources": sources,
            "response_time": response_time,
            "error": error,
            "metadata": metadata or {}
        }
        
        self.qa_logger.info(json.dumps(qa_record, ensure_ascii=False))
    
    def log_error(self, error_msg: str, exc_info: bool = True) -> None:
        """记录错误信息"""
        self.app_logger.error(error_msg, exc_info=exc_info)
    
    def log_info(self, msg: str) -> None:
        """记录普通信息"""
        self.app_logger.info(msg)
    
    def log_warning(self, msg: str) -> None:
        """记录警告信息"""
        self.app_logger.warning(msg)
    
    def log_debug(self, msg: str) -> None:
        """记录调试信息"""
        self.app_logger.debug(msg)

# 创建全局日志记录器实例
qa_logger = QALogger() 