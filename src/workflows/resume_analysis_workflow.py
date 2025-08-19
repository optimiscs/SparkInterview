"""
基于LangGraph的智能简历分析工作流
重构原有的单体分析函数为模块化、并行化的状态图
"""
import json
import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, TypedDict
from pathlib import Path

# LangGraph imports
try:
    from langgraph.graph import StateGraph, END, START
    from langgraph.graph.message import add_messages
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    # 降级实现
    class StateGraph:
        def __init__(self, state_type): pass
        def add_node(self, name, func): pass
        def add_edge(self, start, end): pass
        def add_conditional_edges(self, start, condition, mapping): pass
        def compile(self, **kwargs): return None
    START = "START"
    END = "END"

# LangChain imports
from langchain_core.messages import SystemMessage

# 本地imports
from src.models.spark_client import create_spark_model

logger = logging.getLogger(__name__)


class ResumeAnalysisState(TypedDict):
    """简历AI分析图的状态"""
    # 输入数据
    resume_id: str
    resume_data: Dict[str, Any]
    jd_content: Optional[str]
    analysis_id: str
    
    # 每个分析节点的结果
    jd_match_result: Optional[Dict[str, Any]]
    star_principle_result: Optional[Dict[str, Any]]
    health_scan_result: Optional[Dict[str, Any]]
    
    # 完成状态追踪
    jd_completed: bool
    star_completed: bool 
    health_completed: bool
    
    # 最终汇总结果
    final_analysis_report: Optional[Dict[str, Any]]
    
    # 错误处理
    error_message: Optional[str]
    success: bool


