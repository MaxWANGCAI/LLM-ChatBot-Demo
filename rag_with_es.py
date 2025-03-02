from es_utils import ESManager
from typing import List, Dict
import os
from dotenv import load_dotenv
import dashscope

load_dotenv()

# 设置阿里云 API Key
dashscope.api_key = os.getenv('DASHSCOPE_API_KEY')

class RAGWithES:
    def __init__(self, vector_weight=0.5, role=None):
        self.es_manager = ESManager()
        self.vector_weight = vector_weight
        self.role = role

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict]:
        """检索相关文档"""
        results = self.es_manager.hybrid_search(
            query=query,
            top_k=top_k,
            vector_weight=self.vector_weight,
            role=self.role
        )
        
        # 提取内容和答案
        contexts = []
        for hit in results:
            source = hit["_source"]
            contexts.append({
                "content": source["content"],
                "answer": source["metadata"].get("answer", ""),
                "role": source["metadata"].get("role", ""),
                "score": hit["_score"]
            })
        
        return contexts

    def generate(self, query: str, contexts: List[Dict]) -> str:
        """生成回答"""
        # 构建提示词
        prompt = self._build_prompt(query, contexts)
        
        # 调用阿里云大模型
        messages = [{"role": "system", "content": self._get_system_prompt()}]
        messages.append({"role": "user", "content": prompt})
        
        response = dashscope.Generation.call(
            'qwen-turbo',
            messages=messages,
            result_format='message',
            temperature=0.7,
            max_tokens=1500,
            top_p=0.8,
            enable_search=True
        )
        
        if response.status_code == 200:
            return response.output.text
        else:
            return f"生成回答时出错：{response.message}"

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        if self.role:
            return f"你是一个专业的{self.role}。请以{self.role}的身份和专业知识来回答问题。"
        return "你是一个专业的AI助手。"

    def _build_prompt(self, query: str, contexts: List[Dict]) -> str:
        """构建提示词"""
        context_text = "\n\n".join([
            f"相关文档 {i+1}:\n问题: {ctx['content']}\n答案: {ctx['answer']}\n角色: {ctx['role']}\n相关度: {ctx['score']:.2f}"
            for i, ctx in enumerate(contexts)
        ])
        
        prompt = f"""请基于以下相关文档回答问题。请严格遵循以下规则：

1. 只使用相关文档中提供的信息来回答问题
2. 如果相关文档中没有足够的信息，请明确说明"抱歉，根据现有信息无法完整回答这个问题"
3. 不要添加、推测或编造任何相关文档中未提及的信息
4. 如果对某些细节不确定，请明确指出不确定的部分
5. 回答时要引用相关文档的编号，说明信息来源

相关文档：
{context_text}

用户问题：{query}

请基于以上规则提供回答："""

    def query(self, query: str, top_k: int = 3) -> str:
        """完整的RAG查询流程"""
        # 1. 检索
        contexts = self.retrieve(query, top_k)
        
        # 2. 生成
        response = self.generate(query, contexts)
        
        return response

def main():
    # 测试不同角色的RAG
    roles = ["business", "customer_service", "legal"]
    test_query = "如何处理客户投诉？"
    
    for role in roles:
        print(f"\n测试 {role} 角色:")
        rag = RAGWithES(vector_weight=0.5, role=role)
        response = rag.query(test_query)
        print(f"问题: {test_query}")
        print(f"回答: {response}")
        print("-" * 50)

if __name__ == "__main__":
    main()