import psutil
import time
from typing import Dict, Any
from datetime import datetime
from elasticsearch import Elasticsearch
from app.utils.logger import qa_logger

class SystemMonitor:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.memory_threshold = config.get('memory_threshold', 80)
        self.cpu_threshold = config.get('cpu_threshold', 70)
        self.es_query_timeout = config.get('es_query_timeout', 3)
        self.metrics_history = []

    def collect_system_metrics(self) -> Dict[str, Any]:
        """收集系统指标"""
        try:
            metrics = {
                'timestamp': datetime.now(),
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'network_io': psutil.net_io_counters()._asdict()
            }
            self.metrics_history.append(metrics)
            return metrics
        except Exception as e:
            qa_logger.log_error(f"系统指标收集失败: {str(e)}")
            return {}

    def check_es_performance(self, es: Elasticsearch) -> Dict[str, Any]:
        """检查ES性能指标"""
        try:
            start_time = time.time()
            health = es.cluster.health(timeout=f"{self.es_query_timeout}s")
            query_time = time.time() - start_time

            return {
                'cluster_status': health['status'],
                'query_time': query_time,
                'active_shards': health['active_shards'],
                'relocating_shards': health['relocating_shards'],
                'initializing_shards': health['initializing_shards'],
                'unassigned_shards': health['unassigned_shards']
            }
        except Exception as e:
            qa_logger.log_error(f"ES性能检查失败: {str(e)}")
            return {}

    def check_system_health(self) -> Dict[str, Any]:
        """检查系统健康状态"""
        metrics = self.collect_system_metrics()
        health_status = {
            'status': 'healthy',
            'warnings': [],
            'timestamp': datetime.now()
        }

        if metrics.get('memory_percent', 0) > self.memory_threshold:
            health_status['warnings'].append({
                'type': 'memory_warning',
                'message': f"内存使用率超过阈值: {metrics['memory_percent']}%"
            })
            health_status['status'] = 'warning'

        if metrics.get('cpu_percent', 0) > self.cpu_threshold:
            health_status['warnings'].append({
                'type': 'cpu_warning',
                'message': f"CPU使用率超过阈值: {metrics['cpu_percent']}%"
            })
            health_status['status'] = 'warning'

        return health_status

    def get_performance_report(self) -> Dict[str, Any]:
        """生成性能报告"""
        if not self.metrics_history:
            return {}

        avg_cpu = sum(m['cpu_percent'] for m in self.metrics_history) / len(self.metrics_history)
        avg_memory = sum(m['memory_percent'] for m in self.metrics_history) / len(self.metrics_history)

        return {
            'period_start': self.metrics_history[0]['timestamp'],
            'period_end': self.metrics_history[-1]['timestamp'],
            'samples_count': len(self.metrics_history),
            'avg_cpu_usage': round(avg_cpu, 2),
            'avg_memory_usage': round(avg_memory, 2),
            'max_cpu_usage': max(m['cpu_percent'] for m in self.metrics_history),
            'max_memory_usage': max(m['memory_percent'] for m in self.metrics_history)
        }