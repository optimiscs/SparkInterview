"""
API数据模型定义
使用Pydantic进行数据验证和序列化
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """用户角色枚举"""
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class InterviewStage(str, Enum):
    """面试阶段枚举"""
    SETUP = "setup"
    INTERVIEW = "interview"
    ANALYSIS = "analysis"
    REPORT = "report"
    LEARNING_PATH = "learning_path"
    COMPLETED = "completed"


class QuestionType(str, Enum):
    """问题类型枚举"""
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    SITUATIONAL = "situational"
    BASIC = "basic"


# ==================== 用户相关模型 ====================

class UserCreate(BaseModel):
    """用户创建请求模型"""
    name: str = Field(..., description="用户姓名", min_length=1, max_length=50)
    email: str = Field(..., description="邮箱地址")
    password: str = Field(..., description="密码", min_length=6)
    role: UserRole = Field(default=UserRole.STUDENT, description="用户角色")


class UserUpdate(BaseModel):
    """用户更新请求模型"""
    name: Optional[str] = Field(None, description="用户姓名", min_length=1, max_length=50)
    email: Optional[str] = Field(None, description="邮箱地址")
    avatar_url: Optional[str] = Field(None, description="头像URL")


class UserResponse(BaseModel):
    """用户响应模型"""
    id: str = Field(..., description="用户ID")
    name: str = Field(..., description="用户姓名")
    email: str = Field(..., description="邮箱地址")
    role: UserRole = Field(..., description="用户角色")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    """登录请求模型"""
    email: str = Field(..., description="邮箱地址")
    password: str = Field(..., description="密码")


class LoginResponse(BaseModel):
    """登录响应模型"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    user: UserResponse = Field(..., description="用户信息")


# ==================== 面试相关模型 ====================

class InterviewSetupRequest(BaseModel):
    """面试设置请求模型"""
    user_name: str = Field(..., description="候选人姓名", min_length=1, max_length=50)
    target_position: str = Field(..., description="目标岗位", min_length=1, max_length=100)
    target_field: str = Field(..., description="技术领域", min_length=1, max_length=50)
    resume_text: Optional[str] = Field(None, description="简历文本内容")
    resume_file: Optional[str] = Field(None, description="简历文件路径")
    difficulty_level: Optional[str] = Field("middle", description="难度级别", pattern="^(junior|middle|senior)$")
    question_count: int = Field(8, description="问题数量", ge=5, le=15)


class QuestionInfo(BaseModel):
    """问题信息模型"""
    id: str = Field(..., description="问题ID")
    text: str = Field(..., description="问题内容")
    type: QuestionType = Field(..., description="问题类型")
    difficulty: str = Field(..., description="难度级别")
    field: str = Field(..., description="所属领域")
    expected_keywords: List[str] = Field(default_factory=list, description="期望关键词")


class InterviewSetupResponse(BaseModel):
    """面试设置响应模型"""
    session_id: str = Field(..., description="面试会话ID")
    user_info: Dict[str, Any] = Field(..., description="用户信息")
    questions: List[QuestionInfo] = Field(..., description="面试问题列表")
    estimated_duration: int = Field(..., description="预计时长(分钟)")
    setup_completed: bool = Field(..., description="设置是否完成")


class InterviewQuestionRequest(BaseModel):
    """获取面试问题请求模型"""
    session_id: str = Field(..., description="面试会话ID")


class InterviewQuestionResponse(BaseModel):
    """面试问题响应模型"""
    question: str = Field(..., description="面试官问题")
    question_id: str = Field(..., description="问题ID")
    question_type: str = Field(..., description="问题类型")
    expected_keywords: List[str] = Field(default_factory=list, description="期望关键词")
    is_final: bool = Field(default=False, description="是否为最后一个问题")


class InterviewAnswerRequest(BaseModel):
    """提交面试回答请求模型"""
    session_id: str = Field(..., description="面试会话ID")
    question_id: str = Field(..., description="问题ID")
    question: str = Field(..., description="面试官问题")
    answer: str = Field(..., description="候选人回答", min_length=1)


