#!/usr/bin/env python3
"""
题目生成路由 - 支持ChromaDB智能匹配和生成，Redis存储
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncio
import json
from datetime import datetime
import uuid
import os
import redis

from src.models.spark_client import create_spark_model
from src.database.chroma_manager import chroma_manager

# Redis配置
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    redis_client.ping()  # 测试连接
    print("✅ Redis连接成功")
except Exception as e:
    print(f"⚠️ Redis连接失败: {e}")
    redis_client = None

router = APIRouter(prefix="/questions", tags=["questions"])

# 初始化Spark客户端
spark_client = create_spark_model(model_type="creative", temperature=0.7)

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
    task_id: Optional[str] = None  # 添加可选的任务ID

class QuestionGenerationResponse(BaseModel):
    """题目生成响应模型"""
    success: bool
    questions: List[Dict[str, Any]]
    message: str = ""
    stats: Optional[Dict[str, Any]] = None  # 生成统计信息

@router.post("/generate", response_model=QuestionGenerationResponse)
async def generate_questions(request: QuestionGenerationRequest):
    """智能题目生成：先匹配已有题目，不足时调用大模型生成"""
    try:
        print(f"🎯 开始智能题目生成...")
        print(f"📊 需要题目数量: {request.question_count}")
        print(f"📊 难度等级: {request.difficulty_level}")
        print(f"📊 选中技能: {request.selected_skills}")
        print(f"📊 选中项目: {len(request.selected_projects)} 个")
        
        # 阶段1: 从ChromaDB搜索匹配的题目
        matched_questions = await search_existing_questions(request)
        matched_count = len(matched_questions)
        
        print(f"🔍 匹配到 {matched_count} 个已有题目")
        
        # 阶段2: 计算还需要生成的题目数量
        remaining_count = max(0, request.question_count - matched_count)
        
        generated_questions = []
        if remaining_count > 0:
            print(f"🤖 需要生成 {remaining_count} 个新题目")
            
            # 调整请求以生成剩余题目
            adjusted_request = request.copy()
            adjusted_request.question_count = remaining_count
            
            # 构建prompt
            prompt = build_question_generation_prompt(adjusted_request)
            
            # 调用大模型生成题目
            generated_questions = await generate_questions_with_ai(prompt, adjusted_request)
            
            print(f"✅ 大模型生成 {len(generated_questions)} 个新题目")
            
            # 阶段3: 将新生成的题目存储到ChromaDB
            if generated_questions:
                await store_new_questions(generated_questions, request, request.task_id)
        
        # 阶段4: 合并结果
        final_questions = matched_questions + generated_questions
        
        # 如果题目数量超过需求，进行筛选
        if len(final_questions) > request.question_count:
            # 优先保留匹配度高的题目，然后是新生成的题目
            final_questions = final_questions[:request.question_count]
        
        # 构建统计信息
        stats = {
            "total_questions": len(final_questions),
            "matched_from_db": matched_count,
            "generated_new": len(generated_questions),
            "chroma_stats": chroma_manager.get_collection_stats()
        }
        
        print(f"✅ 题目生成完成: 总计 {len(final_questions)} 个题目")
        print(f"   - 匹配题目: {matched_count} 个")
        print(f"   - 新生成: {len(generated_questions)} 个")
        
        # 阶段5: 存储题目到Redis
        session_id = await store_questions_to_redis(final_questions, request)
        
        return QuestionGenerationResponse(
            success=True,
            questions=final_questions,
            message=f"题目生成成功：匹配 {matched_count} 个，新生成 {len(generated_questions)} 个",
            stats={
                **stats,
                "session_id": session_id,
                "redis_stored": len(final_questions)
            }
        )
        
    except Exception as e:
        print(f"❌ 题目生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"题目生成失败: {str(e)}")

async def search_existing_questions(request: QuestionGenerationRequest) -> List[Dict[str, Any]]:
    """搜索已有的匹配题目"""
    try:
        # 构建搜索请求数据
        search_data = {
            "selected_skills": request.selected_skills,
            "selected_projects": request.selected_projects,
            "question_types": request.question_types,
            "difficulty_level": request.difficulty_level,
            "include_answer": request.include_answer,
            "resume_data": request.resume_data
        }
        
        # 搜索匹配题目，获取比需求稍多的结果用于筛选
        matched_questions = chroma_manager.search_questions(
            search_data, 
            n_results=min(request.question_count * 2, 30)  # 获取2倍数量用于筛选
        )
        
        # 过滤相似度过低的题目
        high_quality_matches = [
            q for q in matched_questions 
            if q.get("similarity_score", 0) > 0.3  # 相似度阈值
        ]
        
        return high_quality_matches[:request.question_count]  # 限制数量
        
    except Exception as e:
        print(f"❌ 搜索已有题目失败: {e}")
        return []

async def store_questions_to_redis(questions: List[Dict[str, Any]], request: QuestionGenerationRequest) -> str:
    """将题目存储到Redis中"""
    if not redis_client:
        print("⚠️ Redis不可用，跳过存储")
        return f"local_{uuid.uuid4().hex[:8]}"
    
    try:
        # 生成会话ID
        session_id = f"interview_{uuid.uuid4().hex[:12]}"
        
        # 构建存储数据
        redis_data = {
            "questions": questions,
            "metadata": {
                "session_id": session_id,
                "created_at": datetime.now().isoformat(),
                "task_id": request.task_id or "",
                "selected_skills": request.selected_skills,
                "selected_projects": request.selected_projects,
                "question_types": request.question_types,
                "difficulty_level": request.difficulty_level,
                "question_count": len(questions),
                "include_answer": request.include_answer,
                "include_points": request.include_points
            }
        }
        
        # 存储到Redis，设置过期时间为24小时
        redis_key = f"interview_questions:{session_id}"
        redis_client.setex(
            redis_key,
            86400,  # 24小时过期
            json.dumps(redis_data, ensure_ascii=False)
        )
        
        print(f"✅ 题目已存储到Redis: {redis_key} ({len(questions)}个题目)")
        return session_id
        
    except Exception as e:
        print(f"❌ Redis存储失败: {e}")
        # 如果Redis存储失败，返回本地会话ID
        return f"local_{uuid.uuid4().hex[:8]}"

async def get_questions_from_redis(session_id: str) -> Optional[Dict[str, Any]]:
    """从Redis获取题目"""
    if not redis_client:
        print("⚠️ Redis不可用")
        return None
    
    try:
        redis_key = f"interview_questions:{session_id}"
        data = redis_client.get(redis_key)
        
        if not data:
            print(f"❌ Redis中未找到会话: {session_id}")
            return None
        
        redis_data = json.loads(data)
        print(f"✅ 从Redis获取题目成功: {session_id} ({len(redis_data['questions'])}个题目)")
        return redis_data
        
    except Exception as e:
        print(f"❌ Redis获取失败: {e}")
        return None

async def store_new_questions(questions: List[Dict[str, Any]], request: QuestionGenerationRequest, task_id: str = None):
    """存储新生成的题目到ChromaDB"""
    try:
        # 构建存储元数据
        basic_info = request.resume_data.get("basic_info", {})
        
        # 生成会话ID（基于参数组合）
        import hashlib
        session_data = f"{request.difficulty_level}_{sorted(request.selected_skills)}_{request.question_count}"
        session_id = hashlib.md5(session_data.encode()).hexdigest()[:16]
        
        metadata = {
            "selected_skills": request.selected_skills,
            "selected_projects": request.selected_projects,
            "difficulty_level": request.difficulty_level,
            "domain": basic_info.get("current_position", ""),
            "position": basic_info.get("current_position", ""),
            "experience_years": basic_info.get("experience_years", ""),
            "question_types": request.question_types,
            "session_id": session_id,
            "task_id": task_id or ""
        }
        
        # 异步存储到ChromaDB
        await asyncio.to_thread(chroma_manager.store_questions, questions, metadata)
        
    except Exception as e:
        print(f"❌ 存储新题目失败: {e}")
        # 存储失败不影响返回结果，只记录错误

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

@router.get("/stats")
async def get_question_stats():
    """获取题目库统计信息"""
    try:
        stats = chroma_manager.get_collection_stats()
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stats": {"total_questions": 0}
        }

@router.post("/search")
async def search_questions_endpoint(request: QuestionGenerationRequest):
    """搜索匹配的题目（测试用）"""
    try:
        matched_questions = await search_existing_questions(request)
        return {
            "success": True,
            "questions": matched_questions,
            "count": len(matched_questions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")

class QuestionRetrievalRequest(BaseModel):
    """题目检索请求模型"""
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    difficulty_level: Optional[int] = None
    question_types: Optional[Dict[str, bool]] = None
    selected_skills: Optional[List[str]] = None

@router.post("/retrieve", response_model=QuestionGenerationResponse)
async def retrieve_questions(request: QuestionRetrievalRequest):
    """检索已存在的题目"""
    try:
        print(f"🔍 开始检索已存在的题目...")
        print(f"📋 检索参数: task_id={request.task_id}, session_id={request.session_id}")
        
        # 如果没有提供task_id或session_id，尝试根据其他参数生成session_id
        session_id = request.session_id
        if not session_id and not request.task_id:
            if request.selected_skills and request.difficulty_level:
                import hashlib
                session_data = f"{request.difficulty_level}_{sorted(request.selected_skills or [])}_{8}"  # 默认题目数量
                session_id = hashlib.md5(session_data.encode()).hexdigest()[:16]
                print(f"🔧 根据参数生成session_id: {session_id}")
        
        # 从ChromaDB检索题目
        questions = chroma_manager.get_questions_by_session(
            session_id=session_id,
            task_id=request.task_id,
            n_results=50
        )
        
        if not questions:
            return QuestionGenerationResponse(
                success=False,
                questions=[],
                message="未找到匹配的题目",
                stats={"total_questions": 0, "matched_from_db": 0, "generated_new": 0}
            )
        
        # 根据条件进一步过滤
        filtered_questions = questions
        
        # 按题目类型过滤
        if request.question_types:
            active_types = [key for key, value in request.question_types.items() if value]
            if active_types:
                filtered_questions = [
                    q for q in filtered_questions 
                    if q.get("type") in active_types
                ]
        
        # 按难度过滤
        if request.difficulty_level:
            filtered_questions = [
                q for q in filtered_questions 
                if q.get("difficulty") == request.difficulty_level
            ]
        
        # 构建统计信息
        stats = {
            "total_questions": len(filtered_questions),
            "matched_from_db": len(filtered_questions),
            "generated_new": 0,
            "chroma_stats": chroma_manager.get_collection_stats()
        }
        
        print(f"✅ 成功检索到 {len(filtered_questions)} 个题目")
        
        return QuestionGenerationResponse(
            success=True,
            questions=filtered_questions,
            message=f"成功检索到 {len(filtered_questions)} 个题目",
            stats=stats
        )
        
    except Exception as e:
        print(f"❌ 题目检索失败: {e}")
        raise HTTPException(status_code=500, detail=f"题目检索失败: {str(e)}")

class InterviewSessionRequest(BaseModel):
    """面试会话请求模型"""
    session_id: str

@router.post("/session", response_model=QuestionGenerationResponse)
async def get_interview_session_questions(request: InterviewSessionRequest):
    """从Redis获取面试会话题目"""
    try:
        print(f"🔍 获取面试会话题目: {request.session_id}")
        
        # 从Redis获取题目
        redis_data = await get_questions_from_redis(request.session_id)
        
        if not redis_data:
            raise HTTPException(
                status_code=404,
                detail=f"未找到面试会话: {request.session_id}"
            )
        
        questions = redis_data.get("questions", [])
        metadata = redis_data.get("metadata", {})
        
        return QuestionGenerationResponse(
            success=True,
            questions=questions,
            message=f"成功获取面试题目，共 {len(questions)} 道",
            stats={
                "total_questions": len(questions),
                "session_id": request.session_id,
                "created_at": metadata.get("created_at"),
                "redis_retrieved": len(questions)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 获取面试会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取面试会话失败: {str(e)}")

@router.delete("/session/{session_id}")
async def delete_interview_session(session_id: str):
    """删除面试会话"""
    try:
        if not redis_client:
            raise HTTPException(status_code=503, detail="Redis服务不可用")
        
        redis_key = f"interview_questions:{session_id}"
        deleted = redis_client.delete(redis_key)
        
        if deleted:
            return {"success": True, "message": "面试会话已删除"}
        else:
            raise HTTPException(status_code=404, detail="面试会话不存在")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")

@router.get("/redis-stats")
async def get_redis_stats():
    """获取Redis统计信息"""
    try:
        if not redis_client:
            return {"success": False, "message": "Redis服务不可用"}
        
        # 获取所有面试会话key
        keys = redis_client.keys("interview_questions:*")
        
        stats = {
            "success": True,
            "total_sessions": len(keys),
            "redis_info": {
                "connected": True,
                "memory_usage": redis_client.info().get("used_memory_human", "N/A")
            }
        }
        
        return stats
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "total_sessions": 0
        } 