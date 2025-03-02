from elasticsearch import Elasticsearch
from typing import Optional, Dict
from contextlib import contextmanager
from app.utils.logger import qa_logger
import time
from datetime import datetime

class ResourceManager:
    """资源管理器，负责管理ES客户端连接等资源"""
    
    def __init__(self, es_host="localhost", es_port=9200, max_connections=5, connection_timeout=30):
        self.es_host = es_host
        self.es_port = es_port
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self._es_clients: Dict[str, Dict] = {}
        self._last_cleanup = datetime.now()
        self._cleanup_interval = 300  # 5分钟清理一次
    
    def _get_client_key(self) -> str:
        """生成客户端标识"""
        return f"{self.es_host}:{self.es_port}"
    
    def _cleanup_old_connections(self):
        """清理过期的连接"""
        now = datetime.now()
        if (now - self._last_cleanup).total_seconds() < self._cleanup_interval:
            return
        
        try:
            for key, client_info in list(self._es_clients.items()):
                if (now - client_info['last_used']).total_seconds() > self.connection_timeout:
                    client_info['client'].close()
                    del self._es_clients[key]
            self._last_cleanup = now
        except Exception as e:
            qa_logger.log_error(f"清理ES连接失败: {str(e)}")
    
    def get_es_client(self) -> Elasticsearch:
        """从连接池获取或创建ES客户端"""
        self._cleanup_old_connections()
        client_key = self._get_client_key()
        
        if client_key in self._es_clients:
            client_info = self._es_clients[client_key]
            client_info['last_used'] = datetime.now()
            return client_info['client']
        
        if len(self._es_clients) >= self.max_connections:
            # 移除最旧的连接
            oldest_key = min(self._es_clients.keys(), 
                           key=lambda k: self._es_clients[k]['last_used'])
            self._es_clients[oldest_key]['client'].close()
            del self._es_clients[oldest_key]
        
        client = Elasticsearch(
            f"http://{self.es_host}:{self.es_port}",
            timeout=30,
            max_retries=3,
            retry_on_timeout=True
        )
        
        self._es_clients[client_key] = {
            'client': client,
            'last_used': datetime.now()
        }
        
        return client
    
    def close_all_clients(self):
        """关闭所有ES客户端连接"""
        for client_info in self._es_clients.values():
            try:
                client_info['client'].close()
            except Exception as e:
                qa_logger.log_error(f"关闭ES客户端失败: {str(e)}")
        self._es_clients.clear()
    
    @contextmanager
    def es_session(self):
        """ES会话上下文管理器"""
        client = None
        try:
            client = self.get_es_client()
            yield client
        finally:
            if client:
                # 更新最后使用时间而不是关闭连接
                client_key = self._get_client_key()
                if client_key in self._es_clients:
                    self._es_clients[client_key]['last_used'] = datetime.now()
    
    def check_es_health(self) -> dict:
        """检查ES服务健康状态"""
        try:
            with self.es_session() as client:
                start_time = time.time()
                health = client.cluster.health(timeout="5s")
                query_time = time.time() - start_time
                
                return {
                    'status': 'success',
                    'cluster_status': health['status'],
                    'query_time': query_time,
                    'active_shards': health['active_shards'],
                    'relocating_shards': health['relocating_shards'],
                    'initializing_shards': health['initializing_shards'],
                    'unassigned_shards': health['unassigned_shards'],
                    'active_connections': len(self._es_clients)
                }
        except Exception as e:
            qa_logger.log_error(f"ES健康检查失败: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def check_indices(self, required_indices: list) -> dict:
        """检查必需的索引是否存在"""
        try:
            with self.es_session() as client:
                results = {}
                for index in required_indices:
                    exists = client.indices.exists(index=index)
                    results[index] = exists
                return {
                    'status': 'success',
                    'indices': results
                }
        except Exception as e:
            qa_logger.log_error(f"检查索引失败: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }