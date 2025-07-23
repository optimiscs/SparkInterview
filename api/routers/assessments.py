"""
能力评估API路由
包括各种能力测试、评估结果分析等功能
"""
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends

from api.models import (
    AssessmentType, AssessmentStartRequest, AssessmentStartResponse,
    AssessmentQuestion, AssessmentAnswerRequest, AssessmentSubmitRequest,
    AssessmentResultResponse, APIResponse
)
from api.routers.users import get_current_user


router = APIRouter()

# 评估会话存储
assessment_sessions = {}

# 预设的评估问题库
ASSESSMENT_QUESTIONS = {
    AssessmentType.TECHNICAL: [
        {
            "id": "tech_1",
            "type": "choice",
            "title": "算法复杂度",
            "content": "以下哪种算法的时间复杂度为 O(n log n)？",
            "options": ["冒泡排序", "快速排序", "选择排序", "插入排序"],
            "max_words": None
        },
        {
            "id": "tech_2", 
            "type": "choice",
            "title": "数据结构",
            "content": "在什么情况下应该使用哈希表？",
            "options": ["需要有序存储数据", "需要快速查找", "需要节省内存", "需要支持范围查询"],
            "max_words": None
        },
        {
            "id": "tech_3",
            "type": "essay",
            "title": "系统设计",
            "content": "请设计一个简单的URL短链接服务，说明核心组件和工作流程。",
            "options": None,
            "max_words": 300
        }
    ],
    
    AssessmentType.COMMUNICATION: [
        {
            "id": "comm_1",
            "type": "choice",
            "title": "沟通场景",
            "content": "当您需要向非技术人员解释复杂技术问题时，最有效的方法是？",
            "options": ["使用专业术语确保准确性", "用类比和实例来解释", "提供详细的技术文档", "直接说结论即可"],
            "max_words": None
        },
        {
            "id": "comm_2",
            "type": "essay", 
            "title": "冲突处理",
            "content": "描述一次您处理团队内部分歧的经历，您是如何协调不同观点的？",
            "options": None,
            "max_words": 250
        }
    ],
    
    AssessmentType.LOGICAL_THINKING: [
        {
            "id": "logic_1",
            "type": "choice",
            "title": "逻辑推理",
            "content": "如果所有A都是B，所有B都是C，那么所有A都是C。这种推理方式是？",
            "options": ["归纳推理", "演绎推理", "类比推理", "因果推理"],
            "max_words": None
        },
        {
            "id": "logic_2",
            "type": "essay",
            "title": "问题分析",
            "content": "请分析：为什么有些软件项目会延期交付？从系统性角度给出至少3个原因。",
            "options": None,
            "max_words": 300
        }
    ],
    
    AssessmentType.LEARNING_ABILITY: [
        {
            "id": "learn_1",
            "type": "choice",
            "title": "学习策略",
            "content": "面对一门全新的技术，您通常会采用什么学习方法？",
            "options": ["直接阅读官方文档", "先看教程和例子", "参加培训课程", "找有经验的人请教"],
            "max_words": None
        },
        {
            "id": "learn_2",
            "type": "essay",
            "title": "学习经历",
            "content": "描述您最近学习的一项新技能，您是如何制定学习计划并坚持执行的？",
            "options": None,
            "max_words": 250
        }
    ],
    
    AssessmentType.TEAMWORK: [
        {
            "id": "team_1",
            "type": "choice",
            "title": "团队角色",
            "content": "在团队项目中，您更倾向于承担什么角色？",
            "options": ["项目协调者", "技术专家", "创意贡献者", "质量把控者"],
            "max_words": None
        },
        {
            "id": "team_2",
            "type": "essay",
            "title": "团队合作",
            "content": "描述一次成功的团队协作经历，您在其中发挥了什么作用？",
            "options": None,
            "max_words": 250
        }
    ],
    
    AssessmentType.INNOVATION: [
        {
            "id": "innov_1",
            "type": "choice",
            "title": "创新思维",
            "content": "面对技术难题时，您认为最重要的是？",
            "options": ["寻找现有的解决方案", "尝试全新的方法", "分析问题的本质", "咨询专家意见"],
            "max_words": None
        },
        {
            "id": "innov_2",
            "type": "essay",
            "title": "创新实践",
            "content": "请描述您提出的一个创新想法或解决方案，它解决了什么问题？",
            "options": None,
            "max_words": 300
        }
    ]
}

