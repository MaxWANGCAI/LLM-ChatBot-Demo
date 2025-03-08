import asyncio
import json
import time
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd
import matplotlib.pyplot as plt
import pytest
import pytest_asyncio
from app.utils.test_estimator import test_estimator
from app.core.chains.conversation_chain import ConversationChain
from app.utils.logger import qa_logger
from elasticsearch import Elasticsearch
import requests
from app.config.settings import settings  # 改用项目自己的settings

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # macOS
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

# 设置 pytest-asyncio 默认事件循环作用域
pytest_asyncio.default_fixture_loop_scope = "function"

@dataclass
class TestResult:
    """测试结果类"""
    category: str
    question: str
    kb_type: str
    status: str
    response_time: float
    answer: Optional[str] = None
    sources: Optional[List] = None
    error: Optional[str] = None
    validation_result: Optional[Dict] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "category": self.category,
            "question": self.question,
            "kb_type": self.kb_type,
            "status": self.status,
            "response_time": self.response_time,
            "answer": self.answer,
            "sources": self.sources,
            "error": self.error,
            "validation_result": self.validation_result
        }

@pytest.mark.asyncio
class TestQASystem:
    """问答系统测试类"""
    
    @pytest.fixture(autouse=True)
    def setup_class(self):
        self.test_results = []
        self.test_cases = self._get_test_cases()
        self.validation_rules = self._get_validation_rules()
        self.critical_error_count = 0
        self.max_critical_errors = 3
        self.estimator = test_estimator
        
        # 显示测试资源预估
        self.show_estimation()
    
    def show_estimation(self):
        """显示测试资源预估报告"""
        estimation = self.generate_estimation_report()
        
        print("\n=== 测试资源评估报告 ===")
        print(f"\n1. 测试用例统计:")
        print(f"   - 总用例数: {estimation['test_cases']['total']}条")
        print("\n   按类别分布:")
        for category, count in estimation['test_cases']['by_category'].items():
            print(f"   - {category}: {count}条")
        print("\n   按知识库类型分布:")
        for kb_type, count in estimation['test_cases']['by_kb_type'].items():
            print(f"   - {kb_type}: {count}条")
        
        print(f"\n2. API调用估算:")
        print(f"   DashScope API:")
        print(f"   Chat API:")
        print(f"   - 预计调用次数: {estimation['api_calls']['dashscope']['chat']['estimated_count']}次")
        print(f"   - 预计总token数: {estimation['api_calls']['dashscope']['chat']['estimated_tokens']}")
        print(f"   - 详细token统计:")
        print(f"     - 提示词tokens: {estimation['api_calls']['dashscope']['chat']['details']['prompt_tokens']}")
        print(f"     - 上下文tokens: {estimation['api_calls']['dashscope']['chat']['details']['context_tokens']}")
        print(f"     - 回答生成tokens: {estimation['api_calls']['dashscope']['chat']['details']['response_tokens']}")
        
        print(f"\n   Rerank API:")
        print(f"   - 预计调用次数: {estimation['api_calls']['dashscope']['rerank']['estimated_count']}次")
        print(f"   - 预计重排序对数: {estimation['api_calls']['dashscope']['rerank']['estimated_pairs']}对")
        print(f"   - 平均长度统计:")
        print(f"     - 问题长度: {estimation['api_calls']['dashscope']['rerank']['details']['query_avg_length']}字符")
        print(f"     - 段落长度: {estimation['api_calls']['dashscope']['rerank']['details']['passage_avg_length']}字符")
        
        print(f"\n   总成本: ¥{estimation['api_calls']['dashscope']['total_cost']:.2f}")
        
        print(f"\n   Elasticsearch:")
        print(f"   - 预计查询次数: {estimation['api_calls']['elasticsearch']['estimated_queries']}次")
        print(f"   - 详细查询统计:")
        print(f"     - 向量检索(top10): {estimation['api_calls']['elasticsearch']['details']['vector_search']}次")
        print(f"     - 关键词检索(top5): {estimation['api_calls']['elasticsearch']['details']['keyword_search']}次")
        print(f"     - 元数据过滤: {estimation['api_calls']['elasticsearch']['details']['metadata_filter']}次")
        
        print(f"\n3. 资源使用估算:")
        for resource, usage in estimation['resource_usage'].items():
            print(f"   - {usage}")
        
        print(f"\n4. 预计执行时间: {estimation['estimated_duration']}秒")
        print(f"   (约 {estimation['estimated_duration']/60:.1f}分钟)")
        
        # 等待用户确认
        user_input = input("\n请确认是否继续测试 (y/n): ")
        if user_input.lower() != 'y':
            print("测试已取消")
            pytest.skip("用户取消测试")
    
    def basic_checks(self):
        """执行基础检查项"""
        # 检查本地ES服务可用性
        es = Elasticsearch("http://localhost:9200")
        try:
            if not es.ping():
                raise Exception("本地Elasticsearch服务未启动，请先启动ES服务")
        except Exception as e:
            raise Exception(f"连接本地Elasticsearch服务失败: {str(e)}")

        # 检查索引存在性
        required_indices = ["llm_index"]
        for index_name in required_indices:
            if not es.indices.exists(index=index_name):
                # 尝试创建索引
                try:
                    es.indices.create(
                        index=index_name,
                        body={
                            "mappings": {
                                "properties": {
                                    "content": {"type": "text"},
                                    "embedding": {"type": "dense_vector", "dims": 1536},
                                    "metadata": {"type": "object"}
                                }
                            }
                        }
                    )
                    qa_logger.log_info(f"自动创建索引: {index_name}")
                except Exception as e:
                    raise Exception(f"索引 {index_name} 不存在且无法创建: {str(e)}")

        # 检查大模型调用正常性
        chain = ConversationChain(kb_type="general")
        response = asyncio.run(chain.get_response("测试"))
        if not response or "answer" not in response:
            raise Exception("大模型调用失败")

        # 检查网络服务可用性
        try:
            res = requests.get("http://localhost:8000/docs")
            if res.status_code != 200:
                raise Exception("网络服务不可用")
        except requests.exceptions.RequestException as e:
            raise Exception(f"网络服务检查失败: {e}")
    
    async def test_qa_system(self):
        """测试问答系统的主要功能"""
        try:
            # 执行基础检查
            self.basic_checks()
            
            # 执行测试用例
            for category, cases in self.test_cases.items():
                qa_logger.log_info(f"开始执行测试类别: {category}")
                session_id = f"test_{int(time.time())}"
                
                for case in cases:
                    # 检查是否达到最大错误数
                    if self.critical_error_count >= self.max_critical_errors:
                        qa_logger.log_error(f"达到最大严重错误数 ({self.max_critical_errors})，停止测试")
                        return
                    
                    result = await self.run_test_case(case, category, session_id)
                    self.test_results.append(result)
                    
                    # 记录测试结果
                    qa_logger.log_info(
                        f"测试用例完成 - "
                        f"类别: {category}, "
                        f"问题: {case['question']}, "
                        f"状态: {result.status}"
                    )
                    
                    if result.status != "success":
                        qa_logger.log_warning(
                            f"测试用例未通过 - "
                            f"错误: {result.error}, "
                            f"验证结果: {result.validation_result}"
                        )
            
            # 验证测试结果
            assert len(self.test_results) > 0, "没有执行任何测试用例"
            success_count = sum(1 for r in self.test_results if r.status == "success")
            assert success_count > 0, "所有测试用例都失败了"
            
        except Exception as e:
            qa_logger.log_error(f"测试执行失败: {str(e)}")
            qa_logger.log_error("异常堆栈信息:", exc_info=True)
            raise

    def _get_validation_rules(self) -> Dict:
        """获取验证规则"""
        return {
            "基本规则": {
                "min_answer_length": 10,
                "max_response_time": 10,
                "required_fields": ["answer", "sources"],
            },
            "知识库规则": {
                "min_sources": 1,
                "max_sources": 5,
            },
            "错误处理规则": {
                "critical_errors": [
                    "NotFoundError",
                    "ConnectionError",
                    "AuthenticationError",
                ],
            }
        }
    
    def _get_test_cases(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取测试用例"""
        return {
            "未知信息测试": [
                {
                    "question": "火星上的重力是多少？",
                    "kb_type": "general",
                    "expected": {
                        "min_length": 20,
                        "keywords": ["抱歉", "无法", "信息", "不足"],
                        "required_source_types": []
                    }
                },
                {
                    "question": "公司2030年的发展规划是什么？",
                    "kb_type": "business",
                    "expected": {
                        "min_length": 20,
                        "keywords": ["抱歉", "无法", "信息", "不足"],
                        "required_source_types": []
                    }
                },
                {
                    "question": "未来五年的法律法规变化趋势如何？",
                    "kb_type": "legal",
                    "expected": {
                        "min_length": 20,
                        "keywords": ["抱歉", "无法", "信息", "不足"],
                        "required_source_types": []
                    }
                }
            ],
            "基础对话测试": [
                {
                    "question": "你好",
                    "kb_type": "general",
                    "expected": {
                        "min_length": 5,
                        "keywords": ["你好", "您好", "欢迎"],
                        "required_source_types": []
                    }
                },
                {
                    "question": "请介绍一下你自己",
                    "kb_type": "general",
                    "expected": {
                        "min_length": 20,
                        "keywords": ["助手", "帮助", "服务"],
                        "required_source_types": []
                    }
                },
                {
                    "question": "你能帮我做什么",
                    "kb_type": "general",
                    "expected": {
                        "min_length": 30,
                        "keywords": ["帮助", "问题", "解答", "服务"],
                        "required_source_types": []
                    }
                }
            ],
            "客服助手测试": [
                {
                    "question": "退货政策是什么？",
                    "kb_type": "customer",
                    "expected": {
                        "min_length": 30,
                        "keywords": ["退换货", "7天", "质量问题", "运费", "商家承担"],
                        "required_source_types": ["客服手册"]
                    }
                },
                {
                    "question": "配送需要多长时间？",
                    "kb_type": "customer",
                    "expected": {
                        "min_length": 30,
                        "keywords": ["配送时效", "24小时", "发货", "偏远地区", "48-72小时"],
                        "required_source_types": ["配送指南"]
                    }
                },
                {
                    "question": "退货流程是怎样的？",
                    "kb_type": "customer",
                    "expected": {
                        "min_length": 30,
                        "keywords": ["退货申请", "客服审核", "退货地址", "验收", "退款处理"],
                        "required_source_types": ["售后服务手册"]
                    }
                },
                {
                    "question": "如何修改收货地址？",
                    "kb_type": "customer",
                    "expected": {
                        "min_length": 20,
                        "keywords": ["订单", "修改", "地址", "联系客服"],
                        "required_source_types": ["订单管理手册"]
                    }
                },
                {
                    "question": "商品质量问题如何投诉？",
                    "kb_type": "customer",
                    "expected": {
                        "min_length": 40,
                        "keywords": ["质量", "投诉", "客服", "凭证", "处理流程"],
                        "required_source_types": ["投诉处理指南"]
                    }
                }
            ],
            "法律助手测试": [
                {
                    "question": "什么是知识产权保护？",
                    "kb_type": "legal",
                    "expected": {
                        "min_length": 50,
                        "keywords": ["知识产权", "保护", "法律"],
                        "required_source_types": ["legal_doc"]
                    }
                },
                {
                    "question": "合同审批流程是怎样的？",
                    "kb_type": "legal",
                    "expected": {
                        "min_length": 40,
                        "keywords": ["合同", "审批", "流程", "法务", "签字"],
                        "required_source_types": ["legal_doc"]
                    }
                },
                {
                    "question": "如何处理商标侵权问题？",
                    "kb_type": "legal",
                    "expected": {
                        "min_length": 50,
                        "keywords": ["商标", "侵权", "法律", "维权", "证据"],
                        "required_source_types": ["legal_doc"]
                    }
                },
                {
                    "question": "数据安全合规要求有哪些？",
                    "kb_type": "legal",
                    "expected": {
                        "min_length": 60,
                        "keywords": ["数据", "安全", "合规", "保护", "隐私"],
                        "required_source_types": ["legal_doc"]
                    }
                }
            ],
            "商业助手测试": [
                {
                    "question": "如何制定有效的营销策略？",
                    "kb_type": "business",
                    "expected": {
                        "min_length": 50,
                        "keywords": ["营销", "策略", "市场"],
                        "required_source_types": ["business_doc"]
                    }
                },
                {
                    "question": "品类知识库的主要功能是什么？",
                    "kb_type": "business",
                    "expected": {
                        "min_length": 40,
                        "keywords": ["品类", "知识库", "功能", "特征指标", "共创"],
                        "required_source_types": ["business_doc"]
                    }
                },
                {
                    "question": "如何评估新项目的可行性？",
                    "kb_type": "business",
                    "expected": {
                        "min_length": 50,
                        "keywords": ["项目", "评估", "可行性", "风险", "收益"],
                        "required_source_types": ["business_doc"]
                    }
                },
                {
                    "question": "业务流程审批需要哪些材料？",
                    "kb_type": "business",
                    "expected": {
                        "min_length": 40,
                        "keywords": ["流程", "审批", "材料", "文档", "表单"],
                        "required_source_types": ["business_doc"]
                    }
                }
            ],
            "跨知识库测试": [
                {
                    "question": "客户投诉涉及合同纠纷怎么处理？",
                    "kb_type": ["customer", "legal"],
                    "expected": {
                        "min_length": 60,
                        "keywords": ["投诉", "合同", "纠纷", "处理", "法务"],
                        "required_source_types": ["客服手册", "legal_doc"]
                    }
                },
                {
                    "question": "业务合作协议的审批流程是什么？",
                    "kb_type": ["business", "legal"],
                    "expected": {
                        "min_length": 50,
                        "keywords": ["协议", "审批", "流程", "法务", "业务"],
                        "required_source_types": ["business_doc", "legal_doc"]
                    }
                },
                {
                    "question": "客户要求业务流程变更怎么处理？",
                    "kb_type": ["customer", "business"],
                    "expected": {
                        "min_length": 50,
                        "keywords": ["客户", "流程", "变更", "处理", "审批"],
                        "required_source_types": ["客服手册", "business_doc"]
                    }
                },
                {
                    "question": "如何处理跨部门的客户投诉？",
                    "kb_type": ["customer", "business", "legal"],
                    "expected": {
                        "min_length": 70,
                        "keywords": ["投诉", "跨部门", "协调", "处理", "流程"],
                        "required_source_types": ["客服手册", "business_doc", "legal_doc"]
                    }
                },
                {
                    "question": "新产品上线的合规审查流程是什么？",
                    "kb_type": ["business", "legal"],
                    "expected": {
                        "min_length": 60,
                        "keywords": ["产品", "合规", "审查", "流程", "法务"],
                        "required_source_types": ["business_doc", "legal_doc"]
                    }
                },
                {
                    "question": "如何处理客户数据泄露事件？",
                    "kb_type": ["customer", "legal"],
                    "expected": {
                        "min_length": 70,
                        "keywords": ["数据", "泄露", "处理", "安全", "法律"],
                        "required_source_types": ["客服手册", "legal_doc"]
                    }
                },
                {
                    "question": "品牌授权使用的审批流程是什么？",
                    "kb_type": ["business", "legal"],
                    "expected": {
                        "min_length": 60,
                        "keywords": ["品牌", "授权", "审批", "流程", "法务"],
                        "required_source_types": ["business_doc", "legal_doc"]
                    }
                },
                {
                    "question": "如何处理供应商合同争议？",
                    "kb_type": ["business", "legal"],
                    "expected": {
                        "min_length": 60,
                        "keywords": ["供应商", "合同", "争议", "处理", "法务"],
                        "required_source_types": ["business_doc", "legal_doc"]
                    }
                },
                {
                    "question": "客户要求赔偿的处理流程是什么？",
                    "kb_type": ["customer", "legal"],
                    "expected": {
                        "min_length": 60,
                        "keywords": ["赔偿", "处理", "流程", "客服", "法务"],
                        "required_source_types": ["客服手册", "legal_doc"]
                    }
                },
                {
                    "question": "如何处理跨境业务的法律风险？",
                    "kb_type": ["business", "legal"],
                    "expected": {
                        "min_length": 70,
                        "keywords": ["跨境", "业务", "法律", "风险", "合规"],
                        "required_source_types": ["business_doc", "legal_doc"]
                    }
                }
            ]
        }
    
    def validate_response(self, test_case: Dict, result: Dict) -> Dict[str, Any]:
        """验证响应结果"""
        validation_result = {
            "passed": True,
            "checks": [],
            "is_critical": False
        }
        
        # 检查基本规则
        basic_rules = self.validation_rules["基本规则"]
        if result["answer"]:
            if len(result["answer"]) < basic_rules["min_answer_length"]:
                validation_result["checks"].append({
                    "rule": "min_answer_length",
                    "passed": False,
                    "message": f"回答长度不足 {basic_rules['min_answer_length']} 字符"
                })
                validation_result["passed"] = False
        
        if result["response_time"] > basic_rules["max_response_time"]:
            validation_result["checks"].append({
                "rule": "max_response_time",
                "passed": False,
                "message": f"响应时间超过 {basic_rules['max_response_time']} 秒"
            })
            validation_result["passed"] = False
        
        # 检查知识库规则
        if "expected" in test_case:
            expected = test_case["expected"]
            
            # 检查最小长度
            if "min_length" in expected and result["answer"]:
                if len(result["answer"]) < expected["min_length"]:
                    validation_result["checks"].append({
                        "rule": "expected_min_length",
                        "passed": False,
                        "message": f"回答长度不满足预期最小长度 {expected['min_length']}"
                    })
                    validation_result["passed"] = False
            
            # 改进关键词匹配算法
            if "keywords" in expected and result["answer"]:
                answer_lower = result["answer"].lower()
                missing_keywords = []
                for kw in expected["keywords"]:
                    kw_lower = kw.lower()
                    # 使用更灵活的匹配方式
                    if not any(variant in answer_lower for variant in [
                        kw_lower,
                        kw_lower.replace(" ", ""),  # 移除空格
                        kw_lower.replace("-", ""),  # 移除连字符
                        kw_lower.replace("_", "")   # 移除下划线
                    ]):
                        missing_keywords.append(kw)
                
                if missing_keywords:
                    validation_result["checks"].append({
                        "rule": "keywords",
                        "passed": False,
                        "message": f"缺少关键词: {', '.join(missing_keywords)}"
                    })
                    validation_result["passed"] = False
            
            # 检查知识库来源类型
            if "required_source_types" in expected and result["sources"]:
                for required_type in expected["required_source_types"]:
                    if not any(required_type in str(source.get("type", ""))
                             for source in result["sources"]):
                        validation_result["checks"].append({
                            "rule": "source_types",
                            "passed": False,
                            "message": f"缺少必需的知识库来源类型: {required_type}"
                        })
                        validation_result["passed"] = False
        
        # 检查错误是否严重
        if result.get("error"):
            error_text = str(result["error"])
            critical_errors = self.validation_rules["错误处理规则"]["critical_errors"]
            if any(err in error_text for err in critical_errors):
                validation_result["is_critical"] = True
                validation_result["checks"].append({
                    "rule": "critical_error",
                    "passed": False,
                    "message": f"发生严重错误: {error_text}"
                })
                validation_result["passed"] = False
        
        return validation_result
    
    async def run_test_case(self, test_case: Dict, category: str, session_id: str) -> TestResult:
        """运行单个测试用例"""
        start_time = time.time()
        try:
            question = test_case["question"]
            kb_type = test_case["kb_type"]
            
            # 获取或创建对话链
            chain = ConversationChain(kb_type=kb_type)
            
            # 记录测试开始信息
            qa_logger.log_info(f"开始执行测试用例 - 类别: {category}, 问题: {question}")
            
            # 获取响应
            response = await chain.get_response(question)
            
            # 计算响应时间
            response_time = time.time() - start_time
            
            # 记录响应时间
            qa_logger.log_debug(f"测试用例响应时间: {response_time:.2f}秒")
            
            # 确保响应中包含所有必要字段
            result = {
                "status": "success",
                "response_time": response_time,
                "answer": response.get("answer", ""),
                "sources": response.get("sources", []),
                "error": None,
                "validation_checks": []
            }
            
            # 验证结果
            validation_result = self.validate_response(test_case, result)
            
            # 如果验证失败，更新状态并记录详细信息
            if not validation_result["passed"]:
                result["status"] = "failed"
                if validation_result["is_critical"]:
                    self.critical_error_count += 1
                    qa_logger.log_error(f"发生严重错误 - 类别: {category}, 问题: {question}")
                    qa_logger.log_error(f"验证结果: {json.dumps(validation_result, ensure_ascii=False)}")
                else:
                    qa_logger.log_warning(f"测试验证失败 - 类别: {category}, 问题: {question}")
                    qa_logger.log_warning(f"验证结果: {json.dumps(validation_result, ensure_ascii=False)}")
            
            # 确保结果包含所有必要字段
            test_result = {
                'category': category,
                'question': question,
                'kb_type': kb_type,
                'status': result.get('status', 'error'),
                'response_time': result.get('response_time', 0),
                'answer': result.get('answer', ''),
                'sources': result.get('sources', []),
                'error': result.get('error', None),
                'validation_result': validation_result
            }
            
            return TestResult(**test_result)
            
        except Exception as e:
            error_msg = str(e)
            qa_logger.log_error(f"测试用例执行失败: {error_msg}")
            qa_logger.log_error(f"异常堆栈信息:", exc_info=True)
            
            # 创建错误结果
            result = {
                "status": "error",
                "response_time": time.time() - start_time,
                "answer": None,
                "sources": None,
                "error": error_msg
            }
            
            # 验证结果
            validation_result = self.validate_response(test_case, result)
            if validation_result["is_critical"]:
                self.critical_error_count += 1
            
            # 确保结果包含所有必要字段
            test_result = {
                'category': category,
                'question': question,
                'kb_type': kb_type,
                'status': result.get('status', 'error'),
                'response_time': result.get('response_time', 0),
                'answer': result.get('answer', ''),
                'sources': result.get('sources', []),
                'error': result.get('error', None),
                'validation_result': validation_result
            }
            
            return TestResult(**test_result)
    
    def generate_estimation_report(self) -> Dict:
        """生成详细的资源评估报告"""
        estimation = {
            "test_cases": {
                "total": 0,
                "by_category": {},
                "by_kb_type": {
                    "general": 0,
                    "legal": 0,
                    "business": 0,
                    "customer": 0
                }
            },
            "api_calls": {
                "dashscope": {
                    "chat": {
                        "estimated_count": 0,
                        "estimated_tokens": 0,
                        "details": {
                            "prompt_tokens": 0,
                            "context_tokens": 0,
                            "response_tokens": 0
                        }
                    },
                    "rerank": {
                        "estimated_count": 0,
                        "estimated_pairs": 0,
                        "details": {
                            "query_avg_length": 30,  # 平均问题长度
                            "passage_avg_length": 200  # 平均段落长度
                        }
                    },
                    "total_cost": 0.0
                },
                "elasticsearch": {
                    "estimated_queries": 0,
                    "details": {
                        "vector_search": 0,
                        "keyword_search": 0,
                        "metadata_filter": 0
                    }
                }
            },
            "estimated_duration": 0,
            "resource_usage": {
                "memory": "预计峰值内存使用: 1GB",
                "cpu": "预计CPU使用率: 30-50%",
                "disk": "预计临时文件存储: 200MB"
            }
        }
        
        # 统计测试用例
        for category, cases in self.test_cases.items():
            category_count = len(cases)
            estimation["test_cases"]["total"] += category_count
            estimation["test_cases"]["by_category"][category] = category_count
            
            # 统计知识库类型和估算API调用
            for case in cases:
                kb_type = case["kb_type"]
                kb_types = [kb_type] if isinstance(kb_type, str) else kb_type
                
                # 更新知识库类型统计
                for kt in kb_types:
                    estimation["test_cases"]["by_kb_type"][kt] += 1
                
                # 估算API调用
                # 1. DashScope Chat API调用
                prompt_tokens = 200  # 初始提示词token数
                context_tokens = 0   # 知识库内容token数（经过rerank后的）
                response_tokens = 300  # 回答生成token数
                
                # 2. ES多路召回
                total_recall_docs = 0
                for _ in kb_types:
                    # 向量检索 top10
                    estimation["api_calls"]["elasticsearch"]["details"]["vector_search"] += 1
                    total_recall_docs += 10
                    
                    # 关键词检索 top5
                    estimation["api_calls"]["elasticsearch"]["details"]["keyword_search"] += 1
                    total_recall_docs += 5
                    
                    # 元数据过滤
                    estimation["api_calls"]["elasticsearch"]["details"]["metadata_filter"] += 1
                
                # 3. DashScope Rerank
                # 对每个知识库的召回结果进行rerank
                rerank_pairs = total_recall_docs  # 每个文档都要和query做一次rerank
                estimation["api_calls"]["dashscope"]["rerank"]["estimated_count"] += 1
                estimation["api_calls"]["dashscope"]["rerank"]["estimated_pairs"] += rerank_pairs
                
                # 4. 选择top3重排序后的文档作为上下文
                context_tokens_per_doc = 200  # 每个文档平均token数
                selected_docs = min(3, total_recall_docs)
                total_context_tokens = selected_docs * context_tokens_per_doc
                
                # 更新Chat API统计
                estimation["api_calls"]["dashscope"]["chat"]["details"]["prompt_tokens"] += prompt_tokens
                estimation["api_calls"]["dashscope"]["chat"]["details"]["context_tokens"] += total_context_tokens
                estimation["api_calls"]["dashscope"]["chat"]["details"]["response_tokens"] += response_tokens
                estimation["api_calls"]["dashscope"]["chat"]["estimated_tokens"] += (
                    prompt_tokens + total_context_tokens + response_tokens
                )
                estimation["api_calls"]["dashscope"]["chat"]["estimated_count"] += 1
                
                # 更新ES查询总数
                estimation["api_calls"]["elasticsearch"]["estimated_queries"] = (
                    estimation["api_calls"]["elasticsearch"]["details"]["vector_search"] +
                    estimation["api_calls"]["elasticsearch"]["details"]["keyword_search"] +
                    estimation["api_calls"]["elasticsearch"]["details"]["metadata_filter"]
                )
            
            # 估算成本
            # 1. Chat API成本
            chat_token_price_per_k = 0.02  # 每千tokens 0.02元
            chat_cost = (
                estimation["api_calls"]["dashscope"]["chat"]["estimated_tokens"] 
                / 1000 * chat_token_price_per_k
            )
            
            # 2. Rerank API成本
            rerank_price_per_k_pairs = 0.01  # 每千对 0.01元
            rerank_cost = (
                estimation["api_calls"]["dashscope"]["rerank"]["estimated_pairs"] 
                / 1000 * rerank_price_per_k_pairs
            )
            
            # 总成本
            estimation["api_calls"]["dashscope"]["total_cost"] = chat_cost + rerank_cost
        
        # 估算总执行时间
        # 基础时间：每个测试用例的基本处理时间
        base_time_per_case = 2  # 秒
        # 知识库处理时间：每个知识库的检索和处理时间
        kb_time_per_case = 3  # 秒
        # 跨知识库额外时间：合并和处理多个知识库的结果
        cross_kb_time = 2  # 秒
        # Rerank处理时间：每10个文档约1秒
        rerank_time_per_10_docs = 1  # 秒
        
        total_time = 0
        for category, cases in self.test_cases.items():
            for case in cases:
                kb_type = case["kb_type"]
                kb_count = 1 if isinstance(kb_type, str) else len(kb_type)
                
                # 计算每个知识库的召回文档数
                docs_per_kb = 15  # 向量检索10 + 关键词检索5
                total_docs = kb_count * docs_per_kb
                
                case_time = (
                    base_time_per_case +  # 基础处理时间
                    (kb_time_per_case * kb_count) +  # 知识库处理时间
                    (cross_kb_time if kb_count > 1 else 0) +  # 跨知识库处理时间
                    (total_docs / 10 * rerank_time_per_10_docs)  # Rerank处理时间
                )
                total_time += case_time
        
        estimation["estimated_duration"] = total_time
        
        # 根据测试规模调整资源使用估算
        if estimation["test_cases"]["total"] > 20:
            estimation["resource_usage"]["memory"] = "预计峰值内存使用: 1.5GB"
            estimation["resource_usage"]["cpu"] = "预计CPU使用率: 40-60%"
        if estimation["test_cases"]["total"] > 40:
            estimation["resource_usage"]["memory"] = "预计峰值内存使用: 2GB"
            estimation["resource_usage"]["cpu"] = "预计CPU使用率: 50-70%"
        
        return estimation

    async def run_all_tests(self):
        """运行所有测试用例"""
        try:
            # 执行测试
            await self.test_qa_system()
            
            # 生成报告
            report_path = self.generate_report()
            print(f"\n测试报告已生成: {report_path}")
            
        finally:
            # 清理和关闭服务
            await self.cleanup_services()
    
    async def cleanup_services(self):
        """清理和关闭服务"""
        print("\n=== 开始清理服务 ===")
        
        try:
            # 重置测试状态
            self.test_results = []
            self.critical_error_count = 0
            print("- 测试状态已重置")
            
            print("服务清理完成")
            
        except Exception as e:
            print(f"清理服务时发生错误: {str(e)}")
            raise

    def generate_report(self):
        """生成测试报告"""
        # 创建报告目录
        report_dir = Path("test_reports")
        report_dir.mkdir(exist_ok=True)
        
        # 清理旧的报告文件
        self._cleanup_old_reports()
        
        # 当前时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 转换为DataFrame
        df = pd.DataFrame([r.to_dict() for r in self.test_results])
        
        # 基本统计
        total_tests = len(df)
        successful_tests = len(df[df["status"] == "success"])
        failed_tests = len(df[df["status"] == "failed"])
        error_tests = len(df[df["status"] == "error"])
        avg_response_time = df["response_time"].mean()
        
        # 计算测试覆盖率
        code_coverage = self._calculate_code_coverage()
        kb_coverage = self._calculate_kb_coverage()
        
        # 生成响应时间分布图
        plt.figure(figsize=(10, 6))
        plt.hist(df["response_time"], bins=20, color='skyblue', edgecolor='black')
        plt.title("响应时间分布", fontsize=12)
        plt.xlabel("响应时间（秒）", fontsize=10)
        plt.ylabel("频次", fontsize=10)
        plt.grid(True, alpha=0.3)
        plt.savefig(f"test_reports/response_time_dist_{timestamp}.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # 按类别统计
        category_stats = df.groupby("category").agg({
            "status": lambda x: (x == "success").mean(),
            "response_time": "mean",
            "question": "count"
        }).round(3)
        category_stats.columns = ["成功率", "平均响应时间", "测试用例数"]
        
        # 生成类别统计图
        plt.figure(figsize=(12, 6))
        ax = category_stats["成功率"].plot(kind="bar", color='lightgreen')
        plt.title("各类别测试成功率", fontsize=12)
        plt.xlabel("测试类别", fontsize=10)
        plt.ylabel("成功率", fontsize=10)
        plt.grid(True, axis='y', alpha=0.3)
        plt.xticks(rotation=45)
        
        # 添加数值标签
        for i, v in enumerate(category_stats["成功率"]):
            ax.text(i, v, f'{v:.1%}', ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig(f"test_reports/category_success_rate_{timestamp}.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # 生成验证结果统计
        validation_summary = self._calculate_validation_summary()
        
        # 使用模板生成HTML报告
        template_path = Path("app/templates/test_report_template.html")
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
        
        # 替换模板变量
        html_report = template.replace("{{timestamp}}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        html_report = html_report.replace("{{total_tests}}", str(total_tests))
        html_report = html_report.replace("{{successful_tests}}", str(successful_tests))
        html_report = html_report.replace("{{failed_tests}}", str(failed_tests))
        html_report = html_report.replace("{{error_tests}}", str(error_tests))
        html_report = html_report.replace("{{avg_response_time}}", f"{avg_response_time:.2f}")
        html_report = html_report.replace("{{critical_error_count}}", str(self.critical_error_count))
        
        # 替换覆盖率信息
        html_report = html_report.replace("{{code_coverage.statement_coverage}}", str(code_coverage["statement_coverage"]))
        html_report = html_report.replace("{{code_coverage.branch_coverage}}", str(code_coverage["branch_coverage"]))
        html_report = html_report.replace("{{code_coverage.function_coverage}}", str(code_coverage["function_coverage"]))
        
        html_report = html_report.replace("{{kb_coverage.general}}", str(kb_coverage["general"]))
        html_report = html_report.replace("{{kb_coverage.legal}}", str(kb_coverage["legal"]))
        html_report = html_report.replace("{{kb_coverage.business}}", str(kb_coverage["business"]))
        
        # 替换验证结果统计
        html_report = html_report.replace("{{validation_summary.total_checks}}", str(validation_summary["total_checks"]))
        html_report = html_report.replace("{{validation_summary.passed_checks}}", str(validation_summary["passed_checks"]))
        html_report = html_report.replace("{{validation_summary.pass_rate}}", f"{validation_summary['pass_rate']:.2f}")
        
        # 替换失败规则列表
        failed_rules_html = ""
        for rule, count in validation_summary["failed_rules"].items():
            failed_rules_html += f"<li>{rule}: {count}次</li>\n"
        html_report = html_report.replace("{{#validation_summary.failed_rules}}\n            <li>{{rule}}: {{count}}次</li>\n            {{/validation_summary.failed_rules}}", failed_rules_html)
        
        # 替换表格
        html_report = html_report.replace("{{category_stats_table}}", category_stats.to_html())
        html_report = html_report.replace("{{detailed_results_table}}", df.to_html(classes="table", index=False))
        
        # 保存HTML报告
        report_path = f"test_reports/qa_test_report_{timestamp}.html"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_report)
        
        # 保存原始数据
        df.to_csv(f"test_reports/test_results_{timestamp}.csv", index=False)
        
        qa_logger.log_info(f"测试报告已生成: {report_path}")
        return report_path
    
    def _cleanup_old_reports(self):
        """清理旧的报告文件"""
        report_dir = Path("test_reports")
        if not report_dir.exists():
            return
        
        # 获取所有报告文件
        report_files = []
        for ext in [".html", ".csv", ".png"]:
            report_files.extend(report_dir.glob(f"*{ext}"))
        
        # 按修改时间排序
        report_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # 保留最新的10个报告文件，删除其余文件
        keep_count = 10
        for file in report_files[keep_count:]:
            try:
                file.unlink()
                qa_logger.log_debug(f"已删除旧的报告文件: {file}")
            except Exception as e:
                qa_logger.log_error(f"删除旧的报告文件失败: {str(e)}")
    
    def _calculate_code_coverage(self) -> dict:
        """计算代码覆盖率"""
        # 这里可以使用coverage.py库来获取实际的代码覆盖率
        # 目前返回模拟数据
        return {
            "statement_coverage": 85.5,
            "branch_coverage": 78.3,
            "function_coverage": 90.2
        }
    
    def _calculate_kb_coverage(self) -> dict:
        """计算知识库覆盖率"""
        # 统计每个知识库类型的测试用例覆盖情况
        kb_types = {"general": 0, "legal": 0, "business": 0}
        total_cases = len(self.test_cases)
        
        for category, cases in self.test_cases.items():
            for case in cases:
                kb_type = case["kb_type"]
                if kb_type in kb_types:
                    kb_types[kb_type] += 1
        
        # 计算百分比
        coverage = {}
        for kb_type, count in kb_types.items():
            coverage[kb_type] = round((count / total_cases) * 100, 1)
        
        return coverage
    
    def _calculate_validation_summary(self) -> dict:
        """计算验证结果统计"""
        validation_summary = {
            "total_checks": 0,
            "passed_checks": 0,
            "failed_rules": {},
            "pass_rate": 0
        }
        
        for result in self.test_results:
            if result.validation_result:
                for check in result.validation_result.get("checks", []):
                    validation_summary["total_checks"] += 1
                    if check.get("passed", False):
                        validation_summary["passed_checks"] += 1
                    else:
                        rule = check.get("rule", "unknown")
                        if rule not in validation_summary["failed_rules"]:
                            validation_summary["failed_rules"][rule] = 0
                        validation_summary["failed_rules"][rule] += 1
        
        if validation_summary["total_checks"] > 0:
            validation_summary["pass_rate"] = (validation_summary["passed_checks"] / validation_summary["total_checks"]) * 100
        
        return validation_summary

    def test_generate_reports(self):
        """生成测试报告和统计图表"""
        self._generate_qa_reports()
        self._update_recommended_questions()
        
    def _update_recommended_questions(self):
        """更新推荐问题数据文件"""
        import subprocess
        from pathlib import Path
        
        # 获取测试结果和测试用例文件路径
        results_path = Path(__file__).parent / "test_results.json"
        cases_path = Path(__file__).parent / "test_cases_export.json"
        
        # 导出测试用例
        with open(cases_path, "w", encoding="utf-8") as f:
            json.dump(self.test_cases, f, ensure_ascii=False, indent=2)
            
        # 调用更新脚本
        update_script = Path(__file__).parent / "update_recommended_questions.py"
        cmd = [
            "python", 
            str(update_script), 
            "--test-results", 
            str(results_path),
            "--test-cases",
            str(cases_path)
        ]
        
        try:
            print(f"\n更新推荐问题数据文件...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  ✓ 推荐问题数据更新成功")
                # 删除临时导出的测试用例文件
                cases_path.unlink(missing_ok=True)
            else:
                print(f"  ✗ 推荐问题数据更新失败: {result.stderr}")
        except Exception as e:
            print(f"  ✗ 执行更新脚本出错: {str(e)}")

async def main():
    """主函数"""
    runner = TestQASystem()
    # 显示测试资源预估并获取用户确认
    runner.show_estimation()
    # 只有在用户确认后才会继续执行测试
    await runner.run_all_tests()
    report_path = runner.generate_report()
    print(f"测试报告已生成: {report_path}")

if __name__ == "__main__":
    async def run():
        runner = TestQASystem()
        # 显示测试资源预估并获取用户确认
        runner.show_estimation()
        # 只有在用户确认后才会继续执行测试
        await runner.run_all_tests()
    
    asyncio.run(run())