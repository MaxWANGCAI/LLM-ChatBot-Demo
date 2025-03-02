#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
服务状态检查脚本
"""

import sys
import os
import logging
import requests
import json
import psutil
import time
from pathlib import Path
from tabulate import tabulate

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
    """检查 Elasticsearch 服务状态"""
    try:
        response = requests.get("http://localhost:9200")
        if response.status_code == 200:
            data = response.json()
            status = {
                "服务": "Elasticsearch",
                "状态": "运行中",
                "版本": data.get("version", {}).get("number", "未知"),
                "集群名称": data.get("cluster_name", "未知"),
                "节点名称": data.get("name", "未知")
            }
            return True, status
        else:
            status = {
                "服务": "Elasticsearch",
                "状态": "异常",
                "错误": f"状态码: {response.status_code}"
            }
            return False, status
    except Exception as e:
        status = {
            "服务": "Elasticsearch",
            "状态": "未运行",
            "错误": str(e)
        }
        return False, status

def check_elasticsearch_indices():
    """检查 Elasticsearch 索引状态"""
    try:
        response = requests.get("http://localhost:9200/_cat/indices?format=json")
        if response.status_code == 200:
            indices = response.json()
            indices_status = []
            
            for index in indices:
                index_status = {
                    "索引名称": index.get("index", "未知"),
                    "状态": index.get("health", "未知"),
                    "文档数": index.get("docs.count", "未知"),
                    "大小": index.get("store.size", "未知")
                }
                indices_status.append(index_status)
            
            return True, indices_status
        else:
            return False, [{"错误": f"获取索引信息失败，状态码: {response.status_code}"}]
    except Exception as e:
        return False, [{"错误": f"获取索引信息异常: {str(e)}"}]

def check_fastapi_server():
    """检查 FastAPI 服务器状态"""
    try:
        response = requests.get("http://localhost:8000/docs")
        if response.status_code == 200:
            # 查找 uvicorn 进程
            uvicorn_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info']):
                try:
                    if proc.info['cmdline'] and 'uvicorn' in ' '.join(proc.info['cmdline']) and 'app.main:app' in ' '.join(proc.info['cmdline']):
                        # 更新 CPU 使用率
                        proc.cpu_percent(interval=0.1)
                        uvicorn_processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            if uvicorn_processes:
                # 再次获取 CPU 使用率（需要两次调用才能获得准确值）
                time.sleep(0.5)
                process_info = []
                for proc in uvicorn_processes:
                    try:
                        memory_mb = proc.memory_info().rss / (1024 * 1024)
                        process_info.append({
                            "服务": "FastAPI (Uvicorn)",
                            "状态": "运行中",
                            "PID": proc.pid,
                            "CPU使用率": f"{proc.cpu_percent()}%",
                            "内存使用": f"{memory_mb:.2f} MB"
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                return True, process_info
            else:
                return True, [{
                    "服务": "FastAPI",
                    "状态": "运行中",
                    "备注": "API 可访问，但未找到对应进程"
                }]
        else:
            return False, [{
                "服务": "FastAPI",
                "状态": "异常",
                "错误": f"状态码: {response.status_code}"
            }]
    except Exception as e:
        return False, [{
            "服务": "FastAPI",
            "状态": "未运行",
            "错误": str(e)
        }]

def check_api_key():
    """检查 API Key 配置"""
    try:
        from app.config.settings import settings
        
        if settings.DASHSCOPE_API_KEY:
            return True, {
                "配置": "API Key",
                "状态": "已配置",
                "类型": "DashScope"
            }
        else:
            return False, {
                "配置": "API Key",
                "状态": "未配置",
                "错误": "DASHSCOPE_API_KEY 未设置"
            }
    except Exception as e:
        return False, {
            "配置": "API Key",
            "状态": "检查失败",
            "错误": str(e)
        }

def check_system_resources():
    """检查系统资源使用情况"""
    try:
        # CPU 使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 内存使用情况
        memory = psutil.virtual_memory()
        memory_used_gb = memory.used / (1024 * 1024 * 1024)
        memory_total_gb = memory.total / (1024 * 1024 * 1024)
        memory_percent = memory.percent
        
        # 磁盘使用情况
        disk = psutil.disk_usage('/')
        disk_used_gb = disk.used / (1024 * 1024 * 1024)
        disk_total_gb = disk.total / (1024 * 1024 * 1024)
        disk_percent = disk.percent
        
        return True, {
            "CPU使用率": f"{cpu_percent}%",
            "内存使用": f"{memory_used_gb:.2f} GB / {memory_total_gb:.2f} GB ({memory_percent}%)",
            "磁盘使用": f"{disk_used_gb:.2f} GB / {disk_total_gb:.2f} GB ({disk_percent}%)"
        }
    except Exception as e:
        return False, {
            "错误": f"获取系统资源信息失败: {str(e)}"
        }

def print_table(title, data):
    """打印表格"""
    if not data:
        print(f"{title}: 无数据")
        return
    
    if isinstance(data, list):
        if data:
            headers = data[0].keys()
            table = [[item.get(h, "") for h in headers] for item in data]
            print(f"\n{title}:")
            print(tabulate(table, headers=headers, tablefmt="grid"))
    else:
        headers = ["项目", "值"]
        table = [[k, v] for k, v in data.items()]
        print(f"\n{title}:")
        print(tabulate(table, headers=headers, tablefmt="grid"))

def check_status():
    """检查所有服务状态"""
    print("\n===== 系统状态检查 =====\n")
    
    # 检查系统资源
    print("正在检查系统资源...")
    success, system_data = check_system_resources()
    print_table("系统资源", system_data)
    
    # 检查 Elasticsearch
    print("\n正在检查 Elasticsearch 服务...")
    es_success, es_data = check_elasticsearch()
    print_table("Elasticsearch 服务", es_data)
    
    # 如果 Elasticsearch 运行正常，检查索引
    if es_success:
        print("\n正在检查 Elasticsearch 索引...")
        indices_success, indices_data = check_elasticsearch_indices()
        print_table("Elasticsearch 索引", indices_data)
    
    # 检查 FastAPI 服务器
    print("\n正在检查 FastAPI 服务器...")
    api_success, api_data = check_fastapi_server()
    print_table("FastAPI 服务器", api_data)
    
    # 检查 API Key
    print("\n正在检查 API Key 配置...")
    key_success, key_data = check_api_key()
    print_table("API Key 配置", key_data)
    
    # 总结
    print("\n===== 状态检查总结 =====")
    services = [
        ("系统资源", success),
        ("Elasticsearch", es_success),
        ("FastAPI 服务器", api_success),
        ("API Key 配置", key_success)
    ]
    
    all_success = all(success for _, success in services)
    
    if all_success:
        print("\n✅ 所有服务正常运行")
    else:
        print("\n⚠️ 部分服务异常:")
        for service, status in services:
            status_str = "✅ 正常" if status else "❌ 异常"
            print(f"  - {service}: {status_str}")
    
    return all_success

if __name__ == "__main__":
    try:
        all_success = check_status()
        sys.exit(0 if all_success else 1)
    except Exception as e:
        logger.error(f"状态检查过程中出错: {str(e)}")
        sys.exit(1) 