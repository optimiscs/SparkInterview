"""
LangChain MCP工具包装
将MCP数据库工具包装成LangChain工具，用于LangGraph智能体
"""
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from src.tools.mcp_database_tool import MCPIntegrationTool, MCPDatabaseTool

logger = logging.getLogger(__name__)


# ==================== 输入模型定义 ====================

class EmotionAnalysisInput(BaseModel):
    """情感分析输入"""
    message: str = Field(description="用户消息文本")


class InfoExtractionInput(BaseModel):
    """信息提取输入"""
    message: str = Field(description="用户消息文本")
    missing_fields: List[str] = Field(description="需要提取的缺失字段列表")


class DatabaseUpdateInput(BaseModel):
    """数据库更新输入"""
    user_id: str = Field(description="用户ID")
    session_id: str = Field(description="会话ID")
    extracted_info: Dict[str, Any] = Field(description="提取的信息字典")


class QuestionGenerationInput(BaseModel):
    """问题生成输入"""
    missing_info: List[str] = Field(description="缺失信息列表")
    user_name: str = Field(description="用户姓名")
    target_position: str = Field(description="目标职位")


class EmotionalSupportInput(BaseModel):
    """情感支持输入"""
    user_emotion: str = Field(description="用户情绪状态")
    user_name: str = Field(description="用户姓名")


class ProfileQueryInput(BaseModel):
    """用户画像查询输入"""
    user_id: str = Field(description="用户ID")
    session_id: Optional[str] = Field(default=None, description="会话ID")


# ==================== LangChain工具实现 ====================

class EmotionAnalysisTool(BaseTool):
    """用户情绪分析工具"""
    name: str = "analyze_user_emotion"
    description: str = "分析用户消息中的情绪状态，返回neutral/anxious/confident/confused之一"
    args_schema: type = EmotionAnalysisInput
    
    def _run(self, message: str) -> str:
        """同步执行（备用）"""
        return asyncio.run(self._arun(message))
    
    async def _arun(self, message: str) -> str:
        """分析用户情绪"""
        message_lower = message.lower()
        
        # 紧张焦虑类
        anxious_words = ["紧张", "担心", "害怕", "焦虑", "不安", "忧虑", "压力", "紧张兮兮"]
        if any(word in message_lower for word in anxious_words):
            return "anxious"
        
        # 自信兴奋类
        confident_words = ["兴奋", "期待", "自信", "高兴", "开心", "满意", "骄傲", "有信心"]
        if any(word in message_lower for word in confident_words):
            return "confident"
        
        # 困惑疑惑类
        confused_words = ["困惑", "不懂", "不清楚", "不明白", "疑惑", "迷茫", "不知道"]
        if any(word in message_lower for word in confused_words):
            return "confused"
        
        return "neutral"


