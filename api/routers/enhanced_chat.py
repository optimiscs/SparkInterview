"""
增强的智能面试官聊天系统 - 基于感知-决策-行动架构
支持主动信息收集和数据库更新
"""
import json
import uuid
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.routers.users import get_current_user
from src.workflow import create_interview_workflow
from src.models.state import create_initial_state, UserInfo
from src.models.spark_client import create_spark_model
from src.database.sqlite_manager import db_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# 智能体会话存储
agent_sessions = {}
# WebSocket连接管理
websocket_connections = {}


class AgentPerceptionResult(BaseModel):
    """感知结果模型"""
    missing_info: List[str]
    confidence_score: float
    user_emotion: str
    information_completeness: float
    suggested_actions: List[str]


class AgentDecision(BaseModel):
    """决策结果模型"""
    action_type: str  # "ask_question", "generate_question", "update_database", "provide_feedback"
    priority: int
    reasoning: str
    parameters: Dict[str, Any]


class EnhancedChatMessage(BaseModel):
    """增强聊天消息模型"""
    role: str
    content: str
    timestamp: datetime = None
    session_id: str = None
    perception_data: Optional[Dict] = None
    decision_data: Optional[Dict] = None
    
    def __init__(self, **data):
        if data.get('timestamp') is None:
            data['timestamp'] = datetime.now()
        super().__init__(**data)


