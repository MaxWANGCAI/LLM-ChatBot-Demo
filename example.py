from es_utils import ESManager

def main():
    # 初始化ES管理器
    es_manager = ESManager()
    
    # 添加示例文档
    documents = [
        {
            "content": "大模型是一种基于深度学习的人工智能模型",
            "metadata": {"category": "AI", "source": "definition"}
        },
        {
            "content": "向量数据库在大模型应用中起着重要作用",
            "metadata": {"category": "database", "source": "technology"}
        }
    ]
    
    # 批量添加文档
    es_manager.bulk_add_documents(documents)
    
    # 执行语义搜索
    query = "什么是人工智能模型？"
    results = es_manager.search_similar(query)
    
    # 打印搜索结果
    for hit in results:
        print(f"Score: {hit['_score']}")
        print(f"Content: {hit['_source']['content']}")
        print(f"Metadata: {hit['_source']['metadata']}")
        print("---")

if __name__ == "__main__":
    main() 