class InterviewAnswerResponse(BaseModel):
    """提交面试回答响应模型"""
    answer_recorded: bool = Field(..., description="回答是否记录成功")
    follow_up_question: Optional[str] = Field(None, description="追问问题")
    should_continue: bool = Field(..., description="是否继续面试")
    interview_completed: bool = Field(default=False, description="面试是否完成")


class InterviewStatusResponse(BaseModel):
    """面试状态响应模型"""
    session_id: str = Field(..., description="面试会话ID")
    stage: InterviewStage = Field(..., description="当前阶段")
    current_question_index: int = Field(..., description="当前问题索引")
    total_questions: int = Field(..., description="总问题数")
    progress_percentage: float = Field(..., description="进度百分比")
    elapsed_time: Optional[int] = Field(None, description="已用时长(秒)")


# ==================== 分析和评估相关模型 ====================

class MultimodalAnalysisResponse(BaseModel):
    """多模态分析结果响应模型"""
    session_id: str = Field(..., description="面试会话ID")
    visual_analysis: Dict[str, Any] = Field(..., description="视觉分析结果")
    audio_analysis: Dict[str, Any] = Field(..., description="听觉分析结果")
    text_analysis: Dict[str, Any] = Field(..., description="文本分析结果")
    comprehensive_assessment: Dict[str, Any] = Field(..., description="综合评估结果")
    analysis_completed: bool = Field(..., description="分析是否完成")


class InterviewReportResponse(BaseModel):
    """面试报告响应模型"""
    session_id: str = Field(..., description="面试会话ID")
    overall_score: float = Field(..., description="总体评分", ge=0, le=10)
    detailed_scores: Dict[str, float] = Field(..., description="详细分数")
    strengths: List[str] = Field(..., description="优势列表")
    weaknesses: List[str] = Field(..., description="劣势列表")
    recommendations: List[str] = Field(..., description="改进建议")
    radar_chart_path: Optional[str] = Field(None, description="雷达图路径")
    detailed_report: Optional[str] = Field(None, description="详细报告文本")
    report_generated_at: datetime = Field(..., description="报告生成时间")


class LearningResourceInfo(BaseModel):
    """学习资源信息模型"""
    title: str = Field(..., description="资源标题")
    description: str = Field(..., description="资源描述")
    url: str = Field(..., description="资源链接")
    type: str = Field(..., description="资源类型")
    competency: str = Field(..., description="对应能力")
    difficulty: str = Field(..., description="难度级别")


class LearningPathResponse(BaseModel):
    """学习路径推荐响应模型"""
    session_id: str = Field(..., description="面试会话ID")
    weak_areas: List[str] = Field(..., description="薄弱领域")
    learning_resources: List[LearningResourceInfo] = Field(..., description="推荐学习资源")
    learning_plan: Optional[str] = Field(None, description="个性化学习计划")
    estimated_study_time: Optional[int] = Field(None, description="预计学习时长(小时)")


# ==================== 能力评估相关模型 ====================

class AssessmentType(str, Enum):
    """评估类型枚举"""
    TECHNICAL = "technical"
    COMMUNICATION = "communication"  
    LOGICAL_THINKING = "logical_thinking"
    LEARNING_ABILITY = "learning_ability"
    TEAMWORK = "teamwork"
    INNOVATION = "innovation"


class AssessmentStartRequest(BaseModel):
    """开始评估请求模型"""
    assessment_type: AssessmentType = Field(..., description="评估类型")
    user_id: str = Field(..., description="用户ID")
    difficulty_level: Optional[str] = Field("middle", description="难度级别")


class AssessmentQuestion(BaseModel):
    """评估问题模型"""
    id: str = Field(..., description="问题ID")
    type: str = Field(..., description="问题类型")
    title: str = Field(..., description="问题标题") 
    content: str = Field(..., description="问题内容")
    options: Optional[List[str]] = Field(None, description="选项列表(选择题)")
    max_words: Optional[int] = Field(None, description="最大字数限制(问答题)")


class AssessmentStartResponse(BaseModel):
    """开始评估响应模型"""
    session_id: str = Field(..., description="评估会话ID")
    assessment_type: AssessmentType = Field(..., description="评估类型")
    questions: List[AssessmentQuestion] = Field(..., description="问题列表")
    time_limit: int = Field(..., description="时间限制(分钟)")
    instructions: str = Field(..., description="评估说明")