class IntelligentInterviewAgent:
    """智能面试官 - 感知决策行动架构"""
    
    def __init__(self, session_id: str, user_info: UserInfo):
        self.session_id = session_id
        self.user_info = user_info
        self.messages: List[EnhancedChatMessage] = []
        self.user_profile = {}  # 动态构建的用户画像
        self.missing_info_stack = []  # 缺失信息栈
        self.interview_stage = "introduction"
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        
        # 初始化用户画像
        self._initialize_user_profile()
        
        # 初始欢迎消息
        self._initialize_agent()
    
    def _initialize_user_profile(self):
        """初始化用户画像，识别缺失信息"""
        self.user_profile = {
            "basic_info": {
                "name": self.user_info.name,
                "target_position": self.user_info.target_position,
                "target_field": self.user_info.target_field,
                "work_years": None,  # 缺失
                "current_company": None,  # 缺失
                "education_level": None,  # 缺失
                "graduation_year": None,  # 缺失
                "expected_salary": None,  # 缺失
            },
            "technical_skills": {},
            "project_experience": {},
            "interview_preferences": {},
            "completeness_score": 0.3  # 初始完整度很低
        }
        
        # 分析简历文本，提取已有信息
        self._extract_info_from_resume()
    
    def _extract_info_from_resume(self):
        """从简历文本中提取信息"""
        resume_text = self.user_info.resume_text or ""
        
        # 使用简单的规则提取（实际可用NLP模型）
        if "年工作经验" in resume_text or "工作经验" in resume_text:
            # 这里可以用正则或NLP提取工作年限
            pass
        
        if "本科" in resume_text:
            self.user_profile["basic_info"]["education_level"] = "本科"
        elif "硕士" in resume_text or "研究生" in resume_text:
            self.user_profile["basic_info"]["education_level"] = "硕士"
        elif "博士" in resume_text:
            self.user_profile["basic_info"]["education_level"] = "博士"
    
    def _initialize_agent(self):
        """初始化智能面试官"""
        # 感知阶段：分析缺失信息
        perception = self._perception_phase()
        
        # 决策阶段：决定开场策略
        decision = self._decision_phase(perception)
        
        # 生成欢迎消息
        welcome_content = self._generate_welcome_message(decision)
        
        welcome_message = EnhancedChatMessage(
            role="assistant",
            content=welcome_content,
            session_id=self.session_id,
            perception_data=perception.dict(),
            decision_data=decision.dict()
        )
        self.messages.append(welcome_message)
    
    def _perception_phase(self, user_message: str = "") -> AgentPerceptionResult:
        """🧠 感知阶段：分析当前状态和缺失信息"""
        
        # 1. 检测缺失的关键信息
        missing_info = []
        basic_info = self.user_profile["basic_info"]
        
        if not basic_info.get("work_years"):
            missing_info.append("work_years")
        if not basic_info.get("current_company"):
            missing_info.append("current_company") 
        if not basic_info.get("education_level"):
            missing_info.append("education_level")
        if not basic_info.get("graduation_year"):
            missing_info.append("graduation_year")
        
        # 2. 计算信息完整度
        total_fields = len(basic_info)
        filled_fields = sum(1 for v in basic_info.values() if v is not None)
        completeness = filled_fields / total_fields
        
        # 3. 情感分析（简化版，可接入情感分析API）
        user_emotion = "neutral"
        if user_message:
            if any(word in user_message for word in ["紧张", "担心", "害怕"]):
                user_emotion = "anxious"
            elif any(word in user_message for word in ["兴奋", "期待", "自信"]):
                user_emotion = "confident"
        
        # 4. 建议行动
        suggested_actions = []
        if len(missing_info) > 0:
            suggested_actions.append("ask_missing_info")
        if completeness < 0.5:
            suggested_actions.append("gather_basic_info")
        if user_emotion == "anxious":
            suggested_actions.append("provide_comfort")
        
        return AgentPerceptionResult(
            missing_info=missing_info,
            confidence_score=0.8,
            user_emotion=user_emotion,
            information_completeness=completeness,
            suggested_actions=suggested_actions
        )
    
    def _decision_phase(self, perception: AgentPerceptionResult) -> AgentDecision:
        """🤖 决策阶段：基于感知结果制定行动策略"""
        
        # 根据信息完整度决定策略
        if perception.information_completeness < 0.5:
            # 信息不足，优先收集基础信息
            if "work_years" in perception.missing_info:
                return AgentDecision(
                    action_type="ask_question",
                    priority=1,
                    reasoning="工作年限是面试评估的关键信息，需要优先获取",
                    parameters={
                        "question_topic": "work_experience",
                        "specific_info": "work_years",
                        "question_style": "friendly"
                    }
                )
        
        if perception.user_emotion == "anxious":
            return AgentDecision(
                action_type="provide_comfort",
                priority=1, 
                reasoning="用户情绪紧张，需要先缓解压力",
                parameters={"comfort_level": "high"}
            )
        
        # 默认：正常面试进行
        return AgentDecision(
            action_type="generate_question",
            priority=2,
            reasoning="信息相对完整，可以开始标准面试流程",
            parameters={"question_type": "behavioral"}
        )
    
    def _action_phase(self, decision: AgentDecision) -> str:
        """⚡ 行动阶段：执行决策"""
        
        if decision.action_type == "ask_question":
            return self._ask_for_missing_info(decision.parameters)
        elif decision.action_type == "provide_comfort":
            return self._provide_comfort()
        elif decision.action_type == "generate_question":
            return self._generate_interview_question()
        else:
            return "让我们继续我们的面试吧。"
    
    def _ask_for_missing_info(self, params: Dict) -> str:
        """主动询问缺失信息"""
        info_type = params.get("specific_info")
        
        questions_map = {
            "work_years": f"在开始面试之前，我想了解一下您的工作背景。请问您有多少年的工作经验呢？这将帮助我为您提供更合适的面试问题。",
            "current_company": "请问您目前在哪家公司工作？或者如果您是应届毕业生，最近的实习经历是在哪里？",
            "education_level": "请问您的最高学历是什么？本科、硕士还是博士？",
            "graduation_year": "请问您是哪一年毕业的？这有助于我了解您的职业发展阶段。"
        }
        
        return questions_map.get(info_type, "请告诉我更多关于您的背景信息。")
    
    def _provide_comfort(self) -> str:
        """提供情感支持"""
        return "我能感觉到您可能有一些紧张，这很正常！面试本身就是一个相互了解的过程。请放松心情，我会尽量营造一个轻松的氛围。我们慢慢来，不用着急。"
    
    def _generate_interview_question(self) -> str:
        """生成面试问题"""
        return f"很好！现在让我们正式开始面试。首先，请您简单介绍一下自己，包括您的教育背景、工作经历，以及为什么对{self.user_info.target_position}这个职位感兴趣。"
    
    def _generate_welcome_message(self, decision: AgentDecision) -> str:
        """生成个性化欢迎消息"""
        base_welcome = f"您好 {self.user_info.name}！我是您的AI面试官李诚。"
        
        if decision.action_type == "ask_question":
            return f"{base_welcome} 我看到您应聘的是{self.user_info.target_position}职位。{self._action_phase(decision)}"
        else:
            return f"{base_welcome} 我看到您应聘的是{self.user_info.target_position}职位，让我们开始面试吧！{self._action_phase(decision)}"
    
    async def process_user_message(self, message: str) -> AsyncGenerator[str, None]:
        """处理用户消息 - 完整的感知决策行动循环"""
        
        # 1. 🧠 感知阶段
        perception = self._perception_phase(message)
        
        # 2. 尝试从用户回答中提取结构化信息
        extracted_info = await self._extract_structured_info(message, perception)
        
        # 3. 如果提取到信息，更新数据库
        if extracted_info:
            await self._update_user_database(extracted_info)
        
        # 添加用户消息到历史
        user_msg = EnhancedChatMessage(
            role="user",
            content=message,
            session_id=self.session_id,
            perception_data=perception.dict()
        )
        self.messages.append(user_msg)
        self.last_activity = datetime.now()
        
        # 4. 🤖 决策阶段
        decision = self._decision_phase(perception)
        
        # 5. ⚡ 行动阶段
        if decision.action_type == "ask_question":
            # 直接询问，不需要调用大模型
            response = self._action_phase(decision)
            yield f"data: {json.dumps({'type': 'chunk', 'content': response, 'session_id': self.session_id})}\n\n"
        else:
            # 使用大模型生成回应
            async for chunk in self._generate_ai_response_with_context(decision, perception):
                yield chunk
        
        # 发送完成标识
        yield f"data: {json.dumps({'type': 'complete', 'session_id': self.session_id})}\n\n"
    
    async def _extract_structured_info(self, message: str, perception: AgentPerceptionResult) -> Dict:
        """从用户回答中提取结构化信息"""
        extracted = {}
        
        # 简单的信息提取（实际应该使用NLP模型）
        if "work_years" in perception.missing_info:
            # 尝试提取工作年限
            import re
            years_pattern = r'(\d+)\s*年'
            match = re.search(years_pattern, message)
            if match:
                extracted["work_years"] = int(match.group(1))
        
        if "current_company" in perception.missing_info:
            # 简单的公司名提取
            if "公司" in message:
                # 这里可以用更复杂的NLP提取
                extracted["current_company"] = "用户提到的公司"
        
        return extracted
    
    async def _update_user_database(self, info: Dict):
        """📊 更新用户数据库 - MCP数据操作"""
        try:
            # 更新内存中的用户画像
            for key, value in info.items():
                if key in self.user_profile["basic_info"]:
                    self.user_profile["basic_info"][key] = value
            
            # 重新计算完整度
            total_fields = len(self.user_profile["basic_info"])
            filled_fields = sum(1 for v in self.user_profile["basic_info"].values() if v is not None)
            self.user_profile["completeness_score"] = filled_fields / total_fields
            
            # 更新数据库（这里需要扩展用户表结构）
            # 实际使用中，可以创建一个用户画像表
            user_data = {}
            if "work_years" in info:
                user_data["work_years"] = info["work_years"]
            if "current_company" in info:
                user_data["current_company"] = info["current_company"]
            
            if user_data:
                # 这里调用数据库更新操作
                # await db_manager.update_user_profile(self.user_info.user_id, user_data)
                logger.info(f"✅ 用户信息已更新: {user_data}")
                
        except Exception as e:
            logger.error(f"❌ 更新用户信息失败: {e}")
    
    async def _generate_ai_response_with_context(self, decision: AgentDecision, perception: AgentPerceptionResult) -> AsyncGenerator[str, None]:
        """带有决策和感知上下文的AI响应生成"""
        try:
            # 构建增强的系统提示词
            system_prompt = self._build_enhanced_system_prompt(decision, perception)
            
            # 构建对话上下文
            conversation_context = self._build_conversation_context()
            
            # 创建星火模型实例
            spark_model = create_spark_model()
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": conversation_context}
            ]
            
            # 流式生成响应
            response_stream = spark_model.stream(messages)
            
            full_response = ""
            for chunk in response_stream:
                content = ""
                if hasattr(chunk, 'content') and chunk.content:
                    content = chunk.content
                elif isinstance(chunk, str):
                    content = chunk
                    
                if content:
                    full_response += content
                    yield f"data: {json.dumps({'type': 'chunk', 'content': content, 'session_id': self.session_id})}\n\n"
            
            # 添加AI回应到消息历史
            ai_msg = EnhancedChatMessage(
                role="assistant",
                content=full_response,
                session_id=self.session_id,
                decision_data=decision.dict()
            )
            self.messages.append(ai_msg)
                
        except Exception as e:
            error_msg = f"抱歉，我遇到了一些技术问题。让我们继续其他话题吧。"
            logger.error(f"AI响应生成失败: {str(e)}")
            yield f"data: {json.dumps({'type': 'chunk', 'content': error_msg, 'session_id': self.session_id})}\n\n"
    
    def _build_enhanced_system_prompt(self, decision: AgentDecision, perception: AgentPerceptionResult) -> str:
        """构建增强的系统提示词"""
        base_prompt = f"""你是一名经验丰富的AI面试官李诚，正在面试应聘{self.user_info.target_position}职位的候选人。

候选人信息：
- 姓名：{self.user_info.name}
- 目标职位：{self.user_info.target_position}
- 目标领域：{self.user_info.target_field}
- 信息完整度：{perception.information_completeness:.1%}
- 当前情绪：{perception.user_emotion}

用户画像完整度：
"""
        
        # 添加用户画像信息
        for key, value in self.user_profile["basic_info"].items():
            status = "✅" if value is not None else "❌"
            base_prompt += f"- {key}: {value or '未知'} {status}\n"
        
        # 添加决策上下文
        base_prompt += f"""
当前决策：
- 行动类型：{decision.action_type}
- 优先级：{decision.priority}
- 决策原因：{decision.reasoning}

面试要求：
1. 如果信息完整度低于50%，优先收集基础信息
2. 根据用户情绪调整沟通方式
3. 对于缺失的关键信息，可以主动询问
4. 保持专业且友好的态度
5. 每次回应控制在100-200字内

请根据以上上下文信息，给出合适的面试官回应。"""
        
        return base_prompt
    
    def _build_conversation_context(self) -> str:
        """构建对话上下文"""
        if len(self.messages) <= 1:
            return "候选人刚开始面试，请根据当前的感知和决策信息给出合适的回应。"
        
        context = "对话历史：\n"
        # 只取最近6轮对话，避免上下文过长
        recent_messages = self.messages[-12:]  # 6轮对话=12条消息
        
        for msg in recent_messages:
            role_name = "候选人" if msg.role == "user" else "面试官"
            context += f"{role_name}: {msg.content}\n"
        
        context += "\n现在请根据系统提示中的感知信息、决策信息和对话历史，作为面试官给出合适的回应："
        return context


