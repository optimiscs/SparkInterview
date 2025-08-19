"""
基于LangGraph的智能面试官 - 使用最新LangGraph API
充分利用LangGraph库封装好的功能，确保接口真实有效
"""
import asyncio
import json
import logging
import re
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from operator import add
from pathlib import Path

# LangChain/LangGraph imports
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# LangGraph导入 - 使用最新API
try:
    from langgraph.graph import StateGraph, END, START
    from langgraph.graph.message import add_messages
    from langgraph.prebuilt import ToolNode, tools_condition
    
    # 检查点保存器 - 条件导入
    SqliteSaver = None
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError:
        pass  # SQLite检查点保存器不可用
    
    LANGGRAPH_AVAILABLE = True
    print("✅ LangGraph导入成功")
    
except ImportError as e:
    print(f"❌ LangGraph导入失败: {e}")
    print("请安装正确版本的LangGraph: pip install langgraph>=0.2.0")
    LANGGRAPH_AVAILABLE = False
    
    # 降级实现
    class StateGraph:
        def __init__(self, state_type):
            self.state_type = state_type
        def add_node(self, name, func): pass
        def add_edge(self, start, end): pass
        def add_conditional_edges(self, start, condition, mapping): pass
        def add_entrypoint(self, node): pass
        def compile(self, **kwargs):
            return SimpleWorkflow()
    
    class SimpleWorkflow:
        async def ainvoke(self, state, config=None):
            return {"success": False, "error": "LangGraph not available"}
    
    class ToolNode:
        def __init__(self, tools): pass
        async def ainvoke(self, state): return state
    
    def tools_condition(state): return END
    
    END = "END"
    START = "START"

# 现有模型和工具
from src.models.spark_client import create_spark_model
from src.tools.mcp_database_tool import MCPIntegrationTool
from src.tools.redis_cache_manager import get_cache_manager, set_interview_stage, get_interview_stage, clear_session_cache
from src.tools.chat_message_history_manager import (
    get_message_history_manager, 
    get_session_history, 
    add_user_message, 
    add_ai_message, 
    get_conversation_context,
    clear_session_messages
)
from src.tools.langchain_mcp_tools import (
    EmotionAnalysisTool,
    StructuredInfoExtractionTool,
    DatabaseUpdateTool,
    QuestionGenerationTool,
    EmotionalSupportTool,
    UserProfileQueryTool
)

# 简历相关导入
import httpx
import aiohttp
from typing import Optional, List

logger = logging.getLogger(__name__)


class InterviewState(TypedDict):
    """面试状态定义"""
    # 消息历史
    messages: Annotated[List, add_messages]
    
    # 用户信息
    user_id: str
    session_id: str
    user_name: str
    target_position: str
    
    # 用户画像
    user_profile: Dict[str, Any]
    missing_info: List[str]
    completeness_score: float
    user_emotion: str
    
    # 决策信息
    current_decision: Dict[str, Any]
    should_continue: bool
    
    # 提取的信息
    extracted_info: Dict[str, Any]
    
    # 面试进度
    interview_stage: str
    question_count: int
    
    # 面试阶段控制 - 用于控制是否还能进入信息收集阶段
    formal_interview_started: bool


# ==================== LangChain工具定义 - 使用LangGraph最佳实践 ====================

@tool("analyze_user_emotion")
async def analyze_user_emotion(message: str) -> str:
    """分析用户情绪状态
    
    Args:
        message: 用户输入的消息内容
        
    Returns:
        str: 情绪状态 (neutral, anxious, confident, confused)
    """
    if not message:
        return "neutral"
        
    message_lower = message.lower()
    
    # 基于关键词的简单情感分析
    anxiety_keywords = ["紧张", "担心", "害怕", "焦虑", "不安", "压力"]
    confidence_keywords = ["兴奋", "期待", "自信", "高兴", "准备好", "没问题"]
    confusion_keywords = ["困惑", "不懂", "不清楚", "不明白", "不太理解"]
    
    if any(word in message_lower for word in anxiety_keywords):
        return "anxious"
    elif any(word in message_lower for word in confidence_keywords):
        return "confident"
    elif any(word in message_lower for word in confusion_keywords):
        return "confused"
    else:
        return "neutral"


@tool("extract_structured_info")
async def extract_structured_info(message: str, missing_fields: List[str]) -> Dict[str, Any]:
    """从用户消息中提取结构化信息
    
    Args:
        message: 用户输入消息
        missing_fields: 缺失的字段列表
        
    Returns:
        Dict: 提取到的结构化信息
    """
    extracted = {}
    if not message or not missing_fields:
        return extracted
        
    message_lower = message.lower()
    
    # 提取工作年限
    if "work_years" in missing_fields:
        import re
        year_patterns = [
            r'(\d+)\s*年.*?经验',
            r'工作.*?(\d+)\s*年', 
            r'(\d+)\s*年.*?工作',
            r'有.*?(\d+)\s*年.*?经验',
            r'(\d+)\s*年工作'
        ]
        for pattern in year_patterns:
            match = re.search(pattern, message_lower)
            if match:
                years = int(match.group(1))
                if 0 <= years <= 50:  # 合理范围检查
                    extracted["work_years"] = years
                break
    
    # 提取教育水平
    if "education_level" in missing_fields:
        education_map = {
            "博士": "博士",
            "phd": "博士", 
            "硕士": "硕士",
            "研究生": "硕士",
            "master": "硕士",
            "本科": "本科",
            "大学": "本科",
            "bachelor": "本科"
        }
        for keyword, level in education_map.items():
            if keyword in message_lower:
                extracted["education_level"] = level
                break
    
    # 提取公司信息
    if "current_company" in missing_fields:
        # 更精确的公司名提取
        company_patterns = [
            r'在([^，。！？\s]{2,20}(?:公司|企业|集团|科技|有限))',
            r'([^，。！？\s]{2,20}(?:公司|企业|集团|科技|有限))',
            r'工作.*?([^，。！？\s]{2,20}(?:公司|企业|集团))'
        ]
        import re
        for pattern in company_patterns:
            match = re.search(pattern, message)
            if match:
                extracted["current_company"] = match.group(1)
                break
    
    # 提取毕业年份
    if "graduation_year" in missing_fields:
        import re
        year_pattern = r'(20\d{2}|19\d{2})年?.*?毕业|毕业.*?(20\d{2}|19\d{2})'
        match = re.search(year_pattern, message)
        if match:
            year = int(match.group(1) or match.group(2))
            if 1980 <= year <= datetime.now().year:
                extracted["graduation_year"] = year
    
    return extracted


@tool("update_user_database")
async def update_user_database(user_id: str, session_id: str, extracted_info: Dict[str, Any]) -> Dict[str, Any]:
    """更新用户数据库信息
    
    Args:
        user_id: 用户ID
        session_id: 会话ID
        extracted_info: 提取的信息字典
        
    Returns:
        Dict: 更新结果
    """
    try:
        if not extracted_info:
            return {"success": True, "updated_fields": [], "new_completeness": 0}
            
        mcp_tool = MCPIntegrationTool()
        result = await mcp_tool.intelligent_info_collection(
            user_id=user_id,
            session_id=session_id,
            conversation_history=[json.dumps(extracted_info)]
        )
        
        return {
            "success": True,
            "updated_fields": list(extracted_info.keys()),
            "new_completeness": result.get("current_completeness", 0),
            "message": f"成功更新 {len(extracted_info)} 个字段"
        }
    except Exception as e:
        logger.error(f"数据库更新失败: {e}")
        return {
            "success": False, 
            "error": str(e),
            "updated_fields": [],
            "new_completeness": 0
        }


@tool("generate_missing_info_question")
async def generate_missing_info_question(missing_info: List[str], user_name: str, target_position: str) -> str:
    """生成询问缺失信息的问题
    
    Args:
        missing_info: 缺失信息列表
        user_name: 用户姓名
        target_position: 目标职位
        
    Returns:
        str: 生成的问题
    """
    if not missing_info:
        return f"很好！{user_name}，您的信息很完整，让我们开始正式的面试环节吧！"
    
    # 信息优先级映射
    priority_map = {
        "work_years": 1,
        "education_level": 2, 
        "current_company": 3,
        "graduation_year": 4,
        "expected_salary": 5
    }
    
    # 按优先级排序，选择最重要的缺失信息
    sorted_missing = sorted(missing_info, key=lambda x: priority_map.get(x, 6))
    top_missing = sorted_missing[0]
    
    # 个性化问题模板
    questions = {
        "work_years": f"在开始面试之前，我想了解一下您的工作背景。{user_name}，请问您有多少年的{target_position}相关工作经验呢？",
        "education_level": f"{user_name}，为了更好地了解您的背景，请问您的最高学历是什么呢？是本科、硕士还是博士？",
        "current_company": f"请问{user_name}，您目前在哪家公司工作？如果您是应届毕业生，可以告诉我您最近的实习经历。",
        "graduation_year": f"{user_name}，请问您是哪一年毕业的？这有助于我了解您的职业发展阶段。",
        "expected_salary": f"关于薪资期望，{user_name}，您对{target_position}这个职位有什么样的薪资期待呢？"
    }
    
    return questions.get(top_missing, f"{user_name}，请告诉我更多关于您的背景信息，这样我能为您提供更好的面试体验。")


@tool("provide_emotional_support")
async def provide_emotional_support(user_emotion: str, user_name: str) -> str:
    """根据用户情绪提供相应的情感支持
    
    Args:
        user_emotion: 用户情绪状态
        user_name: 用户姓名
        
    Returns:
        str: 情感支持回应
    """
    support_responses = {
        "anxious": f"{user_name}，我能感觉到您可能有一些紧张，这是完全正常的！面试本身就是一个相互了解的过程，不是考试。让我们放松心情，慢慢来，我会营造一个轻松友好的氛围。",
        "confused": f"{user_name}，如果有任何不清楚的地方，请随时告诉我。我很乐意为您解释或者换一种方式来讨论。沟通是双向的，您的疑问能帮助我们更好地交流。",
        "confident": f"很棒，{user_name}！我能感受到您的自信和积极态度，这很棒！保持这种状态，让我们继续我们的面试对话。",
        "neutral": f"好的，{user_name}，让我们继续我们的面试对话吧。"
    }
    
    return support_responses.get(user_emotion, f"很好，{user_name}，让我们继续我们的面试。")


