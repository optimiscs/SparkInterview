#!/usr/bin/env python3
"""
ChromaDB管理器 - 用于题目存储和匹配
"""
import chromadb
from chromadb.config import Settings
import json
import uuid
from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ChromaQuestionManager:
    """ChromaDB题目管理器"""
    
    def __init__(self, persist_directory: str = "data/chromadb"):
        """初始化ChromaDB客户端"""
        try:
            self.client = chromadb.PersistentClient(path=persist_directory)
            self.collection = self.client.get_or_create_collection(
                name="interview_questions",
                metadata={
                    "description": "面试题目集合，支持多维度匹配",
                    "created_at": datetime.now().isoformat()
                }
            )
            print(f"✅ ChromaDB初始化成功，数据目录: {persist_directory}")
        except Exception as e:
            print(f"❌ ChromaDB初始化失败: {e}")
            raise
    
    def store_questions(self, questions: List[Dict[str, Any]], metadata: Dict[str, Any]) -> bool:
        """存储题目到ChromaDB"""
        try:
            documents = []
            metadatas = []
            ids = []
            
            for i, question in enumerate(questions):
                # 构建检索文档
                doc_text = self._build_question_document(question, metadata)
                
                # 构建元数据
                question_metadata = {
                    "question_id": question.get("id", f"q_{uuid.uuid4().hex[:8]}"),
                    "type": question.get("type", "tech_basic"),
                    "difficulty": metadata.get("difficulty_level", 2),
                    "skills": json.dumps(metadata.get("selected_skills", [])),
                    "domain": metadata.get("domain", ""),
                    "position": metadata.get("position", ""),
                    "experience_years": metadata.get("experience_years", ""),
                    "created_at": datetime.now().isoformat(),
                    "title": question.get("title", "")[:500],  # 限制长度
                    "points": json.dumps(question.get("points", [])),
                    "has_answer": "yes" if question.get("answer") else "no",
                    "session_id": metadata.get("session_id", ""),  # 添加会话ID
                    "task_id": metadata.get("task_id", "")  # 添加任务ID
                }
                
                documents.append(doc_text)
                metadatas.append(question_metadata)
                ids.append(f"q_{uuid.uuid4().hex}")
            
            # 批量添加到ChromaDB
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
            print(f"✅ 成功存储 {len(questions)} 个题目到ChromaDB")
            return True
            
        except Exception as e:
            print(f"❌ 存储题目失败: {e}")
            logger.error(f"存储题目失败: {e}")
            return False
    
    def search_questions(self, request_data: Dict[str, Any], n_results: int = 10) -> List[Dict[str, Any]]:
        """根据条件搜索匹配的题目"""
        try:
            # 构建查询文本
            query_text = self._build_query_text(request_data)
            
            # 构建where条件
            where_conditions = self._build_where_conditions(request_data)
            
            print(f"🔍 搜索条件: {query_text}")
            print(f"🔍 过滤条件: {where_conditions}")
            
            # 执行搜索
            results = self.collection.query(
                query_texts=[query_text],
                n_results=min(n_results, 50),  # 限制最大结果数
                where=where_conditions
            )
            
            # 解析结果
            matched_questions = self._parse_search_results(results)
            
            print(f"✅ 匹配到 {len(matched_questions)} 个题目")
            return matched_questions
            
        except Exception as e:
            print(f"❌ 搜索题目失败: {e}")
            logger.error(f"搜索题目失败: {e}")
            return []
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """获取题目集合统计信息"""
        try:
            count = self.collection.count()
            return {
                "total_questions": count,
                "collection_name": self.collection.name,
                "last_updated": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"❌ 获取统计信息失败: {e}")
            return {"total_questions": 0, "error": str(e)}
    
    def _build_question_document(self, question: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        """构建题目的检索文档"""
        doc_parts = []
        
        # 题目内容
        if question.get("title"):
            doc_parts.append(f"题目: {question['title']}")
        
        # 考察点
        if question.get("points"):
            doc_parts.append(f"考察点: {', '.join(question['points'])}")
        
        # 技能标签
        skills = metadata.get("selected_skills", [])
        if skills:
            doc_parts.append(f"技能: {', '.join(skills)}")
        
        # 题目类型
        type_map = {
            "tech_basic": "技术基础",
            "project_experience": "项目经验", 
            "algorithm_design": "算法设计",
            "system_design": "系统设计"
        }
        q_type = type_map.get(question.get("type", ""), question.get("type", ""))
        doc_parts.append(f"类型: {q_type}")
        
        # 难度
        difficulty_map = {1: "初级", 2: "中级", 3: "高级"}
        difficulty = difficulty_map.get(metadata.get("difficulty_level", 2), "中级")
        doc_parts.append(f"难度: {difficulty}")
        
        # 领域和职位
        if metadata.get("domain"):
            doc_parts.append(f"领域: {metadata['domain']}")
        if metadata.get("position"):
            doc_parts.append(f"职位: {metadata['position']}")
            
        return " | ".join(doc_parts)
    
    def _build_query_text(self, request_data: Dict[str, Any]) -> str:
        """构建查询文本"""
        query_parts = []
        
        # 技能查询
        skills = request_data.get("selected_skills", [])
        if skills:
            query_parts.append(f"技能: {', '.join(skills)}")
        
        # 项目相关查询
        projects = request_data.get("selected_projects", [])
        if projects:
            project_names = [p.get("name", "") for p in projects if p.get("name")]
            if project_names:
                query_parts.append(f"项目: {', '.join(project_names)}")
        
        # 题目类型查询
        question_types = request_data.get("question_types", {})
        active_types = []
        type_map = {
            "tech_basic": "技术基础",
            "project_experience": "项目经验",
            "algorithm_design": "算法设计", 
            "system_design": "系统设计"
        }
        for key, value in question_types.items():
            if value and key in type_map:
                active_types.append(type_map[key])
        
        if active_types:
            query_parts.append(f"类型: {', '.join(active_types)}")
        
        # 基本信息查询
        resume_data = request_data.get("resume_data", {})
        basic_info = resume_data.get("basic_info", {})
        if basic_info.get("current_position"):
            query_parts.append(f"职位: {basic_info['current_position']}")
        
        return " | ".join(query_parts) if query_parts else "面试题目"
    
    def _build_where_conditions(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """构建where过滤条件"""
        conditions_list = []
        
        # 难度过滤
        difficulty = request_data.get("difficulty_level")
        if difficulty is not None:
            conditions_list.append({"difficulty": {"$eq": difficulty}})
        
        # 题目类型过滤
        question_types = request_data.get("question_types", {})
        active_types = [key for key, value in question_types.items() if value]
        if active_types:
            if len(active_types) == 1:
                conditions_list.append({"type": {"$eq": active_types[0]}})
            else:
                conditions_list.append({"type": {"$in": active_types}})
        
        # 答案要求过滤
        include_answer = request_data.get("include_answer", False)
        if include_answer:
            conditions_list.append({"has_answer": {"$eq": "yes"}})
        
        # 根据条件数量决定返回格式
        if len(conditions_list) == 0:
            return {}  # 无过滤条件
        elif len(conditions_list) == 1:
            return conditions_list[0]  # 单个条件直接返回
        else:
            return {"$and": conditions_list}  # 多个条件用$and包装
    
    def _parse_search_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析搜索结果"""
        questions = []
        
        if not results.get("documents") or not results["documents"][0]:
            return questions
        
        documents = results["documents"][0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        
        for i, (doc, metadata, distance) in enumerate(zip(documents, metadatas, distances)):
            try:
                question = {
                    "id": metadata.get("question_id", f"q_{i}"),
                    "type": metadata.get("type", "tech_basic"),
                    "title": metadata.get("title", ""),
                    "points": json.loads(metadata.get("points", "[]")),
                    "answer": "",  # 实际应用中可能需要单独存储答案
                    "difficulty": metadata.get("difficulty", 2),
                    "created_at": metadata.get("created_at", ""),
                    "similarity_score": 1 - distance,  # 转换为相似度分数
                    "source": "database"  # 标记来源
                }
                
                # 如果需要答案，可以从其他地方获取
                questions.append(question)
                
            except Exception as e:
                print(f"⚠️ 解析题目失败: {e}")
                continue
        
        return questions
    
    def get_questions_by_session(self, session_id: str = None, task_id: str = None, n_results: int = 50) -> List[Dict[str, Any]]:
        """根据会话ID或任务ID获取题目"""
        try:
            if not session_id and not task_id:
                print("❌ 必须提供session_id或task_id")
                return []
            
            # 构建where条件
            where_conditions = {}
            if session_id:
                where_conditions["session_id"] = {"$eq": session_id}
            elif task_id:
                where_conditions["task_id"] = {"$eq": task_id}
            
            print(f"🔍 根据{'会话ID' if session_id else '任务ID'}检索题目: {session_id or task_id}")
            print(f"🔍 检索条件: {where_conditions}")
            
            # 执行查询
            results = self.collection.query(
                query_texts=["题目检索"],  # 占位查询文本
                n_results=n_results,
                where=where_conditions
            )
            
            # 解析结果
            questions = self._parse_search_results(results)
            
            print(f"✅ 找到 {len(questions)} 个题目")
            return questions
            
        except Exception as e:
            print(f"❌ 根据{'会话ID' if session_id else '任务ID'}检索题目失败: {e}")
            logger.error(f"根据{'会话ID' if session_id else '任务ID'}检索题目失败: {e}")
            return []

# 全局实例
chroma_manager = ChromaQuestionManager() 