class StructuredInfoExtractionTool(BaseTool):
    """结构化信息提取工具"""
    name: str = "extract_structured_info"
    description: str = "从用户消息中提取结构化信息，如工作年限、教育背景、公司信息等"
    args_schema: type = InfoExtractionInput
    
    def _run(self, message: str, missing_fields: List[str]) -> Dict[str, Any]:
        return asyncio.run(self._arun(message, missing_fields))
    
    async def _arun(self, message: str, missing_fields: List[str]) -> Dict[str, Any]:
        """提取结构化信息"""
        extracted = {}
        message_lower = message.lower()
        
        # 工作年限提取
        if "work_years" in missing_fields:
            import re
            year_patterns = [
                r'(\d+)\s*年.*?经验',
                r'工作.*?(\d+)\s*年',
                r'(\d+)\s*年.*?工作',
                r'有.*?(\d+)\s*年.*?经验',
                r'(\d+)\s*年.*?从业',
                r'从事.*?(\d+)\s*年'
            ]
            
            for pattern in year_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    years = int(match.group(1))
                    if 0 <= years <= 50:  # 合理范围检查
                        extracted["work_years"] = years
                        logger.info(f"提取工作年限: {years}年")
                        break
        
        # 教育水平提取
        if "education_level" in missing_fields:
            education_map = {
                "博士": "博士",
                "phd": "博士", 
                "硕士": "硕士",
                "研究生": "硕士",
                "master": "硕士",
                "本科": "本科",
                "大学": "本科",
                "bachelor": "本科",
                "专科": "专科",
                "大专": "专科"
            }
            
            for keyword, level in education_map.items():
                if keyword in message_lower:
                    extracted["education_level"] = level
                    logger.info(f"提取教育水平: {level}")
                    break
        
        # 毕业年份提取
        if "graduation_year" in missing_fields:
            import re
            year_pattern = r'(\d{4})\s*年.*?毕业|毕业.*?(\d{4})\s*年'
            match = re.search(year_pattern, message_lower)
            if match:
                year = int(match.group(1) or match.group(2))
                if 1990 <= year <= 2030:  # 合理年份范围
                    extracted["graduation_year"] = year
                    logger.info(f"提取毕业年份: {year}年")
        
        # 公司信息提取
        if "current_company" in missing_fields:
            company_patterns = [
                r'在(.{2,20}?公司)',
                r'(.{2,20}?公司)工作',
                r'就职.*?(.{2,20}?公司)',
                r'(.{2,20}?科技).*?工作',
                r'(.{2,20}?集团).*?工作',
                r'在(.{2,20}?)实习',
                r'(.{2,20}?)的员工'
            ]
            
            import re
            for pattern in company_patterns:
                match = re.search(pattern, message)
                if match:
                    company = match.group(1).strip()
                    if len(company) >= 2 and not any(word in company for word in ["不", "没", "未"]):
                        extracted["current_company"] = company
                        logger.info(f"提取公司信息: {company}")
                        break
        
        # 期望薪资提取
        if "expected_salary" in missing_fields:
            import re
            salary_patterns = [
                r'期望.*?(\d+).*?k',
                r'薪资.*?(\d+).*?k', 
                r'(\d+).*?k.*?薪资',
                r'月薪.*?(\d+)',
                r'工资.*?(\d+)'
            ]
            
            for pattern in salary_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    salary_num = int(match.group(1))
                    if 3 <= salary_num <= 100:  # 3K-100K的合理范围
                        if 'k' in message_lower:
                            extracted["expected_salary"] = f"{salary_num}K"
                        else:
                            extracted["expected_salary"] = f"{salary_num//1000}K" if salary_num >= 1000 else f"{salary_num}K"
                        logger.info(f"提取期望薪资: {extracted['expected_salary']}")
                        break
        
        return extracted


