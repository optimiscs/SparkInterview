"""
向量搜索工具
支持问题检索和学习资源推荐
"""
import json
import uuid
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ..config.settings import database_config


class VectorSearchInput(BaseModel):
    """向量搜索输入"""
    query: str = Field(description="搜索查询")
    collection_name: str = Field(description="集合名称")
    top_k: int = Field(default=5, description="返回结果数量")
    filter_metadata: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="元数据过滤条件"
    )


class VectorSearchTool(BaseTool):
    """向量搜索工具"""
    
    name: str = "vector_search"
    description: str = """
    在向量数据库中搜索相关内容。
    支持面试问题检索和学习资源推荐。
    """
    args_schema: type = VectorSearchInput
    client: Any = None
    encoder: Any = None
    
    def __init__(self):
        super().__init__()
        
        # 初始化ChromaDB客户端
        self.client = chromadb.PersistentClient(
            path=database_config.chroma_persist_dir,
            settings=Settings(
                allow_reset=True,
                anonymized_telemetry=False
            )
        )
        
        # 初始化句子转换器
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        
        # 确保集合存在
        self._ensure_collections()
    
    def _ensure_collections(self):
        """确保必要的集合存在"""
        
        collections = ["questions", "learning_resources"]
        
        for collection_name in collections:
            try:
                self.client.get_collection(collection_name)
            except Exception:
                # 集合不存在，创建新集合
                self.client.create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
    
    def _run(
        self, 
        query: str, 
        collection_name: str, 
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """执行向量搜索"""
        
        try:
            # 获取集合
            collection = self.client.get_collection(collection_name)
            
            # 生成查询向量
            query_embedding = self.encoder.encode(query).tolist()
            
            # 执行搜索
            search_kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": top_k,
                "include": ["documents", "metadatas", "distances"]
            }
            
            # 添加过滤条件
            if filter_metadata:
                search_kwargs["where"] = filter_metadata
            
            results = collection.query(**search_kwargs)
            
            # 格式化结果
            formatted_results = []
            
            if results["documents"] and len(results["documents"]) > 0:
                documents = results["documents"][0]
                metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(documents)
                distances = results["distances"][0] if results["distances"] else [0.0] * len(documents)
                
                for i, (doc, metadata, distance) in enumerate(zip(documents, metadatas, distances)):
                    formatted_results.append({
                        "rank": i + 1,
                        "content": doc,
                        "metadata": metadata,
                        "similarity_score": 1 - distance,  # 转换为相似度分数
                        "distance": distance
                    })
            
            result = {
                "query": query,
                "collection": collection_name,
                "total_results": len(formatted_results),
                "results": formatted_results
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            error_result = {
                "error": True,
                "message": str(e),
                "query": query,
                "collection": collection_name
            }
            return json.dumps(error_result, ensure_ascii=False, indent=2)


class QuestionBankManager:
    """面试题库管理器"""
    
    def __init__(self):
        self.vector_tool = VectorSearchTool()
        self.collection_name = "questions"
    
    def add_questions(self, questions: List[Dict[str, Any]]):
        """批量添加问题到题库"""
        
        collection = self.vector_tool.client.get_collection(self.collection_name)
        
        documents = []
        metadatas = []
        ids = []
        
        for question in questions:
            # 生成ID
            question_id = question.get("id", str(uuid.uuid4()))
            
            # 文档内容
            doc_text = question["text"]
            
            # 元数据
            metadata = {
                "field": question.get("field", "general"),
                "difficulty": question.get("difficulty", "middle"),
                "type": question.get("type", "technical"),
                "keywords": ",".join(question.get("expected_keywords", []))
            }
            
            documents.append(doc_text)
            metadatas.append(metadata)
            ids.append(question_id)
        
        # 生成嵌入
        embeddings = self.vector_tool.encoder.encode(documents).tolist()
        
        # 添加到数据库
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings
        )
    
    def search_questions(
        self, 
        field: str, 
        position: str, 
        difficulty: str = "middle",
        count: int = 10
    ) -> List[Dict[str, Any]]:
        """搜索相关问题"""
        
        # 构建搜索查询
        query = f"{field} {position} 面试"
        
        # 构建过滤条件
        filter_metadata = {
            "$and": [
                {"field": {"$eq": field}},
                {"difficulty": {"$eq": difficulty}}
            ]
        }
        
        # 执行搜索
        result_str = self.vector_tool._run(
            query=query,
            collection_name=self.collection_name,
            top_k=count,
            filter_metadata=filter_metadata
        )
        
        result = json.loads(result_str)
        
        if result.get("error"):
            return []
        
        return result.get("results", [])


class LearningResourceManager:
    """学习资源管理器"""
    
    def __init__(self):
        self.vector_tool = VectorSearchTool()
        self.collection_name = "learning_resources"
    
    def add_resources(self, resources: List[Dict[str, Any]]):
        """批量添加学习资源"""
        
        collection = self.vector_tool.client.get_collection(self.collection_name)
        
        documents = []
        metadatas = []
        ids = []
        
        for resource in resources:
            # 生成ID
            resource_id = resource.get("id", str(uuid.uuid4()))
            
            # 文档内容（标题+描述）
            doc_text = f"{resource['title']} {resource.get('description', '')}"
            
            # 元数据
            metadata = {
                "title": resource["title"],
                "url": resource.get("url", ""),
                "type": resource.get("type", "article"),
                "competency": resource.get("competency", "general"),
                "difficulty": resource.get("difficulty", "beginner")
            }
            
            documents.append(doc_text)
            metadatas.append(metadata)
            ids.append(resource_id)
        
        # 生成嵌入
        embeddings = self.vector_tool.encoder.encode(documents).tolist()
        
        # 添加到数据库
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings
        )
    
    def search_resources(
        self, 
        competency: str, 
        count: int = 3
    ) -> List[Dict[str, Any]]:
        """搜索学习资源"""
        
        # 构建搜索查询
        competency_map = {
            "communication_ability": "沟通表达 演讲技巧",
            "logical_thinking": "逻辑思维 结构化思考",
            "professional_knowledge": "专业知识 技术能力",
            "stress_resilience": "抗压能力 情绪管理"
        }
        
        query = competency_map.get(competency, competency)
        
        # 构建过滤条件
        filter_metadata = {"competency": {"$eq": competency}}
        
        # 执行搜索
        result_str = self.vector_tool._run(
            query=query,
            collection_name=self.collection_name,
            top_k=count,
            filter_metadata=filter_metadata
        )
        
        result = json.loads(result_str)
        
        if result.get("error"):
            return []
        
        return result.get("results", [])


def create_vector_search_tool() -> VectorSearchTool:
    """创建向量搜索工具实例"""
    return VectorSearchTool()


def create_question_bank_manager() -> QuestionBankManager:
    """创建题库管理器实例"""
    return QuestionBankManager()


def create_learning_resource_manager() -> LearningResourceManager:
    """创建学习资源管理器实例"""
    return LearningResourceManager() 