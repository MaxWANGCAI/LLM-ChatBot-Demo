#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
知识库查询脚本
用于查询Elasticsearch中的知识库数据，包括统计信息和详细内容
"""

import sys
import os
import logging
import argparse
from pathlib import Path
from tabulate import tabulate
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

# 添加项目根目录到 Python 路径
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent
sys.path.append(str(root_dir))

from es_utils import ESManager
from app.config.settings import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KnowledgeBaseExplorer:
    def __init__(self, host="localhost", port=9200):
        self.es_manager = ESManager(host=host, port=port)
        self.es = self.es_manager.es
        self.index_name = settings.ELASTICSEARCH_INDEX_NAME
        
    def check_connection(self):
        """检查与Elasticsearch的连接"""
        try:
            return self.es.ping()
        except Exception as e:
            logger.error(f"连接Elasticsearch失败: {e}")
            return False
    
    def get_index_stats(self):
        """获取索引统计信息"""
        try:
            # 检查索引是否存在
            if not self.es.indices.exists(index=self.index_name):
                logger.error(f"索引 {self.index_name} 不存在")
                return None
                
            # 获取索引统计信息
            stats = self.es.indices.stats(index=self.index_name)
            count = self.es.count(index=self.index_name)
            
            return {
                "索引名称": self.index_name,
                "文档总数": count["count"],
                "索引大小": f"{stats['indices'][self.index_name]['total']['store']['size_in_bytes'] / 1024 / 1024:.2f} MB",
                "分片数": stats['indices'][self.index_name]['primaries']['docs']['count']
            }
        except Exception as e:
            logger.error(f"获取索引统计信息失败: {e}")
            return None
    
    def get_category_stats(self):
        """获取各分类的统计信息"""
        try:
            # 聚合查询各分类的文档数量
            aggs = {
                "categories": {
                    "terms": {
                        "field": "metadata.category",
                        "size": 100  # 最多返回100个分类
                    }
                }
            }
            
            response = self.es.search(
                index=self.index_name,
                body={"size": 0, "aggs": aggs}
            )
            
            categories = []
            for bucket in response["aggregations"]["categories"]["buckets"]:
                categories.append({
                    "分类": bucket["key"],
                    "文档数量": bucket["doc_count"]
                })
                
            return categories
        except Exception as e:
            logger.error(f"获取分类统计信息失败: {e}")
            return []
    
    def get_source_stats(self):
        """获取各来源的统计信息"""
        try:
            # 聚合查询各来源的文档数量
            aggs = {
                "sources": {
                    "terms": {
                        "field": "metadata.source",
                        "size": 100  # 最多返回100个来源
                    }
                }
            }
            
            response = self.es.search(
                index=self.index_name,
                body={"size": 0, "aggs": aggs}
            )
            
            sources = []
            for bucket in response["aggregations"]["sources"]["buckets"]:
                sources.append({
                    "来源": bucket["key"],
                    "文档数量": bucket["doc_count"]
                })
                
            return sources
        except Exception as e:
            logger.error(f"获取来源统计信息失败: {e}")
            return []
    
    def get_role_stats(self):
        """获取各角色的统计信息"""
        try:
            # 聚合查询各角色的文档数量
            aggs = {
                "roles": {
                    "terms": {
                        "field": "metadata.role.keyword",
                        "size": 100  # 最多返回100个角色
                    }
                }
            }
            
            response = self.es.search(
                index=self.index_name,
                body={"size": 0, "aggs": aggs}
            )
            
            roles = []
            for bucket in response["aggregations"]["roles"]["buckets"]:
                roles.append({
                    "角色": bucket["key"],
                    "文档数量": bucket["doc_count"]
                })
                
            return roles
        except Exception as e:
            logger.error(f"获取角色统计信息失败: {e}")
            return []
    
    def get_sample_by_role(self):
        """获取每个角色的样本文档"""
        try:
            # 首先获取所有角色
            roles = self.get_role_stats()
            if not roles:
                logger.warning("未找到任何角色信息")
                return []
            
            samples = []
            for role_info in roles:
                role = role_info["角色"]
                # 查询该角色的一条记录
                response = self.es.search(
                    index=self.index_name,
                    body={
                        "query": {"term": {"metadata.role": role}},
                        "size": 1
                    }
                )
                
                if response["hits"]["hits"]:
                    hit = response["hits"]["hits"][0]
                    sample = {
                        "角色": role,
                        "ID": hit["_id"],
                        "内容": hit["_source"]["content"],
                        "元数据": hit["_source"].get("metadata", {}),
                        "时间戳": hit["_source"].get("timestamp", ""),
                        "向量嵌入": "[向量维度: {}]".format(len(hit["_source"].get("embedding", []))) if "embedding" in hit["_source"] else "无向量嵌入"
                    }
                    samples.append(sample)
            
            return samples
        except Exception as e:
            logger.error(f"获取角色样本失败: {e}")
            return []
    
    def search_documents(self, query=None, category=None, source=None, role=None, limit=10):
        """搜索文档"""
        try:
            # 构建查询条件
            must_conditions = []
            
            if query:
                must_conditions.append({"match": {"content": query}})
            
            if category:
                must_conditions.append({"term": {"metadata.category": category}})
                
            if source:
                must_conditions.append({"term": {"metadata.source": source}})
                
            if role:
                must_conditions.append({"term": {"metadata.role": role}})
            
            # 如果没有任何条件，则查询所有文档
            if not must_conditions:
                must_conditions.append({"match_all": {}})
            
            # 执行查询
            response = self.es.search(
                index=self.index_name,
                body={
                    "query": {"bool": {"must": must_conditions}},
                    "size": limit
                }
            )
            
            documents = []
            for hit in response["hits"]["hits"]:
                doc = {
                    "ID": hit["_id"],
                    "内容": hit["_source"]["content"],
                    "分数": hit["_score"]
                }
                
                # 添加元数据
                if "metadata" in hit["_source"]:
                    metadata = hit["_source"]["metadata"]
                    for key, value in metadata.items():
                        doc[key] = value
                
                documents.append(doc)
                
            return documents
        except Exception as e:
            logger.error(f"搜索文档失败: {e}")
            return []
    
    def get_document_by_id(self, doc_id):
        """根据ID获取文档详情"""
        try:
            response = self.es.get(index=self.index_name, id=doc_id)
            return response["_source"]
        except Exception as e:
            logger.error(f"获取文档详情失败: {e}")
            return None


def print_table(data, headers=None):
    """打印表格"""
    if not data:
        print("没有数据")
        return
        
    if headers:
        print(tabulate(data, headers=headers, tablefmt="grid"))
    else:
        # 如果是字典列表，使用第一个字典的键作为表头
        if isinstance(data[0], dict):
            headers = list(data[0].keys())
            rows = [list(item.values()) for item in data]
            print(tabulate(rows, headers=headers, tablefmt="grid"))
        else:
            print(tabulate(data, tablefmt="grid"))


def print_document(doc):
    """打印文档详情"""
    if not doc:
        print("文档不存在")
        return
        
    print("\n" + "=" * 80)
    print("文档内容:")
    print("-" * 80)
    print(doc["content"])
    print("-" * 80)
    
    if "metadata" in doc:
        print("\n元数据:")
        for key, value in doc["metadata"].items():
            print(f"{key}: {value}")
    
    print("=" * 80 + "\n")


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="知识库查询工具")
    parser.add_argument("--host", default="localhost", help="Elasticsearch主机地址")
    parser.add_argument("--port", type=int, default=9200, help="Elasticsearch端口")
    
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # stats子命令 - 显示统计信息
    stats_parser = subparsers.add_parser("stats", help="显示知识库统计信息")
    stats_parser.add_argument("--detail", action="store_true", help="显示详细统计信息")
    
    # search子命令 - 搜索文档
    search_parser = subparsers.add_parser("search", help="搜索知识库文档")
    search_parser.add_argument("--query", help="搜索关键词")
    search_parser.add_argument("--category", help="按分类筛选")
    search_parser.add_argument("--source", help="按来源筛选")
    search_parser.add_argument("--role", help="按角色筛选")
    search_parser.add_argument("--limit", type=int, default=10, help="返回结果数量限制")
    
    # get子命令 - 获取文档详情
    get_parser = subparsers.add_parser("get", help="获取文档详情")
    get_parser.add_argument("id", help="文档ID")
    
    # roles子命令 - 显示角色样本
    roles_parser = subparsers.add_parser("roles", help="显示各角色的样本文档")
    
    args = parser.parse_args()
    
    # 创建知识库浏览器
    explorer = KnowledgeBaseExplorer(host=args.host, port=args.port)
    
    # 检查连接
    if not explorer.check_connection():
        print("无法连接到Elasticsearch，请检查服务是否启动")
        return
    
    # 执行对应的命令
    if args.command == "stats":
        # 显示基本统计信息
        stats = explorer.get_index_stats()
        if stats:
            print("\n知识库基本统计信息:")
            print_table([stats])
        else:
            print("获取统计信息失败")
        
        # 如果需要显示详细统计信息
        if args.detail:
            # 显示分类统计
            categories = explorer.get_category_stats()
            if categories:
                print("\n各分类统计:")
                print_table(categories)
            
            # 显示来源统计
            sources = explorer.get_source_stats()
            if sources:
                print("\n各来源统计:")
                print_table(sources)
    
            # 显示角色统计
            roles = explorer.get_role_stats()
            if roles:
                print("\n各角色统计:")
                print_table(roles)
    
    elif args.command == "search":
        # 搜索文档
        documents = explorer.search_documents(
            query=args.query,
            category=args.category,
            source=args.source,
            role=args.role,
            limit=args.limit
        )
        
        if documents:
            print(f"\n找到 {len(documents)} 条匹配的文档:")
            # 只显示ID、内容(截断)和分数
            simplified_docs = []
            for doc in documents:
                simplified_doc = {
                    "ID": doc["ID"],
                    "内容": doc["内容"][:100] + "..." if len(doc["内容"]) > 100 else doc["内容"],
                    "分数": doc["分数"]
                }
                
                # 添加分类和来源（如果有）
                if "category" in doc:
                    simplified_doc["分类"] = doc["category"]
                if "source" in doc:
                    simplified_doc["来源"] = doc["source"]
                    
                simplified_docs.append(simplified_doc)
                
            print_table(simplified_docs)
            print("\n提示: 使用 'python query_knowledge_base.py get <ID>' 查看完整文档")
        else:
            print("未找到匹配的文档")
    
    elif args.command == "get":
        # 获取文档详情
        doc = explorer.get_document_by_id(args.id)
        print_document(doc)
    
    elif args.command == "roles":
        # 获取各角色的样本文档
        samples = explorer.get_sample_by_role()
        if samples:
            print("\n各角色样本文档:")
            for sample in samples:
                print("\n" + "=" * 80)
                print(f"角色: {sample['角色']}")
                print(f"ID: {sample['ID']}")
                print("-" * 80)
                print("内容:")
                print(sample['内容'][:200] + "..." if len(sample['内容']) > 200 else sample['内容'])
                print("-" * 80)
                print("元数据:")
                for key, value in sample['元数据'].items():
                    print(f"{key}: {value}")
                print("-" * 80)
                print(f"向量嵌入: {sample['向量嵌入']}")
                print("=" * 80)
            print("\n提示: 使用 'python query_knowledge_base.py get <ID>' 查看完整文档")
        else:
            print("未找到任何角色样本")
    
    else:
        # 如果没有指定命令，显示帮助信息
        parser.print_help()


if __name__ == "__main__":
    main()