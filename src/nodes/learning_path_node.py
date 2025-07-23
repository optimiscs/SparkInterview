"""
学习路径推荐节点
根据评估结果推荐个性化学习资源
"""
from typing import Dict, Any, List

from ..models.state import InterviewState
from ..tools.vector_search import create_learning_resource_manager
from ..models.spark_client import create_spark_model


class LearningPathNode:
    """学习路径推荐节点"""
    
    def __init__(self):
        # 使用Spark Pro模型 - 高性价比的资源推荐
        self.llm = create_spark_model("pro")
        
        # 学习资源管理器
        self.resource_manager = create_learning_resource_manager()
        
        # 预先添加一些示例学习资源
        self._init_sample_resources()
    
    def _init_sample_resources(self):
        """初始化示例学习资源"""
        
        sample_resources = [
            # 沟通能力相关
            {
                "title": "如何用STAR法则回答行为面试问题",
                "description": "详细介绍STAR法则的应用技巧和实际案例",
                "url": "https://example.com/star-method",
                "type": "article",
                "competency": "communication_ability",
                "difficulty": "beginner"
            },
            {
                "title": "技术面试中的有效沟通策略",
                "description": "提升技术面试中的表达能力和沟通技巧",
                "url": "https://example.com/tech-communication",
                "type": "video",
                "competency": "communication_ability",
                "difficulty": "intermediate"
            },
            
            # 逻辑思维相关
            {
                "title": "结构化思维训练课程",
                "description": "系统性培养逻辑思维和问题分析能力",
                "url": "https://example.com/structured-thinking",
                "type": "course",
                "competency": "logical_thinking",
                "difficulty": "beginner"
            },
            {
                "title": "系统设计思维方法论",
                "description": "学习如何系统性地分析和解决复杂技术问题",
                "url": "https://example.com/system-design-thinking",
                "type": "article",
                "competency": "logical_thinking",
                "difficulty": "advanced"
            },
            
            # 专业知识相关
            {
                "title": "机器学习基础知识体系",
                "description": "从零开始的机器学习知识框架和学习路径",
                "url": "https://example.com/ml-basics",
                "type": "course",
                "competency": "professional_knowledge",
                "difficulty": "beginner"
            },
            {
                "title": "后端开发最佳实践指南",
                "description": "涵盖架构设计、数据库优化、性能调优等核心知识",
                "url": "https://example.com/backend-best-practices",
                "type": "book",
                "competency": "professional_knowledge",
                "difficulty": "intermediate"
            },
            
            # 抗压能力相关
            {
                "title": "面试焦虑管理技巧",
                "description": "学习如何在面试中保持冷静和自信",
                "url": "https://example.com/interview-anxiety",
                "type": "article",
                "competency": "stress_resilience",
                "difficulty": "beginner"
            },
            {
                "title": "职场压力管理与心理建设",
                "description": "提升心理韧性和压力应对能力",
                "url": "https://example.com/stress-management",
                "type": "course",
                "competency": "stress_resilience",
                "difficulty": "intermediate"
            }
        ]
        
        try:
            self.resource_manager.add_resources(sample_resources)
            print("✅ 学习资源库初始化完成")
        except Exception as e:
            print(f"⚠️ 学习资源库初始化失败: {e}")
    
    def _identify_weak_areas(self, assessment: Dict[str, Any]) -> List[str]:
        """识别需要改进的能力领域"""
        
        weak_areas = []
        
        # 找出分数低于6分的维度
        for dimension, data in assessment.items():
            if isinstance(data, dict) and "score" in data:
                score = data["score"]
                if score < 6:
                    weak_areas.append(dimension)
        
        # 如果没有明显薄弱项，选择分数最低的两项
        if not weak_areas:
            scores = []
            for dimension, data in assessment.items():
                if isinstance(data, dict) and "score" in data:
                    scores.append((dimension, data["score"]))
            
            # 按分数排序，取最低的两项
            scores.sort(key=lambda x: x[1])
            weak_areas = [dim for dim, score in scores[:2]]
        
        return weak_areas
    
    def _search_resources_for_competency(
        self, 
        competency: str, 
        count: int = 3
    ) -> List[Dict[str, Any]]:
        """为特定能力搜索学习资源"""
        
        try:
            resources = self.resource_manager.search_resources(competency, count)
            return resources
        except Exception as e:
            print(f"⚠️ 搜索 {competency} 相关资源失败: {e}")
            return []
    
    def _generate_custom_learning_plan(
        self, 
        state: InterviewState,
        weak_areas: List[str],
        resources: List[Dict[str, Any]]
    ) -> str:
        """生成个性化学习计划"""
        
        user_info = state["user_info"]
        assessment = state["multimodal_analysis"].comprehensive_assessment
        
        # 构建学习计划生成提示
        plan_prompt = f"""
请为以下候选人制定一个个性化的学习提升计划：

候选人信息：
- 姓名：{user_info.name}
- 目标岗位：{user_info.target_position}
- 技术领域：{user_info.target_field}

面试评估结果：
"""
        
        # 添加评估详情
        for dimension, data in assessment.items():
            if isinstance(data, dict):
                score = data.get("score", 5)
                comment = data.get("comment", "")
                plan_prompt += f"- {dimension}: {score}/10 - {comment}\n"
        
        plan_prompt += f"""
需要重点提升的领域：{', '.join(weak_areas)}

请生成一个为期3个月的学习计划，包括：
1. 学习目标设定
2. 分阶段学习安排
3. 具体学习建议
4. 自我检验方法

要求：
- 计划具体可行
- 针对性强
- 循序渐进
- 包含实践环节

请用markdown格式输出。
"""
        
        try:
            response = self.llm(plan_prompt)
            return response.strip()
        except Exception as e:
            print(f"⚠️ 学习计划生成失败: {e}")
            return "学习计划生成失败，建议咨询专业导师制定个性化方案。"
    
    def generate_learning_path(self, state: InterviewState) -> InterviewState:
        """生成学习路径推荐"""
        
        print("🎯 生成学习路径推荐...")
        
        try:
            # 获取评估结果
            analysis = state.get("multimodal_analysis")
            if not analysis or not analysis.comprehensive_assessment:
                raise Exception("缺少评估结果，无法推荐学习路径")
            
            assessment = analysis.comprehensive_assessment
            
            print("  🔍 识别薄弱领域...")
            # 识别需要改进的领域
            weak_areas = self._identify_weak_areas(assessment)
            
            print(f"  📚 为 {len(weak_areas)} 个领域搜索学习资源...")
            # 为每个薄弱领域搜索资源
            all_resources = []
            
            for competency in weak_areas:
                resources = self._search_resources_for_competency(competency, 2)
                all_resources.extend(resources)
            
            # 如果没有足够的资源，添加通用资源
            if len(all_resources) < 3:
                general_resources = self._search_resources_for_competency("professional_knowledge", 3)
                all_resources.extend(general_resources)
            
            # 去重并限制数量
            unique_resources = []
            seen_titles = set()
            
            for resource in all_resources:
                title = resource.get("metadata", {}).get("title", "")
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    unique_resources.append(resource)
                
                if len(unique_resources) >= 5:  # 最多5个资源
                    break
            
            print("  📋 生成个性化学习计划...")
            # 生成学习计划
            learning_plan = self._generate_custom_learning_plan(
                state, weak_areas, unique_resources
            )
            
            # 更新状态
            state["learning_resources"] = unique_resources
            state["metadata"]["learning_plan"] = learning_plan
            state["metadata"]["weak_areas"] = weak_areas
            
            # 打印推荐摘要
            self._print_learning_summary(weak_areas, unique_resources)
            
            print("✅ 学习路径推荐完成")
            return state
            
        except Exception as e:
            error_msg = f"学习路径生成失败: {str(e)}"
            print(f"❌ {error_msg}")
            state["errors"].append(error_msg)
            return state
    
    def _print_learning_summary(
        self, 
        weak_areas: List[str], 
        resources: List[Dict[str, Any]]
    ):
        """打印学习推荐摘要"""
        
        print("\n🎯 学习路径推荐摘要")
        print("=" * 40)
        
        print("📈 重点提升领域:")
        for area in weak_areas:
            area_names = {
                "professional_knowledge": "专业知识",
                "skill_match": "技能匹配",
                "communication_ability": "语言表达",
                "logical_thinking": "逻辑思维",
                "stress_resilience": "抗压能力"
            }
            area_name = area_names.get(area, area)
            print(f"  • {area_name}")
        
        print(f"\n📚 推荐学习资源 ({len(resources)}个):")
        for i, resource in enumerate(resources, 1):
            metadata = resource.get("metadata", {})
            title = metadata.get("title", "未知标题")
            resource_type = metadata.get("type", "article")
            print(f"  {i}. {title} ({resource_type})")
        
        print("=" * 40)


def create_learning_path_node() -> LearningPathNode:
    """创建学习路径推荐节点实例"""
    return LearningPathNode() 