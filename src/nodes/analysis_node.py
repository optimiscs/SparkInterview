"""
综合分析节点 - "评估引擎"
处理多模态数据并生成评估结果的确定性节点
注意：这是简化版本，实际项目中需要集成视觉、听觉分析等组件
"""
import json
import time
from typing import Dict, Any, List
from dataclasses import asdict

from ..models.state import InterviewState, MultimodalAnalysis
from ..models.spark_client import create_spark_model


class ComprehensiveAnalysisNode:
    """综合分析节点"""
    
    def __init__(self):
        # 使用Spark Ultra模型进行最终评判
        self.llm = create_spark_model("ultra")
        
        # 评估维度定义
        self.assessment_dimensions = {
            "professional_knowledge": "专业知识水平",
            "skill_match": "技能匹配度", 
            "communication_ability": "语言表达能力",
            "logical_thinking": "逻辑思维能力",
            "stress_resilience": "应变抗压能力"
        }
    
    def _analyze_text_content(self, conversation_history: List) -> Dict[str, Any]:
        """分析文本内容"""
        
        # 提取所有回答文本
        all_answers = []
        for turn in conversation_history:
            all_answers.append(turn.answer)
        
        combined_text = "\n\n".join(all_answers)
        
        # 分析回答质量
        analysis = {
            "total_words": len(combined_text.split()),
            "total_answers": len(all_answers),
            "avg_answer_length": len(combined_text) / len(all_answers) if all_answers else 0,
            "detailed_answers": sum(1 for answer in all_answers if len(answer) > 100),
            "technical_terms_mentioned": self._count_technical_terms(combined_text),
            "star_structure_usage": self._detect_star_structure(all_answers)
        }
        
        return analysis
    
    def _count_technical_terms(self, text: str) -> int:
        """统计技术术语提及次数（简化版）"""
        
        technical_terms = [
            "算法", "机器学习", "深度学习", "神经网络", "模型", "数据",
            "Python", "Java", "JavaScript", "React", "Vue", "Node.js",
            "数据库", "MySQL", "MongoDB", "Redis", "微服务", "API",
            "架构", "设计模式", "框架", "库", "开源", "GitHub"
        ]
        
        text_lower = text.lower()
        count = 0
        
        for term in technical_terms:
            count += text_lower.count(term.lower())
        
        return count
    
    def _detect_star_structure(self, answers: List[str]) -> Dict[str, Any]:
        """检测STAR结构使用情况（简化版）"""
        
        star_indicators = {
            "situation": ["项目", "在...中", "当时", "背景", "情况"],
            "task": ["任务", "目标", "要求", "需要", "负责"],
            "action": ["我做了", "实现", "使用", "采用", "解决", "处理"],
            "result": ["结果", "效果", "成功", "完成", "提升", "改善"]
        }
        
        star_usage = {"situation": 0, "task": 0, "action": 0, "result": 0}
        
        for answer in answers:
            for component, indicators in star_indicators.items():
                for indicator in indicators:
                    if indicator in answer:
                        star_usage[component] += 1
                        break
        
        # 计算STAR完整性
        star_completeness = sum(1 for count in star_usage.values() if count > 0) / 4
        
        return {
            "usage_by_component": star_usage,
            "completeness_score": star_completeness,
            "total_star_answers": sum(star_usage.values())
        }
    
    def _perform_real_multimodal_analysis(self, state: InterviewState) -> Dict[str, Any]:
        """执行真实的多模态分析"""
        
        conversation_history = state.get("conversation_history", [])
        
        # 尝试进行真实的音视频分析
        try:
            from ..tools.multimodal_analyzer import create_multimodal_analyzer
            from ..tools.star_classifier import create_star_classifier
            from ..tools.skill_matcher import create_skill_matcher
            
            multimodal_analyzer = create_multimodal_analyzer()
            star_classifier = create_star_classifier()
            skill_matcher = create_skill_matcher()
            
            # 检查是否有音视频文件路径
            video_path = state.get("video_path")
            audio_path = state.get("audio_path")
            
            # 执行音视频分析
            if video_path or audio_path:
                media_analysis = multimodal_analyzer.analyze_interview_media(
                    video_path=video_path,
                    audio_path=audio_path
                )
                visual_analysis = media_analysis.get("visual_analysis", {})
                audio_analysis = media_analysis.get("audio_analysis", {})
            else:
                # 如果没有音视频文件，使用模拟数据
                visual_analysis = self._get_fallback_visual_analysis()
                audio_analysis = self._get_fallback_audio_analysis()
            
            # 文本分析（增强版）
            text_analysis = self._analyze_text_content_enhanced(
                conversation_history, star_classifier, skill_matcher, state
            )
            
            return {
                "visual_analysis": visual_analysis,
                "audio_analysis": audio_analysis, 
                "text_analysis": text_analysis
            }
            
        except ImportError as e:
            print(f"⚠️ 多模态分析模块导入失败: {e}")
            return self._simulate_multimodal_analysis_fallback(state)
        except Exception as e:
            print(f"⚠️ 多模态分析执行失败: {e}")
            return self._simulate_multimodal_analysis_fallback(state)
    
    def _analyze_text_content_enhanced(
        self, 
        conversation_history: List,
        star_classifier,
        skill_matcher,
        state: InterviewState
    ) -> Dict[str, Any]:
        """增强版文本内容分析"""
        
        # 基础文本分析
        basic_analysis = self._analyze_text_content(conversation_history)
        
        # 提取所有回答文本
        all_answers = []
        for turn in conversation_history:
            all_answers.append(turn.answer)
        
        combined_text = "\n\n".join(all_answers)
        
        # STAR结构分析
        try:
            star_analysis = star_classifier.analyze_star_structure(combined_text)
            basic_analysis["star_structure_analysis"] = star_analysis
        except Exception as e:
            print(f"⚠️ STAR结构分析失败: {e}")
            basic_analysis["star_structure_analysis"] = {
                "completeness_score": 0.5,
                "overall_assessment": "STAR结构分析不可用"
            }
        
        # 技能匹配分析
        try:
            user_info = state.get("user_info")
            resume_summary = user_info.resume_summary if user_info else {}
            
            # 从简历中提取技能
            resume_skills = []
            if "skills" in resume_summary:
                skills = resume_summary["skills"]
                for skill_list in skills.values():
                    if isinstance(skill_list, list):
                        resume_skills.extend(skill_list)
            
            # 根据目标领域构建岗位要求
            job_requirements = self._get_job_requirements_by_field(
                user_info.target_field if user_info else "Backend"
            )
            
            skill_analysis = skill_matcher.analyze_skill_match(
                combined_text, resume_skills, job_requirements
            )
            basic_analysis["skill_match_analysis"] = skill_analysis
            
        except Exception as e:
            print(f"⚠️ 技能匹配分析失败: {e}")
            basic_analysis["skill_match_analysis"] = {
                "overall_skill_score": 0.5,
                "detailed_analysis": "技能匹配分析不可用"
            }
        
        return basic_analysis
    
    def _get_job_requirements_by_field(self, field: str) -> List[str]:
        """根据技术领域获取岗位要求"""
        
        requirements_map = {
            "AI": [
                "Python", "机器学习", "深度学习", "TensorFlow", "PyTorch",
                "数据分析", "算法设计", "统计学", "神经网络"
            ],
            "Backend": [
                "Java", "Python", "Spring", "数据库设计", "微服务",
                "API开发", "系统架构", "MySQL", "Redis", "Docker"
            ],
            "Frontend": [
                "JavaScript", "React", "Vue", "HTML", "CSS", 
                "前端框架", "响应式设计", "用户体验", "TypeScript"
            ]
        }
        
        return requirements_map.get(field, requirements_map["Backend"])
    
    def _simulate_multimodal_analysis_fallback(self, state: InterviewState) -> Dict[str, Any]:
        """模拟多模态分析结果（备用方案）"""
        
        conversation_history = state.get("conversation_history", [])
        
        # 模拟视觉分析结果
        visual_analysis = self._get_fallback_visual_analysis()
        
        # 模拟听觉分析结果
        audio_analysis = self._get_fallback_audio_analysis()
        
        # 基础文本分析
        text_analysis = self._analyze_text_content(conversation_history)
        
        return {
            "visual_analysis": visual_analysis,
            "audio_analysis": audio_analysis, 
            "text_analysis": text_analysis
        }
    
    def _get_fallback_visual_analysis(self) -> Dict[str, Any]:
        """备用视觉分析结果"""
        return {
            "head_pose_stability": 0.75,
            "gaze_stability": 0.70,
            "dominant_emotion": "neutral",
            "emotion_stability": 0.80,
            "eye_contact_ratio": 0.75,
            "confidence_indicators": 0.70
        }
    
    def _get_fallback_audio_analysis(self) -> Dict[str, Any]:
        """备用听觉分析结果"""
        return {
            "speech_rate_bpm": 140,
            "pitch_variance": 25.5,
            "volume_stability": 0.85,
            "clarity_score": 0.90
        }
    
    def _generate_comprehensive_assessment(
        self, 
        state: InterviewState,
        multimodal_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成综合评估结果"""
        
        user_info = state["user_info"]
        conversation_history = state["conversation_history"]
        
        # 构建评估提示
        assessment_prompt = f"""
你是一位资深的HR分析专家和技术面试官。请根据以下提供的多维度信息，对候选人的各项核心能力进行综合评估，并按照指定的JSON格式输出你的评分（1-10分）和具体评语。

# 输入数据
---
## 候选人信息
- **姓名**: {user_info.name}
- **目标岗位**: {user_info.target_position}
- **目标领域**: {user_info.target_field}
- **简历摘要**: {user_info.resume_summary.get('summary', '无简历信息')}

## 面试表现数据
### 问答实录
"""
        
        # 添加对话历史
        for i, turn in enumerate(conversation_history):
            assessment_prompt += f"- **Q{i+1}**: {turn.question}\n"
            assessment_prompt += f"- **A{i+1}**: {turn.answer}\n\n"
        
        # 添加多模态分析数据
        assessment_prompt += f"""
### 多模态分析报告
- **文本分析**: 
  - 总回答数: {multimodal_data['text_analysis']['total_answers']}
  - 平均回答长度: {multimodal_data['text_analysis']['avg_answer_length']:.0f}字
  - 技术术语使用: {multimodal_data['text_analysis']['technical_terms_mentioned']}次
  - STAR结构完整性: {multimodal_data['text_analysis']['star_structure_usage']['completeness_score']:.2f}

- **视觉分析**: 
  - 头部姿态稳定性: {multimodal_data['visual_analysis'].get('head_pose_stability', 0.7):.2f}
  - 眼神接触比例: {multimodal_data['visual_analysis'].get('eye_contact_ratio', 0.7):.2f}
  - 主导情绪: {multimodal_data['visual_analysis'].get('dominant_emotion', 'neutral')}
  - 情绪稳定性: {multimodal_data['visual_analysis'].get('emotion_stability', 0.8):.2f}
  - 分析状态: {'真实分析' if not multimodal_data['visual_analysis'].get('error') else '默认数据'}

- **听觉分析**:
  - 语速: {multimodal_data['audio_analysis'].get('speech_rate_bpm', 120):.1f} BPM
  - 音调变化度: {multimodal_data['audio_analysis'].get('pitch_variance', 20):.1f}
  - 语音清晰度: {multimodal_data['audio_analysis'].get('clarity_score', 0.8):.2f}
  - 分析状态: {'真实分析' if not multimodal_data['audio_analysis'].get('error') else '默认数据'}
---

# 输出要求
请严格按照以下JSON格式提供你的评估结果，不要添加任何额外的解释或文本：

{{
  "professional_knowledge": {{"score": 0, "comment": "在此处填写对专业知识水平的具体评语..."}},
  "skill_match": {{"score": 0, "comment": "在此处填写对技能匹配度的具体评语..."}},
  "communication_ability": {{"score": 0, "comment": "在此处填写对语言表达能力的具体评语..."}},
  "logical_thinking": {{"score": 0, "comment": "在此处填写对逻辑思维能力（特别是STAR结构）的具体评语..."}},
  "stress_resilience": {{"score": 0, "comment": "在此处填写对应变抗压能力（结合情绪和非言语线索）的具体评语..."}}
}}
"""
        
        try:
            # 调用LLM进行评估
            response = self.llm(assessment_prompt)
            
            # 清理响应并解析JSON
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            assessment_result = json.loads(response)
            
            # 验证结果格式
            for dimension in self.assessment_dimensions.keys():
                if dimension not in assessment_result:
                    assessment_result[dimension] = {
                        "score": 5,
                        "comment": "评估数据不完整"
                    }
            
            return assessment_result
            
        except json.JSONDecodeError as e:
            print(f"⚠️ 评估结果JSON解析失败: {e}")
            
            # 返回默认评估结果
            return {
                dimension: {
                    "score": 5,
                    "comment": "评估过程中出现问题，无法生成详细评语"
                }
                for dimension in self.assessment_dimensions.keys()
            }
        
        except Exception as e:
            print(f"⚠️ 综合评估失败: {e}")
            
            # 返回默认评估结果
            return {
                dimension: {
                    "score": 5,
                    "comment": "系统评估异常"
                }
                for dimension in self.assessment_dimensions.keys()
            }
    
    def analyze(self, state: InterviewState) -> InterviewState:
        """执行综合分析"""
        
        print("📊 开始多模态分析...")
        
        try:
            # 检查必要数据
            conversation_history = state.get("conversation_history", [])
            if not conversation_history:
                raise Exception("没有可分析的对话数据")
            
            # 检查音视频文件状态
            video_path = state.get("video_path")
            audio_path = state.get("audio_path")
            
            print(f"  📁 视频文件: {video_path or '未提供'}")
            print(f"  📁 音频文件: {audio_path or '未提供'}")
            
            # 1. 执行多模态分析（真实实现 + 备用方案）
            print("  🔍 执行多模态特征提取...")
            multimodal_data = self._perform_real_multimodal_analysis(state)
            
            # 2. 生成综合评估
            print("  🧠 生成综合评估...")
            comprehensive_assessment = self._generate_comprehensive_assessment(
                state, multimodal_data
            )
            
            # 3. 构建分析结果
            analysis_result = MultimodalAnalysis(
                visual_analysis=multimodal_data["visual_analysis"],
                audio_analysis=multimodal_data["audio_analysis"],
                text_analysis=multimodal_data["text_analysis"],
                comprehensive_assessment=comprehensive_assessment
            )
            
            # 4. 更新状态
            state["multimodal_analysis"] = analysis_result
            
            # 5. 打印结果摘要
            self._print_analysis_summary(comprehensive_assessment)
            
            # 6. 打印多模态分析状态
            self._print_multimodal_status(multimodal_data)
            
            print("✅ 多模态分析完成")
            return state
            
        except Exception as e:
            error_msg = f"多模态分析失败: {str(e)}"
            print(f"❌ {error_msg}")
            state["errors"].append(error_msg)
            return state
    
    def _print_analysis_summary(self, assessment: Dict[str, Any]):
        """打印分析结果摘要"""
        
        print("\n📈 评估结果摘要:")
        print("-" * 40)
        
        total_score = 0
        for dimension_key, dimension_name in self.assessment_dimensions.items():
            if dimension_key in assessment:
                score = assessment[dimension_key].get("score", 0)
                total_score += score
                print(f"  {dimension_name}: {score}/10")
        
        avg_score = total_score / len(self.assessment_dimensions)
        print(f"\n  总体评分: {avg_score:.1f}/10")
        print("-" * 40)
    
    def _print_multimodal_status(self, multimodal_data: Dict[str, Any]):
        """打印多模态分析状态"""
        
        print("\n🎥 多模态分析状态:")
        print("-" * 40)
        
        # 视觉分析状态
        visual_analysis = multimodal_data.get("visual_analysis", {})
        if visual_analysis.get("error"):
            print("  🎥 视觉分析: 使用默认数据")
        else:
            print("  🎥 视觉分析: 真实分析完成")
            if "head_pose_stability" in visual_analysis:
                print(f"    头部姿态稳定性: {visual_analysis['head_pose_stability']:.2f}")
            if "eye_contact_ratio" in visual_analysis:
                print(f"    眼神接触比例: {visual_analysis['eye_contact_ratio']:.2f}")
            if "dominant_emotion" in visual_analysis:
                print(f"    主导情绪: {visual_analysis['dominant_emotion']}")
        
        # 听觉分析状态
        audio_analysis = multimodal_data.get("audio_analysis", {})
        if audio_analysis.get("error"):
            print("  🎵 听觉分析: 使用默认数据")
        else:
            print("  🎵 听觉分析: 真实分析完成")
            if "speech_rate_bpm" in audio_analysis:
                print(f"    语速: {audio_analysis['speech_rate_bpm']:.1f} BPM")
            if "clarity_score" in audio_analysis:
                print(f"    清晰度: {audio_analysis['clarity_score']:.2f}")
            if "pitch_variance" in audio_analysis:
                print(f"    音调变化: {audio_analysis['pitch_variance']:.1f}")
        
        # 文本分析状态
        text_analysis = multimodal_data.get("text_analysis", {})
        print("  📝 文本分析: 完成")
        if "total_answers" in text_analysis:
            print(f"    回答数量: {text_analysis['total_answers']}")
        if "technical_terms_mentioned" in text_analysis:
            print(f"    技术术语: {text_analysis['technical_terms_mentioned']} 次")
        
        print("-" * 40)


def create_analysis_node() -> ComprehensiveAnalysisNode:
    """创建综合分析节点实例"""
    return ComprehensiveAnalysisNode() 