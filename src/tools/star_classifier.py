"""
STAR法则检测分类器
基于BERT的序列句子分类，用于检测面试回答中的STAR结构
"""
import torch
import torch.nn as nn
import numpy as np
from typing import List, Dict, Any, Tuple
from transformers import (
    BertTokenizer, 
    BertForSequenceClassification,
    BertConfig,
    AutoTokenizer,
    AutoModelForSequenceClassification
)
import logging
from pathlib import Path
import re

from ..config.settings import model_config


class STARClassifier:
    """STAR法则分类器"""
    
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.max_length = model_config.MAX_SEQUENCE_LENGTH
        
        # STAR标签映射
        self.label_map = {
            0: 'Other',      # 其他
            1: 'Situation',  # 情境
            2: 'Task',       # 任务
            3: 'Action',     # 行动
            4: 'Result'      # 结果
        }
        
        self.reverse_label_map = {v: k for k, v in self.label_map.items()}
        
        # 尝试加载预训练模型，如果不存在则使用基础BERT
        self.tokenizer = None
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """加载BERT模型"""
        
        model_path = "./models/star_classifier"
        
        if Path(model_path).exists():
            # 加载已训练的模型
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(model_path)
                self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
                self.model.to(self.device)
                self.model.eval()
                print("✅ 加载预训练STAR分类器成功")
                return
            except Exception as e:
                logging.warning(f"加载预训练模型失败: {e}")
        
        # 使用基础BERT模型 + 规则分类器
        try:
            model_name = model_config.BERT_MODEL_NAME
            self.tokenizer = BertTokenizer.from_pretrained(model_name)
            
            # 创建分类器配置
            config = BertConfig.from_pretrained(model_name)
            config.num_labels = len(self.label_map)
            
            self.model = BertForSequenceClassification.from_pretrained(
                model_name, config=config
            )
            self.model.to(self.device)
            self.model.eval()
            
            print("✅ 加载基础BERT模型成功，将使用规则辅助分类")
            
        except Exception as e:
            logging.error(f"模型加载失败: {e}")
            self.tokenizer = None
            self.model = None
            print("⚠️ 模型加载失败，将使用纯规则分类器")
    
    def predict_sentence_roles(self, sentences: List[str]) -> List[Dict[str, Any]]:
        """预测句子的STAR角色"""
        
        if not sentences:
            return []
        
        # 如果模型可用，使用BERT分类
        if self.model is not None and self.tokenizer is not None:
            return self._bert_classify_sentences(sentences)
        else:
            # 否则使用规则分类器
            return self._rule_based_classify_sentences(sentences)
    
    def _bert_classify_sentences(self, sentences: List[str]) -> List[Dict[str, Any]]:
        """使用BERT模型分类句子"""
        
        results = []
        
        try:
            for sentence in sentences:
                # 分词和编码
                inputs = self.tokenizer(
                    sentence,
                    max_length=self.max_length,
                    padding='max_length',
                    truncation=True,
                    return_tensors='pt'
                )
                
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                # 预测
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    logits = outputs.logits
                    probabilities = torch.softmax(logits, dim=1)
                    predicted_id = torch.argmax(probabilities, dim=1).item()
                    confidence = probabilities[0][predicted_id].item()
                
                predicted_label = self.label_map[predicted_id]
                
                # 如果置信度低，使用规则辅助
                if confidence < 0.6:
                    rule_result = self._rule_classify_single_sentence(sentence)
                    if rule_result['confidence'] > 0.5:
                        predicted_label = rule_result['label']
                        confidence = rule_result['confidence']
                
                results.append({
                    'sentence': sentence,
                    'label': predicted_label,
                    'confidence': confidence,
                    'method': 'bert'
                })
                
        except Exception as e:
            logging.error(f"BERT分类失败: {e}")
            return self._rule_based_classify_sentences(sentences)
        
        return results
    
    def _rule_based_classify_sentences(self, sentences: List[str]) -> List[Dict[str, Any]]:
        """基于规则的句子分类"""
        
        results = []
        
        for sentence in sentences:
            result = self._rule_classify_single_sentence(sentence)
            results.append({
                'sentence': sentence,
                'label': result['label'],
                'confidence': result['confidence'],
                'method': 'rule'
            })
        
        return results
    
    def _rule_classify_single_sentence(self, sentence: str) -> Dict[str, Any]:
        """规则分类单个句子"""
        
        sentence = sentence.lower().strip()
        
        # STAR关键词模式
        patterns = {
            'Situation': [
                r'(当时|那时|在.*项目中|在.*公司|背景是|情况是|项目背景)',
                r'(我们面临|遇到了|公司.*需要|团队.*要求)',
                r'(项目.*要求|需求是|目标是)'
            ],
            'Task': [
                r'(我的任务是|负责|需要完成|要求.*完成|目标是)',
                r'(我被分配|分配给我|我的职责|我需要)',
                r'(任务.*包括|工作内容|具体要做)'
            ],
            'Action': [
                r'(我.*采用|我.*使用|我.*实现|我.*开发|我.*设计)',
                r'(我.*分析|我.*研究|我.*优化|我.*改进|我.*解决)',
                r'(具体.*做法|实施.*方案|采取.*措施|使用.*方法)'
            ],
            'Result': [
                r'(结果.*是|最终.*实现|成功.*完成|效果.*显著)',
                r'(提升了.*|减少了.*|增加了.*|改善了.*|优化了.*)',
                r'(获得了.*|达到.*|实现.*增长|节省.*|效率.*提高)'
            ]
        }
        
        # 计算每个类别的匹配分数
        scores = {}
        
        for label, pattern_list in patterns.items():
            score = 0
            for pattern in pattern_list:
                if re.search(pattern, sentence):
                    score += 1
            scores[label] = score / len(pattern_list)  # 归一化
        
        # 添加其他类别
        scores['Other'] = 0
        
        # 如果所有STAR分数都很低，归类为Other
        max_star_score = max(scores[label] for label in ['Situation', 'Task', 'Action', 'Result'])
        
        if max_star_score < 0.2:
            predicted_label = 'Other'
            confidence = 0.7
        else:
            predicted_label = max(scores.items(), key=lambda x: x[1])[0]
            confidence = min(scores[predicted_label] + 0.3, 1.0)  # 基础置信度
        
        return {
            'label': predicted_label,
            'confidence': confidence,
            'scores': scores
        }
    
    def analyze_star_structure(self, answer_text: str) -> Dict[str, Any]:
        """分析整个回答的STAR结构"""
        
        # 分句
        sentences = self._split_sentences(answer_text)
        
        if not sentences:
            return self._get_empty_star_analysis()
        
        # 分类每个句子
        sentence_results = self.predict_sentence_roles(sentences)
        
        # 统计STAR分布
        label_counts = {}
        for result in sentence_results:
            label = result['label']
            label_counts[label] = label_counts.get(label, 0) + 1
        
        # 计算STAR完整性
        star_components = ['Situation', 'Task', 'Action', 'Result']
        present_components = [comp for comp in star_components if label_counts.get(comp, 0) > 0]
        
        completeness_score = len(present_components) / len(star_components)
        
        # 分析STAR序列
        sequence_analysis = self._analyze_star_sequence(sentence_results)
        
        # 生成总体评估
        overall_assessment = self._generate_star_assessment(
            label_counts, completeness_score, sequence_analysis, len(sentences)
        )
        
        return {
            'sentence_classifications': sentence_results,
            'label_distribution': label_counts,
            'present_components': present_components,
            'missing_components': [comp for comp in star_components if comp not in present_components],
            'completeness_score': completeness_score,
            'sequence_analysis': sequence_analysis,
            'total_sentences': len(sentences),
            'overall_assessment': overall_assessment
        }
    
    def _split_sentences(self, text: str) -> List[str]:
        """分句"""
        
        # 简单的中英文分句
        import re
        
        # 处理中文句号、问号、感叹号，英文句号
        sentences = re.split(r'[。！？.!?]+', text)
        
        # 清理和过滤
        cleaned_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 5:  # 过滤太短的句子
                cleaned_sentences.append(sentence)
        
        return cleaned_sentences
    
    def _analyze_star_sequence(self, sentence_results: List[Dict]) -> Dict[str, Any]:
        """分析STAR序列的逻辑性"""
        
        # 提取标签序列
        labels = [result['label'] for result in sentence_results]
        
        # 期望的STAR顺序
        expected_order = ['Situation', 'Task', 'Action', 'Result']
        
        # 找到STAR组件的位置
        component_positions = {}
        for i, label in enumerate(labels):
            if label in expected_order:
                if label not in component_positions:
                    component_positions[label] = []
                component_positions[label].append(i)
        
        # 检查逻辑顺序
        sequence_score = 0
        if len(component_positions) >= 2:
            ordered_components = []
            for comp in expected_order:
                if comp in component_positions:
                    ordered_components.append((comp, min(component_positions[comp])))
            
            # 检查是否按预期顺序出现
            is_ordered = all(
                ordered_components[i][1] <= ordered_components[i+1][1] 
                for i in range(len(ordered_components)-1)
            )
            
            if is_ordered:
                sequence_score = 1.0
            else:
                sequence_score = 0.5  # 部分有序
        
        return {
            'component_positions': component_positions,
            'sequence_score': sequence_score,
            'is_logical_order': sequence_score >= 0.8
        }
    
    def _generate_star_assessment(
        self, 
        label_counts: Dict[str, int], 
        completeness_score: float,
        sequence_analysis: Dict[str, Any],
        total_sentences: int
    ) -> str:
        """生成STAR结构评估"""
        
        if completeness_score >= 0.75:
            if sequence_analysis['is_logical_order']:
                return "优秀：回答包含完整的STAR结构，逻辑清晰"
            else:
                return "良好：回答包含完整的STAR结构，但逻辑顺序可以改进"
        elif completeness_score >= 0.5:
            missing = 4 - len([k for k in ['Situation', 'Task', 'Action', 'Result'] if label_counts.get(k, 0) > 0])
            return f"中等：回答包含部分STAR结构，缺少{missing}个关键要素"
        else:
            return "需要改进：回答缺乏清晰的STAR结构，建议按照情境-任务-行动-结果的框架组织答案"
    
    def _get_empty_star_analysis(self) -> Dict[str, Any]:
        """空回答的STAR分析"""
        return {
            'sentence_classifications': [],
            'label_distribution': {},
            'present_components': [],
            'missing_components': ['Situation', 'Task', 'Action', 'Result'],
            'completeness_score': 0.0,
            'sequence_analysis': {
                'component_positions': {},
                'sequence_score': 0.0,
                'is_logical_order': False
            },
            'total_sentences': 0,
            'overall_assessment': "无有效内容可分析"
        }


