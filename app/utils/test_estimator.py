from typing import Dict, List, Any
from app.utils.logger import qa_logger

class TestEstimator:
    """测试资源预估器"""
    
    def __init__(self):
        self.api_costs = {
            'text_embedding': {
                'name': '文本向量嵌入',
                'model': 'text-embedding-v2',
                'count': 0,
                'unit_price': 0.001  # 每千字符的价格（元）
            },
            'text_generation': {
                'name': '文本生成',
                'model': 'qwen-max',
                'count': 0,
                'unit_price': 0.01  # 每千字符的价格（元）
            }
        }
    
    def estimate_embedding_cost(self, text_length: int) -> float:
        """估算文本向量嵌入成本"""
        return (text_length / 1000) * self.api_costs['text_embedding']['unit_price']
    
    def estimate_generation_cost(self, prompt_length: int) -> float:
        """估算文本生成成本"""
        return (prompt_length / 1000) * self.api_costs['text_generation']['unit_price']
    
    def analyze_test_cases(self, test_cases: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """分析测试用例并预估API调用量"""
        total_cases = 0
        total_embedding_chars = 0
        total_generation_chars = 0
        
        # 统计每个类别的测试用例
        category_stats = {}
        
        for category, cases in test_cases.items():
            category_stats[category] = {
                'case_count': len(cases),
                'total_chars': sum(len(case['question']) for case in cases)
            }
            total_cases += len(cases)
            
            # 每个问题都需要进行向量嵌入
            for case in cases:
                question_length = len(case['question'])
                total_embedding_chars += question_length
                # 假设每个回答平均500字
                total_generation_chars += question_length + 500
        
        # 计算总成本
        embedding_cost = self.estimate_embedding_cost(total_embedding_chars)
        generation_cost = self.estimate_generation_cost(total_generation_chars)
        total_cost = embedding_cost + generation_cost
        
        return {
            'summary': {
                'total_test_cases': total_cases,
                'total_embedding_chars': total_embedding_chars,
                'total_generation_chars': total_generation_chars,
                'estimated_costs': {
                    'embedding': round(embedding_cost, 2),
                    'generation': round(generation_cost, 2),
                    'total': round(total_cost, 2)
                }
            },
            'category_details': category_stats,
            'api_details': {
                'text_embedding': {
                    'model': self.api_costs['text_embedding']['model'],
                    'estimated_calls': total_cases
                },
                'text_generation': {
                    'model': self.api_costs['text_generation']['model'],
                    'estimated_calls': total_cases
                }
            }
        }
    
    def generate_estimation_report(self, test_cases: Dict[str, List[Dict[str, Any]]]) -> str:
        """生成预估报告"""
        estimation = self.analyze_test_cases(test_cases)
        
        report = [
            "=== 测试资源预估报告 ===",
            f"\n总测试用例数: {estimation['summary']['total_test_cases']}",
            "\n按类别统计:"
        ]
        
        for category, stats in estimation['category_details'].items():
            report.append(f"- {category}: {stats['case_count']} 个用例，共 {stats['total_chars']} 字符")
        
        report.extend([
            "\nAPI调用统计:",
            f"- 文本向量嵌入: {estimation['api_details']['text_embedding']['estimated_calls']} 次调用",
            f"- 文本生成: {estimation['api_details']['text_generation']['estimated_calls']} 次调用",
            "\n预估成本:",
            f"- 文本向量嵌入: {estimation['summary']['estimated_costs']['embedding']} 元",
            f"- 文本生成: {estimation['summary']['estimated_costs']['generation']} 元",
            f"- 总成本: {estimation['summary']['estimated_costs']['total']} 元"
        ])
        
        return '\n'.join(report)

# 创建预估器实例
test_estimator = TestEstimator()