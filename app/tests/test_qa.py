import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd
import matplotlib.pyplot as plt
from app.api.routers.chat import ChatRequest, ChatResponse
from app.core.chains.conversation_chain import ConversationChain
from app.utils.logger import qa_logger
import requests
from elasticsearch import Elasticsearch

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # macOS
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

class TestResult:
    """测试结果类"""
    def __init__(self, 
                 category: str,
                 question: str,
                 kb_type: str,
                 status: str,
                 response_time: float,
                 answer: Optional[str] = None,
                 sources: Optional[List] = None,
                 error: Optional[str] = None,
                 validation_result: Optional[Dict] = None):
        self.category = category
        self.question = question
        self.kb_type = kb_type
        self.status = status
        self.response_time = response_time
        self.answer = answer
        self.sources = sources
        self.error = error
        self.validation_result = validation_result or {}
    
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

class QATestRunner:
    """问答系统测试运行器"""
    
    def __init__(self):
        self.test_results: List[TestResult] = []
        self.test_cases = self._get_test_cases()
        self.validation_rules = self._get_validation_rules()
        self.critical_error_count = 0
        self.max_critical_errors = 3  # 最大允许的严重错误数
    
    def _get_validation_rules(self) -> Dict:
        """获取验证规则"""
        return {
            "基本规则": {
                "min_answer_length": 10,  # 最小回答长度
                "max_response_time": 10,  # 最大响应时间（秒）
                "required_fields": ["answer", "sources"],  # 必需字段
            },
            "知识库规则": {
                "min_sources": 1,  # 最小知识库引用数
                "max_sources": 5,  # 最大知识库引用数
            },
            "错误处理规则": {
                "critical_errors": [
                    "NotFoundError",  # Elasticsearch 索引不存在
                    "ConnectionError",  # 连接错误
                    "AuthenticationError",  # 认证错误
                ],
            }
        }
    
    def _get_test_cases(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取测试用例"""
        return {
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
            
            # 检查关键词
            if "keywords" in expected and result["answer"]:
                missing_keywords = [
                    kw for kw in expected["keywords"]
                    if kw not in result["answer"]
                ]
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
            
            # 获取响应
            response = await chain.get_response(question)
            
            # 计算响应时间
            response_time = time.time() - start_time
            
            result = {
                "status": "success",
                "response_time": response_time,
                "answer": response["answer"],
                "sources": response["sources"],
                "error": None
            }
            
            # 验证结果
            validation_result = self.validate_response(test_case, result)
            
            # 如果验证失败，更新状态
            if not validation_result["passed"]:
                result["status"] = "failed"
                if validation_result["is_critical"]:
                    self.critical_error_count += 1
            
            return TestResult(
                category=category,
                question=question,
                kb_type=kb_type,
                **result,
                validation_result=validation_result
            )
            
        except Exception as e:
            error_msg = str(e)
            qa_logger.log_error(f"测试用例执行失败: {error_msg}")
            
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
            
            return TestResult(
                category=category,
                question=test_case["question"],
                kb_type=test_case["kb_type"],
                **result,
                validation_result=validation_result
            )
    
    def basic_checks(self):
        """执行基础检查项"""
        es = Elasticsearch("http://localhost:9200")

        # 检查ES服务可用性
        if not es.ping():
            raise Exception("Elasticsearch 服务不可用")

        # 检查索引存在性
        required_indices = ["knowledge_base_general", "knowledge_base_legal", "knowledge_base_business"]
        for index in required_indices:
            if not es.indices.exists(index=index):
                raise Exception(f"索引不存在: {index}")

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

    async def run_all_tests(self):
        """运行所有测试用例"""
        try:
            self.basic_checks()
        except Exception as e:
            qa_logger.log_error(f"基础检查失败: {e}")
            return

        for category, test_cases in self.test_cases.items():
            qa_logger.log_info(f"开始执行测试类别: {category}")
            session_id = f"test_{int(time.time())}"
            
            for test_case in test_cases:
                # 检查是否达到最大错误数
                if self.critical_error_count >= self.max_critical_errors:
                    qa_logger.log_error(f"达到最大严重错误数 ({self.max_critical_errors})，停止测试")
                    return
                
                result = await self.run_test_case(test_case, category, session_id)
                self.test_results.append(result)
                
                # 记录测试结果
                qa_logger.log_info(
                    f"测试用例完成 - "
                    f"类别: {category}, "
                    f"问题: {test_case['question']}, "
                    f"状态: {result.status}"
                )
                
                if result.status != "success":
                    qa_logger.log_warning(
                        f"测试用例未通过 - "
                        f"错误: {result.error}, "
                        f"验证结果: {result.validation_result}"
                    )
    
    def generate_report(self):
        """生成测试报告"""
        # 创建报告目录
        report_dir = Path("test_reports")
        report_dir.mkdir(exist_ok=True)
        
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
        
        # 按类别统计
        category_stats = df.groupby("category").agg({
            "status": lambda x: (x == "success").mean(),
            "response_time": "mean"
        }).round(3)
        
        # 生成响应时间分布图
        plt.figure(figsize=(10, 6))
        plt.hist(df["response_time"], bins=20)
        plt.title("响应时间分布")
        plt.xlabel("响应时间（秒）")
        plt.ylabel("频次")
        plt.savefig(f"test_reports/response_time_dist_{timestamp}.png")
        plt.close()
        
        # 生成类别统计图
        plt.figure(figsize=(12, 6))
        category_stats["status"].plot(kind="bar")
        plt.title("各类别测试成功率")
        plt.xlabel("测试类别")
        plt.ylabel("成功率")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(f"test_reports/category_success_rate_{timestamp}.png")
        plt.close()
        
        # 生成验证结果统计
        validation_summary = {
            "total_checks": 0,
            "passed_checks": 0,
            "failed_rules": {}
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
        
        # 生成HTML报告
        html_report = f"""
        <html>
        <head>
            <title>问答系统测试报告</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .success {{ color: green; }}
                .failed {{ color: orange; }}
                .error {{ color: red; }}
                .summary-box {{ 
                    border: 1px solid #ddd;
                    padding: 15px;
                    margin-bottom: 20px;
                    background-color: #f9f9f9;
                }}
            </style>
        </head>
        <body>
            <h1>问答系统测试报告</h1>
            <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            
            <div class="summary-box">
                <h2>测试概要</h2>
                <ul>
                    <li>总测试用例数: {total_tests}</li>
                    <li>成功用例数: <span class="success">{successful_tests}</span></li>
                    <li>失败用例数: <span class="failed">{failed_tests}</span></li>
                    <li>错误用例数: <span class="error">{error_tests}</span></li>
                    <li>平均响应时间: {avg_response_time:.2f}秒</li>
                    <li>严重错误数: {self.critical_error_count}</li>
                </ul>
            </div>
            
            <div class="summary-box">
                <h2>验证结果统计</h2>
                <ul>
                    <li>总检查项: {validation_summary["total_checks"]}</li>
                    <li>通过检查项: {validation_summary["passed_checks"]}</li>
                    <li>检查通过率: {(validation_summary["passed_checks"] / validation_summary["total_checks"] * 100):.2f}%</li>
                </ul>
                <h3>失败规则统计</h3>
                <ul>
                    {chr(10).join(f'<li>{rule}: {count}次</li>' for rule, count in validation_summary["failed_rules"].items())}
                </ul>
            </div>
            
            <h2>类别统计</h2>
            {category_stats.to_html()}
            
            <h2>响应时间分布</h2>
            <img src="response_time_dist_{timestamp}.png" alt="响应时间分布">
            
            <h2>类别成功率</h2>
            <img src="category_success_rate_{timestamp}.png" alt="类别成功率">
            
            <h2>详细测试结果</h2>
            {df.to_html(classes="table", index=False)}
        </body>
        </html>
        """
        
        # 保存HTML报告
        report_path = f"test_reports/qa_test_report_{timestamp}.html"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_report)
        
        # 保存原始数据
        df.to_csv(f"test_reports/test_results_{timestamp}.csv", index=False)
        
        qa_logger.log_info(f"测试报告已生成: {report_path}")
        return report_path

async def main():
    """主函数"""
    runner = QATestRunner()
    await runner.run_all_tests()
    report_path = runner.generate_report()
    print(f"测试报告已生成: {report_path}")

if __name__ == "__main__":
    asyncio.run(main()) 