# ==================== API路由 ====================

class EnhancedChatStartRequest(BaseModel):
    """增强聊天开始请求"""
    user_name: str
    target_position: str
    target_field: str
    resume_text: str = ""


@router.post("/enhanced-chat/start")
async def start_enhanced_chat_session(
    request: EnhancedChatStartRequest,
    current_user: dict = Depends(get_current_user)
):
    """开始增强的智能面试会话"""
    try:
        # 创建会话ID
        session_id = str(uuid.uuid4())
        
        # 创建用户信息
        user_info = UserInfo(
            user_id=current_user["id"],
            name=request.user_name,
            target_position=request.target_position,
            target_field=request.target_field,
            resume_text=request.resume_text,
            resume_summary={}
        )
        
        # 创建智能面试官
        agent = IntelligentInterviewAgent(session_id, user_info)
        agent_sessions[session_id] = agent
        
        # 返回初始响应（欢迎消息）
        welcome_message = agent.messages[0]
        
        return {
            "session_id": session_id,
            "message": {
                "role": welcome_message.role,
                "content": welcome_message.content,
                "timestamp": welcome_message.timestamp.isoformat(),
                "perception_data": welcome_message.perception_data,
                "decision_data": welcome_message.decision_data
            },
            "user_profile": agent.user_profile,
            "interview_stage": agent.interview_stage
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"创建增强聊天会话失败: {str(e)}"
        )


