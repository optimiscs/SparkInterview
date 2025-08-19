"""
LangGraph智能体重构演示
展示感知-决策-行动架构的LangGraph实现
"""
import asyncio
import json
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('langgraph_demo.log')
    ]
)
logger = logging.getLogger(__name__)

# 导入LangGraph智能体
try:
    from src.agents.langgraph_interview_agent import LangGraphInterviewAgent
    from src.tools.langchain_mcp_tools import (
        emotion_analysis_tool, 
        info_extraction_tool,
        question_generation_tool,
        emotional_support_tool
    )
    
    print("✅ 成功导入LangGraph模块")
except ImportError as e:
    print(f"❌ 导入模块失败: {e}")
    print("请确保已安装必要的依赖: pip install langgraph langchain")
    exit(1)


class LangGraphDemo:
    """LangGraph智能体演示类"""
    
    def __init__(self):
        try:
            self.agent = LangGraphInterviewAgent()
            print("🤖 LangGraph智能体初始化成功")
        except Exception as e:
            print(f"❌ 智能体初始化失败: {e}")
            self.agent = None
    
    async def demo_individual_tools(self):
        """演示单个LangChain工具"""
        print("\n" + "="*60)
        print("🔧 LangChain工具单独测试")
        print("="*60)
        
        # 1. 情感分析工具
        print("\\n1️⃣ 测试情感分析工具")
        test_messages = [
            "我很紧张，担心回答不好",
            "我很兴奋，期待这次面试",
            "我不太明白这个问题",
            "我觉得还可以"
        ]
        
        for msg in test_messages:
            emotion = await emotion_analysis_tool._arun(msg)
            print(f"   消息: {msg}")
            print(f"   情绪: {emotion}")
        
        # 2. 信息提取工具
        print("\\n2️⃣ 测试信息提取工具")
        test_extractions = [
            ("我有3年的工作经验，在阿里巴巴工作", ["work_years", "current_company"]),
            ("我是硕士学历，2020年毕业的", ["education_level", "graduation_year"]),
            ("期望薪资20K左右", ["expected_salary"])
        ]
        
        for msg, missing_fields in test_extractions:
            extracted = await info_extraction_tool._arun(msg, missing_fields)
            print(f"   消息: {msg}")
            print(f"   提取结果: {extracted}")
        
        # 3. 问题生成工具
        print("\\n3️⃣ 测试问题生成工具")
        question = await question_generation_tool._arun(
            missing_info=["work_years", "education_level"],
            user_name="张三",
            target_position="算法工程师"
        )
        print(f"   生成问题: {question}")
        
        # 4. 情感支持工具
        print("\\n4️⃣ 测试情感支持工具")
        support = await emotional_support_tool._arun(
            user_emotion="anxious",
            user_name="李四"
        )
        print(f"   情感支持: {support}")
    
    async def demo_complete_workflow(self):
        """演示完整的LangGraph工作流"""
        print("\\n" + "="*60)
        print("🔄 LangGraph完整工作流演示")
        print("="*60)
        
        if not self.agent:
            print("❌ 智能体未初始化，跳过工作流演示")
            return
        
        # 场景1: 缺失信息的智能收集
        await self._demo_missing_info_scenario()
        
        # 场景2: 情绪支持场景
        await self._demo_emotional_support_scenario()
        
        # 场景3: 正常面试流程
        await self._demo_normal_interview_scenario()
    
    async def _demo_missing_info_scenario(self):
        """演示缺失信息收集场景"""
        print("\\n🎬 场景1: 智能信息收集")
        print("-" * 40)
        
        try:
            # 开始面试
            start_result = await self.agent.start_interview(
                user_id="demo_user_001",
                session_id="demo_session_001",
                user_name="张三",
                target_position="算法工程师",
                target_field="人工智能",
                resume_text="本科毕业，熟悉Python和机器学习"
            )
            
            print(f"🤖 面试官: {start_result['welcome_message']}")
            
            # 用户简单回应（缺少工作经验信息）
            user_response = "好的，我准备好了"
            print(f"👤 用户: {user_response}")
            
            # 处理消息
            result = await self.agent.process_message(
                user_id="demo_user_001",
                session_id="demo_session_001", 
                user_name="张三",
                target_position="算法工程师",
                user_message=user_response,
                user_profile={
                    "basic_info": {
                        "work_years": None,
                        "education_level": None,
                        "current_company": None
                    },
                    "completeness_score": 0.2
                }
            )
            
            if result["success"]:
                print(f"🤖 面试官: {result['response']}")
                print(f"📊 信息完整度: {result.get('completeness_score', 0):.1%}")
                print(f"🧠 用户情绪: {result.get('user_emotion', 'unknown')}")
                print(f"🎯 决策类型: {result.get('decision', {}).get('action_type', 'unknown')}")
                
                # 用户提供工作经验
                user_response2 = "我有3年的算法工程师工作经验，目前在字节跳动工作"
                print(f"👤 用户: {user_response2}")
                
                result2 = await self.agent.process_message(
                    user_id="demo_user_001",
                    session_id="demo_session_001",
                    user_name="张三", 
                    target_position="算法工程师",
                    user_message=user_response2,
                    user_profile=result["user_profile"]
                )
                
                if result2["success"]:
                    print(f"🤖 面试官: {result2['response']}")
                    print(f"📊 更新后完整度: {result2.get('completeness_score', 0):.1%}")
                    print(f"✅ 缺失信息: {result2.get('missing_info', [])}")
            
        except Exception as e:
            print(f"❌ 场景1演示失败: {e}")
    
    async def _demo_emotional_support_scenario(self):
        """演示情感支持场景"""
        print("\\n🎬 场景2: 情感支持")
        print("-" * 40)
        
        try:
            # 模拟紧张的用户
            nervous_message = "我很紧张，担心自己回答不好，这是我第一次面试"
            print(f"👤 用户: {nervous_message}")
            
            result = await self.agent.process_message(
                user_id="demo_user_002",
                session_id="demo_session_002",
                user_name="李四",
                target_position="前端工程师",
                user_message=nervous_message,
                user_profile={
                    "basic_info": {"work_years": 1, "education_level": "本科"},
                    "completeness_score": 0.6
                }
            )
            
            if result["success"]:
                print(f"🤖 面试官: {result['response']}")
                print(f"🧠 检测到情绪: {result.get('user_emotion', 'unknown')}")
                print(f"🎯 决策类型: {result.get('decision', {}).get('action_type', 'unknown')}")
                print(f"💡 决策原因: {result.get('decision', {}).get('reasoning', 'unknown')}")
            
        except Exception as e:
            print(f"❌ 场景2演示失败: {e}")
    
    async def _demo_normal_interview_scenario(self):
        """演示正常面试流程"""
        print("\\n🎬 场景3: 正常面试流程")
        print("-" * 40)
        
        try:
            # 模拟信息相对完整的用户
            complete_profile = {
                "basic_info": {
                    "work_years": 3,
                    "education_level": "硕士",
                    "current_company": "腾讯",
                    "graduation_year": 2020
                },
                "completeness_score": 0.8
            }
            
            normal_message = "我准备好回答技术问题了"
            print(f"👤 用户: {normal_message}")
            
            result = await self.agent.process_message(
                user_id="demo_user_003",
                session_id="demo_session_003",
                user_name="王五",
                target_position="数据科学家",
                user_message=normal_message,
                user_profile=complete_profile
            )
            
            if result["success"]:
                print(f"🤖 面试官: {result['response']}")
                print(f"📊 信息完整度: {result.get('completeness_score', 0):.1%}")
                print(f"🎯 决策类型: {result.get('decision', {}).get('action_type', 'unknown')}")
                print(f"💡 决策原因: {result.get('decision', {}).get('reasoning', 'unknown')}")
            
        except Exception as e:
            print(f"❌ 场景3演示失败: {e}")
    
    async def demo_architecture_comparison(self):
        """演示架构对比"""
        print("\\n" + "="*60)
        print("📊 LangGraph vs 手动实现 架构对比")
        print("="*60)
        
        comparison = """
🔧 手动实现 (enhanced_chat.py):
├── 手动状态管理 (self.user_profile, self.messages)
├── 复杂的条件判断逻辑
├── 手动工具调用和错误处理
├── 硬编码的工作流程
└── 难以扩展和维护

🚀 LangGraph实现:
├── 声明式状态图 (StateGraph)
├── 清晰的节点和边定义
├── 内置工具执行器 (ToolExecutor)
├── 检查点保存 (SqliteSaver)
├── 条件路由 (conditional_edges)
└── 易于可视化和调试

📈 主要优势:
• 状态管理自动化
• 工作流可视化
• 错误处理标准化  
• 扩展性更强
• 调试更容易
• 代码更简洁
        """
        print(comparison)
    
    async def run_all_demos(self):
        """运行所有演示"""
        print("🚀 开始LangGraph智能体重构演示")
        print("展示LangChain + LangGraph简化感知-决策-行动架构")
        
        try:
            # 1. 单个工具测试
            await self.demo_individual_tools()
            
            # 2. 完整工作流演示
            await self.demo_complete_workflow()
            
            # 3. 架构对比
            await self.demo_architecture_comparison()
            
            print("\\n" + "="*60)
            print("🎉 LangGraph重构演示完成！")
            print("✅ 成功展示了LangGraph简化的智能体架构")
            print("✅ LangChain工具集成MCP数据源访问")
            print("✅ 声明式状态图管理工作流")
            print("✅ 感知-决策-行动循环更清晰简洁")
            print("="*60)
            
        except Exception as e:
            print(f"❌ 演示过程中出错: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """主函数"""
    demo = LangGraphDemo()
    await demo.run_all_demos()


if __name__ == "__main__":
    print("🤖 启动LangGraph智能体重构演示...")
    asyncio.run(main())