# 评估指导说明
ASSESSMENT_INSTRUCTIONS = {
    AssessmentType.TECHNICAL: "本测试将评估您的技术知识水平、编程能力和系统设计思维。请根据您的实际经验回答。",
    AssessmentType.COMMUNICATION: "本测试将评估您的沟通表达能力、倾听技巧和人际交往能力。请结合具体经历回答。",
    AssessmentType.LOGICAL_THINKING: "本测试将评估您的逻辑分析能力、问题解决思路和系统性思维。请仔细分析后回答。",
    AssessmentType.LEARNING_ABILITY: "本测试将评估您的学习策略、知识获取能力和持续学习意识。请诚实回答。",
    AssessmentType.TEAMWORK: "本测试将评估您的团队协作能力、沟通协调技巧和集体责任感。请基于真实经历回答。",
    AssessmentType.INNOVATION: "本测试将评估您的创新思维、创意能力和解决问题的新颖方法。请发挥您的想象力。"
}

# 时间限制（分钟）
TIME_LIMITS = {
    AssessmentType.TECHNICAL: 45,
    AssessmentType.COMMUNICATION: 30,
    AssessmentType.LOGICAL_THINKING: 40,
    AssessmentType.LEARNING_ABILITY: 35,
    AssessmentType.TEAMWORK: 25,
    AssessmentType.INNOVATION: 50
}


@router.post("/start",
             response_model=AssessmentStartResponse,
             summary="开始评估",
             description="开始指定类型的能力评估")
async def start_assessment(
    request: AssessmentStartRequest,
    current_user: dict = Depends(get_current_user)
):
    """开始能力评估"""
    try:
        # 创建评估会话ID
        session_id = str(uuid.uuid4())
        
        # 获取问题
        questions = ASSESSMENT_QUESTIONS.get(request.assessment_type, [])
        if not questions:
            raise HTTPException(
                status_code=400,
                detail="不支持的评估类型"
            )
        
        # 根据难度级别筛选问题
        if request.difficulty_level == "junior":
            questions = questions[:2]  # 简单级别只做前2题
        elif request.difficulty_level == "senior":
            questions = questions  # 高级级别做所有题目
        
        # 存储评估会话
        assessment_sessions[session_id] = {
            "assessment_type": request.assessment_type,
            "difficulty_level": request.difficulty_level,
            "user_id": current_user["id"],
            "questions": questions,
            "answers": {},
            "started_at": datetime.now(),
            "submitted": False
        }
        
        # 转换问题格式
        response_questions = []
        for q in questions:
            response_questions.append(AssessmentQuestion(
                id=q["id"],
                type=q["type"],
                title=q["title"],
                content=q["content"],
                options=q["options"],
                max_words=q["max_words"]
            ))
        
        return AssessmentStartResponse(
            session_id=session_id,
            assessment_type=request.assessment_type,
            questions=response_questions,
            time_limit=TIME_LIMITS.get(request.assessment_type, 30),
            instructions=ASSESSMENT_INSTRUCTIONS.get(request.assessment_type, "请认真完成评估。")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"开始评估失败: {str(e)}"
        )


@router.post("/answer",
             response_model=APIResponse,
             summary="提交单题答案",
             description="提交单个问题的答案")
async def submit_answer(
    request: AssessmentAnswerRequest,
    current_user: dict = Depends(get_current_user)
):
    """提交单题答案"""
    session_id = request.session_id
    
    if session_id not in assessment_sessions:
        raise HTTPException(
            status_code=404,
            detail="评估会话不存在"
        )
    
    session = assessment_sessions[session_id]
    
    # 权限检查
    if session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此评估会话"
        )
    
    # 检查是否已提交
    if session["submitted"]:
        raise HTTPException(
            status_code=400,
            detail="评估已提交，无法修改答案"
        )
    
    # 保存答案
    session["answers"][request.question_id] = request.answer
    
    return APIResponse(message="答案已保存")


@router.post("/submit",
             response_model=AssessmentResultResponse,
             summary="提交评估",
             description="提交完整的评估答案并获取结果")
async def submit_assessment(
    request: AssessmentSubmitRequest,
    current_user: dict = Depends(get_current_user)
):
    """提交评估并获取结果"""
    session_id = request.session_id
    
    if session_id not in assessment_sessions:
        raise HTTPException(
            status_code=404,
            detail="评估会话不存在"
        )
    
    session = assessment_sessions[session_id]
    
    # 权限检查
    if session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此评估会话"
        )
    
    # 检查是否已提交
    if session["submitted"]:
        raise HTTPException(
            status_code=400,
            detail="评估已提交"
        )
    
    try:
        # 合并答案
        session["answers"].update(request.answers)
        session["submitted"] = True
        session["submitted_at"] = datetime.now()
        
        # 计算分数和分析
        result = analyze_assessment_result(session)
        
        return AssessmentResultResponse(
            session_id=session_id,
            assessment_type=session["assessment_type"],
            score=result["score"],
            level=result["level"],
            analysis=result["analysis"],
            suggestions=result["suggestions"],
            completed_at=datetime.now()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"评估提交失败: {str(e)}"
        )


