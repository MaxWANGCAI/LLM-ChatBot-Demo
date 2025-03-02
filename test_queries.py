from rag_with_es import RAGWithES

def test_role_specific_queries():
    """测试针对不同角色的查询"""
    test_cases = [
        {
            "role": "business",  # 业务内部知识库助手
            "queries": [
                "公司的主要业务范围有哪些？",
                "如何申请新项目立项？",
                "业务流程审批需要哪些材料？",
                "项目预算编制有什么要求？",
                "如何处理跨部门协作问题？"
            ]
        },
        {
            "role": "customer",  # 客服知识库助手
            "queries": [
                "如何修改订单信息？",
                "退款流程是怎样的？",
                "产品使用过程中遇到问题怎么办？",
                "如何查询订单状态？",
                "会员积分规则是什么？"
            ]
        },
        {
            "role": "legal",  # 法务知识库助手
            "queries": [
                "合同审批流程是怎样的？",
                "知识产权保护有哪些注意事项？",
                "如何处理客户投诉？",
                "数据安全合规要求有哪些？",
                "签订合同需要注意什么？"
            ]
        }
    ]
    
    for case in test_cases:
        role = case["role"]
        print(f"\n\n测试 {role} 角色的回答：")
        print("=" * 50)
        
        rag = RAGWithES(vector_weight=0.5, role=role)
        
        for query in case["queries"]:
            print(f"\n问题: {query}")
            print("-" * 30)
            response = rag.query(query)
            print(f"回答: {response}")
            print("-" * 50)

def test_hybrid_search_weights():
    """测试不同的混合搜索权重"""
    # 选择一个在所有知识库中都可能出现的通用问题
    query = "如何保护客户隐私数据？"
    weights = [0.0, 0.3, 0.5, 0.7, 1.0]
    
    print("\n\n测试不同的混合搜索权重：")
    print("=" * 50)
    
    for weight in weights:
        print(f"\n向量搜索权重: {weight}")
        print("-" * 30)
        rag = RAGWithES(vector_weight=weight)
        response = rag.query(query)
        print(f"回答: {response}")
        print("-" * 50)

def test_cross_domain_queries():
    """测试跨领域问题的处理能力"""
    test_queries = [
        {
            "query": "客户投诉涉及合同纠纷怎么处理？",
            "roles": ["customer_service", "legal"]
        },
        {
            "query": "业务合作协议的审批流程是什么？",
            "roles": ["business", "legal"]
        },
        {
            "query": "客户要求业务流程变更怎么处理？",
            "roles": ["customer_service", "business"]
        }
    ]
    
    print("\n\n测试跨领域问题处理：")
    print("=" * 50)
    
    for test_case in test_queries:
        query = test_case["query"]
        print(f"\n问题: {query}")
        print("跨领域测试：")
        
        for role in test_case["roles"]:
            print(f"\n{role} 视角的回答:")
            print("-" * 30)
            rag = RAGWithES(vector_weight=0.5, role=role)
            response = rag.query(query)
            print(f"回答: {response}")
        print("-" * 50)

if __name__ == "__main__":
    print("开始全面测试 RAG 系统...")
    
    # 1. 测试角色特定查询
    test_role_specific_queries()
    
    # 2. 测试混合搜索权重
    test_hybrid_search_weights()
    
    # 3. 测试跨领域问题
    test_cross_domain_queries()
    
    print("\n测试完成！")