@router.post("/enhanced-chat/message")
async def send_enhanced_chat_message(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """发送增强聊天消息"""
    session_id = request.get("session_id")
    message = request.get("message", "")
    
    if session_id not in agent_sessions:
        raise HTTPException(
            status_code=404,
            detail="聊天会话不存在"
        )
    
    agent = agent_sessions[session_id]
    
    # 权限检查
    if agent.user_info.user_id != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此聊天会话"
        )
    
    try:
        # 创建Server-Sent Events响应
        async def generate_response():
            yield "data: {\"type\": \"start\", \"session_id\": \"" + session_id + "\"}\n\n"
            
            async for chunk in agent.process_user_message(message):
                yield chunk
                
            # 发送更新的用户画像
            yield f"data: {json.dumps({'type': 'profile_update', 'profile': agent.user_profile, 'session_id': session_id})}\n\n"
            yield "data: {\"type\": \"end\"}\n\n"
        
        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"处理消息失败: {str(e)}"
        )


@router.get("/enhanced-chat/profile/{session_id}")
async def get_user_profile(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取动态用户画像"""
    if session_id not in agent_sessions:
        raise HTTPException(
            status_code=404,
            detail="会话不存在"
        )
    
    agent = agent_sessions[session_id]
    
    # 权限检查
    if agent.user_info.user_id != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此会话"
        )
    
    return {
        "session_id": session_id,
        "user_profile": agent.user_profile,
        "missing_info": agent._perception_phase().missing_info,
        "completeness_score": agent.user_profile["completeness_score"]
    }