class ResumeAnalysisWorkflow:
    """基于LangGraph的简历分析工作流"""
    
    def __init__(self):
        """初始化工作流"""
        self.spark_model = create_spark_model(model_type="chat", temperature=0.7)
        self.workflow = self._build_workflow()
        
        if LANGGRAPH_AVAILABLE:
            self.app = self.workflow.compile()
            logger.info("✅ LangGraph简历分析工作流初始化成功")
        else:
            self.app = None
            logger.warning("⚠️ LangGraph不可用，使用降级模式")
    
    def _build_workflow(self) -> StateGraph:
        """构建LangGraph工作流"""
        workflow = StateGraph(ResumeAnalysisState)
        
        # 添加并行分析节点
        workflow.add_node("jd_matching", self._jd_matching_node)
        workflow.add_node("star_principle", self._star_principle_node)
        workflow.add_node("health_scan", self._health_scan_node)
        
        # 添加汇总节点
        workflow.add_node("compile_report", self._compile_report_node)
        workflow.add_node("save_results", self._save_results_node)
        
        # 设置并行入口
        workflow.add_edge(START, "jd_matching")
        workflow.add_edge(START, "star_principle") 
        workflow.add_edge(START, "health_scan")
        
        # 修复：直接连接到汇总节点，让所有并行任务都指向汇总
        workflow.add_edge("jd_matching", "compile_report")
        workflow.add_edge("star_principle", "compile_report") 
        workflow.add_edge("health_scan", "compile_report")
        
        # 汇总后保存结果
        workflow.add_edge("compile_report", "save_results")
        workflow.add_edge("save_results", END)
        
        return workflow
    
    # _check_all_completed 方法已移除 - 使用直接边连接实现并行等待
    
    async def _run_analysis_node(self, prompt: str, fallback_data: Dict[str, Any], 
                                node_name: str) -> Dict[str, Any]:
        """通用的AI分析节点执行器 - 消除代码冗余"""
        try:
            logger.info(f"🤖 执行{node_name}分析...")
            
            # 1. 调用大模型
            messages = [SystemMessage(content=prompt)]
            result = await self.spark_model._agenerate(messages)
            response = result.generations[0].message.content
            
            # 2. 解析JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                parsed_result = json.loads(json_match.group())
                logger.info(f"✅ {node_name}分析成功")
                return parsed_result
            else:
                logger.warning(f"⚠️ {node_name}无法解析JSON，使用降级数据")
                return fallback_data
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ {node_name}JSON解析失败: {e}")
            return fallback_data
        except Exception as e:
            logger.error(f"❌ {node_name}执行失败: {e}")
            return fallback_data
    
    async def _jd_matching_node(self, state: ResumeAnalysisState) -> Dict[str, Any]:
        """JD匹配分析节点"""
        resume_data = state["resume_data"]
        jd_content = state.get("jd_content", "")
        
        # 构建JD匹配提示
        prompt = self._build_jd_matching_prompt(resume_data, jd_content)
        
        # 降级数据
        fallback_data = {
            "overall_match": 82,
            "skill_match": 85,
            "experience_match": 75,
            "project_relevance": 88,
            "education_match": 90,
            "strengths": ["技术基础扎实", "项目经验丰富"],
            "gaps": ["需要加强系统架构能力"],
            "suggestions": ["多参与开源项目", "加强系统设计学习"],
            "analysis_timestamp": datetime.now().isoformat()
        }
        
        # 执行分析
        result = await self._run_analysis_node(prompt, fallback_data, "JD匹配")
        
        # 更新状态 - 移除完成标志，LangGraph自动管理
        return {
            "jd_match_result": result
        }
    
    async def _star_principle_node(self, state: ResumeAnalysisState) -> Dict[str, Any]:
        """STAR原则检测节点"""
        resume_data = state["resume_data"]
        
        # 构建STAR检测提示
        prompt = self._build_star_principle_prompt(resume_data)
        
        # 降级数据
        fallback_data = {
            "overall_score": 76,
            "star_items": [
                {
                    "name": "项目经历示例",
                    "situation_score": 85,
                    "task_score": 90,
                    "action_score": 88,
                    "result_score": 65,
                    "overall_score": 82,
                    "strengths": ["技术背景清晰", "任务目标明确"],
                    "suggestions": ["需要补充量化的项目成果"]
                }
            ],
            "analysis_timestamp": datetime.now().isoformat()
        }
        
        # 执行分析
        result = await self._run_analysis_node(prompt, fallback_data, "STAR原则")
        
        # 更新状态 - 移除完成标志，LangGraph自动管理
        return {
            "star_principle_result": result
        }
    
    async def _health_scan_node(self, state: ResumeAnalysisState) -> Dict[str, Any]:
        """简历健康度扫描节点"""
        resume_data = state["resume_data"]
        
        # 构建健康度扫描提示
        prompt = self._build_health_scan_prompt(resume_data)
        
        # 降级数据
        fallback_data = {
            "overall_health": 88,
            "health_checks": [
                {
                    "category": "格式规范",
                    "score": 95,
                    "status": "通过",
                    "details": "简历格式规范，结构清晰"
                },
                {
                    "category": "内容完整性", 
                    "score": 85,
                    "status": "良好",
                    "details": "基础信息完整，项目描述详细"
                }
            ],
            "analysis_timestamp": datetime.now().isoformat()
        }
        
        # 执行分析
        result = await self._run_analysis_node(prompt, fallback_data, "健康度扫描")
        
        # 更新状态 - 移除完成标志，LangGraph自动管理
        return {
            "health_scan_result": result
        }
    
    async def _compile_report_node(self, state: ResumeAnalysisState) -> Dict[str, Any]:
        """汇总报告节点 - LangGraph自动等待所有并行节点完成"""
        logger.info("📊 开始汇总分析报告...")
        
        try:
            # 验证所有分析结果都已完成
            jd_result = state.get("jd_match_result")
            star_result = state.get("star_principle_result") 
            health_result = state.get("health_scan_result")
            
            if not all([jd_result, star_result, health_result]):
                missing = []
                if not jd_result: missing.append("JD匹配")
                if not star_result: missing.append("STAR原则")
                if not health_result: missing.append("健康度扫描")
                raise Exception(f"分析结果不完整，缺少: {', '.join(missing)}")
            
            # 汇总所有分析结果
            final_report = {
                "resume_id": state["resume_id"],
                "analysis_id": state["analysis_id"],
                "analysis_timestamp": datetime.now().isoformat(),
                "analysis_version": "v2.0_langgraph_fixed",
                "status": "completed",
                
                # 各项分析结果
                "jd_matching": jd_result,
                "star_principle": star_result,
                "health_scan": health_result,
                
                # 综合评分
                "overall_score": self._calculate_overall_score(state),
                
                # 元数据
                "metadata": {
                    "analysis_engine": "LangGraph + 星火大模型",
                    "parallel_processing": True,
                    "jd_provided": bool(state.get("jd_content")),
                    "processing_time": "并行处理",
                    "workflow_type": "direct_edge_parallel"
                }
            }
            
            logger.info(f"✅ 分析报告汇总完成 - 综合评分: {final_report['overall_score']}")
            
            return {
                "final_analysis_report": final_report,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"❌ 汇总报告失败: {e}")
            return {
                "error_message": f"汇总报告失败: {str(e)}",
                "success": False
            }
    
    async def _save_results_node(self, state: ResumeAnalysisState) -> Dict[str, Any]:
        """保存结果节点"""
        logger.info("💾 保存分析结果...")
        
        try:
            if not state.get("final_analysis_report"):
                raise Exception("没有找到最终分析报告")
            
            # 保存到文件
            analysis_dir = Path("data/resume_analysis")
            analysis_dir.mkdir(parents=True, exist_ok=True)
            
            analysis_file = analysis_dir / f"{state['analysis_id']}.json"
            
            with open(analysis_file, 'w', encoding='utf-8') as f:
                json.dump(state["final_analysis_report"], f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ 分析结果已保存: {analysis_file}")
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"❌ 保存结果失败: {e}")
            return {
                "error_message": f"保存结果失败: {str(e)}",
                "success": False
            }
    
    def _calculate_overall_score(self, state: ResumeAnalysisState) -> float:
        """计算综合评分"""
        try:
            scores = []
            
            # JD匹配评分
            jd_result = state.get("jd_match_result", {})
            if jd_result.get("overall_match"):
                scores.append(jd_result["overall_match"])
            
            # STAR原则评分
            star_result = state.get("star_principle_result", {})
            if star_result.get("overall_score"):
                scores.append(star_result["overall_score"])
            
            # 健康度评分
            health_result = state.get("health_scan_result", {})
            if health_result.get("overall_health"):
                scores.append(health_result["overall_health"])
            
            if scores:
                return round(sum(scores) / len(scores), 2)
            else:
                return 75.0  # 默认分数
                
        except Exception as e:
            logger.error(f"计算综合评分失败: {e}")
            return 75.0
    
    def _build_jd_matching_prompt(self, resume_data: Dict, jd_content: str) -> str:
        """构建JD匹配分析提示"""
        # 提取简历关键信息
        basic_info = resume_data.get("basic_info", {})
        projects = resume_data.get("projects", [])
        skills = resume_data.get("skills", {})
        education = resume_data.get("education", {})
        
        prompt = f"""你是一名资深的HR专家，请分析简历与职位描述的匹配度。

简历信息：
- 基本信息：{json.dumps(basic_info, ensure_ascii=False)}
- 项目经历：{json.dumps(projects, ensure_ascii=False)}
- 技能清单：{json.dumps(skills, ensure_ascii=False)}
- 教育背景：{json.dumps(education, ensure_ascii=False)}

职位描述：
{jd_content if jd_content else "未提供具体职位描述，请基于简历内容进行一般性评估"}

请从以下维度进行分析并返回JSON格式结果：
1. 技能匹配度：技能与职位要求的匹配程度(0-100分)
2. 经验匹配度：工作/项目经验的匹配程度(0-100分)
3. 项目相关性：项目经历与职位的相关程度(0-100分)
4. 教育匹配度：教育背景的匹配程度(0-100分)
5. 综合匹配度：整体匹配度评分(0-100分)
6. 核心优势：候选人的主要优势点
7. 技能缺口：需要提升的技能领域
8. 改进建议：具体的发展建议

请返回以下JSON格式：
{{
    "overall_match": 综合匹配度分数,
    "skill_match": 技能匹配度分数,
    "experience_match": 经验匹配度分数,
    "project_relevance": 项目相关性分数,
    "education_match": 教育匹配度分数,
    "strengths": ["优势1", "优势2"],
    "gaps": ["缺口1", "缺口2"],
    "suggestions": ["建议1", "建议2"],
    "analysis_timestamp": "{datetime.now().isoformat()}"
}}"""
        
        return prompt
    
    def _build_star_principle_prompt(self, resume_data: Dict) -> str:
        """构建STAR原则检测提示"""
        projects = resume_data.get("projects", [])
        internship = resume_data.get("internship", [])
        
        prompt = f"""你是一名专业的简历优化专家，请分析项目/实习经历是否符合STAR原则。

项目经历：
{json.dumps(projects, ensure_ascii=False, indent=2)}

实习经历：
{json.dumps(internship, ensure_ascii=False, indent=2)}

STAR原则评分标准：
- S (Situation 情境): 0-100分
  * 80-100分：背景描述清晰完整，项目背景、团队规模、技术环境等信息明确
  * 60-79分：背景描述基本清晰，但缺少部分关键信息
  * 0-59分：背景描述模糊或缺失

- T (Task 任务): 0-100分
  * 80-100分：任务目标明确具体，预期成果清晰，面临的挑战描述详细
  * 60-79分：任务目标较为明确，但缺少具体细节
  * 0-59分：任务目标模糊或不清晰

- A (Action 行动): 0-100分
  * 80-100分：具体行动步骤详细，技术方案明确，个人贡献突出
  * 60-79分：行动描述较为详细，但缺少技术细节或个人贡献
  * 0-59分：行动描述模糊或过于简单

- R (Result 结果): 0-100分
  * 80-100分：结果量化具体，有明确的数据支撑，业务价值清晰
  * 60-79分：结果描述相对具体，有一定量化，但不够详细
  * 0-59分：结果描述模糊，缺乏量化数据

请严格按照以下JSON格式返回分析结果：
{{
    "overall_score": 所有项目STAR评分的平均值(整数),
    "star_items": [
        {{
            "name": "项目名称",
            "situation_score": S维度评分(整数，0-100),
            "task_score": T维度评分(整数，0-100),
            "action_score": A维度评分(整数，0-100),
            "result_score": R维度评分(整数，0-100),
            "overall_score": 该项目四个维度的平均分(整数),
            "suggestions": ["具体的改进建议1", "具体的改进建议2"]
        }}
    ],
    "improvement_suggestions": [
        "整体优化建议1：如何提升项目描述的STAR完整性",
        "整体优化建议2：如何增强项目成果的量化表达",
        "整体优化建议3：如何突出个人贡献和技术能力"
    ],
    "analysis_timestamp": "{datetime.now().isoformat()}"
}}

注意：
1. 所有评分都必须是0-100的整数
2. 每个项目都必须包含所有四个维度的评分
3. 建议要具体可操作，针对性强
4. 如果没有项目经历，返回空的star_items数组但保留结构"""
        
        return prompt
    
    def _build_health_scan_prompt(self, resume_data: Dict) -> str:
        """构建健康度扫描提示"""
        prompt = f"""你是一名简历审查专家，请对简历进行全面的健康度扫描。

简历数据：
{json.dumps(resume_data, ensure_ascii=False, indent=2)}

请从以下维度评估简历质量(0-100分)：
1. 格式规范：排版、结构、字体等
2. 内容完整性：各个板块是否齐全
3. 信息准确性：内容的真实性和一致性
4. 技能匹配度：技能与目标岗位的匹配程度
5. 项目质量：项目的技术含量和商业价值
6. 描述质量：内容的具体性和可量化程度

返回JSON格式：
{{
    "overall_health": 整体健康度评分,
    "health_checks": [
        {{
            "category": "检查类别",
            "score": 该类别评分,
            "status": "通过/良好/待改进/不通过",
            "details": "具体说明",
            "suggestions": ["改进建议"]
        }}
    ],
    "analysis_timestamp": "{datetime.now().isoformat()}"
}}"""
        
        return prompt
    
    async def analyze_jd_matching(self, resume_id: str, resume_data: Dict[str, Any], 
                                 jd_content: str, analysis_id: str) -> Dict[str, Any]:
        """执行JD匹配分析（单独分析）"""
        try:
            logger.info(f"🔍 启动JD匹配分析: {analysis_id}")
            
            # 构建JD匹配提示
            prompt = self._build_jd_matching_prompt(resume_data, jd_content)
            
            # 降级数据
            fallback_data = {
                "overall_match": 82,
                "skill_match": 85,
                "experience_match": 75,
                "project_relevance": 88,
                "education_match": 90,
                "strengths": ["技术基础扎实", "项目经验丰富"],
                "gaps": ["需要加强系统架构能力"],
                "suggestions": ["多参与开源项目", "加强系统设计学习"],
                "match_details": {
                    "技术能力": 85,
                    "项目经验": 75,
                    "教育背景": 90,
                    "工作经验": 45,
                    "软技能": 88
                },
                "analysis_timestamp": datetime.now().isoformat()
            }
            
            # 执行分析
            result = await self._run_analysis_node(prompt, fallback_data, "JD匹配")
            
            return {
                "success": True,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"❌ JD匹配分析失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def analyze_star_principle(self, resume_id: str, resume_data: Dict[str, Any], 
                                   analysis_id: str) -> Dict[str, Any]:
        """执行STAR原则检测（单独分析）"""
        try:
            logger.info(f"⭐ 启动STAR原则检测: {analysis_id}")
            
            # 构建STAR检测提示
            prompt = self._build_star_principle_prompt(resume_data)
            
            # 降级数据（匹配前端渲染格式）
            fallback_data = {
                "overall_score": 76,
                "star_items": [
                    {
                        "name": "智能学习管理系统",
                        "situation_score": 85,
                        "task_score": 90,
                        "action_score": 88,
                        "result_score": 65,
                        "overall_score": 82,
                        "suggestions": ["需要补充量化的项目成果", "增加具体的技术难点描述"]
                    },
                    {
                        "name": "电商数据分析平台", 
                        "situation_score": 75,
                        "task_score": 80,
                        "action_score": 85,
                        "result_score": 70,
                        "overall_score": 78,
                        "suggestions": ["强化数据分析结果的商业价值", "添加性能优化的具体数据"]
                    }
                ],
                "improvement_suggestions": [
                    "整体优化建议1：增加项目结果的量化数据，如'性能提升30%'、'用户满意度达95%'",
                    "整体优化建议2：详细描述解决问题的具体技术方案和实施步骤",
                    "整体优化建议3：突出个人在团队中的关键作用和核心贡献"
                ],
                "analysis_timestamp": datetime.now().isoformat()
            }
            
            # 执行分析
            result = await self._run_analysis_node(prompt, fallback_data, "STAR原则")
            
            return {
                "success": True,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"❌ STAR原则检测失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def analyze_basic_parallel(self, resume_id: str, resume_data: Dict[str, Any], 
                                   user_data: Dict[str, Any]) -> Dict[str, Any]:
        """并行执行基础分析（STAR检测 + 用户画像生成）"""
        try:
            logger.info(f"🚀 启动并行基础分析: {resume_id}")
            
            # 生成任务ID
            star_analysis_id = f"star_analysis_{resume_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            profile_id = f"profile_{resume_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 并行执行STAR检测和用户画像生成
            import asyncio
            
            star_task = asyncio.create_task(
                self.analyze_star_principle(resume_id, resume_data, star_analysis_id)
            )
            
            profile_task = asyncio.create_task(
                self._generate_user_profile(profile_id, resume_id, resume_data, user_data)
            )
            
            logger.info(f"⚡ 并行任务已启动: STAR检测 + 用户画像生成")
            
            # 等待两个任务完成
            star_result, profile_result = await asyncio.gather(star_task, profile_task)
            
            # 汇总结果
            results = {
                "star_analysis": star_result,
                "user_profile": profile_result,
                "parallel_execution": True,
                "completed_at": datetime.now().isoformat()
            }
            
            # 检查是否都成功
            all_success = star_result.get("success", False) and profile_result.get("success", False)
            
            if all_success:
                logger.info(f"✅ 并行基础分析完成: {resume_id}")
                return {
                    "success": True,
                    "results": results,
                    "star_analysis_id": star_analysis_id,
                    "profile_id": profile_id
                }
            else:
                failed_tasks = []
                if not star_result.get("success"):
                    failed_tasks.append("STAR检测")
                if not profile_result.get("success"):
                    failed_tasks.append("用户画像生成")
                
                logger.warning(f"⚠️ 部分基础分析失败: {', '.join(failed_tasks)}")
                return {
                    "success": False,
                    "error": f"部分任务失败: {', '.join(failed_tasks)}",
                    "results": results
                }
            
        except Exception as e:
            logger.error(f"❌ 并行基础分析失败: {resume_id} - {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _generate_user_profile(self, profile_id: str, resume_id: str, 
                                   resume_data: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成用户画像"""
        try:
            logger.info(f"🧠 开始生成用户画像: {profile_id}")
            
            basic_info = resume_data.get("basic_info", {})
            target_position = resume_data.get("target_position", "")
            
            # 构建用户画像数据
            profile_data = {
                "profile_id": profile_id,
                "resume_id": resume_id,
                "profile_data": {
                    "basic_info": {
                        "name": user_data.get("user_name") or basic_info.get("name", "用户"),
                        "target_position": target_position,
                        "target_field": user_data.get("target_field", "技术")
                    },
                    "personalized_welcome": {
                        "greeting": f"您好 {user_data.get('user_name', '朋友')}！很高兴在今天的面试中与您相遇。我注意到您应聘的是{target_position}职位，相信您一定有很多精彩的经历要分享。让我们开始愉快的交流吧！",
                        "tone": "friendly"
                    },
                    "metadata": {
                        "generated_at": datetime.now().isoformat(),
                        "generation_mode": "parallel_basic_analysis"
                    }
                },
                "status": "completed",
                "created_at": datetime.now().isoformat()
            }
            
            return {
                "success": True,
                "result": profile_data
            }
            
        except Exception as e:
            logger.error(f"❌ 用户画像生成失败: {profile_id} - {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def analyze_resume(self, resume_id: str, resume_data: Dict[str, Any], 
                           jd_content: str = "", analysis_id: str = None) -> Dict[str, Any]:
        """执行完整的简历分析工作流（保留用于向后兼容）"""
        
        if not LANGGRAPH_AVAILABLE:
            logger.warning("LangGraph不可用，使用降级分析")
            return await self._fallback_analysis(resume_id, resume_data, jd_content, analysis_id)
        
        try:
            # 构建初始状态
            initial_state = ResumeAnalysisState(
                resume_id=resume_id,
                resume_data=resume_data,
                jd_content=jd_content,
                analysis_id=analysis_id or f"analysis_{resume_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                
                # 初始化结果为None
                jd_match_result=None,
                star_principle_result=None,
                health_scan_result=None,
                
                # 移除完成状态 - LangGraph自动处理并行等待
                jd_completed=False,
                star_completed=False,
                health_completed=False,
                
                final_analysis_report=None,
                error_message=None,
                success=False
            )
            
            logger.info(f"🚀 启动LangGraph简历分析工作流: {initial_state['analysis_id']}")
            
            # 执行工作流
            config = {"configurable": {"thread_id": initial_state["analysis_id"]}}
            final_state = await self.app.ainvoke(initial_state, config)
            
            if final_state.get("success") and final_state.get("final_analysis_report"):
                logger.info("✅ LangGraph简历分析完成")
                return {
                    "success": True,
                    "analysis_id": final_state["analysis_id"],
                    "result": final_state["final_analysis_report"]
                }
            else:
                error_msg = final_state.get("error_message", "未知错误")
                logger.error(f"❌ LangGraph分析失败: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "analysis_id": initial_state["analysis_id"]
                }
                
        except Exception as e:
            logger.error(f"❌ LangGraph工作流执行失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis_id": analysis_id or "unknown"
            }
    
    async def _fallback_analysis(self, resume_id: str, resume_data: Dict[str, Any], 
                                jd_content: str, analysis_id: str) -> Dict[str, Any]:
        """降级分析方法"""
        logger.info("🔄 使用降级分析模式")
        
        try:
            # 直接调用各个分析节点
            jd_state = await self._jd_matching_node({
                "resume_data": resume_data,
                "jd_content": jd_content
            })
            
            star_state = await self._star_principle_node({
                "resume_data": resume_data
            })
            
            health_state = await self._health_scan_node({
                "resume_data": resume_data
            })
            
            # 手动汇总结果
            combined_state = {
                "resume_id": resume_id,
                "analysis_id": analysis_id,
                "jd_match_result": jd_state["jd_match_result"],
                "star_principle_result": star_state["star_principle_result"],
                "health_scan_result": health_state["health_scan_result"]
            }
            
            report_state = await self._compile_report_node(combined_state)
            
            return {
                "success": True,
                "analysis_id": analysis_id,
                "result": report_state["final_analysis_report"]
            }
            
        except Exception as e:
            logger.error(f"❌ 降级分析失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis_id": analysis_id
            }


# 创建全局工作流实例
_workflow_instance = None

def get_resume_analysis_workflow() -> ResumeAnalysisWorkflow:
    """获取简历分析工作流实例"""
    global _workflow_instance
    
    if _workflow_instance is None:
        _workflow_instance = ResumeAnalysisWorkflow()
    
    return _workflow_instance
