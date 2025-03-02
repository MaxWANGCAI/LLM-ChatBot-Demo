#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FastAPI 服务器启动脚本
"""

import sys
import os
import logging
import subprocess
import time
import signal
import requests
from pathlib import Path

# 添加项目根目录到 Python 路径
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent
sys.path.append(str(root_dir))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_elasticsearch():
    """检查 Elasticsearch 是否可用"""
    try:
        response = requests.get("http://localhost:9200")
        if response.status_code == 200:
            logger.info("Elasticsearch 服务正常")
            return True
        else:
            logger.error(f"Elasticsearch 服务异常，状态码: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Elasticsearch 服务检查失败: {str(e)}")
        return False

def check_indices():
    """检查必要的索引是否存在"""
    try:
        from app.utils.es_init import init_elasticsearch_indices
        
        logger.info("检查并初始化 Elasticsearch 索引")
        if init_elasticsearch_indices():
            logger.info("Elasticsearch 索引检查/初始化成功")
            return True
        else:
            logger.error("Elasticsearch 索引初始化失败")
            return False
    except Exception as e:
        logger.error(f"Elasticsearch 索引检查失败: {str(e)}")
        return False

def check_api_key():
    """检查 API Key 是否已设置"""
    from app.config.settings import settings
    
    if not settings.DASHSCOPE_API_KEY:
        logger.error("未设置 DASHSCOPE_API_KEY 环境变量")
        return False
    
    logger.info("API Key 检查通过")
    return True

def start_server():
    """启动 FastAPI 服务器"""
    try:
        # 检查前置条件
        if not check_elasticsearch():
            logger.error("Elasticsearch 服务检查失败，无法启动服务器")
            return False
        
        if not check_indices():
            logger.warning("Elasticsearch 索引检查失败，部分功能可能不可用")
        
        if not check_api_key():
            logger.error("API Key 检查失败，无法启动服务器")
            return False
        
        # 启动 FastAPI 服务器
        logger.info("启动 FastAPI 服务器...")
        
        # 使用 uvicorn 启动服务
        cmd = ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "debug"]
        
        # 启动进程
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # 设置信号处理
        def signal_handler(sig, frame):
            logger.info("接收到终止信号，正在关闭服务器...")
            process.terminate()
            process.wait(timeout=5)
            logger.info("服务器已关闭")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 等待服务启动
        time.sleep(2)
        
        # 检查服务是否成功启动
        try:
            response = requests.get("http://localhost:8000/docs")
            if response.status_code == 200:
                logger.info("FastAPI 服务器启动成功，API 文档地址: http://localhost:8000/docs")
            else:
                logger.warning(f"FastAPI 服务器可能未正常启动，状态码: {response.status_code}")
        except Exception as e:
            logger.warning(f"无法连接到 FastAPI 服务器: {str(e)}")
        
        # 输出服务器日志
        logger.info("服务器日志输出:")
        while True:
            output = process.stdout.readline()
            if output:
                print(output.strip())
            
            error = process.stderr.readline()
            if error:
                print(f"ERROR: {error.strip()}", file=sys.stderr)
            
            # 检查进程是否结束
            if process.poll() is not None:
                logger.info(f"服务器进程已结束，退出码: {process.returncode}")
                break
        
        return True
        
    except Exception as e:
        logger.error(f"启动服务器时出错: {str(e)}")
        return False

if __name__ == "__main__":
    start_server() 