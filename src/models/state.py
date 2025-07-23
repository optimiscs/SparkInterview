"""
LangGraph 状态管理
定义整个面试流程中的状态数据结构
"""
from typing import List, Dict, Any, Optional, TypedDict
from dataclasses import dataclass
from enum import Enum


class InterviewStage(Enum):
    """面试阶段枚举"""
    SETUP = "setup"
    INTERVIEW = "interview"
    ANALYSIS = "analysis"
    REPORT = "report"
    LEARNING_PATH = "learning_path"
    COMPLETED = "completed"


class QuestionType(Enum):
    """问题类型枚举"""
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    SITUATIONAL = "situational"
    BASIC = "basic"


@dataclass
class Question:
    """问题数据结构"""
    id: str
    text: str
    type: QuestionType
    difficulty: str  # "junior", "middle", "senior"
    field: str  # "AI", "Backend", "Frontend"
    expected_keywords: List[str]


@dataclass
class UserInfo:
    """用户信息数据结构"""
    user_id: str
    name: str
    target_position: str
    target_field: str
    resume_text: str
    resume_summary: Dict[str, Any]


@dataclass
class ConversationTurn:
    """对话轮次数据结构"""
    question_id: str
    question: str
    answer: str
    timestamp: float
    follow_up_questions: List[str] = None


@dataclass
class MultimodalAnalysis:
    """多模态分析结果"""
    
    # 视觉分析结果
    visual_analysis: Dict[str, Any] = None
    
    # 听觉分析结果  
    audio_analysis: Dict[str, Any] = None
    
    # 文本分析结果
    text_analysis: Dict[str, Any] = None
    
    # 综合评估结果
    comprehensive_assessment: Dict[str, Any] = None


@dataclass
class InterviewReport:
    """面试报告数据结构"""
    overall_score: float
    detailed_scores: Dict[str, float]
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    radar_chart_path: str


class InterviewState(TypedDict):
    """
    LangGraph 状态定义
    这是整个工作流中的共享状态
    """
    
    # 基础信息
    session_id: str
    stage: InterviewStage
    
    # 用户信息
    user_info: Optional[UserInfo]
    
    # 面试设置
    questions: List[Question]
    current_question_index: int
    
    # 对话历史
    conversation_history: List[ConversationTurn]
    
    # 多媒体文件路径
    video_path: Optional[str]
    audio_path: Optional[str]
    
    # 分析结果
    multimodal_analysis: Optional[MultimodalAnalysis]
    
    # 最终报告
    interview_report: Optional[InterviewReport]
    
    # 学习路径推荐
    learning_resources: List[Dict[str, Any]]
    
    # 错误信息
    errors: List[str]
    
    # 元数据
    metadata: Dict[str, Any]


def create_initial_state(session_id: str, user_info: UserInfo) -> InterviewState:
    """创建初始状态"""
    return InterviewState(
        session_id=session_id,
        stage=InterviewStage.SETUP,
        user_info=user_info,
        questions=[],
        current_question_index=0,
        conversation_history=[],
        video_path=None,
        audio_path=None,
        multimodal_analysis=None,
        interview_report=None,
        learning_resources=[],
        errors=[],
        metadata={}
    )


def update_state_stage(state: InterviewState, new_stage: InterviewStage) -> InterviewState:
    """更新状态阶段"""
    state["stage"] = new_stage
    return state


def add_conversation_turn(
    state: InterviewState, 
    question_id: str, 
    question: str, 
    answer: str,
    timestamp: float
) -> InterviewState:
    """添加对话轮次"""
    turn = ConversationTurn(
        question_id=question_id,
        question=question,
        answer=answer,
        timestamp=timestamp
    )
    state["conversation_history"].append(turn)
    return state


def add_error(state: InterviewState, error_message: str) -> InterviewState:
    """添加错误信息"""
    state["errors"].append(error_message)
    return state 