class AssessmentAnswerRequest(BaseModel):
    """提交评估答案请求模型"""
    session_id: str = Field(..., description="评估会话ID")
    question_id: str = Field(..., description="问题ID")
    answer: str = Field(..., description="答案内容")


class AssessmentSubmitRequest(BaseModel):
    """提交评估请求模型"""
    session_id: str = Field(..., description="评估会话ID")
    answers: Dict[str, str] = Field(..., description="所有答案")


class AssessmentResultResponse(BaseModel):
    """评估结果响应模型"""
    session_id: str = Field(..., description="评估会话ID")
    assessment_type: AssessmentType = Field(..., description="评估类型")
    score: float = Field(..., description="评估分数", ge=0, le=100)
    level: str = Field(..., description="能力等级")
    analysis: str = Field(..., description="分析报告")
    suggestions: List[str] = Field(..., description="改进建议")
    completed_at: datetime = Field(..., description="完成时间")


# ==================== 学习资源相关模型 ====================

class ResourceCategory(str, Enum):
    """资源分类枚举"""
    ARTICLE = "article"
    VIDEO = "video"
    COURSE = "course"
    BOOK = "book"
    PRACTICE = "practice"


class LearningResourceCreate(BaseModel):
    """创建学习资源请求模型"""
    title: str = Field(..., description="资源标题", min_length=1, max_length=200)
    description: str = Field(..., description="资源描述", max_length=500)
    url: str = Field(..., description="资源链接")
    category: ResourceCategory = Field(..., description="资源分类")
    competency: str = Field(..., description="对应能力")
    difficulty: str = Field(..., description="难度级别", pattern="^(beginner|intermediate|advanced)$")
    tags: List[str] = Field(default_factory=list, description="标签列表")


class LearningResourceResponse(BaseModel):
    """学习资源响应模型"""
    id: str = Field(..., description="资源ID")
    title: str = Field(..., description="资源标题")
    description: str = Field(..., description="资源描述")
    url: str = Field(..., description="资源链接")
    category: ResourceCategory = Field(..., description="资源分类")
    competency: str = Field(..., description="对应能力")
    difficulty: str = Field(..., description="难度级别")
    tags: List[str] = Field(..., description="标签列表")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True


class ResourceSearchRequest(BaseModel):
    """资源搜索请求模型"""
    query: Optional[str] = Field(None, description="搜索关键词")
    competency: Optional[str] = Field(None, description="能力类型")
    difficulty: Optional[str] = Field(None, description="难度级别")
    category: Optional[ResourceCategory] = Field(None, description="资源分类")
    limit: int = Field(10, description="返回结果数量", ge=1, le=50)
    offset: int = Field(0, description="偏移量", ge=0)


class ResourceSearchResponse(BaseModel):
    """资源搜索响应模型"""
    resources: List[LearningResourceResponse] = Field(..., description="资源列表")
    total: int = Field(..., description="总数量")
    has_more: bool = Field(..., description="是否有更多")


# ==================== 通用响应模型 ====================

class APIResponse(BaseModel):
    """通用API响应模型"""
    code: int = Field(default=200, description="状态码")
    message: str = Field(default="success", description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    code: int = Field(..., description="错误码")
    message: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="错误详情")


# ==================== 文件上传相关模型 ====================

class FileUploadResponse(BaseModel):
    """文件上传响应模型"""
    filename: str = Field(..., description="文件名")
    file_path: str = Field(..., description="文件路径")
    file_size: int = Field(..., description="文件大小(字节)")
    upload_time: datetime = Field(..., description="上传时间")


class ResumeParseRequest(BaseModel):
    """简历解析请求模型"""
    file_path: str = Field(..., description="简历文件路径")
    extract_format: str = Field(default="structured", description="提取格式")


class ResumeParseResponse(BaseModel):
    """简历解析响应模型"""
    success: bool = Field(..., description="解析是否成功")
    data: Optional[Dict[str, Any]] = Field(None, description="解析结果")
    error: Optional[str] = Field(None, description="错误信息") 