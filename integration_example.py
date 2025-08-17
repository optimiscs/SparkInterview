"""
智能体集成示例 - 展示感知决策行动架构的完整使用
结合MCP工具进行数据源访问和更新
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List

# 导入智能体相关模块
from api.routers.enhanced_chat import IntelligentInterviewAgent, AgentPerceptionResult, AgentDecision
from src.tools.mcp_database_tool import MCPDatabaseTool, MCPIntegrationTool
from src.models.state import UserInfo
from src.models.spark_client import create_spark_model

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentDemoScenario:
    """智能体使用场景演示"""
    
    def __init__(self):
        self.mcp_tool = MCPIntegrationTool()
        self.db_tool = MCPDatabaseTool()
        
    async def scenario_1_missing_work_experience(self):
        """场景1: 缺失工作经验信息的智能收集"""
        print("\\n" + "="*60)
        print("🎬 场景1: 智能体主动收集缺失的工作经验信息")
        print("="*60)
        
        # 1. 创建用户信息（缺少工作年限）
        user_info = UserInfo(
            user_id="demo_user_001",
            name="张三",
            target_position="算法工程师", 
            target_field="人工智能",
            resume_text="本科毕业，熟悉Python和机器学习，做过几个项目",
            resume_summary={}
        )
        
        # 2. 创建智能面试官
        agent = IntelligentInterviewAgent("demo_session_001", user_info)
        
        print(f"👤 用户: {user_info.name}")
        print(f"📋 应聘职位: {user_info.target_position}")
        print(f"📄 初始简历信息: {user_info.resume_text}")
        
        # 3. 展示初始感知结果
        initial_perception = agent._perception_phase()
        print(f"\\n🧠 智能体感知结果:")
        print(f"   - 信息完整度: {initial_perception.information_completeness:.1%}")
        print(f"   - 缺失信息: {initial_perception.missing_info}")
        print(f"   - 用户情绪: {initial_perception.user_emotion}")
        print(f"   - 建议行动: {initial_perception.suggested_actions}")
        
        # 4. 展示决策过程
        decision = agent._decision_phase(initial_perception)
        print(f"\\n🤖 智能体决策:")
        print(f"   - 行动类型: {decision.action_type}")
        print(f"   - 优先级: {decision.priority}")
        print(f"   - 决策原因: {decision.reasoning}")
        
        # 5. 执行行动
        action_result = agent._action_phase(decision)
        print(f"\\n⚡ 智能体行动:")
        print(f"   面试官: {action_result}")
        
        # 6. 模拟用户回答
        user_response = "我有3年的工作经验，目前在一家AI创业公司做算法工程师"
        print(f"\\n👤 用户回答: {user_response}")
        
        # 7. 使用MCP工具提取信息
        conversation_history = [user_response]
        extraction_result = await self.mcp_tool.intelligent_info_collection(
            user_info.user_id, 
            "demo_session_001",
            conversation_history
        )
        
        print(f"\\n📊 MCP信息提取结果:")
        print(f"   - 是否有更新: {extraction_result['updated']}")
        print(f"   - 提取的信息: {extraction_result['extracted_info']}")
        print(f"   - 当前完整度: {extraction_result['current_completeness']:.1%}")
        print(f"   - 剩余缺失字段: {extraction_result['missing_fields']}")
        
        return extraction_result
    
    async def scenario_2_emotional_support(self):
        """场景2: 情绪感知与支持"""
        print("\\n" + "="*60)
        print("🎬 场景2: 智能体情绪感知与支持")
        print("="*60)
        
        user_info = UserInfo(
            user_id="demo_user_002",
            name="李四",
            target_position="前端工程师",
            target_field="前端开发", 
            resume_text="应届毕业生，担心自己经验不足",
            resume_summary={}
        )
        
        agent = IntelligentInterviewAgent("demo_session_002", user_info)
        
        # 模拟紧张的用户消息
        nervous_message = "我很紧张，担心自己回答不好，经验也不够丰富"
        
        # 感知用户情绪
        perception = agent._perception_phase(nervous_message)
        print(f"🧠 情绪感知:")
        print(f"   - 检测到用户情绪: {perception.user_emotion}")
        print(f"   - 建议行动: {perception.suggested_actions}")
        
        # 决策支持策略
        decision = agent._decision_phase(perception)
        print(f"\\n🤖 支持决策:")
        print(f"   - 行动类型: {decision.action_type}")
        print(f"   - 决策原因: {decision.reasoning}")
        
        # 提供情感支持
        support_response = agent._action_phase(decision)
        print(f"\\n⚡ 情感支持:")
        print(f"   面试官: {support_response}")
        
    async def scenario_3_adaptive_questioning(self):
        """场景3: 自适应问题生成"""
        print("\\n" + "="*60)
        print("🎬 场景3: 基于用户画像的自适应问题生成")
        print("="*60)
        
        # 创建有一定信息的用户
        user_info = UserInfo(
            user_id="demo_user_003",
            name="王五",
            target_position="数据科学家",
            target_field="数据科学",
            resume_text="硕士学历，有2年数据分析经验，熟悉Python、SQL、机器学习",
            resume_summary={}
        )
        
        agent = IntelligentInterviewAgent("demo_session_003", user_info)
        
        # 预先设置一些用户画像信息
        agent.user_profile["basic_info"].update({
            "work_years": 2,
            "education_level": "硕士", 
            "current_company": "数据分析公司"
        })
        agent.user_profile["completeness_score"] = 0.8  # 较高完整度
        
        # 感知当前状态
        perception = agent._perception_phase()
        print(f"🧠 用户画像感知:")
        print(f"   - 信息完整度: {perception.information_completeness:.1%}")
        print(f"   - 缺失信息: {perception.missing_info}")
        
        # 基于高完整度的决策
        decision = agent._decision_phase(perception)
        print(f"\\n🤖 面试策略决策:")
        print(f"   - 行动类型: {decision.action_type}")
        print(f"   - 决策原因: {decision.reasoning}")
        
        # 生成适应性问题
        question_response = agent._action_phase(decision)
        print(f"\\n⚡ 自适应问题:")
        print(f"   面试官: {question_response}")
    
    async def scenario_4_mcp_database_operations(self):
        """场景4: MCP数据库操作演示"""
        print("\\n" + "="*60)
        print("🎬 场景4: MCP数据库操作和数据源访问")
        print("="*60)
        
        # 1. 插入用户画像数据
        profile_data = {
            "basic_info": {
                "work_years": 5,
                "current_company": "科技公司A",
                "education_level": "硕士",
                "graduation_year": 2019,
                "expected_salary": "30-40K"
            },
            "technical_skills": {
                "programming": ["Python", "Java", "JavaScript"],
                "frameworks": ["Django", "React", "TensorFlow"],
                "databases": ["MySQL", "MongoDB", "Redis"]
            },
            "completeness_score": 0.9
        }
        
        print("💾 插入用户画像数据...")
        success = await self.db_tool.insert_user_profile(
            user_id="demo_user_004",
            session_id="demo_session_004", 
            profile_data=profile_data
        )
        print(f"   插入结果: {'✅ 成功' if success else '❌ 失败'}")
        
        # 2. 查询用户画像
        print("\\n🔍 查询用户画像...")
        retrieved_profile = await self.db_tool.get_user_profile(
            user_id="demo_user_004",
            session_id="demo_session_004"
        )
        
        if retrieved_profile:
            print("   查询结果: ✅ 成功")
            print(f"   完整度: {retrieved_profile['completeness_score']:.1%}")
            print(f"   工作年限: {retrieved_profile['work_years']}年")
            print(f"   教育水平: {retrieved_profile['education_level']}")
        else:
            print("   查询结果: ❌ 未找到")
        
        # 3. 更新特定字段
        print("\\n✏️ 更新特定字段...")
        update_success = await self.db_tool.update_specific_field(
            user_id="demo_user_004",
            session_id="demo_session_004",
            field="current_company",
            value="新科技公司B"
        )
        print(f"   更新结果: {'✅ 成功' if update_success else '❌ 失败'}")
        
        # 4. 获取统计信息
        print("\\n📈 获取完整度统计...")
        stats = await self.db_tool.get_completion_statistics()
        if stats:
            print(f"   总用户数: {stats.get('total_users', 0)}")
            print(f"   高完整度用户: {stats.get('high_complete', 0)}")
            print(f"   平均完整度: {stats.get('average_completeness', 0):.1%}")
        
        # 5. 查询信息不完整的用户
        print("\\n🔍 查询信息不完整的用户...")
        incomplete_users = await self.db_tool.query_missing_info_users(limit=5)
        print(f"   找到 {len(incomplete_users)} 个信息不完整的用户")
        
        for user in incomplete_users[:3]:  # 显示前3个
            print(f"   - 用户 {user['user_id']}: 完整度 {user['completeness_score']:.1%}")
    
    async def run_all_scenarios(self):
        """运行所有演示场景"""
        print("🚀 开始智能体集成演示")
        print("展示感知-决策-行动架构 + MCP工具集成")
        
        try:
            # 场景1: 信息收集
            await self.scenario_1_missing_work_experience()
            
            # 场景2: 情绪支持
            await self.scenario_2_emotional_support()
            
            # 场景3: 自适应问题
            await self.scenario_3_adaptive_questioning()
            
            # 场景4: 数据库操作
            await self.scenario_4_mcp_database_operations()
            
            print("\\n" + "="*60)
            print("🎉 所有演示场景完成！")
            print("智能体成功展示了感知-决策-行动的完整循环")
            print("并通过MCP工具实现了数据源的智能访问和更新")
            print("="*60)
            
        except Exception as e:
            print(f"❌ 演示过程中出错: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """主函数 - 运行演示"""
    demo = AgentDemoScenario()
    await demo.run_all_scenarios()


if __name__ == "__main__":
    # 运行演示
    asyncio.run(main())