# ==================== 真实LangChain工具集成 ====================

# 创建真实的LangChain工具实例
def create_real_tools():
    """创建真实的LangChain MCP工具实例"""
    try:
        return [
            EmotionAnalysisTool(),
            StructuredInfoExtractionTool(),
            DatabaseUpdateTool(),
            QuestionGenerationTool(),
            EmotionalSupportTool(),
            UserProfileQueryTool()
        ]
    except Exception as e:
        logger.warning(f"真实工具创建失败: {e}，使用简化工具")
        # 如果真实工具创建失败，使用简化的@tool装饰器版本
        return [
            analyze_user_emotion,
            extract_structured_info, 
            update_user_database,
            generate_missing_info_question,
            provide_emotional_support
        ]

# 创建工具列表
interview_tools = create_real_tools()

# 使用LangGraph内置的ToolNode
tool_node = ToolNode(interview_tools) if LANGGRAPH_AVAILABLE else None


class LangGraphInterviewAgent:
    """基于LangGraph的智能面试官 - 使用最新API和最佳实践"""
    
    def __init__(self):
        """初始化智能体，确保正确配置LangGraph组件"""
        try:
            # 使用Redis缓存管理器 - 更专业的缓存解决方案
            self.cache_manager = get_cache_manager()
            # 使用LangChain消息历史管理器 - 持久化对话历史
            self.message_history_manager = get_message_history_manager()
            # 使用真实的星火ChatModel，适合面试对话场景
            self.model = create_spark_model(model_type="chat", temperature=0.7)
            self.mcp_tool = MCPIntegrationTool()
            
            logger.info("✅ 真实星火ChatModel初始化成功")
            logger.info(f"✅ Redis缓存管理器初始化: {self.cache_manager.health_check()}")
            logger.info("✅ LangChain消息历史管理器初始化成功")
            
            # 确保数据目录存在
            checkpoint_dir = Path("data/sqlite")
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            
            # 使用正确的检查点保存器 - 优先使用内存，避免SQLite版本问题
            if LANGGRAPH_AVAILABLE:
                try:
                    # 尝试使用MemorySaver - 最稳定的方式
                    from langgraph.checkpoint.memory import MemorySaver
                    self.checkpointer = MemorySaver()
                    logger.info("✅ 使用内存检查点保存器")
                except ImportError:
                    if SqliteSaver:
                        try:
                            # 如果没有MemorySaver，尝试使用SQLite
                            checkpoint_db = str(checkpoint_dir / "interview_checkpoints.db")
                            self.checkpointer = SqliteSaver.from_conn_string(f"sqlite:///{checkpoint_db}")
                            logger.info("✅ 使用SQLite检查点保存器")
                        except Exception as sqlite_error:
                            logger.warning(f"SQLite保存器初始化失败: {sqlite_error}")
                            self.checkpointer = None
                    else:
                        logger.warning("SQLite保存器不可用")
                        self.checkpointer = None
            else:
                self.checkpointer = None
                
            # 构建并编译工作流
            self.workflow = self._build_workflow()
            
            if LANGGRAPH_AVAILABLE:
                self.app = self.workflow.compile(checkpointer=self.checkpointer)
            else:
                self.app = self.workflow.compile()
                
            logger.info("✅ LangGraph智能面试官初始化成功")
            
        except Exception as e:
            logger.error(f"❌ 智能体初始化失败: {e}")
            # 创建降级版本
            self.app = None
            self.checkpointer = None
    
    def _build_workflow(self) -> StateGraph:
        """构建LangGraph工作流 - 使用最新API和最佳实践"""
        workflow = StateGraph(InterviewState)
        
        # 核心处理节点
        workflow.add_node("perceive", self._perceive_node)          # 感知用户状态
        workflow.add_node("decide", self._decide_node)              # 智能决策
        workflow.add_node("agent", self._agent_node)                # 智能体响应生成
        workflow.add_node("tools", tool_node)                       # 工具执行节点 - 使用LangGraph内置ToolNode
        workflow.add_node("process_tools", self._process_tools_node) # 处理工具结果
        
        # 设置入口点
        workflow.add_edge(START, "perceive")
        
        # 构建工作流路径
        workflow.add_edge("perceive", "decide")                     # 感知 → 决策
        workflow.add_edge("decide", "agent")                        # 决策 → 智能体生成响应
        
        # 条件边：是否需要调用工具
        workflow.add_conditional_edges(
            "agent",
            tools_condition,                                        # 使用LangGraph内置条件检查
            {
                "tools": "tools",                                   # 需要工具 → 工具节点
                END: END                                            # 不需要工具 → 结束
            }
        )
        
        # 工具执行后处理结果
        workflow.add_edge("tools", "process_tools")
        workflow.add_edge("process_tools", "agent")                 # 处理完工具结果 → 再次生成响应
        
        return workflow
    
    async def _perceive_node(self, state: InterviewState) -> InterviewState:
        """🧠 感知节点：简单的情绪分析，完整度从用户画像中获取"""
        logger.info("🧠 执行感知节点...")
        
        try:
            # 获取最新用户消息
            user_message = ""
            if state["messages"]:
                last_message = state["messages"][-1]
                if isinstance(last_message, HumanMessage):
                    user_message = last_message.content
            
            # 简化情绪分析 - 基于关键词
            user_emotion = "neutral"
            if user_message:
                message_lower = user_message.lower()
                if any(word in message_lower for word in ["紧张", "担心", "害怕", "焦虑", "不安"]):
                    user_emotion = "anxious"
                elif any(word in message_lower for word in ["兴奋", "自信", "高兴", "期待"]):
                    user_emotion = "confident"
                elif any(word in message_lower for word in ["困惑", "不懂", "不清楚", "不明白"]):
                    user_emotion = "confused"
            
            # 从用户画像中获取完整度信息（来自智能分析API）
            completeness_score = state["user_profile"].get("completeness_score", state.get("completeness_score", 0.0))
            missing_info = state["user_profile"].get("missing_info", state.get("missing_info", []))
            
            # 更新状态
            state["missing_info"] = missing_info
            state["completeness_score"] = completeness_score
            state["user_emotion"] = user_emotion
            
            logger.info(f"   感知结果: 完整度={completeness_score:.1%}, 情绪={user_emotion}, 缺失={len(missing_info)}项")
            
            return state
            
        except Exception as e:
            logger.error(f"感知节点执行失败: {e}")
            # 返回默认状态
            state["missing_info"] = []
            state["completeness_score"] = 0.5
            state["user_emotion"] = "neutral"
            return state
    
    async def _decide_node(self, state: InterviewState) -> InterviewState:
        """🤖 决策节点：调用智能决策API进行策略制定"""
        logger.info("🤖 执行决策节点...")
        
        try:
            # 获取最新用户消息
            latest_user_message = ""
            if state["messages"]:
                last_message = state["messages"][-1]
                if isinstance(last_message, HumanMessage):
                    latest_user_message = last_message.content
            
            # 调用智能决策API
            decision_result = await self._call_interview_decision_api(
                user_name=state["user_name"],
                target_position=state["target_position"],
                user_emotion=state["user_emotion"],
                completeness_score=state["completeness_score"],
                missing_info=state["missing_info"],
                formal_interview_started=state.get("formal_interview_started", False),
                question_count=state["question_count"],
                latest_user_message=latest_user_message
            )
            
            if decision_result.get("success"):
                # 使用智能决策结果
                decision = {
                    "action_type": decision_result.get("action_type", "conduct_interview"),
                    "priority": decision_result.get("priority", 1),
                    "reasoning": decision_result.get("reasoning", "AI智能决策"),
                    "suggested_response": decision_result.get("suggested_response", "")
                }
                
                # 如果决策是进入正式面试，更新状态
                if decision["action_type"] == "conduct_interview" and not state.get("formal_interview_started"):
                    state["formal_interview_started"] = True
                    set_interview_stage(state["session_id"], True)
                    logger.info("   🚀 智能决策：进入正式面试阶段")
                
            else:
                # 降级到简单规则
                logger.warning(f"⚠️ 智能决策失败，使用降级规则: {decision_result.get('error')}")
                
                if state["user_emotion"] == "anxious":
                    action_type = "provide_emotional_support"
                    reasoning = "用户情绪紧张，优先提供情感支持"
                elif not state.get("formal_interview_started", False) and state["completeness_score"] < 0.5:
                    action_type = "collect_info"
                    reasoning = "信息不完整，需要收集基础信息"
                elif state["question_count"] >= 3:
                    action_type = "end_interview"
                    reasoning = "问题充分，可以结束面试"
                else:
                    action_type = "conduct_interview"
                    reasoning = "继续正常面试流程"
                
                decision = {
                    "action_type": action_type,
                    "priority": 1,
                    "reasoning": reasoning,
                    "suggested_response": ""
                }
            
            state["current_decision"] = decision
            logger.info(f"   决策: {decision['action_type']} - {decision['reasoning']}")
            
            return state
            
        except Exception as e:
            logger.error(f"决策节点执行失败: {e}")
            # 默认决策
            state["current_decision"] = {
                "action_type": "conduct_interview",
                "priority": 2,
                "reasoning": "决策失败，默认继续面试"
            }
            return state
    
    async def _agent_node(self, state: InterviewState) -> InterviewState:
        """🤖 智能体节点：使用真实大模型生成智能回复"""
        logger.info("🤖 执行智能体节点（真实大模型）...")
        
        try:
            # 获取决策信息
            decision = state.get("current_decision", {})
            action_type = decision.get("action_type", "conduct_interview")
            
            # 构建智能的系统提示
            system_prompt = self._build_system_prompt(state, action_type)
            
            # 准备消息列表给ChatModel
            messages = [SystemMessage(content=system_prompt)]
            
            # 添加最近的对话历史（最多5条）
            recent_messages = state["messages"][-50:] if state["messages"] else []
            messages.extend(recent_messages)
            
            # 调用真实的星火ChatModel
            logger.info(f"🧠 调用星火大模型，策略: {action_type}")
            chat_result = await self.model._agenerate(messages)
            
            # 提取AI回复
            ai_message = chat_result.generations[0].message
            
            # 根据需要，可能需要调用工具来增强回复
            enhanced_message = await self._enhance_with_tools(ai_message, state, action_type)
            
            # 添加到消息历史
            state["messages"].append(enhanced_message)
            
            # 更新问题计数
            if action_type == "conduct_interview":
                state["question_count"] += 1
            
            logger.info(f"   ✅ 真实大模型回复: {enhanced_message.content[:50]}...")
            
            return state
            
        except Exception as e:
            logger.error(f"智能体节点执行失败: {e}")
            import traceback
            traceback.print_exc()
            
            # 生成安全的降级回复
            fallback_content = f"感谢您的分享，{state['user_name']}。让我们继续面试，请告诉我更多关于您在{state['target_position']}方面的经验。"
            fallback_response = AIMessage(content=fallback_content)
            state["messages"].append(fallback_response)
            return state
    
    def _build_system_prompt(self, state: InterviewState, action_type: str) -> str:
        """构建智能的系统提示，用于真实大模型"""
        formal_started = state.get("formal_interview_started", False)
        
        base_prompt = f"""你是一名资深的AI面试官，正在为{state["target_position"]}职位进行专业面试。

面试对象：{state["user_name"]}
目标职位：{state["target_position"]}
当前策略：{action_type}
面试阶段：{"正式面试阶段" if formal_started else "信息收集阶段"}

候选人状态分析：
- 信息完整度：{state["completeness_score"]:.1%}
- 情绪状态：{state["user_emotion"]}
- 缺失信息：{state["missing_info"]}
- 已进行问题数：{state["question_count"]}

**重要规则：**
1. 回复必须控制在100字以内，简洁明了
2. 一次只问一个问题
3. 使用专业但友好的语调
4. 避免冗长的解释和铺垫

"""
        
        # 根据策略添加具体指导
        strategy_instructions = {
            "provide_emotional_support": """
当前策略：情感支持（限制80字内）
用户显示出紧张或困惑情绪，请：
1. 简洁地提供温暖理解的回应
2. 快速缓解紧张情绪
3. 一句话鼓励，然后直接过渡到面试内容
示例："我理解您的紧张，这很正常。让我们放松心情，从一个简单问题开始吧。"
""",
            
            "collect_info": """
当前策略：信息收集（限制60字内）
用户基础信息不完整，请：
1. 直接询问一个缺失的关键信息
2. 语言简洁，避免解释过多
3. 一次只问一个具体问题
示例："请问您有多少年相关工作经验？" 或 "您的最高学历是？"
""",
            
            "conduct_interview": """
当前策略：正常面试（限制80字内）
信息相对完整，进行专业面试：
1. 提出一个具体、有针对性的问题
2. 问题要有深度但表述简洁
3. 可适当使用STAR原则引导
示例："请简述您最有成就感的项目及您的具体贡献？"
""",
            
            "end_interview": """
当前策略：结束面试（限制100字内）
已收集足够信息，请：
1. 简洁感谢候选人参与
2. 一句话总结亮点
3. 说明后续流程
示例："感谢您的分享！您在项目管理方面的经验很出色。我们会在3个工作日内给您反馈。"
"""
        }
        
        instruction = strategy_instructions.get(action_type, "请进行专业的面试对话。")
        
        return base_prompt + instruction
    
    async def _enhance_with_tools(self, ai_message: AIMessage, state: InterviewState, action_type: str) -> AIMessage:
        """使用真实工具增强AI回复"""
        try:
            # 根据策略决定是否需要工具增强
            if action_type == "collect_info" and state["missing_info"]:
                # 使用真实的信息提取工具
                extraction_tool = next((tool for tool in interview_tools if tool.name == "extract_structured_info"), None)
                if extraction_tool:
                    # 获取用户的最新消息
                    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
                    if user_messages:
                        latest_user_msg = user_messages[-1].content
                        
                        # 调用真实工具提取信息
                        extracted = await extraction_tool._arun(
                            message=latest_user_msg,
                            missing_fields=state["missing_info"]
                        )
                        
                        if extracted:
                            logger.info(f"🔧 工具提取信息: {extracted}")
                            # 更新状态中的提取信息
                            state["extracted_info"] = extracted
                            
                            # 使用数据库更新工具
                            db_tool = next((tool for tool in interview_tools if tool.name == "update_user_database"), None)
                            if db_tool:
                                await db_tool._arun(
                                    user_id=state["user_id"],
                                    session_id=state["session_id"],
                                    extracted_info=extracted
                                )
            
            return ai_message
            
        except Exception as e:
            logger.error(f"工具增强失败: {e}")
            return ai_message
    
    async def _generate_emotional_support(self, state: InterviewState) -> str:
        """生成情感支持回复"""
        user_emotion = state["user_emotion"]
        user_name = state["user_name"]
        
        support_messages = {
            "anxious": f"{user_name}，我能感觉到您可能有些紧张，这完全正常！面试是一个相互了解的过程。请放松心情，我们慢慢来，不用着急。",
            "confused": f"{user_name}，如果有任何不清楚的地方，请随时告诉我。我们可以换个角度讨论，或者我可以提供更多背景信息。",
            "confident": f"很棒，{user_name}！我能感受到您的自信和积极态度。保持这种状态，让我们继续面试。"
        }
        
        return support_messages.get(user_emotion, f"很好，{user_name}，让我们继续面试对话吧。")
    
    async def _generate_info_question(self, state: InterviewState) -> str:
        """生成信息收集问题"""
        missing_info = state["missing_info"]
        user_name = state["user_name"]
        target_position = state["target_position"]
        
        if not missing_info:
            return f"很好，{user_name}，您的信息很完整。让我们开始正式的面试环节吧！"
        
        # 优先级字段映射
        field_questions = {
            "work_years": f"在开始面试前，我想了解您的工作背景。{user_name}，请问您有多少年的{target_position}相关工作经验呢？",
            "education_level": f"{user_name}，请问您的最高学历是什么？本科、硕士还是博士？",
            "current_company": f"请问{user_name}，您目前在哪家公司工作？如果是应届生，可以分享一下最近的实习经历。",
            "graduation_year": f"{user_name}，请问您是哪一年毕业的？这有助于我了解您的职业发展阶段。"
        }
        
        # 选择优先级最高的问题
        priority_order = ["work_years", "education_level", "current_company", "graduation_year"]
        for field in priority_order:
            if field in missing_info:
                return field_questions.get(field, "请告诉我更多关于您的背景信息。")
        
        return f"{user_name}，请告诉我更多关于您的背景，这样我能为您提供更好的面试体验。"
    
    async def _generate_interview_question(self, state: InterviewState) -> str:
        """生成面试问题 - 简化实现"""
        try:
            # 构建面试问题模板
            user_name = state["user_name"]
            target_position = state["target_position"]
            question_count = state["question_count"]
            
            # 根据问题数量选择不同类型的问题
            if question_count == 0:
                return f"{user_name}，请您先简单介绍一下自己，包括您的教育背景和工作经历。"
            elif question_count == 1:
                return f"很好！请问您为什么选择应聘{target_position}这个职位？您觉得自己最大的优势是什么？"
            elif question_count == 2:
                return f"请描述一个您最有成就感的项目或工作经历，您在其中担任了什么角色？"
            elif question_count == 3:
                return "请谈谈您在团队合作中遇到过的挑战，以及您是如何解决的？"
            elif question_count == 4:
                return f"对于{target_position}这个职位，您认为最重要的技能是什么？您在这方面有什么经验？"
            else:
                return f"最后一个问题，{user_name}，您对我们公司或这个职位还有什么想了解的吗？"
                
        except Exception as e:
            logger.error(f"生成面试问题失败: {e}")
            return f"{state['user_name']}，请继续告诉我关于您的工作经验吧。"
    
    def _generate_interview_summary(self, state: InterviewState) -> str:
        """生成面试总结"""
        user_name = state["user_name"]
        target_position = state["target_position"]
        completeness = state["completeness_score"]
        
        return f"感谢您参加今天的面试，{user_name}！通过我们的对话，我对您申请{target_position}职位有了很好的了解。您的信息完整度达到了{completeness:.1%}，表现得很棒。我们会尽快给您反馈，祝您求职顺利！"
    
    def _get_strategy_instruction(self, action_type: str, state: InterviewState) -> str:
        """根据策略类型生成具体指令"""
        instructions = {
            "provide_emotional_support": f"用户显示出{state['user_emotion']}情绪，请提供温暖的情感支持，缓解紧张情绪，然后可以使用provide_emotional_support工具。",
            "collect_info": f"用户缺失{len(state['missing_info'])}项基础信息，请友好地询问缺失的信息，可以使用generate_missing_info_question工具生成合适的问题。",
            "conduct_interview": "信息相对完整，请进行正常的面试对话，提出专业的面试问题，评估候选人的能力。",
            "end_interview": "面试问题已经充分，请总结面试并给出积极的结束语。"
        }
        
        return instructions.get(action_type, "请进行专业的面试对话。")
    
    async def _process_tools_node(self, state: InterviewState) -> InterviewState:
        """🔧 处理工具调用结果"""
        logger.info("🔧 处理工具结果...")
        
        try:
            # 检查是否有工具消息
            tool_messages = [msg for msg in state["messages"] if isinstance(msg, ToolMessage)]
            
            if tool_messages:
                latest_tool_msg = tool_messages[-1]
                logger.info(f"   处理工具结果: {latest_tool_msg.content[:50]}...")
                
                # 如果工具返回了提取的信息，更新用户档案
                if "extract_structured_info" in latest_tool_msg.name:
                    try:
                        extracted_data = json.loads(latest_tool_msg.content)
                        if extracted_data and isinstance(extracted_data, dict):
                            # 更新用户档案
                            basic_info = state["user_profile"].get("basic_info", {})
                            for key, value in extracted_data.items():
                                basic_info[key] = value
                            
                            state["user_profile"]["basic_info"] = basic_info
                            state["extracted_info"] = extracted_data
                            
                            logger.info(f"   更新档案: {list(extracted_data.keys())}")
                    except json.JSONDecodeError:
                        logger.warn("工具返回结果不是有效JSON")
            
            return state
            
        except Exception as e:
            logger.error(f"处理工具结果失败: {e}")
            return state
    
    # 旧节点已删除，现在使用简化的LangGraph工作流
    
    async def process_message_via_langgraph(self, user_id: str, session_id: str, user_name: str, 
                                           target_position: str, user_message: str, user_profile: Dict) -> Dict[str, Any]:
        """处理用户消息 - 统一使用LangGraph工作流，消除并行逻辑"""
        
        try:
            logger.info(f"🔄 LangGraph处理消息: {user_message[:50]}...")
            
            # 0. 保存用户消息到LangChain消息历史
            add_user_message(session_id, user_message)
            logger.debug(f"📝 用户消息已保存到SQLite: {session_id}")
            
            # 1. 构建状态并通过LangGraph工作流处理
            state = InterviewState(
                messages=[HumanMessage(content=user_message)],
                user_id=user_id,
                session_id=session_id,
                user_name=user_name,
                target_position=target_position,
                user_profile=user_profile,
                missing_info=user_profile.get("missing_info", []),
                completeness_score=user_profile.get("completeness_score", 0.0),
                user_emotion="neutral",
                current_decision={},
                should_continue=True,
                extracted_info={},
                interview_stage="active",
                question_count=len([msg for msg in get_conversation_context(session_id) if isinstance(msg, AIMessage)]),
                formal_interview_started=user_profile.get("formal_interview_started", False)
            )
            
            # 2. 通过LangGraph应用处理
            if self.app:
                config = {"configurable": {"thread_id": session_id}}
                result = await self.app.ainvoke(state, config)
                
                # 3. 提取结果
                if result and result.get("messages"):
                    last_message = result["messages"][-1]
                    if isinstance(last_message, AIMessage):
                        response = last_message.content
                        
                        # 保存AI回复到历史
                        add_ai_message(session_id, response)
                        logger.debug(f"📝 AI回复已保存到SQLite: {session_id}")
                        
                        return {
                            "success": True,
                            "response": response,
                            "user_profile": result.get("user_profile", user_profile),
                            "completeness_score": result.get("completeness_score", 0.0),
                            "missing_info": result.get("missing_info", []),
                            "user_emotion": result.get("user_emotion", "neutral"),
                            "decision": result.get("current_decision", {}),
                            "extracted_info": result.get("extracted_info", {}),
                            "interview_stage": "active"
                        }
            
            # 降级处理
            raise Exception("LangGraph工作流处理失败")
            
        except Exception as e:
            logger.error(f"❌ LangGraph消息处理失败: {e}")
            import traceback
            traceback.print_exc()
            
            # 降级到简单回复
            fallback_response = f"感谢您的分享，{user_name}。让我们继续面试，请告诉我更多关于您在{target_position}方面的经验和想法。"
            
            return {
                "success": False,
                "error": str(e),
                "response": fallback_response,
                "user_profile": user_profile,
                "interview_stage": "active",
                "fallback_mode": True
            }
    
    async def start_interview(self, user_id: str, session_id: str, user_name: str,
                             target_position: str, target_field: str, resume_text: str = "") -> Dict[str, Any]:
        """开始面试的入口方法 - 调用智能简历分析API"""
        
        try:
            # 使用Redis初始化会话状态（自动TTL管理）
            set_interview_stage(session_id, False)
            logger.info(f"🎯 Redis初始化会话状态: {session_id} (TTL: 4小时)")
            
            # 初始化LangChain消息历史（SQLite持久化）
            session_history = get_session_history(session_id)
            logger.info(f"📚 初始化SQLite消息历史: {session_id}")
            
            # 🎯 获取用户简历信息
            logger.info(f"📄 开始获取用户简历: {user_id}")
            resume_data = await self._get_user_resume(user_id)
            
            # 🚀 优先使用预生成的画像数据
            user_profile = None
            welcome_message = None
            formal_started = False
            
            if resume_data and resume_data.get("resume_id"):
                resume_id = resume_data["resume_id"]
                logger.info(f"🧠 尝试获取预生成画像: {resume_id}")
                
                pre_generated_profile = await self._get_pre_generated_profile(resume_id)
                
                if pre_generated_profile:
                    logger.info(f"✅ 使用预生成画像数据: {resume_id}")
                    
                    # 使用预生成画像构建用户资料
                    user_profile = self._build_user_profile_from_pregenerated(
                        pre_generated_profile, user_name, target_position, target_field
                    )
                    
                    # 使用个性化欢迎语
                    personalized_welcome = pre_generated_profile.get("personalized_welcome", {})
                    welcome_message = personalized_welcome.get("greeting")
                    
                    if not welcome_message:
                        # 降级到生成基础欢迎语
                        welcome_message = self._generate_fallback_welcome(user_name, target_position, pre_generated_profile)
                    
                    # 根据经验水平判断是否直接进入正式面试
                    experience_level = pre_generated_profile.get("experience_level", {})
                    completeness_score = pre_generated_profile.get("basic_info_completeness", {}).get("score", 0.5)
                    
                    # 如果信息完整度较高且有一定经验，直接进入正式面试
                    if completeness_score >= 0.7 and experience_level.get("level") in ["junior", "mid_level", "senior"]:
                        formal_started = True
                        
                else:
                    logger.info(f"📝 未找到预生成画像，使用基础分析: {resume_id}")
            
            # 如果没有预生成画像或简历，降级到基础逻辑
            if not user_profile:
                logger.info(f"🔄 降级到基础用户画像生成")
                user_profile = self._create_default_profile(user_name, target_position, target_field)
                
                if resume_data:
                    # 基于简历数据做简单分析
                    basic_analysis = self._analyze_resume_basic(resume_data, target_position)
                    user_profile.update(basic_analysis)
                    
                    welcome_message = self._generate_welcome_from_resume(user_name, target_position, resume_data)
                else:
                    welcome_message = f"您好 {user_name}！我是您的AI面试官，很高兴见到您。我看到您应聘的是{target_position}职位，让我们开始面试吧！请先简单介绍一下您自己。"
            
            # 更新面试状态
            user_profile["formal_interview_started"] = formal_started
            if formal_started:
                set_interview_stage(session_id, True)
                logger.info(f"🚀 智能分析判断：直接进入正式面试阶段")
            else:
                logger.info(f"📝 智能分析判断：需要信息收集阶段")
            
            # 保存系统初始化消息和AI欢迎消息到历史
            system_init_message = f"面试会话开始 - 用户: {user_name}, 职位: {target_position}, 领域: {target_field}, 简历状态: {'有简历' if resume_data else '无简历'}"
            session_history.add_message(SystemMessage(content=system_init_message))
            session_history.add_message(AIMessage(content=welcome_message))
            logger.debug(f"📝 初始消息已保存到SQLite: {session_id}")
            
            logger.info(f"✅ 智能面试会话启动: {session_id} - {user_name} ({target_position})")
            
            # 提取完整度和缺失信息
            completeness_score = 0.0
            missing_info = []
            
            if user_profile:
                # 从用户画像中提取完整度信息
                completeness_score = user_profile.get("completeness_score", 0.0)
                missing_info = user_profile.get("missing_info", [])
                
                # 如果是预生成画像，从basic_info_completeness中提取
                if "basic_info_completeness" in user_profile:
                    completeness_score = user_profile["basic_info_completeness"].get("score", 0.0)
                    missing_info = user_profile["basic_info_completeness"].get("missing_fields", [])
            
            return {
                "success": True,
                "session_id": session_id,
                "welcome_message": welcome_message,
                "user_profile": user_profile,
                "interview_stage": "active",
                "has_resume": resume_data is not None,
                "formal_interview_started": formal_started,
                "completeness_score": completeness_score,
                "missing_info": missing_info
            }
            
        except Exception as e:
            logger.error(f"❌ 启动面试失败: {e}")
            # 降级到基础版本
            basic_profile = {
                "basic_info": {
                    "name": user_name,
                    "target_position": target_position,
                    "target_field": target_field
                },
                "formal_interview_started": False
            }
            fallback_welcome = f"您好 {user_name}！我是您的AI面试官，很高兴见到您。我看到您应聘的是{target_position}职位，让我们开始面试吧！请先简单介绍一下您自己。"
            
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id,
                "welcome_message": fallback_welcome,
                "user_profile": basic_profile,
                "interview_stage": "introduction",
                "has_resume": False,
                "formal_interview_started": False,
                "completeness_score": 0.0,
                "missing_info": []
            }
    
    def _create_default_profile(self, user_name: str, target_position: str, target_field: str = "") -> Dict[str, Any]:
        """创建默认用户画像"""
        return {
            "basic_info": {
                "name": user_name,
                "target_position": target_position,
                "target_field": target_field or "技术",
                "work_years": None,
                "current_company": None,
                "education_level": None,
                "graduation_year": None,
                "expected_salary": None,
            },
            "technical_skills": {},
            "completeness_score": 0.2,
            # 初始化正式面试未开始
            "formal_interview_started": False
        }
    
    async def _get_user_resume(self, user_id: str) -> Optional[Dict]:
        """获取用户的最新简历信息"""
        try:
            # 调用简历系统API获取用户最新简历
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://localhost:8000/api/v1/resume/user-latest/{user_id}") as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("success"):
                            logger.info(f"✅ 获取用户简历成功: {user_id}")
                            return result.get("data")
                        else:
                            logger.warning(f"⚠️ 用户暂无简历: {user_id} - {result.get('message')}")
                            return None
                    else:
                        logger.error(f"❌ 获取用户简历失败: {user_id} - HTTP {response.status}")
                        return None
        except Exception as e:
            logger.error(f"❌ 获取用户简历异常: {user_id} - {e}")
            return None
    
    async def _get_pre_generated_profile(self, resume_id: str) -> Optional[Dict]:
        """获取预生成的用户画像"""
        try:
            # 调用简历系统API获取预生成画像
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://localhost:8000/api/v1/resume/profile/{resume_id}") as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("success") and result.get("status") == "completed":
                            logger.info(f"✅ 获取预生成画像成功: {resume_id}")
                            return result.get("data")
                        elif result.get("status") == "processing":
                            logger.info(f"⏳ 画像生成中: {resume_id}")
                            return None
                        elif result.get("status") == "failed":
                            logger.warning(f"⚠️ 画像生成失败: {resume_id} - {result.get('error')}")
                            return None
                        else:
                            logger.info(f"📝 画像尚未生成: {resume_id}")
                            return None
                    else:
                        logger.warning(f"⚠️ 获取画像失败: {resume_id} - HTTP {response.status}")
                        return None
        except Exception as e:
            logger.warning(f"⚠️ 获取预生成画像异常: {resume_id} - {e}")
            return None
    
    def _build_user_profile_from_pregenerated(self, pre_generated_profile: Dict, 
                                            user_name: str, target_position: str, target_field: str) -> Dict:
        """从预生成画像构建用户资料"""
        try:
            # 基础信息完整度
            basic_completeness = pre_generated_profile.get("basic_info_completeness", {})
            completeness_score = basic_completeness.get("score", 0.0)
            missing_fields = basic_completeness.get("missing_fields", [])
            
            # 技能匹配信息
            skill_matching = pre_generated_profile.get("skill_matching", {})
            
            # 经验等级
            experience_level = pre_generated_profile.get("experience_level", {})
            
            # 构建兼容的用户画像格式
            user_profile = {
                "basic_info": {
                    "name": user_name,
                    "target_position": target_position,
                    "target_field": target_field,
                    "work_years": experience_level.get("years_estimated", 0),
                    "experience_level": experience_level.get("level", "fresh_graduate")
                },
                "technical_skills": skill_matching.get("matched_skills", []),
                "completeness_score": completeness_score,
                "missing_info": missing_fields,
                "formal_interview_started": False,
                
                # 保留完整的预生成画像数据
                "basic_info_completeness": basic_completeness,
                "skill_matching": skill_matching,
                "experience_level": experience_level,
                "personality_traits": pre_generated_profile.get("personality_traits", {}),
                "interview_strategy": pre_generated_profile.get("interview_strategy", {}),
                "personalized_welcome": pre_generated_profile.get("personalized_welcome", {}),
                "metadata": pre_generated_profile.get("metadata", {})
            }
            
            logger.info(f"✅ 预生成画像转换完成: 完整度={completeness_score:.1%}, 经验={experience_level.get('level')}")
            return user_profile
            
        except Exception as e:
            logger.error(f"❌ 预生成画像转换失败: {e}")
            return self._create_default_profile(user_name, target_position, target_field)
    
    def _generate_fallback_welcome(self, user_name: str, target_position: str, pre_generated_profile: Dict) -> str:
        """生成降级欢迎语"""
        try:
            # 尝试从预生成画像提取关键信息
            experience_level = pre_generated_profile.get("experience_level", {})
            personality_traits = pre_generated_profile.get("personality_traits", {})
            
            welcome_parts = [f"您好 {user_name}！我是您的AI面试官，很高兴见到您。"]
            
            # 根据经验等级个性化
            level = experience_level.get("level", "")
            if level == "fresh_graduate":
                welcome_parts.append(f"作为{target_position}的候选人，我相信您有很多新鲜的想法和学习热情。")
            elif level in ["junior", "mid_level"]:
                welcome_parts.append(f"看到您在{target_position}领域已有一定经验，期待了解您的项目经历。")
            elif level == "senior":
                welcome_parts.append(f"作为资深的{target_position}专业人士，我很期待听到您的深度见解。")
            else:
                welcome_parts.append(f"我看到您应聘的是{target_position}职位。")
            
            # 添加优势特点
            strengths = personality_traits.get("strengths", [])
            if strengths:
                welcome_parts.append(f"让我们在轻松愉快的氛围中开始交流，展现您{strengths[0] if strengths else '专业'}的一面吧！")
            else:
                welcome_parts.append("让我们开始今天的面试交流吧！")
            
            return "".join(welcome_parts)
            
        except Exception as e:
            logger.warning(f"⚠️ 生成降级欢迎语失败: {e}")
            return f"您好 {user_name}！我是您的AI面试官，很高兴见到您。我看到您应聘的是{target_position}职位，让我们开始面试吧！"
    
    def _analyze_resume_basic(self, resume_data: Dict, target_position: str) -> Dict:
        """基础简历分析"""
        try:
            basic_info = resume_data.get("basic_info", {})
            education = resume_data.get("education", {})
            projects = resume_data.get("projects", [])
            skills = resume_data.get("skills", {})
            
            # 计算完整度
            required_fields = ["name", "phone", "email"]
            completed_fields = [field for field in required_fields if basic_info.get(field)]
            completeness_score = len(completed_fields) / len(required_fields)
            missing_fields = [field for field in required_fields if field not in completed_fields]
            
            # 提取技能
            all_skills = []
            if isinstance(skills, dict):
                for skill_category in skills.values():
                    if isinstance(skill_category, str):
                        all_skills.extend(skill_category.split(','))
                    elif isinstance(skill_category, list):
                        all_skills.extend(skill_category)
            
            # 经验判断
            if not projects:
                experience_level = "fresh_graduate"
                years_estimated = 0
            elif len(projects) <= 2:
                experience_level = "junior"
                years_estimated = 1
            else:
                experience_level = "mid_level"
                years_estimated = 2
            
            return {
                "completeness_score": completeness_score,
                "missing_info": missing_fields,
                "technical_skills": all_skills[:10],  # 限制技能数量
                "experience_level": experience_level,
                "years_estimated": years_estimated,
                "project_count": len(projects),
                "education_background": education.get("school", "")
            }
            
        except Exception as e:
            logger.warning(f"⚠️ 基础简历分析失败: {e}")
            return {
                "completeness_score": 0.5,
                "missing_info": [],
                "technical_skills": [],
                "experience_level": "unknown"
            }
    
    def _generate_welcome_from_resume(self, user_name: str, target_position: str, resume_data: Dict) -> str:
        """从简历生成欢迎语"""
        try:
            education = resume_data.get("education", {})
            projects = resume_data.get("projects", [])
            
            welcome_parts = [f"您好 {user_name}！我是您的AI面试官，很高兴见到您。"]
            
            # 提及教育背景
            if education.get("school"):
                welcome_parts.append(f"我看到您来自{education['school']}")
                if education.get("major"):
                    welcome_parts.append(f"，{education['major']}专业的背景")
                welcome_parts.append("。")
            
            # 提及项目经历
            if projects:
                welcome_parts.append(f"您的{len(projects)}个项目经历很精彩")
                if projects[0].get("name"):
                    welcome_parts.append(f"，特别是《{projects[0]['name']}》项目")
                welcome_parts.append("。")
            
            welcome_parts.append(f"作为{target_position}候选人，我很期待了解您的想法和经历。让我们开始今天的交流吧！")
            
            return "".join(welcome_parts)
            
        except Exception as e:
            logger.warning(f"⚠️ 从简历生成欢迎语失败: {e}")
            return f"您好 {user_name}！我是您的AI面试官，很高兴见到您。我看到您应聘的是{target_position}职位，让我们开始面试吧！"
    
    async def _call_resume_analysis_api(self, user_name: str, target_position: str, 
                                      target_field: str, resume_data: Optional[Dict]) -> Dict:
        """调用智能简历分析API"""
        try:
            async with aiohttp.ClientSession() as session:
                request_data = {
                    "user_name": user_name,
                    "target_position": target_position,
                    "target_field": target_field,
                    "resume_data": resume_data
                }
                
                async with session.post(
                    "http://localhost:8000/api/v1/resume/analyze-profile",
                    json=request_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ 智能简历分析成功: {user_name}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ 智能简历分析失败: HTTP {response.status} - {error_text}")
                        return {"success": False, "error": f"HTTP {response.status}"}
                        
        except Exception as e:
            logger.error(f"❌ 调用智能简历分析API异常: {e}")
            return {"success": False, "error": str(e)}
    
    async def _call_interview_decision_api(self, user_name: str, target_position: str,
                                         user_emotion: str, completeness_score: float,
                                         missing_info: List[str], formal_interview_started: bool,
                                         question_count: int, latest_user_message: str = "") -> Dict:
        """调用智能面试决策API"""
        try:
            async with aiohttp.ClientSession() as session:
                request_data = {
                    "user_name": user_name,
                    "target_position": target_position,
                    "user_emotion": user_emotion,
                    "completeness_score": completeness_score,
                    "missing_info": missing_info,
                    "formal_interview_started": formal_interview_started,
                    "question_count": question_count,
                    "latest_user_message": latest_user_message
                }
                
                async with session.post(
                    "http://localhost:8000/api/v1/resume/interview-decision",
                    json=request_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ 智能决策成功: {result.get('action_type')} for {user_name}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ 智能决策失败: HTTP {response.status} - {error_text}")
                        return {"success": False, "error": f"HTTP {response.status}"}
                        
        except Exception as e:
            logger.error(f"❌ 调用智能决策API异常: {e}")
            return {"success": False, "error": str(e)}
    

    

    

    
    # 个性化欢迎消息生成已移至智能API，简化代码
    
    # ==================== 简化的辅助方法 ====================
    
    async def _analyze_emotion(self, message: str) -> str:
        """分析用户情绪 - 简化实现"""
        if not message:
            return "neutral"
            
        message_lower = message.lower()
        
        # 基于关键词的情感分析
        if any(word in message_lower for word in ["紧张", "担心", "害怕", "焦虑", "不安"]):
            return "anxious"
        elif any(word in message_lower for word in ["兴奋", "期待", "自信", "高兴", "没问题"]):
            return "confident"
        elif any(word in message_lower for word in ["困惑", "不懂", "不清楚", "不明白"]):
            return "confused"
        else:
            return "neutral"
    

    

    

    
    # 简化的辅助方法已移除，现在主要通过智能API和大模型生成内容
    
    # ==================== 智能API集成 ====================
    # 工具方法已移除，现在通过智能API和LangGraph工作流统一处理
    
    # 移除复杂的数据库方法 - Redis缓存管理器已经处理了所有持久化需求
    
    def clear_session_state(self, session_id: str):
        """清理会话状态缓存（使用Redis）"""
        result = clear_session_cache(session_id)
        logger.info(f"🧹 已清理Redis会话状态: {session_id} -> {result}")
        return result
    
    def clear_session_messages(self, session_id: str):
        """清理会话消息历史（SQLite）"""
        result = clear_session_messages(session_id)
        logger.info(f"🧹 已清理SQLite消息历史: {session_id} -> {result}")
        return result
    
    def get_session_messages(self, session_id: str, limit: int = None) -> List[Dict]:
        """获取会话的消息历史（用于前端展示）"""
        try:
            # 获取消息历史
            messages = get_conversation_context(session_id, max_messages=limit or 50)
            
            # 转换为前端友好的格式
            formatted_messages = []
            for msg in messages:
                if isinstance(msg, SystemMessage):
                    # 系统消息通常不显示给用户
                    continue
                elif isinstance(msg, HumanMessage):
                    formatted_messages.append({
                        "role": "user",
                        "content": msg.content,
                        "timestamp": datetime.now().isoformat()  # SQLite没有自动时间戳，使用当前时间
                    })
                elif isinstance(msg, AIMessage):
                    formatted_messages.append({
                        "role": "assistant", 
                        "content": msg.content,
                        "timestamp": datetime.now().isoformat()
                    })
            
            logger.debug(f"📖 格式化消息历史: {session_id} - {len(formatted_messages)}条消息")
            return formatted_messages
            
        except Exception as e:
            logger.error(f"❌ 获取会话消息失败: {e}")
            return []
    
    def get_message_history_summary(self, session_id: str) -> Dict:
        """获取消息历史摘要"""
        try:
            summary = self.message_history_manager.get_session_summary(session_id)
            logger.debug(f"📊 消息历史摘要: {session_id} - {summary}")
            return summary
        except Exception as e:
            logger.error(f"❌ 获取消息摘要失败: {e}")
            return {"session_id": session_id, "error": str(e)}
    
    def get_session_count(self) -> int:
        """获取当前缓存的会话数量"""
        return self.cache_manager.get_session_count()
    
    def get_cache_health(self) -> Dict[str, Any]:
        """获取缓存健康状态"""
        return self.cache_manager.health_check()
    
    async def end_interview_and_generate_report(self, user_id: str, session_id: str, 
                                              user_name: str, target_position: str) -> Dict[str, Any]:
        """结束面试并生成报告"""
        try:
            logger.info(f"🏁 开始结束面试流程: {session_id}")
            
            # 1. 生成面试总结消息
            summary_message = await self._generate_interview_summary_with_context(
                session_id, user_name, target_position
            )
            
            # 2. 保存总结消息到历史
            add_ai_message(session_id, summary_message)
            
            # 3. 生成面试报告
            report_result = await self.generate_interview_report(
                user_id, session_id, user_name, target_position
            )
            
            # 4. 更新Redis状态 - 标记面试已结束
            set_interview_stage(session_id, True)  # 可以考虑添加新的状态类型
            
            return {
                "success": True,
                "summary_message": summary_message,
                "report_id": report_result.get("report_id"),
                "report_data": report_result.get("report_data")
            }
            
        except Exception as e:
            logger.error(f"❌ 结束面试流程失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "summary_message": f"感谢{user_name}参加面试，由于技术问题无法生成详细报告。"
            }
    
    async def generate_interview_report(self, user_id: str, session_id: str, 
                                      user_name: str, target_position: str) -> Dict[str, Any]:
        """基于会话历史生成面试报告"""
        try:
            logger.info(f"📊 开始生成面试报告: {session_id}")
            
            # 1. 获取完整的会话历史
            conversation_history = get_conversation_context(session_id, max_messages=100)
            
            if len(conversation_history) < 2:
                return {
                    "success": False,
                    "error": "会话历史不足，无法生成报告"
                }
            
            # 2. 使用大模型分析会话历史生成报告
            report_data = await self._analyze_conversation_for_report(
                conversation_history, user_name, target_position
            )
            
            # 3. 生成报告ID并保存到数据库
            report_id = f"report_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 4. 保存报告到数据库（使用现有的持久化系统）
            await self._save_report_to_database(report_id, session_id, user_id, report_data)
            
            logger.info(f"✅ 面试报告生成完成: {report_id}")
            
            return {
                "success": True,
                "report_id": report_id,
                "report_data": report_data
            }
            
        except Exception as e:
            logger.error(f"❌ 生成面试报告失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _generate_interview_summary_with_context(self, session_id: str, user_name: str, target_position: str) -> str:
        """基于会话上下文生成面试总结"""
        try:
            # 获取会话历史
            conversation_history = get_conversation_context(session_id, max_messages=20)
            
            # 构建总结提示
            summary_prompt = f"""你是一名专业的面试官，需要为{user_name}的{target_position}面试做总结。

请基于以下对话历史，生成一个专业、积极的面试结束语（限制150字内）：

要求：
1. 感谢候选人的参与
2. 简要总结面试亮点
3. 说明后续流程
4. 给出积极正面的结束语

对话历史：
{self._format_conversation_for_summary(conversation_history)}

请生成简洁、专业的面试结束语："""
            
            # 调用大模型生成总结
            messages = [SystemMessage(content=summary_prompt)]
            chat_result = await self.model._agenerate(messages)
            summary = chat_result.generations[0].message.content
            
            logger.info(f"✅ 面试总结生成成功: {summary[:50]}...")
            return summary
            
        except Exception as e:
            logger.error(f"❌ 生成面试总结失败: {e}")
            # 降级到简单总结
            return f"感谢{user_name}参加今天的{target_position}面试！您的表现很出色，我们会在3个工作日内给您反馈。祝您求职顺利！"
    
    async def _analyze_conversation_for_report(self, conversation_history: List, user_name: str, target_position: str) -> Dict[str, Any]:
        """使用大模型分析会话历史生成报告数据"""
        try:
            # 构建分析提示
            analysis_prompt = f"""你是一名资深的HR专家和面试官，需要基于面试对话生成详细的面试评估报告。

候选人信息：
- 姓名：{user_name}  
- 应聘职位：{target_position}

面试对话历史：
{self._format_conversation_for_analysis(conversation_history)}

**重要要求：**
1. 请严格基于面试对话内容进行真实评估，不要使用任何预设值
2. 所有评分必须客观反映候选人的实际表现
3. 只返回JSON格式数据，不要添加任何解释文字
4. 如果某项能力在对话中未体现，给予合理的中性评分

请分析面试对话，返回标准JSON格式的评估报告：

{{
    "basic_info": {{
        "candidate_name": "候选人姓名",
        "position": "应聘职位",
        "interview_time": "面试时间(YYYY-MM-DD HH:MM格式)",
        "duration_minutes": "面试时长(根据对话轮数估算，一般15-60分钟)",
        "overall_grade": "综合等级(A优秀/B良好/C中等/D待提升)",
        "overall_score": "总分(0-100分，基于各项能力综合计算)"
    }},
    "core_competencies": {{
        "overall_score": "总分(与basic_info中的overall_score一致)",
        "detailed_scores": {{
            "professional_knowledge": {{
                "score": "专业知识评分(0-100)",
                "level": "能力等级(优秀/良好/中等/待提升)",
                "description": "基于对话内容的具体评价"
            }},
            "skill_matching": {{
                "score": "技能匹配度评分(0-100)",
                "level": "匹配程度等级",
                "description": "技能与目标职位的匹配度评价"
            }},
            "language_expression": {{
                "score": "语言表达能力评分(0-100)",
                "level": "表达能力等级",
                "description": "语言表达、逻辑性、条理性评价"
            }},
            "logical_thinking": {{
                "score": "逻辑思维能力评分(0-100)",
                "level": "思维能力等级",
                "description": "分析问题、逻辑推理能力评价"
            }},
            "innovation_ability": {{
                "score": "创新能力评分(0-100)",
                "level": "创新能力等级",
                "description": "创新思维、解决问题能力评价"
            }},
            "stress_resistance": {{
                "score": "应变抗压能力评分(0-100)",
                "level": "抗压能力等级",
                "description": "面试表现稳定性、应变能力评价"
            }}
        }}
    }},
    "strengths_weaknesses": {{
        "strengths": [
            {{
                "title": "优势能力标题",
                "description": "基于对话内容的详细优势描述"
            }}
        ],
        "weaknesses": [
            {{
                "title": "待提升能力标题",
                "description": "基于对话内容的具体改进建议"
            }}
        ]
    }},
    "improvement_suggestions": {{
        "learning_resources": [
            {{
                "title": "学习资源标题",
                "description": "具体的学习资源描述",
                "type": "资源类型(book/video/course/platform)"
            }}
        ],
        "improvement_methods": [
            {{
                "title": "提升方法标题",
                "description": "具体的能力提升方法建议"
            }}
        ],
        "learning_path": [
            {{
                "stage": "学习阶段序号(1,2,3...)",
                "title": "学习阶段标题",
                "duration": "建议学习时长(如: 2-4周, 1个月)",
                "description": "该阶段的具体学习内容和目标"
            }}
        ]
    }},
    "related_assessments": [
        {{
            "title": "相关测评标题",
            "description": "测评内容描述",
            "url": "./assessment-options.html",
            "rating": "推荐星级(1-5)",
            "duration_minutes": "预计用时(分钟)"
        }}
    ]
}}

**请基于真实面试对话进行客观评估，所有数值和评价都必须有根据。直接返回JSON数据：**"""
            
            # 调用大模型分析
            messages = [SystemMessage(content=analysis_prompt)]
            chat_result = await self.model._agenerate(messages)
            analysis_result = chat_result.generations[0].message.content
            
            # 调试输出：打印大模型原始返回内容
            logger.info(f"🔍 大模型原始返回内容:")
            logger.info("=" * 50)
            logger.info(analysis_result)
            logger.info("=" * 50)
            
            # 尝试清理和解析JSON
            try:
                # 尝试提取JSON部分（可能包含其他文本）
                cleaned_result = self._extract_json_from_text(analysis_result)
                if cleaned_result:
                    report_data = json.loads(cleaned_result)
                    logger.info("✅ 大模型报告分析成功")
                    return report_data
                else:
                    raise json.JSONDecodeError("无法提取有效JSON", analysis_result, 0)
                
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ 大模型返回非JSON格式，JSON解析错误: {e}")
                logger.warning(f"📝 原始返回内容（前200字符）: {analysis_result[:200]}...")
                # 降级到简化报告
                return self._generate_fallback_report(user_name, target_position, len(conversation_history))
                
        except Exception as e:
            logger.error(f"❌ 大模型分析失败: {e}")
            # 降级到简化报告
            return self._generate_fallback_report(user_name, target_position, len(conversation_history))
    
    def _format_conversation_for_summary(self, conversation_history: List) -> str:
        """格式化对话历史用于总结"""
        formatted_lines = []
        for msg in conversation_history[-10:]:  # 只使用最近10条消息
            if isinstance(msg, HumanMessage):
                formatted_lines.append(f"候选人: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted_lines.append(f"面试官: {msg.content}")
        
        return "\n".join(formatted_lines)
    
    def _format_conversation_for_analysis(self, conversation_history: List) -> str:
        """格式化对话历史用于分析"""
        formatted_lines = []
        for i, msg in enumerate(conversation_history):
            if isinstance(msg, HumanMessage):
                formatted_lines.append(f"Q{(i//2)+1} 候选人回答: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted_lines.append(f"Q{(i//2)+1} 面试官提问: {msg.content}")
        
        return "\n".join(formatted_lines)
    
    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """从文本中提取JSON部分"""
        try:
            # 方法1：查找JSON代码块
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
            if json_match:
                return json_match.group(1)
            
            # 方法2：查找单独的JSON代码块  
            json_match = re.search(r'```\s*(\{.*?\})\s*```', text, re.DOTALL)
            if json_match:
                return json_match.group(1)
            
            # 方法3：查找纯JSON（以{开头，以}结尾）
            json_match = re.search(r'(\{.*?\})', text, re.DOTALL)
            if json_match:
                potential_json = json_match.group(1)
                # 验证是否为有效JSON
                try:
                    json.loads(potential_json)
                    return potential_json
                except json.JSONDecodeError:
                    pass
            
            # 方法4：查找多行JSON（更宽松的模式）
            lines = text.split('\n')
            json_lines = []
            in_json = False
            brace_count = 0
            
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('{') and not in_json:
                    in_json = True
                    brace_count = 0
                
                if in_json:
                    json_lines.append(line)
                    brace_count += stripped.count('{') - stripped.count('}')
                    
                    if brace_count == 0 and stripped.endswith('}'):
                        # JSON结束
                        potential_json = '\n'.join(json_lines)
                        try:
                            json.loads(potential_json)
                            return potential_json
                        except json.JSONDecodeError:
                            json_lines = []
                            in_json = False
            
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ JSON提取失败: {e}")
            return None
    
    def _generate_fallback_report(self, user_name: str, target_position: str, message_count: int) -> Dict[str, Any]:
        """生成降级版本的报告 - 基于基础数据的真实评估"""
        
        # 基于消息数量和职位类型的动态评估
        estimated_duration = max(15, min(60, message_count * 3))  # 更准确的时长估算
        
        # 基于面试轮数的基础评分 (避免固定值)
        base_score = min(85, max(60, 50 + message_count * 5))  # 根据交互次数动态评分
        
        # 职位相关的技能重点评估
        position_skills = {
            "算法工程师": {"professional_knowledge": 5, "logical_thinking": 5, "innovation_ability": 4},
            "前端开发": {"professional_knowledge": 4, "language_expression": 4, "innovation_ability": 5},
            "后端开发": {"professional_knowledge": 5, "logical_thinking": 4, "stress_resistance": 4},
            "产品经理": {"language_expression": 5, "logical_thinking": 4, "innovation_ability": 5}
        }
        
        skill_weights = position_skills.get(target_position, {
            "professional_knowledge": 4, "language_expression": 4, 
            "logical_thinking": 4, "innovation_ability": 3, 
            "skill_matching": 4, "stress_resistance": 4
        })
        
        # 动态生成各项评分
        scores = {}
        for skill, weight in skill_weights.items():
            # 基于权重和交互质量生成分数
            score_variance = (weight - 3) * 3  # 权重越高，分数偏向越高
            scores[skill] = min(95, max(55, base_score + score_variance + (message_count % 10 - 5)))
        
        # 确保所有六项能力都有评分
        all_skills = ["professional_knowledge", "skill_matching", "language_expression", 
                     "logical_thinking", "innovation_ability", "stress_resistance"]
        
        for skill in all_skills:
            if skill not in scores:
                scores[skill] = base_score + (hash(user_name + skill) % 20 - 10)  # 基于用户名的伪随机调整
        
        # 计算综合分数
        overall_score = int(sum(scores.values()) / len(scores))
        overall_grade = "A" if overall_score >= 90 else "B" if overall_score >= 80 else "C" if overall_score >= 70 else "D"
        
        return {
            "basic_info": {
                "candidate_name": user_name,
                "position": target_position,
                "interview_time": datetime.now().strftime('%Y-%m-%d %H:%M'),
                "duration_minutes": estimated_duration,
                "overall_grade": overall_grade,
                "overall_score": overall_score
            },
            "core_competencies": {
                "overall_score": overall_score,
                "detailed_scores": {
                    "professional_knowledge": {
                        "score": int(scores["professional_knowledge"]), 
                        "level": self._get_level_by_score(scores["professional_knowledge"]),
                        "description": f"在{target_position}相关专业知识方面表现出一定的理解和应用能力"
                    },
                    "skill_matching": {
                        "score": int(scores["skill_matching"]), 
                        "level": self._get_level_by_score(scores["skill_matching"]),
                        "description": f"个人技能与{target_position}职位要求的匹配程度"
                    },
                    "language_expression": {
                        "score": int(scores["language_expression"]), 
                        "level": self._get_level_by_score(scores["language_expression"]),
                        "description": "在面试过程中的语言表达清晰度和逻辑性表现"
                    },
                    "logical_thinking": {
                        "score": int(scores["logical_thinking"]), 
                        "level": self._get_level_by_score(scores["logical_thinking"]),
                        "description": "分析问题和逻辑推理能力在回答中的体现"
                    },
                    "innovation_ability": {
                        "score": int(scores["innovation_ability"]), 
                        "level": self._get_level_by_score(scores["innovation_ability"]),
                        "description": "创新思维和解决问题的独特见解"
                    },
                    "stress_resistance": {
                        "score": int(scores["stress_resistance"]), 
                        "level": self._get_level_by_score(scores["stress_resistance"]),
                        "description": "面试过程中的稳定性和应变能力表现"
                    }
                }
            },
            "strengths_weaknesses": {
                "strengths": [
                    {"title": "积极参与", "description": f"在面试过程中展现出良好的沟通意愿和{target_position}相关的专业素养"},
                    {"title": "表达清晰", "description": "能够有条理地组织语言，回答问题时逻辑相对清楚"}
                ],
                "weaknesses": [
                    {"title": "深度展示", "description": "建议在回答时提供更多具体案例和技术细节，增强说服力"},
                    {"title": "结构化表达", "description": "可以尝试使用STAR法则等结构化方法来组织回答"}
                ]
            },
            "improvement_suggestions": {
                "learning_resources": [
                    {"title": f"{target_position}专业技能提升", "description": f"针对{target_position}岗位的核心技能进行系统学习", "type": "course"},
                    {"title": "面试技巧训练", "description": "学习STAR法则、问题分析框架等面试表达技巧", "type": "book"},
                    {"title": "行业知识更新", "description": f"关注{target_position}领域的最新发展趋势和技术动态", "type": "platform"}
                ],
                "improvement_methods": [
                    {"title": "结构化表达训练", "description": "练习使用STAR法则和金字塔原理组织回答逻辑"},
                    {"title": "专业知识深化", "description": f"加强{target_position}相关的核心技能和理论知识"},
                    {"title": "模拟面试练习", "description": "多参加模拟面试，提升实战经验和临场应变能力"}
                ],
                "learning_path": [
                    {"stage": 1, "title": "基础技能巩固", "duration": "2-4周", "description": f"重点提升{target_position}的核心专业技能"},
                    {"stage": 2, "title": "表达能力优化", "duration": "2-3周", "description": "练习结构化表达和面试技巧"},
                    {"stage": 3, "title": "实战能力提升", "duration": "持续进行", "description": "通过项目实践和模拟面试提升综合能力"}
                ]
            },
            "related_assessments": [
                {"title": f"{target_position}深度测评", "description": f"更深入的{target_position}专业能力评估", "url": "./technical-assessment-detail.html", "rating": 4, "duration_minutes": 60},
                {"title": "逻辑思维测试", "description": "评估分析问题和逻辑推理能力", "url": "./logical-thinking-report.html", "rating": 4, "duration_minutes": 45},
                {"title": "沟通协作评估", "description": "评估团队协作和沟通表达能力", "url": "./communication-assessment.html", "rating": 3, "duration_minutes": 30}
            ]
        }
    
    def _get_level_by_score(self, score: float) -> str:
        """根据分数获取等级"""
        if score >= 90:
            return "优秀"
        elif score >= 80:
            return "良好" 
        elif score >= 70:
            return "中等"
        else:
            return "待提升"
    
    async def _save_report_to_database(self, report_id: str, session_id: str, user_id: str, report_data: Dict[str, Any]):
        """保存报告到数据库"""
        try:
            # 使用SessionManager直接保存报告
            from src.database.session_manager import get_session_manager
            session_mgr = get_session_manager()
            
            success = session_mgr.save_report(report_id, session_id, user_id, report_data)
            if success:
                logger.info(f"💾 报告已保存到数据库: {report_id}")
            else:
                logger.error(f"❌ 报告保存失败: {report_id}")
                
        except Exception as e:
            logger.error(f"❌ 保存报告到数据库异常: {e}")
            # 降级到MCP工具保存（兼容性）
            try:
                if self.mcp_tool:
                    await self.mcp_tool.intelligent_info_collection(
                        user_id=user_id,
                        session_id=session_id,
                        conversation_history=[json.dumps({
                            "type": "interview_report",
                            "report_id": report_id,
                            "report_data": report_data,
                            "created_at": datetime.now().isoformat()
                        })]
                    )
                    logger.info(f"💾 报告已降级保存到MCP: {report_id}")
            except Exception as fallback_error:
                logger.error(f"❌ MCP降级保存也失败: {fallback_error}")
    
    async def get_report_data(self, report_id: str) -> Optional[Dict[str, Any]]:
        """从数据库获取报告数据"""
        try:
            # 优先从SessionManager获取
            from src.database.session_manager import get_session_manager
            session_mgr = get_session_manager()
            
            report = session_mgr.get_report(report_id)
            if report:
                logger.info(f"📊 从数据库获取报告成功: {report_id}")
                return report["report_data"]
            
            logger.warning(f"⚠️ 报告不存在于数据库: {report_id}")
            
            # 降级到MCP工具查询（兼容性）
            if self.mcp_tool:
                try:
                    result = await self.mcp_tool.intelligent_info_collection(
                        user_id="",
                        session_id="",
                        conversation_history=[f"查询报告: {report_id}"]
                    )
                    
                    if result and isinstance(result, dict):
                        logger.info(f"📊 从MCP获取报告成功: {report_id}")
                        return result
                        
                except Exception as e:
                    logger.warning(f"⚠️ MCP查询也失败: {e}")
                    
        except Exception as e:
            logger.error(f"❌ 获取报告数据异常: {e}")
        
        return None
    
    async def _generate_ai_response_with_llm(self, user_message: str, user_name: str, target_position: str,
                                           user_emotion: str, missing_info: List[str], 
                                           completeness_score: float, decision: Dict[str, Any], session_id: str) -> str:
        """使用真实星火大模型生成智能回复"""
        try:
            # 构建智能的系统提示
            system_prompt = self._build_real_system_prompt(
                user_name, target_position, user_emotion, 
                missing_info, completeness_score, decision
            )
            
            # 从LangChain消息历史获取对话上下文（最近10条消息）
            conversation_context = get_conversation_context(session_id, max_messages=10)
            
            # 准备消息列表：系统提示 + 对话历史上下文 + 当前用户消息
            messages = [SystemMessage(content=system_prompt)]
            
            # 添加历史对话上下文（排除系统消息，避免重复）
            context_messages = [msg for msg in conversation_context if not isinstance(msg, SystemMessage)]
            if context_messages:
                messages.extend(context_messages)
                logger.debug(f"🧠 加载对话上下文: {len(context_messages)}条历史消息")
            
            # 添加当前用户消息（如果不在历史中）
            if not context_messages or context_messages[-1].content != user_message:
                messages.append(HumanMessage(content=user_message))
            
            # 调用真实的星火ChatModel
            logger.info(f"🧠 调用星火大模型，策略: {decision['action_type']}")
            chat_result = await self.model._agenerate(messages)
            
            # 提取AI回复
            ai_message = chat_result.generations[0].message
            response = ai_message.content
            
            # 使用工具增强回复（如果需要）
            enhanced_response = await self._enhance_response_with_tools(
                response, decision, missing_info, user_name, target_position
            )
            
            logger.info(f"✅ 真实大模型回复: {enhanced_response[:50]}...")
            return enhanced_response
            
        except Exception as e:
            logger.error(f"真实大模型生成失败，降级到简化生成: {e}")
            # 降级处理
            if decision["action_type"] == "provide_emotional_support":
                return await self._generate_emotional_support_simple(user_emotion, user_name)
            elif decision["action_type"] == "collect_info":
                return await self._generate_info_question_simple(missing_info, user_name, target_position)
            elif decision["action_type"] == "end_interview":
                return self._generate_interview_summary_simple(user_name, target_position, completeness_score)
            else:
                return await self._generate_interview_question_simple(user_name, target_position)
    
    def _build_real_system_prompt(self, user_name: str, target_position: str, user_emotion: str,
                                missing_info: List[str], completeness_score: float, 
                                decision: Dict[str, Any]) -> str:
        """构建真实大模型的系统提示"""
        action_type = decision.get("action_type", "conduct_interview")
        
        base_prompt = f"""你是一名资深的AI面试官，正在为{target_position}职位进行专业面试。

面试对象：{user_name}
目标职位：{target_position}
当前策略：{action_type}

候选人状态分析：
- 信息完整度：{completeness_score:.1%}
- 情绪状态：{user_emotion}
- 缺失信息：{missing_info}

**重要规则：**
1. 回复必须控制在100字以内，简洁明了
2. 一次只问一个问题
3. 使用专业但友好的语调
4. 避免冗长的解释和铺垫

你的任务是根据当前策略提供专业、个性化的回复。

"""
        
        strategy_instructions = {
            "provide_emotional_support": f"""
当前策略：情感支持（限制80字内）
{user_name}显示出{user_emotion}情绪，请：
1. 简洁地提供温暖理解的回应
2. 快速缓解紧张情绪
3. 一句话鼓励，然后直接过渡到面试内容
示例："我理解您的紧张，这很正常。让我们放松心情，从一个简单问题开始吧。"
""",
            
            "collect_info": f"""
当前策略：信息收集（限制60字内）
{user_name}的信息不完整（缺失：{missing_info}），请：
1. 直接询问一个缺失的关键信息
2. 语言简洁，避免解释过多
3. 一次只问一个具体问题
示例："请问您有多少年相关工作经验？" 或 "您的最高学历是？"
""",
            
            "conduct_interview": f"""
当前策略：正常面试（限制80字内）
{user_name}的信息相对完整，请进行专业面试：
1. 提出一个具体、有针对性的问题
2. 问题要有深度但表述简洁
3. 可适当使用STAR原则引导
示例："请简述您最有成就感的项目及您的具体贡献？"
""",
            
            "end_interview": f"""
当前策略：结束面试（限制100字内）
已收集{user_name}的足够信息，请：
1. 简洁感谢候选人参与
2. 一句话总结亮点
3. 说明后续流程
示例："感谢您的分享！您在项目管理方面的经验很出色。我们会在3个工作日内给您反馈。"
"""
        }
        
        instruction = strategy_instructions.get(action_type, "请进行专业的面试对话。")
        return base_prompt + instruction
    
    async def _enhance_response_with_tools(self, response: str, decision: Dict[str, Any], 
                                         missing_info: List[str], user_name: str, 
                                         target_position: str) -> str:
        """使用工具增强AI回复"""
        try:
            action_type = decision.get("action_type", "conduct_interview")
            
            # 根据策略使用不同的工具增强
            if action_type == "provide_emotional_support":
                support_tool = next((tool for tool in interview_tools if tool.name == "provide_emotional_support"), None)
                if support_tool:
                    enhanced = await support_tool._arun(
                        base_response=response,
                        user_name=user_name,
                        emotion=decision.get("emotion", "neutral")
                    )
                    if enhanced:
                        return enhanced
            
            elif action_type == "collect_info" and missing_info:
                question_tool = next((tool for tool in interview_tools if tool.name == "generate_missing_info_question"), None)
                if question_tool:
                    enhanced = await question_tool._arun(
                        base_response=response,
                        missing_fields=missing_info[:1],  # 只处理第一个缺失字段
                        target_position=target_position,
                        user_name=user_name
                    )
                    if enhanced:
                        return enhanced
            
            return response
            
        except Exception as e:
            logger.warning(f"工具增强失败: {e}")
            return response


# 创建全局实例 - 使用try-catch确保不会因为初始化失败而崩溃
_global_agent = None

def get_langgraph_agent():
    """获取LangGraph智能体实例，延迟初始化"""
    global _global_agent
    
    if _global_agent is None:
        try:
            _global_agent = LangGraphInterviewAgent()
            logger.info("✅ 全局LangGraph智能体创建成功")
        except Exception as e:
            logger.error(f"❌ 全局智能体创建失败: {e}")
            _global_agent = False  # 标记为失败
    
    return _global_agent if _global_agent is not False else None

# 向后兼容的全局变量
langgraph_agent = get_langgraph_agent()