class DatabaseUpdateTool(BaseTool):
    """数据库更新工具"""
    name: str = "update_user_database"
    description: str = "将提取的用户信息更新到数据库中"
    args_schema: type = DatabaseUpdateInput
    
    def __init__(self):
        super().__init__()
        # 使用object.__setattr__避免Pydantic字段冲突
        object.__setattr__(self, 'mcp_tool', MCPIntegrationTool())
    
    def _run(self, user_id: str, session_id: str, extracted_info: Dict[str, Any]) -> Dict[str, Any]:
        return asyncio.run(self._arun(user_id, session_id, extracted_info))
    
    async def _arun(self, user_id: str, session_id: str, extracted_info: Dict[str, Any]) -> Dict[str, Any]:
        """更新用户数据库"""
        try:
            if not extracted_info:
                return {"success": True, "message": "无信息需要更新"}
            
            # 使用MCP工具更新
            result = await self.mcp_tool.intelligent_info_collection(
                user_id=user_id,
                session_id=session_id, 
                conversation_history=[json.dumps(extracted_info, ensure_ascii=False)]
            )
            
            return {
                "success": result["updated"],
                "updated_fields": list(extracted_info.keys()),
                "new_completeness": result["current_completeness"],
                "missing_fields": result["missing_fields"]
            }
            
        except Exception as e:
            logger.error(f"数据库更新失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class QuestionGenerationTool(BaseTool):
    """缺失信息问题生成工具"""
    name: str = "generate_missing_info_question" 
    description: str = "基于缺失信息生成针对性的面试问题"
    args_schema: type = QuestionGenerationInput
    
    def _run(self, missing_info: List[str], user_name: str, target_position: str) -> str:
        return asyncio.run(self._arun(missing_info, user_name, target_position))
    
    async def _arun(self, missing_info: List[str], user_name: str, target_position: str) -> str:
        """生成询问缺失信息的问题"""
        
        if not missing_info:
            return f"看起来您的信息很完整，{user_name}，让我们开始正式的{target_position}面试吧！"
        
        # 定义问题优先级和对应问题
        question_templates = {
            "work_years": {
                "priority": 1,
                "question": f"在开始面试之前，我想了解一下您的工作背景。请问您有多少年的{target_position}相关工作经验呢？这将帮助我为您提供更合适的面试问题。"
            },
            "education_level": {
                "priority": 2,
                "question": "请问您的最高学历是什么？本科、硕士还是博士？这有助于我了解您的学术背景。"
            },
            "current_company": {
                "priority": 3,
                "question": "请问您目前在哪家公司工作？如果您是应届毕业生，可以告诉我最近的实习经历。"
            },
            "graduation_year": {
                "priority": 4,
                "question": "请问您是哪一年毕业的？这有助于我了解您的职业发展阶段。"
            },
            "expected_salary": {
                "priority": 5,
                "question": f"为了更好地匹配岗位，请问您对{target_position}职位的薪资期望是多少？"
            }
        }
        
        # 按优先级排序，选择最重要的缺失信息
        prioritized_missing = sorted(
            missing_info, 
            key=lambda x: question_templates.get(x, {"priority": 999})["priority"]
        )
        
        top_missing = prioritized_missing[0]
        question = question_templates.get(top_missing, {
            "question": f"请告诉我更多关于您的{top_missing}信息。"
        })["question"]
        
        logger.info(f"生成缺失信息问题，针对字段: {top_missing}")
        return question


class EmotionalSupportTool(BaseTool):
    """情感支持工具"""
    name: str = "provide_emotional_support"
    description: str = "基于用户情绪提供相应的情感支持和鼓励"
    args_schema: type = EmotionalSupportInput
    
    def _run(self, user_emotion: str, user_name: str) -> str:
        return asyncio.run(self._arun(user_emotion, user_name))
    
    async def _arun(self, user_emotion: str, user_name: str) -> str:
        """提供情感支持"""
        
        support_messages = {
            "anxious": f"{user_name}，我能感觉到您可能有一些紧张，这很正常！面试本身就是一个相互了解的过程。请放松心情，深呼吸，我会尽量营造一个轻松的氛围。我们慢慢来，不用着急，您可以的！",
            
            "confused": f"{user_name}，如果有任何不清楚的地方，请随时告诉我。我们可以换一种方式来讨论这个话题，或者我可以提供更多的背景信息来帮助您理解。沟通是双向的，请不要有压力。",
            
            "confident": f"很好，{user_name}！我能感受到您的自信和积极态度，这很棒。保持这种状态，让我们继续进行面试。您的自信会让整个面试过程更加顺畅。",
            
            "neutral": f"很好，{user_name}，您看起来很平静专注。让我们继续我们的面试吧，有任何问题都可以随时告诉我。"
        }
        
        message = support_messages.get(user_emotion, support_messages["neutral"])
        logger.info(f"提供情感支持，针对情绪: {user_emotion}")
        return message


class UserProfileQueryTool(BaseTool):
    """用户画像查询工具"""
    name: str = "query_user_profile"
    description: str = "查询用户的完整画像信息"
    args_schema: type = ProfileQueryInput
    
    def __init__(self):
        super().__init__()
        # 使用object.__setattr__避免Pydantic字段冲突
        object.__setattr__(self, 'db_tool', MCPDatabaseTool())
    
    def _run(self, user_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        return asyncio.run(self._arun(user_id, session_id))
    
    async def _arun(self, user_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """查询用户画像"""
        try:
            profile = await self.db_tool.get_user_profile(user_id, session_id)
            
            if profile:
                return {
                    "success": True,
                    "profile_data": profile["profile_data"],
                    "completeness_score": profile["completeness_score"],
                    "work_years": profile.get("work_years"),
                    "education_level": profile.get("education_level"),
                    "current_company": profile.get("current_company")
                }
            else:
                return {
                    "success": False,
                    "message": "未找到用户画像"
                }
                
        except Exception as e:
            logger.error(f"查询用户画像失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# ==================== 工具集合 ====================

def get_langchain_mcp_tools():
    """获取所有LangChain MCP工具"""
    return [
        EmotionAnalysisTool(),
        StructuredInfoExtractionTool(),
        DatabaseUpdateTool(),
        QuestionGenerationTool(),
        EmotionalSupportTool(),
        UserProfileQueryTool()
    ]


# 创建工具实例（单例模式）
emotion_analysis_tool = EmotionAnalysisTool()
info_extraction_tool = StructuredInfoExtractionTool()
database_update_tool = DatabaseUpdateTool()
question_generation_tool = QuestionGenerationTool()
emotional_support_tool = EmotionalSupportTool()
profile_query_tool = UserProfileQueryTool()

# 工具列表
ALL_LANGCHAIN_MCP_TOOLS = [
    emotion_analysis_tool,
    info_extraction_tool,
    database_update_tool,
    question_generation_tool,
    emotional_support_tool,
    profile_query_tool
]
