"""
LangGraph 工作流定义
多模态面试评测智能体系统的核心编排逻辑
"""
import uuid
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .models.state import InterviewState, InterviewStage, UserInfo, create_initial_state
from .agents.setup_agent import create_setup_agent
from .agents.interviewer_agent import create_interviewer_agent
from .nodes.analysis_node import create_analysis_node
from .nodes.report_node import create_report_node
from .nodes.learning_path_node import create_learning_path_node


class InterviewWorkflow:
    """面试工作流程管理器"""
    
    def __init__(self):
        # 创建智能体和节点
        self.setup_agent = create_setup_agent()
        self.interviewer_agent = create_interviewer_agent()
        self.analysis_node = create_analysis_node()
        self.report_node = create_report_node()
        self.learning_path_node = create_learning_path_node()
        
        # 创建内存存储器
        self.memory = MemorySaver()
        
        # 构建工作流图
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """构建LangGraph工作流图"""
        
        # 创建状态图
        workflow = StateGraph(InterviewState)
        
        # 添加节点
        workflow.add_node("setup", self._setup_node)
        workflow.add_node("interview", self._interview_node)
        workflow.add_node("analysis", self._analysis_node)
        workflow.add_node("report", self._report_node)
        workflow.add_node("learning_path", self._learning_path_node)
        
        # 设置入口点
        workflow.set_entry_point("setup")
        
        # 添加边 - 定义节点间的转换逻辑
        workflow.add_edge("setup", "interview")
        workflow.add_edge("interview", "analysis")
        workflow.add_edge("analysis", "report")
        workflow.add_edge("report", "learning_path")
        workflow.add_edge("learning_path", END)
        
        # 编译图
        return workflow.compile(checkpointer=self.memory)
    
    def _setup_node(self, state: InterviewState) -> InterviewState:
        """面试设置节点"""
        print("🔧 执行面试设置...")
        
        try:
            # 执行面试设置
            updated_state = self.setup_agent.setup_interview(state)
            
            # 验证设置是否成功
            if not updated_state.get("questions") or len(updated_state["questions"]) == 0:
                raise Exception("未能生成面试问题")
            
            print(f"✅ 面试设置完成，准备了 {len(updated_state['questions'])} 个问题")
            return updated_state
            
        except Exception as e:
            error_msg = f"面试设置失败: {str(e)}"
            print(f"❌ {error_msg}")
            state["errors"].append(error_msg)
            return state
    
    def _interview_node(self, state: InterviewState) -> InterviewState:
        """面试执行节点"""
        print("🎤 开始面试...")
        
        try:
            # 检查是否有问题可以进行面试
            if not state.get("questions") or len(state["questions"]) == 0:
                raise Exception("没有可用的面试问题")
            
            # 执行面试
            updated_state = self.interviewer_agent.conduct_interview(state)
            
            # 验证面试是否完成
            conversation_history = updated_state.get("conversation_history", [])
            if len(conversation_history) == 0:
                raise Exception("面试过程中没有收集到对话数据")
            
            print(f"✅ 面试完成，共进行了 {len(conversation_history)} 轮对话")
            return updated_state
            
        except Exception as e:
            error_msg = f"面试执行失败: {str(e)}"
            print(f"❌ {error_msg}")
            state["errors"].append(error_msg)
            return state
    
    def _analysis_node(self, state: InterviewState) -> InterviewState:
        """综合分析节点"""
        print("📊 开始多模态分析...")
        
        try:
            # 执行综合分析
            updated_state = self.analysis_node.analyze(state)
            
            # 验证分析结果
            analysis_result = updated_state.get("multimodal_analysis")
            if not analysis_result or not analysis_result.comprehensive_assessment:
                raise Exception("分析未能生成有效结果")
            
            print("✅ 多模态分析完成")
            return updated_state
            
        except Exception as e:
            error_msg = f"分析执行失败: {str(e)}"
            print(f"❌ {error_msg}")
            state["errors"].append(error_msg)
            return state
    
    def _report_node(self, state: InterviewState) -> InterviewState:
        """报告生成节点"""
        print("📋 生成面试报告...")
        
        try:
            # 生成报告
            updated_state = self.report_node.generate_report(state)
            
            # 验证报告生成
            report = updated_state.get("interview_report")
            if not report:
                raise Exception("报告生成失败")
            
            print("✅ 面试报告生成完成")
            return updated_state
            
        except Exception as e:
            error_msg = f"报告生成失败: {str(e)}"
            print(f"❌ {error_msg}")
            state["errors"].append(error_msg)
            return state
    
    def _learning_path_node(self, state: InterviewState) -> InterviewState:
        """学习路径推荐节点"""
        print("🎯 生成学习路径...")
        
        try:
            # 生成学习路径
            updated_state = self.learning_path_node.generate_learning_path(state)
            
            # 设置最终状态
            updated_state["stage"] = InterviewStage.COMPLETED
            
            print("✅ 学习路径推荐完成")
            return updated_state
            
        except Exception as e:
            error_msg = f"学习路径生成失败: {str(e)}"
            print(f"❌ {error_msg}")
            state["errors"].append(error_msg)
            state["stage"] = InterviewStage.COMPLETED
            return state
    
    def run_interview(
        self, 
        user_name: str,
        target_position: str,
        target_field: str,
        resume_text: str = "",
        resume_path: str = None
    ) -> InterviewState:
        """
        运行完整的面试流程
        
        Args:
            user_name: 用户姓名
            target_position: 目标岗位
            target_field: 目标领域
            resume_text: 简历文本内容
            resume_path: 简历文件路径
        
        Returns:
            最终的面试状态
        """
        
        # 生成会话ID
        session_id = str(uuid.uuid4())
        
        # 创建用户信息
        user_info = UserInfo(
            user_id=session_id,
            name=user_name,
            target_position=target_position,
            target_field=target_field,
            resume_text=resume_text,
            resume_summary={}
        )
        
        # 如果有简历文件路径，添加到用户信息
        if resume_path:
            user_info.resume_path = resume_path
        
        # 创建初始状态
        initial_state = create_initial_state(session_id, user_info)
        
        print("🚀 启动多模态面试评测系统")
        print("=" * 60)
        print(f"会话ID: {session_id}")
        print(f"候选人: {user_name}")
        print(f"目标岗位: {target_position}")
        print(f"技术领域: {target_field}")
        print("=" * 60)
        
        try:
            # 运行工作流
            final_state = self.graph.invoke(
                initial_state,
                config={"configurable": {"thread_id": session_id}}
            )
            
            # 输出最终结果摘要
            self._print_final_summary(final_state)
            
            return final_state
            
        except Exception as e:
            error_msg = f"工作流执行失败: {str(e)}"
            print(f"❌ {error_msg}")
            
            # 返回错误状态
            initial_state["errors"].append(error_msg)
            initial_state["stage"] = InterviewStage.COMPLETED
            return initial_state
    
    def _print_final_summary(self, state: InterviewState):
        """打印最终结果摘要"""
        
        print("\n" + "=" * 60)
        print("📊 面试结果摘要")
        print("=" * 60)
        
        # 基本信息
        user_info = state.get("user_info")
        if user_info:
            print(f"候选人: {user_info.name}")
            print(f"目标岗位: {user_info.target_position}")
        
        # 面试统计
        questions = state.get("questions", [])
        conversation_history = state.get("conversation_history", [])
        print(f"准备问题: {len(questions)} 个")
        print(f"对话轮次: {len(conversation_history)} 轮")
        
        # 分析结果
        analysis = state.get("multimodal_analysis")
        if analysis and analysis.comprehensive_assessment:
            assessment = analysis.comprehensive_assessment
            print(f"\n📈 综合评估:")
            
            for key, value in assessment.items():
                if isinstance(value, dict) and "score" in value:
                    score = value["score"]
                    print(f"  {key}: {score}/10")
        
        # 错误信息
        errors = state.get("errors", [])
        if errors:
            print(f"\n⚠️ 发现 {len(errors)} 个问题:")
            for error in errors:
                print(f"  - {error}")
        
        # 学习资源
        learning_resources = state.get("learning_resources", [])
        if learning_resources:
            print(f"\n🎯 推荐学习资源: {len(learning_resources)} 个")
        
        print("=" * 60)


def create_interview_workflow() -> InterviewWorkflow:
    """创建面试工作流实例"""
    return InterviewWorkflow()


# 便捷函数
def run_simple_interview(
    user_name: str,
    target_position: str, 
    target_field: str,
    resume_text: str = ""
) -> InterviewState:
    """
    运行简单面试流程的便捷函数
    
    Args:
        user_name: 用户姓名
        target_position: 目标岗位 
        target_field: 目标领域
        resume_text: 简历文本内容
        
    Returns:
        面试结果状态
    """
    
    workflow = create_interview_workflow()
    return workflow.run_interview(
        user_name=user_name,
        target_position=target_position,
        target_field=target_field,
        resume_text=resume_text
    ) 