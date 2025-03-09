from fastapi import APIRouter, HTTPException, Query, Path as FastAPIPath
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import random
import os
from pathlib import Path
from app.utils.logger import qa_logger

router = APIRouter()

# 存储已经展示过的问题ID
shown_question_ids = set()

class RecommendedQuestion(BaseModel):
    """推荐问题模型"""
    id: str
    question: str
    category: str
    kb_type: str

class QuickAnswer(BaseModel):
    """快速回答模型"""
    id: str
    question: str
    answer: str
    source_type: str

class RecommendationResponse(BaseModel):
    """推荐问题响应模型"""
    recommendations: List[RecommendedQuestion]

def load_questions() -> List[Dict[str, Any]]:
    """从文件加载推荐问题"""
    try:
        # 确保目录存在
        data_dir = Path(__file__).parent.parent.parent / "data"
        if not data_dir.exists():
            data_dir.mkdir(parents=True, exist_ok=True)
            
        file_path = data_dir / "recommended_questions.json"
        
        # 如果文件不存在，创建一个基本的数据结构
        if not file_path.exists():
            sample_data = {
                "questions": [
                    {
                        "id": "q1",
                        "question": "智能助手有哪些功能？",
                        "category": "基础对话测试",
                        "kb_type": "general",
                        "answer": "我是一个智能知识库助手，可以回答您关于公司、法律和客户服务的问题。我能够检索相关信息，提供准确的答案，并帮助您解决各种问题。如果您有任何疑问，随时可以向我提问！"
                    },
                    {
                        "id": "q2",
                        "question": "公司的主要业务是什么？",
                        "category": "业务信息查询",
                        "kb_type": "business",
                        "answer": "我们公司是一家领先的科技公司，主要业务包括人工智能解决方案、智能知识库系统和数据分析服务。我们致力于为企业提供智能化的信息管理和决策支持工具，帮助客户提高工作效率和信息利用率。"
                    },
                    {
                        "id": "q3",
                        "question": "如何联系客服？",
                        "category": "客户服务",
                        "kb_type": "customer",
                        "answer": "您可以通过以下方式联系我们的客服团队：\n1. 客服热线：400-888-9999（工作日9:00-18:00）\n2. 电子邮件：support@example.com\n3. 在线客服：访问我们的官方网站，点击右下角的\"在线客服\"按钮\n我们的客服团队将会尽快回应您的问题和需求。"
                    }
                ]
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(sample_data, f, ensure_ascii=False, indent=2)
                
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        qa_logger.log_error(f"加载推荐问题失败: {str(e)}")
        # 返回一个基本的数据结构
        return {"questions": []}

@router.get("/recommended-questions", response_model=RecommendationResponse)
async def get_recommended_questions(
    count: int = Query(3, description="返回的推荐问题数量"), 
    exclude_shown: bool = Query(True, description="是否排除已显示过的问题"),
    kb_type: str = Query("all", description="知识库类型过滤")
) -> RecommendationResponse:
    """获取推荐问题"""
    global shown_question_ids
    
    # 加载所有问题
    data = load_questions()
    all_questions = data.get("questions", [])
    
    if not all_questions:
        return RecommendationResponse(recommendations=[])
    
    # 根据知识库类型过滤问题
    if kb_type != "all":
        all_questions = [q for q in all_questions if q.get("kb_type") == kb_type]
        
        # 如果过滤后没有问题，返回空列表
        if not all_questions:
            return RecommendationResponse(recommendations=[])
    
    # 筛选未展示过的问题
    available_questions = all_questions
    if exclude_shown and shown_question_ids:
        available_questions = [q for q in all_questions if q["id"] not in shown_question_ids]
        
        # 如果所有问题都已展示过，重置展示记录
        if not available_questions:
            shown_question_ids.clear()
            available_questions = all_questions
    
    # 随机选择问题
    selected_questions = random.sample(
        available_questions, 
        min(count, len(available_questions))
    )
    
    # 更新已展示问题记录
    for q in selected_questions:
        shown_question_ids.add(q["id"])
    
    # 转换为响应模型
    recommendations = [
        RecommendedQuestion(
            id=q["id"],
            question=q["question"],
            category=q["category"],
            kb_type=q["kb_type"]
        ) for q in selected_questions
    ]
    
    return RecommendationResponse(recommendations=recommendations)

@router.get("/quick-answer/{question_id}", response_model=QuickAnswer)
async def get_quick_answer(question_id: str = FastAPIPath(..., description="问题ID")) -> QuickAnswer:
    """获取问题的快速回答"""
    # 加载所有问题
    data = load_questions()
    all_questions = data.get("questions", [])
    
    # 查找指定ID的问题
    question = next((q for q in all_questions if q["id"] == question_id), None)
    
    if not question:
        raise HTTPException(
            status_code=404, 
            detail={
                "message": f"问题ID '{question_id}' 不存在",
                "suggestion": "请使用 /api/recommended-questions 接口获取可用的问题列表"
            }
        )
    
    return QuickAnswer(
        id=question["id"],
        question=question["question"],
        answer=question.get("answer", "抱歉，该问题暂无预设回答。"),
        source_type="预设回答"
    )