#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FastAPI 服务器停止脚本
"""

import os
import sys
import logging
import subprocess
import signal
import time
import psutil
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

def find_uvicorn_processes():
    """查找所有 uvicorn 进程"""
    uvicorn_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # 检查命令行是否包含 uvicorn 和 app.main:app
            if proc.info['cmdline'] and 'uvicorn' in ' '.join(proc.info['cmdline']) and 'app.main:app' in ' '.join(proc.info['cmdline']):
                uvicorn_processes.append(proc)
                logger.info(f"找到 uvicorn 进程: PID={proc.pid}, 命令={' '.join(proc.info['cmdline'])}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    return uvicorn_processes

def stop_server():
    """停止 FastAPI 服务器"""
    try:
        # 查找 uvicorn 进程
        uvicorn_processes = find_uvicorn_processes()
        
        if not uvicorn_processes:
            logger.info("未找到运行中的 uvicorn 进程")
            return True
        
        # 停止所有找到的进程
        for proc in uvicorn_processes:
            logger.info(f"正在停止 uvicorn 进程 (PID={proc.pid})...")
            
            try:
                # 尝试优雅地终止进程
                proc.terminate()
                
                # 等待进程终止
                gone, alive = psutil.wait_procs([proc], timeout=5)
                
                # 如果进程仍然存活，强制终止
                if alive:
                    logger.warning(f"进程 (PID={proc.pid}) 未响应终止信号，正在强制终止...")
                    for p in alive:
                        p.kill()
                
                logger.info(f"进程 (PID={proc.pid}) 已停止")
                
            except psutil.NoSuchProcess:
                logger.info(f"进程 (PID={proc.pid}) 已不存在")
            except Exception as e:
                logger.error(f"停止进程 (PID={proc.pid}) 时出错: {str(e)}")
        
        # 再次检查是否所有进程都已停止
        time.sleep(1)
        remaining = find_uvicorn_processes()
        
        if remaining:
            logger.warning(f"仍有 {len(remaining)} 个 uvicorn 进程在运行")
            return False
        else:
            logger.info("所有 uvicorn 进程已停止")
            return True
            
    except Exception as e:
        logger.error(f"停止服务器时出错: {str(e)}")
        return False

def stop_server_shell():
    """使用 shell 命令停止 FastAPI 服务器"""
    try:
        logger.info("尝试使用 shell 命令停止 uvicorn 进程...")
        
        # 使用 pkill 命令终止 uvicorn 进程
        result = subprocess.run(
            ["pkill", "-f", "uvicorn app.main:app"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("uvicorn 进程已成功停止")
            return True
        elif result.returncode == 1:
            logger.info("未找到匹配的 uvicorn 进程")
            return True
        else:
            logger.error(f"停止 uvicorn 进程失败: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"执行 shell 命令停止服务器时出错: {str(e)}")
        return False

if __name__ == "__main__":
    # 首先尝试使用 psutil 停止服务器
    if not stop_server():
        # 如果失败，尝试使用 shell 命令
        if stop_server_shell():
            logger.info("服务器已成功停止")
        else:
            logger.error("无法停止服务器")
            sys.exit(1)
    else:
        logger.info("服务器已成功停止")
    
    sys.exit(0)