def analyze_assessment_result(session: Dict[str, Any]) -> Dict[str, Any]:
    """分析评估结果"""
    assessment_type = session["assessment_type"]
    answers = session["answers"]
    questions = session["questions"]
    
    # 简单的评分逻辑（实际应用中会更复杂）
    total_questions = len(questions)
    answered_questions = len(answers)
    
    # 基础分数（基于答题完整度）
    base_score = (answered_questions / total_questions) * 60
    
    # 根据答案质量调整分数
    quality_bonus = 0
    
    for question in questions:
        question_id = question["id"]
        if question_id in answers:
            answer = answers[question_id]
            
            if question["type"] == "choice":
                # 选择题有标准答案（这里简化处理）
                quality_bonus += 10
            elif question["type"] == "essay":
                # 问答题根据答案长度和关键词给分
                if len(answer.strip()) > 50:
                    quality_bonus += 15
                if len(answer.strip()) > 150:
                    quality_bonus += 10
    
    # 计算最终分数
    final_score = min(100, base_score + quality_bonus)
    
    # 确定等级
    if final_score >= 85:
        level = "优秀"
    elif final_score >= 75:
        level = "良好" 
    elif final_score >= 60:
        level = "合格"
    else:
        level = "需提升"
    
    # 生成分析报告
    analysis = generate_assessment_analysis(assessment_type, final_score, answers)
    
    # 生成改进建议
    suggestions = generate_assessment_suggestions(assessment_type, final_score)
    
    return {
        "score": final_score,
        "level": level,
        "analysis": analysis,
        "suggestions": suggestions
    }


def generate_assessment_analysis(assessment_type: AssessmentType, score: float, answers: Dict[str, str]) -> str:
    """生成评估分析报告"""
    
    analysis_templates = {
        AssessmentType.TECHNICAL: f"""
您的技术能力评估得分为 {score:.1f} 分。从答案中可以看出，您对技术概念有{'较好' if score >= 75 else '基本' if score >= 60 else '有限'}的理解。
{'您展现出了扎实的技术基础和系统性思维。' if score >= 85 else '建议加强技术深度的学习和实践。' if score < 60 else '继续保持学习热情，注重理论与实践结合。'}
""",
        
        AssessmentType.COMMUNICATION: f"""
您的沟通能力评估得分为 {score:.1f} 分。您在表达{'方面表现出色' if score >= 75 else '上有一定基础' if score >= 60 else '上需要加强练习'}。
{'您具备良好的沟通意识和表达技巧。' if score >= 85 else '建议多参与团队讨论和公开演讲。' if score < 60 else '继续培养倾听和表达的平衡能力。'}
""",
        
        AssessmentType.LOGICAL_THINKING: f"""
您的逻辑思维评估得分为 {score:.1f} 分。您展现出{'强' if score >= 75 else '中等' if score >= 60 else '有待提升的'}逻辑分析能力。
{'您的思维方式系统且有条理。' if score >= 85 else '建议加强逻辑推理和问题分析训练。' if score < 60 else '继续培养结构化思维能力。'}
""",
        
        AssessmentType.LEARNING_ABILITY: f"""
您的学习能力评估得分为 {score:.1f} 分。您的学习策略{'很有效' if score >= 75 else '较为合理' if score >= 60 else '需要优化'}。
{'您展现出了优秀的自主学习能力。' if score >= 85 else '建议制定更系统的学习计划。' if score < 60 else '继续探索适合自己的学习方法。'}
""",
        
        AssessmentType.TEAMWORK: f"""
您的团队协作评估得分为 {score:.1f} 分。您在团队合作方面{'表现突出' if score >= 75 else '有良好基础' if score >= 60 else '有提升空间'}。
{'您是一个出色的团队成员。' if score >= 85 else '建议多参与团队项目提升协作技能。' if score < 60 else '继续培养团队意识和沟通协调能力。'}
""",
        
        AssessmentType.INNOVATION: f"""
您的创新思维评估得分为 {score:.1f} 分。您的创新能力{'很强' if score >= 75 else '中等' if score >= 60 else '需要培养'}。
{'您具备出色的创新意识和实践能力。' if score >= 85 else '建议多尝试新方法和跨域思考。' if score < 60 else '继续保持好奇心和探索精神。'}
"""
    }
    
    return analysis_templates.get(assessment_type, f"您的评估得分为 {score:.1f} 分。").strip()