def create_star_classifier() -> STARClassifier:
    """创建STAR分类器实例"""
    return STARClassifier()


# 示例训练数据（如果需要训练自定义模型）
STAR_TRAINING_EXAMPLES = [
    # Situation examples
    ("我在上一家公司担任后端开发工程师时，团队面临一个紧急的性能优化项目。", "Situation"),
    ("当时公司的用户量快速增长，现有系统开始出现性能瓶颈。", "Situation"),
    ("项目背景是我们需要在一个月内将系统响应时间提升50%。", "Situation"),
    
    # Task examples  
    ("我的任务是分析系统瓶颈并制定优化方案。", "Task"),
    ("我负责数据库查询优化和缓存策略设计。", "Task"),
    ("需要我在不影响现有功能的前提下进行性能改进。", "Task"),
    
    # Action examples
    ("我首先使用profiling工具分析了系统性能瓶颈。", "Action"),
    ("然后我设计了Redis缓存方案，并优化了关键SQL查询。", "Action"),
    ("我还实施了数据库连接池和异步处理机制。", "Action"),
    
    # Result examples
    ("最终系统响应时间提升了60%，超过了预期目标。", "Result"),
    ("项目成功完成，用户体验显著改善，获得了团队认可。", "Result"),
    ("这次优化为公司节省了大量服务器成本。", "Result"),
    
    # Other examples
    ("谢谢您的问题。", "Other"),
    ("我认为这是一个很有趣的技术挑战。", "Other"),
    ("总的来说，我很享受解决复杂问题的过程。", "Other")
] 