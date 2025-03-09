import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from logging.handlers import RotatingFileHandler
import traceback
import sys
import os

# 全局日志配置
qa_logger = logging.getLogger("qa_service")

def setup_logger(log_name, log_file=None, level=logging.INFO):
    """设置应用的日志记录器
    
    Args:
        log_name: 日志记录器名称
        log_file: 日志文件路径，如果不提供则输出到标准输出
        level: 日志级别
    
    Returns:
        配置好的日志记录器实例
    """
    logger = logging.getLogger(log_name)
    logger.setLevel(level)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 如果提供了日志文件路径，创建文件处理器
    if log_file:
        # 确保日志目录存在
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # 创建滚动文件处理器，最大10MB，备份5个文件
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def configure_global_logging():
    """设置全局日志配置
    
    配置日志格式和输出级别，确保所有日志都有统一格式
    """
    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 设置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 设置格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    root_logger.addHandler(console_handler)
    
    # 添加文件处理器
    file_handler = RotatingFileHandler(
        f"logs/app_{datetime.now().strftime('%Y%m%d')}.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 设置第三方库的日志级别
    logging.getLogger("elasticsearch").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)

class QALogger:
    """问答系统日志记录器"""
    
    def __init__(self, max_bytes=10*1024*1024, backup_count=5):
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
            '%(asctime)s - %(name)s - %(levelname)s - %(process)d - %(thread)d - %(message)s'
        )
        
        # 确保移除已存在的处理器
        for handler in self.app_logger.handlers[:] + self.qa_logger.handlers[:]:
            handler.close()
            if isinstance(handler, logging.Handler):
                if handler in self.app_logger.handlers:
                    self.app_logger.removeHandler(handler)
                if handler in self.qa_logger.handlers:
                    self.qa_logger.removeHandler(handler)
        
        # 应用日志处理器（按大小轮转）
        app_handler = RotatingFileHandler(
            f"logs/app_{datetime.now().strftime('%Y%m%d')}.log",
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        app_handler.setFormatter(formatter)
        self.app_logger.addHandler(app_handler)
        
        # 问答日志处理器（按大小轮转）
        qa_handler = RotatingFileHandler(
            f"logs/qa_{datetime.now().strftime('%Y%m%d')}.log",
            maxBytes=max_bytes,
            backupCount=backup_count
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
        try:
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
        except Exception as e:
            self.log_error(f"记录问答交互失败: {str(e)}")
    
    def log_error(self, error_msg: str, exc_info: bool = True, stack_info: bool = True) -> None:
        """记录错误信息，包含详细的堆栈跟踪和系统信息"""
        try:
            error_context = {
                "error_message": error_msg,
                "python_version": sys.version,
                "timestamp": datetime.now().isoformat()
            }
            
            if exc_info:
                error_context["traceback"] = traceback.format_exc()
            
            if stack_info:
                error_context["stack_info"] = traceback.extract_stack().format()
            
            self.app_logger.error(
                json.dumps(error_context, ensure_ascii=False),
                exc_info=exc_info,
                stack_info=stack_info
            )
        except Exception as e:
            # 确保日志记录本身的错误不会导致程序崩溃
            print(f"Error logging failed: {str(e)}")
    
    def log_info(self, msg: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录普通信息"""
        try:
            if extra:
                msg = f"{msg} - {json.dumps(extra, ensure_ascii=False)}"
            self.app_logger.info(msg)
        except Exception as e:
            self.log_error(f"记录信息失败: {str(e)}")
    
    def log_warning(self, msg: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录警告信息"""
        try:
            if extra:
                msg = f"{msg} - {json.dumps(extra, ensure_ascii=False)}"
            self.app_logger.warning(msg)
        except Exception as e:
            self.log_error(f"记录警告失败: {str(e)}")
    
    def log_debug(self, msg: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录调试信息"""
        try:
            if extra:
                msg = f"{msg} - {json.dumps(extra, ensure_ascii=False)}"
            self.app_logger.debug(msg)
        except Exception as e:
            self.log_error(f"记录调试信息失败: {str(e)}")

# 创建全局日志记录器实例
qa_logger = QALogger()