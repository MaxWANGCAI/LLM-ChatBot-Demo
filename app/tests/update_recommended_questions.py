#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
更新推荐问题数据文件中的答案

这个脚本用于在测试完成后，将测试结果中的AI回答更新到推荐问题数据文件中。
这样可以确保推荐问题的回答始终与最新的大模型输出保持一致。
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import argparse

# 添加项目根目录到系统路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.utils.logger import qa_logger

def load_recommended_questions() -> Dict:
    """加载推荐问题数据文件"""
    try:
        file_path = Path(__file__).parent.parent / "data" / "recommended_questions.json"
        
        if not file_path.exists():
            qa_logger.log_error(f"推荐问题文件不存在: {file_path}")
            return {"questions": []}
            
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception as e:
        qa_logger.log_error(f"加载推荐问题失败: {str(e)}")
        return {"questions": []}

def load_test_results(results_file: str) -> List[Dict]:
    """加载测试结果"""
    try:
        with open(results_file, "r", encoding="utf-8") as f:
            results = json.load(f)
            return results
    except Exception as e:
        qa_logger.log_error(f"加载测试结果失败: {str(e)}")
        return []

def update_recommended_questions(recommended_data: Dict, test_results: List[Dict]) -> Dict:
    """更新推荐问题数据"""
    # 创建问题到ID的映射
    question_to_id = {q["question"]: q["id"] for q in recommended_data["questions"]}
    
    # 创建问题到测试结果的映射
    updated_questions = 0
    
    for result in test_results:
        if result["status"] != "成功":
            continue
            
        question = result["question"]
        if question in question_to_id:
            # 找到对应的问题ID
            q_id = question_to_id[question]
            
            # 更新回答
            for i, q in enumerate(recommended_data["questions"]):
                if q["id"] == q_id:
                    if q["answer"] != result["answer"]:
                        qa_logger.log_info(f"更新问题回答: {question}")
                        recommended_data["questions"][i]["answer"] = result["answer"]
                        updated_questions += 1
                    break
    
    qa_logger.log_info(f"总共更新了 {updated_questions} 个推荐问题的回答")
    return recommended_data

def save_recommended_questions(data: Dict) -> bool:
    """保存更新后的推荐问题数据"""
    try:
        file_path = Path(__file__).parent.parent / "data" / "recommended_questions.json"
        
        # 备份原文件
        backup_path = file_path.with_suffix('.json.bak')
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as src:
                with open(backup_path, "w", encoding="utf-8") as dst:
                    dst.write(src.read())
            qa_logger.log_info(f"已备份原文件到: {backup_path}")
        
        # 保存更新后的文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        qa_logger.log_info(f"已保存更新后的推荐问题数据到: {file_path}")
        return True
    except Exception as e:
        qa_logger.log_error(f"保存推荐问题数据失败: {str(e)}")
        return False

def create_missing_questions(test_cases: Dict[str, List[Dict]], recommended_data: Dict) -> Dict:
    """从测试用例中创建缺失的推荐问题"""
    # 获取已有问题
    existing_questions = {q["question"] for q in recommended_data["questions"]}
    
    # 获取最大ID编号
    max_id = 0
    for q in recommended_data["questions"]:
        q_id = q["id"]
        if q_id.startswith("q"):
            try:
                id_num = int(q_id[1:])
                max_id = max(max_id, id_num)
            except ValueError:
                continue
    
    # 遍历测试用例，添加缺失的问题
    new_questions = 0
    for category, cases in test_cases.items():
        for case in cases:
            question = case["question"]
            kb_type = case.get("kb_type", "general")
            
            if question not in existing_questions:
                # 创建新ID
                max_id += 1
                new_id = f"q{max_id}"
                
                # 添加新问题
                recommended_data["questions"].append({
                    "id": new_id,
                    "question": question,
                    "category": category,
                    "kb_type": kb_type,
                    "answer": "此问题暂无预设回答，将在测试后自动更新。"
                })
                new_questions += 1
                qa_logger.log_info(f"添加新问题: {question}")
    
    qa_logger.log_info(f"总共添加了 {new_questions} 个新推荐问题")
    return recommended_data

def main():
    parser = argparse.ArgumentParser(description="更新推荐问题数据文件中的答案")
    parser.add_argument("--test-results", required=True, help="测试结果JSON文件路径")
    parser.add_argument("--test-cases", required=False, help="测试用例JSON文件路径，用于添加缺失的问题")
    args = parser.parse_args()
    
    # 加载推荐问题数据
    recommended_data = load_recommended_questions()
    
    # 如果提供了测试用例文件，添加缺失的问题
    if args.test_cases:
        try:
            with open(args.test_cases, "r", encoding="utf-8") as f:
                test_cases = json.load(f)
            recommended_data = create_missing_questions(test_cases, recommended_data)
        except Exception as e:
            qa_logger.log_error(f"处理测试用例失败: {str(e)}")
    
    # 加载测试结果
    test_results = load_test_results(args.test_results)
    if not test_results:
        qa_logger.log_error("无测试结果可用，退出")
        return 1
        
    # 更新推荐问题数据
    updated_data = update_recommended_questions(recommended_data, test_results)
    
    # 保存更新后的数据
    if not save_recommended_questions(updated_data):
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main()) 