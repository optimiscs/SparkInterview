"""
技能匹配分析工具
使用Sentence-Transformer进行语义相似度计算，评估技能匹配度
"""
import numpy as np
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import logging
from pathlib import Path
import re

try:
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("sklearn not available, using fallback similarity calculation")


class SkillMatcher:
    """技能匹配分析器"""
    
    def __init__(self):
        # 尝试加载Sentence-Transformer模型
        self.model = None
        self._load_sentence_transformer()
        
        # 技能关键词库
        self.skill_categories = {
            'programming_languages': [
                'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'go', 'rust',
                'php', 'ruby', 'swift', 'kotlin', 'scala', 'r', 'matlab'
            ],
            'web_frameworks': [
                'react', 'vue', 'angular', 'django', 'flask', 'spring', 'express',
                'fastapi', 'laravel', 'rails', 'nextjs', 'nuxt'
            ],
            'databases': [
                'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
                'oracle', 'sqlite', 'cassandra', 'dynamodb'
            ],
            'cloud_platforms': [
                'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform',
                'jenkins', 'gitlab', 'github actions'
            ],
            'ai_ml': [
                'tensorflow', 'pytorch', 'scikit-learn', 'pandas', 'numpy',
                'opencv', 'nlp', 'deep learning', 'machine learning', 'neural networks'
            ],
            'tools': [
                'git', 'linux', 'bash', 'vim', 'vscode', 'intellij',
                'postman', 'swagger', 'jira', 'confluence'
            ]
        }
        
        # 展开所有技能关键词
        self.all_skills = []
        for category, skills in self.skill_categories.items():
            self.all_skills.extend(skills)
    
    def _load_sentence_transformer(self):
        """加载Sentence-Transformer模型"""
        
        # 尝试不同的模型，按优先级排序
        model_candidates = [
            'all-MiniLM-L6-v2',  # 轻量级，速度快
            'paraphrase-multilingual-MiniLM-L12-v2',  # 多语言支持
            'all-mpnet-base-v2'  # 高质量但较大
        ]
        
        for model_name in model_candidates:
            try:
                self.model = SentenceTransformer(model_name)
                print(f"✅ 加载Sentence-Transformer模型成功: {model_name}")
                return
            except Exception as e:
                logging.warning(f"加载模型 {model_name} 失败: {e}")
        
        print("⚠️ 无法加载Sentence-Transformer模型，将使用关键词匹配")
    
    def analyze_skill_match(
        self, 
        answer_text: str, 
        resume_skills: List[str],
        job_requirements: List[str]
    ) -> Dict[str, Any]:
        """分析技能匹配度"""
        
        # 提取回答中的技能
        mentioned_skills = self._extract_skills_from_text(answer_text)
        
        # 计算各种匹配度
        if self.model is not None:
            semantic_scores = self._calculate_semantic_similarity(
                answer_text, resume_skills, job_requirements
            )
        else:
            semantic_scores = self._fallback_similarity_calculation(
                mentioned_skills, resume_skills, job_requirements
            )
        
        # 技能一致性分析
        consistency_analysis = self._analyze_skill_consistency(
            mentioned_skills, resume_skills
        )
        
        # 岗位匹配度分析
        job_match_analysis = self._analyze_job_requirement_match(
            mentioned_skills, job_requirements
        )
        
        # 综合评分
        overall_score = self._calculate_overall_skill_score(
            semantic_scores, consistency_analysis, job_match_analysis
        )
        
        return {
            'mentioned_skills': mentioned_skills,
            'semantic_similarity': semantic_scores,
            'skill_consistency': consistency_analysis,
            'job_requirement_match': job_match_analysis,
            'overall_skill_score': overall_score,
            'detailed_analysis': self._generate_detailed_skill_analysis(
                mentioned_skills, resume_skills, job_requirements, overall_score
            )
        }
    
    def _extract_skills_from_text(self, text: str) -> Dict[str, List[str]]:
        """从文本中提取技能关键词"""
        
        text_lower = text.lower()
        found_skills = {category: [] for category in self.skill_categories.keys()}
        
        # 关键词匹配
        for category, skills in self.skill_categories.items():
            for skill in skills:
                # 简单的关键词匹配
                if skill.lower() in text_lower:
                    found_skills[category].append(skill)
                
                # 处理一些常见的变体
                skill_variations = self._get_skill_variations(skill)
                for variation in skill_variations:
                    if variation.lower() in text_lower:
                        if skill not in found_skills[category]:
                            found_skills[category].append(skill)
        
        # 过滤空的类别
        found_skills = {k: v for k, v in found_skills.items() if v}
        
        return found_skills
    
    def _get_skill_variations(self, skill: str) -> List[str]:
        """获取技能的常见变体"""
        
        variations = [skill]
        
        # 一些常见的技能别名
        aliases = {
            'javascript': ['js', 'node.js', 'nodejs'],
            'typescript': ['ts'],
            'react': ['reactjs', 'react.js'],
            'vue': ['vuejs', 'vue.js'],
            'python': ['py'],
            'postgresql': ['postgres'],
            'machine learning': ['ml', '机器学习'],
            'deep learning': ['dl', '深度学习'],
            'artificial intelligence': ['ai', '人工智能'],
            'natural language processing': ['nlp', '自然语言处理']
        }
        
        if skill in aliases:
            variations.extend(aliases[skill])
        
        return variations
    
    def _calculate_semantic_similarity(
        self, 
        answer_text: str,
        resume_skills: List[str], 
        job_requirements: List[str]
    ) -> Dict[str, float]:
        """使用Sentence-Transformer计算语义相似度"""
        
        try:
            # 准备文本
            texts = [answer_text]
            
            # 添加简历技能描述
            resume_text = " ".join(resume_skills) if resume_skills else ""
            if resume_text:
                texts.append(resume_text)
            
            # 添加岗位要求描述
            job_text = " ".join(job_requirements) if job_requirements else ""
            if job_text:
                texts.append(job_text)
            
            # 生成嵌入
            embeddings = self.model.encode(texts)
            
            scores = {}
            
            # 计算与简历的相似度
            if len(embeddings) >= 2 and resume_text:
                if SKLEARN_AVAILABLE:
                    similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
                else:
                    similarity = self._manual_cosine_similarity(embeddings[0], embeddings[1])
                scores['resume_similarity'] = float(similarity)
            else:
                scores['resume_similarity'] = 0.0
            
            # 计算与岗位要求的相似度
            if len(embeddings) >= 3 and job_text:
                if SKLEARN_AVAILABLE:
                    similarity = cosine_similarity([embeddings[0]], [embeddings[2]])[0][0]
                else:
                    similarity = self._manual_cosine_similarity(embeddings[0], embeddings[2])
                scores['job_requirement_similarity'] = float(similarity)
            elif len(embeddings) >= 2 and job_text and not resume_text:
                if SKLEARN_AVAILABLE:
                    similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
                else:
                    similarity = self._manual_cosine_similarity(embeddings[0], embeddings[1])
                scores['job_requirement_similarity'] = float(similarity)
            else:
                scores['job_requirement_similarity'] = 0.0
            
            return scores
            
        except Exception as e:
            logging.error(f"语义相似度计算失败: {e}")
            return self._fallback_similarity_calculation(
                self._extract_skills_from_text(answer_text), 
                resume_skills, 
                job_requirements
            )
    
    def _manual_cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """手动计算余弦相似度"""
        
        try:
            dot_product = np.dot(vec1, vec2)
            norm_a = np.linalg.norm(vec1)
            norm_b = np.linalg.norm(vec2)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            return dot_product / (norm_a * norm_b)
        except:
            return 0.0
    
    def _fallback_similarity_calculation(
        self, 
        mentioned_skills: Dict[str, List[str]],
        resume_skills: List[str], 
        job_requirements: List[str]
    ) -> Dict[str, float]:
        """备用的相似度计算方法"""
        
        # 展开提及的技能
        all_mentioned = []
        for skills_list in mentioned_skills.values():
            all_mentioned.extend(skills_list)
        
        # 计算关键词重叠度
        resume_overlap = 0
        if resume_skills:
            resume_skills_lower = [skill.lower() for skill in resume_skills]
            overlap_count = sum(1 for skill in all_mentioned 
                              if any(skill.lower() in resume_skill for resume_skill in resume_skills_lower))
            resume_overlap = overlap_count / len(resume_skills) if resume_skills else 0
        
        job_overlap = 0
        if job_requirements:
            job_requirements_lower = [req.lower() for req in job_requirements]
            overlap_count = sum(1 for skill in all_mentioned 
                              if any(skill.lower() in req for req in job_requirements_lower))
            job_overlap = overlap_count / len(job_requirements) if job_requirements else 0
        
        return {
            'resume_similarity': min(resume_overlap, 1.0),
            'job_requirement_similarity': min(job_overlap, 1.0)
        }
    
    def _analyze_skill_consistency(
        self, 
        mentioned_skills: Dict[str, List[str]], 
        resume_skills: List[str]
    ) -> Dict[str, Any]:
        """分析技能一致性"""
        
        all_mentioned = []
        for skills_list in mentioned_skills.values():
            all_mentioned.extend(skills_list)
        
        if not resume_skills:
            return {
                'consistency_score': 0.5,
                'consistent_skills': [],
                'new_skills': all_mentioned,
                'analysis': "无简历技能信息可比较"
            }
        
        resume_skills_lower = [skill.lower() for skill in resume_skills]
        
        # 找出一致的技能
        consistent_skills = []
        new_skills = []
        
        for skill in all_mentioned:
            if any(skill.lower() in resume_skill.lower() or 
                   resume_skill.lower() in skill.lower() for resume_skill in resume_skills_lower):
                consistent_skills.append(skill)
            else:
                new_skills.append(skill)
        
        # 计算一致性分数
        if all_mentioned:
            consistency_score = len(consistent_skills) / len(all_mentioned)
        else:
            consistency_score = 1.0  # 如果没有提及技能，认为是一致的
        
        return {
            'consistency_score': consistency_score,
            'consistent_skills': consistent_skills,
            'new_skills': new_skills,
            'analysis': self._generate_consistency_analysis(
                consistency_score, len(consistent_skills), len(new_skills)
            )
        }
    
    def _analyze_job_requirement_match(
        self, 
        mentioned_skills: Dict[str, List[str]], 
        job_requirements: List[str]
    ) -> Dict[str, Any]:
        """分析岗位要求匹配度"""
        
        all_mentioned = []
        for skills_list in mentioned_skills.values():
            all_mentioned.extend(skills_list)
        
        if not job_requirements:
            return {
                'match_score': 0.5,
                'matched_requirements': [],
                'missing_requirements': [],
                'analysis': "无岗位要求信息可比较"
            }
        
        # 找出匹配的要求
        matched_requirements = []
        missing_requirements = []
        
        for requirement in job_requirements:
            requirement_lower = requirement.lower()
            
            # 检查是否有相关技能被提及
            is_matched = any(
                skill.lower() in requirement_lower or requirement_lower in skill.lower()
                for skill in all_mentioned
            )
            
            if is_matched:
                matched_requirements.append(requirement)
            else:
                missing_requirements.append(requirement)
        
        # 计算匹配分数
        if job_requirements:
            match_score = len(matched_requirements) / len(job_requirements)
        else:
            match_score = 1.0
        
        return {
            'match_score': match_score,
            'matched_requirements': matched_requirements,
            'missing_requirements': missing_requirements,
            'analysis': self._generate_job_match_analysis(
                match_score, len(matched_requirements), len(missing_requirements)
            )
        }
    
    def _calculate_overall_skill_score(
        self, 
        semantic_scores: Dict[str, float],
        consistency_analysis: Dict[str, Any],
        job_match_analysis: Dict[str, Any]
    ) -> float:
        """计算综合技能分数"""
        
        # 权重设计
        weights = {
            'semantic_resume': 0.3,
            'semantic_job': 0.4,
            'consistency': 0.2,
            'job_match': 0.1
        }
        
        score = 0.0
        score += semantic_scores.get('resume_similarity', 0) * weights['semantic_resume']
        score += semantic_scores.get('job_requirement_similarity', 0) * weights['semantic_job']
        score += consistency_analysis['consistency_score'] * weights['consistency']
        score += job_match_analysis['match_score'] * weights['job_match']
        
        return min(score, 1.0)
    
    def _generate_consistency_analysis(
        self, 
        consistency_score: float, 
        consistent_count: int, 
        new_count: int
    ) -> str:
        """生成一致性分析文本"""
        
        if consistency_score >= 0.8:
            return f"优秀：提及的{consistent_count}个技能与简历高度一致"
        elif consistency_score >= 0.6:
            return f"良好：提及的技能中有{consistent_count}个与简历一致，{new_count}个为新技能"
        elif consistency_score >= 0.4:
            return f"中等：技能描述与简历部分一致，建议保持一致性"
        else:
            return f"需要改进：提及的技能与简历一致性较低，可能存在不实描述"
    
    def _generate_job_match_analysis(
        self, 
        match_score: float, 
        matched_count: int, 
        missing_count: int
    ) -> str:
        """生成岗位匹配分析文本"""
        
        if match_score >= 0.8:
            return f"优秀：很好地展示了{matched_count}项岗位要求的技能"
        elif match_score >= 0.6:
            return f"良好：展示了{matched_count}项相关技能，还可进一步突出{missing_count}项要求"
        elif match_score >= 0.4:
            return f"中等：部分匹配岗位要求，建议更多展示相关技能"
        else:
            return f"需要改进：技能展示与岗位要求匹配度较低"
    
    def _generate_detailed_skill_analysis(
        self, 
        mentioned_skills: Dict[str, List[str]],
        resume_skills: List[str], 
        job_requirements: List[str],
        overall_score: float
    ) -> str:
        """生成详细的技能分析报告"""
        
        analysis_parts = []
        
        # 技能提及情况
        if mentioned_skills:
            skills_summary = []
            for category, skills in mentioned_skills.items():
                if skills:
                    skills_summary.append(f"{category}: {', '.join(skills)}")
            
            if skills_summary:
                analysis_parts.append(f"在回答中提及的技能包括：{'; '.join(skills_summary)}")
        else:
            analysis_parts.append("回答中未明确提及具体技能")
        
        # 综合评价
        if overall_score >= 0.8:
            analysis_parts.append("技能展示优秀，很好地匹配了岗位要求")
        elif overall_score >= 0.6:
            analysis_parts.append("技能展示良好，基本符合岗位要求")
        elif overall_score >= 0.4:
            analysis_parts.append("技能展示中等，可以更好地突出相关技能")
        else:
            analysis_parts.append("建议在回答中更明确地展示相关技能和经验")
        
        return "。".join(analysis_parts) + "。"


def create_skill_matcher() -> SkillMatcher:
    """创建技能匹配器实例"""
    return SkillMatcher() 