"""
面试设置智能体 - "协调员"
负责简历解析、问题筛选等准备工作
"""
import json
import os
import glob
from pathlib import Path
from typing import Dict, Any, List, Optional
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage

from ..models.spark_client import create_spark_model
from ..models.state import InterviewState, InterviewStage, Question, QuestionType
from ..tools.resume_parser import create_resume_parser_tool
from ..tools.vector_search import create_question_bank_manager


class InterviewSetupAgent:
    """面试设置智能体"""
    
    def __init__(self):
        # 使用Star Pro模型 - 高性价比
        self.llm = create_spark_model("pro")
        
        # 工具
        self.resume_parser = create_resume_parser_tool()
        self.question_bank = create_question_bank_manager()
        
        # 创建提示模板
        self.system_prompt = """
你是一位专业的面试协调员，负责为模拟面试做准备工作。你的任务包括：

1. 解析候选人的简历，提取关键信息
2. 根据岗位要求和候选人背景，从题库中筛选合适的面试问题
3. 生成面试计划和问题列表

请始终保持专业、高效的工作态度，确保为候选人提供高质量的模拟面试体验。

可用工具：
- resume_parser: 解析简历文件，提取结构化信息
- vector_search: 从问题库中搜索相关面试题

请根据用户的需求，使用合适的工具完成任务。
"""
        
        self.tools = [self.resume_parser]
    
    def _find_resume_files(self, jianli_dir: str = "data/jianli") -> List[str]:
        """从jianli目录中查找简历文件"""
        
        # 确保目录路径存在
        if not os.path.exists(jianli_dir):
            print(f"⚠️ 简历目录不存在: {jianli_dir}")
            return []
        
        # 支持的简历文件格式
        supported_extensions = ['*.pdf', '*.docx', '*.doc']
        resume_files = []
        
        for ext in supported_extensions:
            pattern = os.path.join(jianli_dir, ext)
            files = glob.glob(pattern)
            resume_files.extend(files)
        
        # 按修改时间排序，最新的在前
        resume_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        if resume_files:
            print(f"📄 在 {jianli_dir} 中找到 {len(resume_files)} 个简历文件:")
            for i, file in enumerate(resume_files, 1):
                file_name = os.path.basename(file)
                file_size = os.path.getsize(file) / 1024  # KB
                print(f"   {i}. {file_name} ({file_size:.1f}KB)")
        else:
            print(f"⚠️ 在 {jianli_dir} 中未找到简历文件")
        
        return resume_files
    
    def _select_resume_file(self, resume_files: List[str]) -> Optional[str]:
        """选择要使用的简历文件（默认选择第一个，即最新的）"""
        
        if not resume_files:
            return None
        
        # 默认选择第一个文件（最新的）
        selected_file = resume_files[0]
        file_name = os.path.basename(selected_file)
        print(f"✅ 自动选择简历文件: {file_name}")
        
        return selected_file
    
    def _parse_resume(self, resume_path: str) -> Dict[str, Any]:
        """解析简历"""
        
        try:
            result_str = self.resume_parser._run(resume_path, "structured")
            result = json.loads(result_str)
            
            if result.get("error"):
                raise Exception(result["message"])
            
            return result
        except Exception as e:
            raise Exception(f"简历解析失败: {str(e)}")
    
    def _select_questions(
        self, 
        field: str, 
        position: str, 
        resume_summary: Dict[str, Any],
        question_count: int = 8
    ) -> List[Question]:
        """根据岗位和简历选择问题"""
        
        # 确定难度级别
        work_experience = resume_summary.get("work_experience", [])
        
        if len(work_experience) == 0:
            difficulty = "junior"
        elif len(work_experience) <= 2:
            difficulty = "middle"
        else:
            difficulty = "senior"
        
        # 搜索相关问题
        questions_data = self.question_bank.search_questions(
            field=field,
            position=position,
            difficulty=difficulty,
            count=question_count * 2  # 获取更多候选问题
        )
        
        # 转换为Question对象
        questions = []
        
        for i, q_data in enumerate(questions_data[:question_count]):
            content = q_data.get("content", "")
            metadata = q_data.get("metadata", {})
            
            question = Question(
                id=f"q_{i+1}",
                text=content,
                type=QuestionType(metadata.get("type", "technical")),
                difficulty=difficulty,
                field=field,
                expected_keywords=metadata.get("keywords", "").split(",")
            )
            
            questions.append(question)
        
        # 如果题库中问题不足，添加默认问题
        if len(questions) < 3:
            default_questions = self._get_default_questions(field, difficulty)
            questions.extend(default_questions[:3])
        
        return questions[:question_count]
    
    def _get_default_questions(self, field: str, difficulty: str) -> List[Question]:
        """获取默认问题"""
        
        default_questions_map = {
            "AI": {
                "junior": [
                    "请介绍一下你对机器学习的理解。",
                    "什么是监督学习和无监督学习？",
                    "请描述一个你做过的AI相关项目。"
                ],
                "middle": [
                    "请解释深度学习中的反向传播算法。",
                    "如何处理机器学习中的过拟合问题？",
                    "请比较CNN和RNN的适用场景。"
                ],
                "senior": [
                    "请设计一个推荐系统的架构方案。",
                    "如何在生产环境中部署和监控ML模型？",
                    "请分析Transformer架构的优势和局限性。"
                ]
            },
            "Backend": {
                "junior": [
                    "请介绍你熟悉的编程语言和框架。",
                    "什么是RESTful API？",
                    "请描述一个你开发的后端项目。"
                ],
                "middle": [
                    "如何设计一个高并发的Web服务？",
                    "请解释数据库事务的ACID特性。",
                    "如何处理系统的缓存策略？"
                ],
                "senior": [
                    "请设计一个分布式系统的架构。",
                    "如何保证微服务之间的数据一致性？",
                    "请分析系统性能瓶颈的排查方法。"
                ]
            }
        }
        
        questions_text = default_questions_map.get(field, {}).get(difficulty, [
            "请介绍一下你的技术背景。",
            "描述一个你最有成就感的项目。",
            "你是如何学习新技术的？"
        ])
        
        questions = []
        for i, text in enumerate(questions_text):
            question = Question(
                id=f"default_{i+1}",
                text=text,
                type=QuestionType.TECHNICAL if "技术" in text else QuestionType.BEHAVIORAL,
                difficulty=difficulty,
                field=field,
                expected_keywords=[]
            )
            questions.append(question)
        
        return questions
    
    def setup_interview(self, state: InterviewState) -> InterviewState:
        """执行面试设置"""
        
        try:
            user_info = state["user_info"]
            resume_summary = None
            
            # 1. 解析简历 - 优先从jianli目录自动获取
            print("📋 开始简历解析...")
            
            # 首先尝试从jianli目录自动获取简历
            resume_files = self._find_resume_files()
            selected_resume = self._select_resume_file(resume_files)
            
            if selected_resume:
                # 从jianli目录找到简历文件
                try:
                    resume_summary = self._parse_resume(selected_resume)
                    user_info.resume_summary = resume_summary
                    user_info.resume_path = selected_resume  # 保存简历路径
                    print(f"✅ 成功解析简历: {os.path.basename(selected_resume)}")
                except Exception as e:
                    print(f"❌ 简历解析失败: {str(e)}")
                    resume_summary = None
            
            # 如果自动获取失败，尝试用户指定的路径
            if not resume_summary and hasattr(user_info, 'resume_path') and user_info.resume_path:
                try:
                    resume_summary = self._parse_resume(user_info.resume_path)
                    user_info.resume_summary = resume_summary
                    print(f"✅ 成功解析用户指定简历: {user_info.resume_path}")
                except Exception as e:
                    print(f"❌ 用户指定简历解析失败: {str(e)}")
                    resume_summary = None
            
            # 如果都没有简历文件，使用已有的文本信息
            if not resume_summary:
                resume_summary = {"summary": getattr(user_info, 'resume_text', None) or "无简历信息"}
                user_info.resume_summary = resume_summary
                print("⚠️ 使用默认简历信息（无具体简历文件）")
            
            # 2. 选择面试问题
            questions = self._select_questions(
                field=user_info.target_field,
                position=user_info.target_position,
                resume_summary=resume_summary,
                question_count=8
            )
            
            # 3. 更新状态
            state["user_info"] = user_info
            state["questions"] = questions
            state["stage"] = InterviewStage.INTERVIEW
            state["current_question_index"] = 0
            
            # 4. 记录元数据
            state["metadata"]["setup_completed"] = True
            state["metadata"]["total_questions"] = len(questions)
            state["metadata"]["difficulty_level"] = questions[0].difficulty if questions else "middle"
            
            print(f"✅ 面试设置完成:")
            print(f"   - 候选人: {user_info.name}")
            print(f"   - 目标岗位: {user_info.target_position}")
            print(f"   - 技术领域: {user_info.target_field}")
            print(f"   - 问题数量: {len(questions)}")
            print(f"   - 难度级别: {questions[0].difficulty if questions else 'unknown'}")
            
            return state
            
        except Exception as e:
            # 记录错误
            error_msg = f"面试设置失败: {str(e)}"
            state["errors"].append(error_msg)
            print(f"❌ {error_msg}")
            
            return state


def create_setup_agent() -> InterviewSetupAgent:
    """创建面试设置智能体实例"""
    return InterviewSetupAgent() 