def generate_assessment_suggestions(assessment_type: AssessmentType, score: float) -> List[str]:
    """生成改进建议"""
    
    suggestions_map = {
        AssessmentType.TECHNICAL: [
            "深入学习相关技术领域的核心知识",
            "通过实际项目提升编程和设计能力",
            "关注行业最新技术趋势和最佳实践",
            "参与开源项目增加实战经验"
        ] if score < 75 else [
            "继续保持技术学习的热情",
            "分享技术知识，提升影响力",
            "探索新兴技术领域",
            "承担更有挑战性的技术工作"
        ],
        
        AssessmentType.COMMUNICATION: [
            "练习公开演讲和表达技巧",
            "参加沟通技能培训课程",
            "多参与团队讨论和会议",
            "学习有效倾听和反馈技巧"
        ] if score < 75 else [
            "发挥沟通优势，帮助团队建设",
            "担任项目协调或培训角色",
            "学习跨文化沟通技巧",
            "发展领导力和影响力"
        ],
        
        AssessmentType.LOGICAL_THINKING: [
            "练习逻辑推理和问题分析",
            "学习结构化思维方法",
            "阅读逻辑思维相关书籍",
            "参与案例分析和讨论"
        ] if score < 75 else [
            "应用逻辑思维解决复杂问题",
            "指导他人提升分析能力",
            "参与战略规划和决策制定",
            "发展系统性思维能力"
        ],
        
        AssessmentType.LEARNING_ABILITY: [
            "制定系统的学习计划",
            "探索多样化的学习方法",
            "建立知识管理体系",
            "培养持续学习的习惯"
        ] if score < 75 else [
            "分享学习方法和经验",
            "指导他人的学习成长",
            "探索前沿知识领域",
            "建立个人品牌和影响力"
        ],
        
        AssessmentType.TEAMWORK: [
            "主动参与团队活动和项目",
            "学习团队协作工具和方法",
            "培养同理心和包容性",
            "提升冲突处理能力"
        ] if score < 75 else [
            "承担团队领导责任",
            "促进团队文化建设",
            "指导新成员融入团队",
            "推动团队创新和改进"
        ],
        
        AssessmentType.INNOVATION: [
            "培养好奇心和探索精神",
            "学习创新思维方法",
            "关注行业创新趋势",
            "尝试跨领域思考和实践"
        ] if score < 75 else [
            "推动创新项目的实施",
            "分享创新理念和方法",
            "建立创新团队和文化",
            "探索颠覆性创新机会"
        ]
    }
    
    return suggestions_map.get(assessment_type, ["继续努力提升相关能力"])


@router.get("/result/{session_id}",
            response_model=AssessmentResultResponse,
            summary="获取评估结果",
            description="获取已完成评估的结果")
async def get_assessment_result(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取评估结果"""
    if session_id not in assessment_sessions:
        raise HTTPException(
            status_code=404,
            detail="评估会话不存在"
        )
    
    session = assessment_sessions[session_id]
    
    # 权限检查
    if session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此评估会话"
        )
    
    if not session["submitted"]:
        raise HTTPException(
            status_code=400,
            detail="评估尚未提交"
        )
    
    # 重新计算结果
    result = analyze_assessment_result(session)
    
    return AssessmentResultResponse(
        session_id=session_id,
        assessment_type=session["assessment_type"],
        score=result["score"],
        level=result["level"],
        analysis=result["analysis"],
        suggestions=result["suggestions"],
        completed_at=session.get("submitted_at", datetime.now())
    )


@router.get("/history",
            response_model=List[AssessmentResultResponse],
            summary="获取评估历史",
            description="获取用户的评估历史记录")
async def get_assessment_history(
    current_user: dict = Depends(get_current_user)
):
    """获取用户的评估历史"""
    user_assessments = []
    
    for session_id, session in assessment_sessions.items():
        if session["user_id"] == current_user["id"] and session["submitted"]:
            result = analyze_assessment_result(session)
            
            user_assessments.append(AssessmentResultResponse(
                session_id=session_id,
                assessment_type=session["assessment_type"],
                score=result["score"],
                level=result["level"],
                analysis=result["analysis"],
                suggestions=result["suggestions"],
                completed_at=session.get("submitted_at", datetime.now())
            ))
    
    # 按完成时间排序
    user_assessments.sort(key=lambda x: x.completed_at, reverse=True)
    
    return user_assessments 