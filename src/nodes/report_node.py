"""
报告生成节点
将分析结果转化为用户友好的可视化报告
"""
import os
import json
from typing import Dict, Any, List
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
from datetime import datetime

from ..models.state import InterviewState, InterviewReport
from ..models.spark_client import create_spark_model


class ReportGenerationNode:
    """报告生成节点"""
    
    def __init__(self):
        # 使用Spark Pro模型 - 高性价比的报告生成
        self.llm = create_spark_model("pro")
        
        # 设置中文字体
        self._setup_chinese_font()
        
    def _setup_chinese_font(self):
        """设置matplotlib中文字体"""
        try:
            # 尝试设置常见的中文字体
            chinese_fonts = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
            
            for font_name in chinese_fonts:
                try:
                    plt.rcParams['font.sans-serif'] = [font_name]
                    plt.rcParams['axes.unicode_minus'] = False
                    break
                except:
                    continue
        except Exception as e:
            print(f"⚠️ 中文字体设置失败: {e}")
    
    def _generate_radar_chart(
        self, 
        assessment: Dict[str, Any], 
        session_id: str
    ) -> str:
        """生成能力雷达图"""
        
        try:
            # 准备数据
            dimensions = {
                "专业知识": assessment.get("professional_knowledge", {}).get("score", 5),
                "技能匹配": assessment.get("skill_match", {}).get("score", 5),
                "语言表达": assessment.get("communication_ability", {}).get("score", 5),
                "逻辑思维": assessment.get("logical_thinking", {}).get("score", 5),
                "抗压能力": assessment.get("stress_resilience", {}).get("score", 5)
            }
            
            # 创建雷达图
            categories = list(dimensions.keys())
            values = list(dimensions.values())
            
            # 为了闭合图形，将第一个值添加到末尾
            values += values[:1]
            
            # 计算角度
            angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
            angles += angles[:1]
            
            # 创建图形
            fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))
            
            # 绘制雷达图
            ax.plot(angles, values, 'o-', linewidth=2, label='候选人能力', color='#1f77b4')
            ax.fill(angles, values, alpha=0.25, color='#1f77b4')
            
            # 设置刻度和标签
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(categories, fontsize=12)
            ax.set_ylim(0, 10)
            ax.set_yticks([2, 4, 6, 8, 10])
            ax.set_yticklabels(['2', '4', '6', '8', '10'], fontsize=10)
            ax.grid(True)
            
            # 添加标题
            plt.title('面试能力评估雷达图', fontsize=16, fontweight='bold', pad=20)
            
            # 保存图片
            chart_path = f"./data/cache/radar_chart_{session_id}.png"
            os.makedirs(os.path.dirname(chart_path), exist_ok=True)
            plt.savefig(chart_path, dpi=300, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            plt.close()
            
            return chart_path
            
        except Exception as e:
            print(f"⚠️ 雷达图生成失败: {e}")
            return ""
    
    def _extract_strengths_and_weaknesses(
        self, 
        assessment: Dict[str, Any]
    ) -> tuple[List[str], List[str]]:
        """提取优势和劣势"""
        
        strengths = []
        weaknesses = []
        
        # 根据分数判断优势和劣势
        for dimension, data in assessment.items():
            if isinstance(data, dict) and "score" in data:
                score = data["score"]
                comment = data.get("comment", "")
                
                if score >= 8:
                    strengths.append(f"在{dimension}方面表现出色")
                elif score <= 4:
                    weaknesses.append(f"{dimension}需要进一步提升")
        
        # 如果没有明显的优势或劣势，生成通用描述
        if not strengths:
            strengths.append("整体表现稳定")
        
        if not weaknesses:
            weaknesses.append("建议继续保持并提升各项能力")
        
        return strengths, weaknesses
    
    def _generate_recommendations(
        self, 
        assessment: Dict[str, Any],
        conversation_history: List
    ) -> List[str]:
        """生成改进建议"""
        
        try:
            # 找出分数最低的两个维度
            scores = {}
            for dimension, data in assessment.items():
                if isinstance(data, dict) and "score" in data:
                    scores[dimension] = data["score"]
            
            # 按分数排序，找出最需要改进的维度
            sorted_dimensions = sorted(scores.items(), key=lambda x: x[1])
            weak_dimensions = sorted_dimensions[:2]
            
            recommendations = []
            
            # 针对薄弱环节生成建议
            dimension_suggestions = {
                "professional_knowledge": [
                    "建议加强相关技术领域的理论学习",
                    "多参与技术社区和开源项目",
                    "定期阅读行业技术文档和最佳实践"
                ],
                "skill_match": [
                    "深入学习岗位要求的核心技能",
                    "通过实际项目练习提升技能熟练度",
                    "考虑获得相关技术认证"
                ],
                "communication_ability": [
                    "练习用STAR法则组织回答",
                    "多参加技术分享和演讲活动",
                    "注意表达的逻辑性和条理性"
                ],
                "logical_thinking": [
                    "培养结构化思维方式",
                    "练习问题分析和解决方法",
                    "学习系统性思考框架"
                ],
                "stress_resilience": [
                    "多参加模拟面试练习",
                    "学习压力管理技巧",
                    "增强自信心和心理素质"
                ]
            }
            
            for dimension, score in weak_dimensions:
                suggestions = dimension_suggestions.get(dimension, ["继续加强相关能力"])
                recommendations.extend(suggestions[:2])  # 每个维度取2个建议
            
            return recommendations[:4]  # 最多返回4个建议
            
        except Exception as e:
            print(f"⚠️ 生成建议失败: {e}")
            return ["建议多练习面试技巧", "继续提升专业技能"]
    
    def _generate_detailed_report(
        self, 
        state: InterviewState,
        report: InterviewReport
    ) -> str:
        """生成详细的文字报告"""
        
        user_info = state["user_info"]
        analysis = state["multimodal_analysis"]
        
        report_prompt = f"""
请基于以下面试数据，生成一份专业的面试反馈报告。

候选人信息：
- 姓名：{user_info.name}
- 应聘岗位：{user_info.target_position}
- 技术领域：{user_info.target_field}

面试评估结果：
{json.dumps(analysis.comprehensive_assessment, ensure_ascii=False, indent=2)}

请生成一份包含以下内容的报告：
1. 总体评价（200字左右）
2. 各维度详细分析（每个维度100字左右）
3. 具体改进建议

要求：
- 语言专业、客观
- 既要指出优势，也要指出不足
- 提供具体可行的改进建议
- 语气鼓励性、建设性

请用markdown格式输出。
"""
        
        try:
            response = self.llm(report_prompt)
            return response.strip()
        except Exception as e:
            print(f"⚠️ 详细报告生成失败: {e}")
            return "报告生成出现问题，请联系技术支持。"
    
    def generate_report(self, state: InterviewState) -> InterviewState:
        """生成面试报告"""
        
        print("📋 生成面试报告...")
        
        try:
            # 获取分析结果
            analysis = state.get("multimodal_analysis")
            if not analysis or not analysis.comprehensive_assessment:
                raise Exception("缺少分析结果，无法生成报告")
            
            assessment = analysis.comprehensive_assessment
            session_id = state["session_id"]
            
            print("  📊 生成能力雷达图...")
            # 生成雷达图
            radar_chart_path = self._generate_radar_chart(assessment, session_id)
            
            print("  📝 分析优势和劣势...")
            # 提取优势和劣势
            strengths, weaknesses = self._extract_strengths_and_weaknesses(assessment)
            
            print("  💡 生成改进建议...")
            # 生成建议
            recommendations = self._generate_recommendations(
                assessment, 
                state["conversation_history"]
            )
            
            # 计算总体分数
            total_score = 0
            score_count = 0
            detailed_scores = {}
            
            for dimension, data in assessment.items():
                if isinstance(data, dict) and "score" in data:
                    score = data["score"]
                    total_score += score
                    score_count += 1
                    detailed_scores[dimension] = score
            
            overall_score = total_score / score_count if score_count > 0 else 5.0
            
            print("  📄 生成详细报告...")
            # 创建报告对象
            interview_report = InterviewReport(
                overall_score=overall_score,
                detailed_scores=detailed_scores,
                strengths=strengths,
                weaknesses=weaknesses,
                recommendations=recommendations,
                radar_chart_path=radar_chart_path
            )
            
            # 生成详细的文字报告
            detailed_report = self._generate_detailed_report(state, interview_report)
            
            # 更新状态
            state["interview_report"] = interview_report
            state["metadata"]["detailed_report"] = detailed_report
            state["metadata"]["report_generated_at"] = datetime.now().isoformat()
            
            # 打印报告摘要
            self._print_report_summary(interview_report)
            
            print("✅ 面试报告生成完成")
            return state
            
        except Exception as e:
            error_msg = f"报告生成失败: {str(e)}"
            print(f"❌ {error_msg}")
            state["errors"].append(error_msg)
            return state
    
    def _print_report_summary(self, report: InterviewReport):
        """打印报告摘要"""
        
        print("\n📊 面试报告摘要")
        print("=" * 40)
        print(f"总体评分: {report.overall_score:.1f}/10")
        
        print("\n🎯 详细分数:")
        for dimension, score in report.detailed_scores.items():
            print(f"  {dimension}: {score}/10")
        
        print(f"\n✨ 主要优势:")
        for strength in report.strengths:
            print(f"  • {strength}")
        
        print(f"\n📈 改进建议:")
        for rec in report.recommendations:
            print(f"  • {rec}")
        
        if report.radar_chart_path:
            print(f"\n📊 雷达图已保存至: {report.radar_chart_path}")
        
        print("=" * 40)


def create_report_node() -> ReportGenerationNode:
    """创建报告生成节点实例"""
    return ReportGenerationNode() 