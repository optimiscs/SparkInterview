#!/usr/bin/env python3
"""
题目生成路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncio
import json
from datetime import datetime
import uuid

from src.models.spark_client import SparkLLM

router = APIRouter(prefix="/api/v1/questions", tags=["questions"])

# 初始化Spark客户端
spark_client = SparkLLM()

class QuestionGenerationRequest(BaseModel):
    """题目生成请求模型"""
    resume_data: Dict[str, Any]
    selected_skills: List[str]
    selected_projects: List[Dict[str, Any]]
    question_types: Dict[str, bool]
    question_count: int
    difficulty_level: int
    include_answer: bool
    include_points: bool

class QuestionGenerationResponse(BaseModel):
    """题目生成响应模型"""
    success: bool
    questions: List[Dict[str, Any]]
    message: str = ""

@router.post("/generate", response_model=QuestionGenerationResponse)
async def generate_questions(request: QuestionGenerationRequest):
    """生成个性化面试题目"""
    try:
        print(f"🎯 开始生成题目...")
        print(f"📊 题目数量: {request.question_count}")
        print(f"📊 难度等级: {request.difficulty_level}")
        print(f"📊 选中技能: {request.selected_skills}")
        print(f"📊 选中项目: {len(request.selected_projects)} 个")
        
        # 构建prompt
        prompt = build_question_generation_prompt(request)
        
        # 调用大模型生成题目
        questions = await generate_questions_with_ai(prompt, request)
        
        print(f"✅ 题目生成成功，共生成 {len(questions)} 个题目")
        
        return QuestionGenerationResponse(
            success=True,
            questions=questions,
            message="题目生成成功"
        )
        
    except Exception as e:
        print(f"❌ 题目生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"题目生成失败: {str(e)}")

def build_question_generation_prompt(request: QuestionGenerationRequest) -> str:
    """构建题目生成的prompt"""
    
    # 基本信息
    basic_info = request.resume_data.get('basic_info', {})
    name = basic_info.get('name', '候选人')
    position = basic_info.get('current_position', '算法工程师')
    experience_years = basic_info.get('experience_years', '2')
    
    # 技能信息
    all_skills = request.resume_data.get('skills', [])
    selected_skills = request.selected_skills if request.selected_skills else all_skills[:5]
    
    # 项目信息
    all_projects = request.resume_data.get('projects', [])
    selected_projects = request.selected_projects if request.selected_projects else all_projects
    
    # 工作经历
    experience = request.resume_data.get('experience', [])
    
    # 难度映射
    difficulty_map = {
        1: "初级（适合应届毕业生或0-2年工作经验）",
        2: "中级（适合2-5年工作经验）", 
        3: "高级（适合5年以上工作经验）"
    }
    difficulty_desc = difficulty_map.get(request.difficulty_level, "中级")
    
    # 题目类型
    question_types = []
    if request.question_types.get('tech_basic'):
        question_types.append("技术基础题")
    if request.question_types.get('project_experience'):
        question_types.append("项目经验题")
    if request.question_types.get('algorithm_design'):
        question_types.append("算法设计题")
    if request.question_types.get('system_design'):
        question_types.append("系统设计题")
    
    prompt = f"""
你是一位资深的面试官，需要为候选人{name}生成个性化的面试题目。

候选人信息：
- 姓名：{name}
- 目标岗位：{position}
- 工作年限：{experience_years}年

技能栈：{', '.join(selected_skills)}

项目经验：
{chr(10).join([f"- {p.get('name', 'N/A')}: {p.get('description', 'N/A')} (技术栈: {p.get('tech_stack', 'N/A')})" for p in selected_projects])}

工作经历：
{chr(10).join([f"- {exp.get('company', 'N/A')} ({exp.get('period', 'N/A')}): {exp.get('position', 'N/A')}" for exp in experience])}

题目要求：
- 题目数量：{request.question_count}个
- 难度等级：{difficulty_desc}
- 题目类型：{', '.join(question_types)}
- 包含参考答案：{'是' if request.include_answer else '否'}
- 标注考察点：{'是' if request.include_points else '否'}

请根据候选人的技能栈、项目经验和工作经历，生成个性化、有深度的面试题目。题目应该：
1. 紧密结合候选人的实际项目经验
2. 考察候选人的核心技能
3. 符合目标岗位的要求
4. 难度适中，符合候选人的经验水平
5. 具有实际应用价值

请以JSON格式返回，格式如下：
{{
    "questions": [
        {{
            "type": "题目类型（tech_basic/project_experience/algorithm_design/system_design）",
            "title": "题目内容",
            "points": ["考察点1", "考察点2", "考察点3"],
            "answer": "参考答案（如果要求包含）"
        }}
    ]
}}

请确保生成的题目数量准确，内容质量高，符合面试标准。
"""
    
    return prompt

async def generate_questions_with_ai(prompt: str, request: QuestionGenerationRequest) -> List[Dict[str, Any]]:
    """使用AI生成题目"""
    
    try:
        # 调用Spark Pro生成题目
        response = spark_client.chat_with_messages(
            messages=[{"role": "user", "content": prompt}]
        )
        
        # 解析响应
        content = response
        print(f"🤖 AI响应: {content[:200]}...")
        
        # 提取JSON部分
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            raise Exception("无法从AI响应中提取JSON数据")
        
        json_str = content[json_start:json_end]
        result = json.loads(json_str)
        
        questions = result.get('questions', [])
        
        # 验证题目数量
        if len(questions) != request.question_count:
            print(f"⚠️ 生成的题目数量({len(questions)})与要求({request.question_count})不符")
        
        # 处理题目格式
        processed_questions = []
        for i, q in enumerate(questions):
            processed_q = {
                'id': f"q_{uuid.uuid4().hex[:8]}",
                'type': q.get('type', 'tech_basic'),
                'title': q.get('title', ''),
                'points': q.get('points', []),
                'answer': q.get('answer', '') if request.include_answer else '',
                'difficulty': request.difficulty_level,
                'created_at': datetime.now().isoformat()
            }
            processed_questions.append(processed_q)
        
        return processed_questions
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析失败: {e}")
        # 如果JSON解析失败，返回默认题目
        return generate_fallback_questions(request)
    except Exception as e:
        print(f"❌ AI生成失败: {e}")
        return generate_fallback_questions(request)

def generate_fallback_questions(request: QuestionGenerationRequest) -> List[Dict[str, Any]]:
    """生成备用题目"""
    
    fallback_questions = [
        {
            'id': f"q_{uuid.uuid4().hex[:8]}",
            'type': 'tech_basic',
            'title': '请解释Python中的装饰器模式，并给出一个实际应用示例。',
            'points': ['装饰器概念', 'Python语法', '实际应用'],
            'answer': '装饰器是Python中的一种设计模式，允许在不修改函数定义的情况下增加函数功能...',
            'difficulty': request.difficulty_level,
            'created_at': datetime.now().isoformat()
        },
        {
            'id': f"q_{uuid.uuid4().hex[:8]}",
            'type': 'project_experience',
            'title': '请详细描述你在项目中遇到的技术挑战以及解决方案。',
            'points': ['问题分析', '解决方案', '技术选型'],
            'answer': '在项目开发中，我遇到了性能瓶颈问题。通过分析发现是数据库查询效率低下...',
            'difficulty': request.difficulty_level,
            'created_at': datetime.now().isoformat()
        }
    ]
    
    # 根据请求的题目数量调整
    return fallback_questions[:request.question_count] 