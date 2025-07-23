"""
学习资源API路由
包括资源搜索、推荐、管理等功能
"""
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends

from api.models import (
    LearningResourceCreate, LearningResourceResponse,
    ResourceSearchRequest, ResourceSearchResponse,
    ResourceCategory, APIResponse
)
from api.routers.users import get_current_user


router = APIRouter()

# 学习资源存储
learning_resources = {}

# 初始化一些示例学习资源
def initialize_sample_resources():
    """初始化示例学习资源"""
    sample_resources = [
        # 技术能力相关
        {
            "id": str(uuid.uuid4()),
            "title": "Python编程从入门到精通",
            "description": "全面的Python编程教程，涵盖基础语法到高级特性",
            "url": "https://example.com/python-tutorial",
            "category": ResourceCategory.COURSE,
            "competency": "professional_knowledge",
            "difficulty": "beginner",
            "tags": ["Python", "编程", "入门"],
            "created_at": datetime.now()
        },
        {
            "id": str(uuid.uuid4()),
            "title": "算法与数据结构实战",
            "description": "通过实际案例学习常用算法和数据结构",
            "url": "https://example.com/algorithm-course",
            "category": ResourceCategory.VIDEO,
            "competency": "professional_knowledge",
            "difficulty": "intermediate",
            "tags": ["算法", "数据结构", "面试"],
            "created_at": datetime.now()
        },
        {
            "id": str(uuid.uuid4()),
            "title": "系统设计面试指南",
            "description": "如何在系统设计面试中表现出色",
            "url": "https://example.com/system-design-interview",
            "category": ResourceCategory.BOOK,
            "competency": "professional_knowledge",
            "difficulty": "advanced",
            "tags": ["系统设计", "面试", "架构"],
            "created_at": datetime.now()
        },
        
        # 沟通能力相关
        {
            "id": str(uuid.uuid4()),
            "title": "有效沟通的艺术",
            "description": "提升职场沟通技巧的实用指南",
            "url": "https://example.com/communication-skills",
            "category": ResourceCategory.ARTICLE,
            "competency": "communication_ability",
            "difficulty": "beginner",
            "tags": ["沟通", "表达", "职场"],
            "created_at": datetime.now()
        },
        {
            "id": str(uuid.uuid4()),
            "title": "STAR面试回答法则",
            "description": "学会用STAR法则结构化回答面试问题",
            "url": "https://example.com/star-method",
            "category": ResourceCategory.VIDEO,
            "competency": "communication_ability",
            "difficulty": "intermediate",
            "tags": ["面试技巧", "STAR", "表达"],
            "created_at": datetime.now()
        },
        {
            "id": str(uuid.uuid4()),
            "title": "公众演讲与表达训练",
            "description": "克服紧张，提升演讲和表达能力",
            "url": "https://example.com/public-speaking",
            "category": ResourceCategory.COURSE,
            "competency": "communication_ability",
            "difficulty": "advanced",
            "tags": ["演讲", "表达", "自信"],
            "created_at": datetime.now()
        },
        
        # 逻辑思维相关
        {
            "id": str(uuid.uuid4()),
            "title": "结构化思维训练",
            "description": "培养清晰的逻辑思维和分析能力",
            "url": "https://example.com/structured-thinking",
            "category": ResourceCategory.COURSE,
            "competency": "logical_thinking",
            "difficulty": "beginner",
            "tags": ["逻辑思维", "分析", "结构化"],
            "created_at": datetime.now()
        },
        {
            "id": str(uuid.uuid4()),
            "title": "问题解决方法论",
            "description": "系统性解决复杂问题的思维框架",
            "url": "https://example.com/problem-solving",
            "category": ResourceCategory.ARTICLE,
            "competency": "logical_thinking",
            "difficulty": "intermediate",
            "tags": ["问题解决", "方法论", "思维"],
            "created_at": datetime.now()
        },
        
        # 学习能力相关
        {
            "id": str(uuid.uuid4()),
            "title": "高效学习法",
            "description": "科学的学习方法和技巧分享",
            "url": "https://example.com/learning-methods",
            "category": ResourceCategory.BOOK,
            "competency": "learning_ability",
            "difficulty": "beginner",
            "tags": ["学习方法", "效率", "技巧"],
            "created_at": datetime.now()
        },
        {
            "id": str(uuid.uuid4()),
            "title": "终身学习者的养成",
            "description": "如何保持持续学习的动力和习惯",
            "url": "https://example.com/lifelong-learning",
            "category": ResourceCategory.ARTICLE,
            "competency": "learning_ability",
            "difficulty": "intermediate",
            "tags": ["终身学习", "习惯", "成长"],
            "created_at": datetime.now()
        },
        
        # 团队协作相关
        {
            "id": str(uuid.uuid4()),
            "title": "高效团队协作指南",
            "description": "建设高效团队的方法和实践",
            "url": "https://example.com/teamwork-guide",
            "category": ResourceCategory.VIDEO,
            "competency": "stress_resilience",
            "difficulty": "beginner",
            "tags": ["团队协作", "管理", "效率"],
            "created_at": datetime.now()
        },
        {
            "id": str(uuid.uuid4()),
            "title": "冲突管理与解决",
            "description": "处理团队冲突的策略和技巧",
            "url": "https://example.com/conflict-resolution",
            "category": ResourceCategory.COURSE,
            "competency": "stress_resilience",
            "difficulty": "advanced",
            "tags": ["冲突管理", "协调", "解决方案"],
            "created_at": datetime.now()
        },
        
        # 创新思维相关
        {
            "id": str(uuid.uuid4()),
            "title": "创新思维训练营",
            "description": "激发创新潜能的思维训练方法",
            "url": "https://example.com/innovation-thinking",
            "category": ResourceCategory.COURSE,
            "competency": "innovation",
            "difficulty": "intermediate",
            "tags": ["创新思维", "创意", "训练"],
            "created_at": datetime.now()
        },
        {
            "id": str(uuid.uuid4()),
            "title": "设计思维实战",
            "description": "用设计思维解决复杂问题",
            "url": "https://example.com/design-thinking",
            "category": ResourceCategory.PRACTICE,
            "competency": "innovation",
            "difficulty": "advanced",
            "tags": ["设计思维", "创新", "实战"],
            "created_at": datetime.now()
        }
    ]
    
    for resource in sample_resources:
        learning_resources[resource["id"]] = resource

# 初始化示例资源
initialize_sample_resources()


@router.post("/create",
             response_model=LearningResourceResponse,
             summary="创建学习资源",
             description="创建新的学习资源（管理员功能）")
async def create_learning_resource(
    resource_data: LearningResourceCreate,
    current_user: dict = Depends(get_current_user)
):
    """创建学习资源"""
    # 检查权限
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="权限不足，只有管理员可以创建学习资源"
        )
    
    try:
        # 创建资源
        resource_id = str(uuid.uuid4())
        new_resource = {
            "id": resource_id,
            "title": resource_data.title,
            "description": resource_data.description,
            "url": resource_data.url,
            "category": resource_data.category,
            "competency": resource_data.competency,
            "difficulty": resource_data.difficulty,
            "tags": resource_data.tags,
            "created_at": datetime.now()
        }
        
        learning_resources[resource_id] = new_resource
        
        return LearningResourceResponse(**new_resource)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"创建学习资源失败: {str(e)}"
        )


@router.post("/search",
             response_model=ResourceSearchResponse,
             summary="搜索学习资源",
             description="根据条件搜索学习资源")
async def search_learning_resources(
    search_request: ResourceSearchRequest,
    current_user: dict = Depends(get_current_user)
):
    """搜索学习资源"""
    try:
        # 获取所有资源
        all_resources = list(learning_resources.values())
        
        # 应用过滤条件
        filtered_resources = []
        
        for resource in all_resources:
            # 关键词搜索
            if search_request.query:
                query_lower = search_request.query.lower()
                if not (query_lower in resource["title"].lower() or 
                       query_lower in resource["description"].lower() or
                       any(query_lower in tag.lower() for tag in resource["tags"])):
                    continue
            
            # 能力类型过滤
            if search_request.competency and resource["competency"] != search_request.competency:
                continue
            
            # 难度级别过滤
            if search_request.difficulty and resource["difficulty"] != search_request.difficulty:
                continue
            
            # 资源分类过滤
            if search_request.category and resource["category"] != search_request.category:
                continue
            
            filtered_resources.append(resource)
        
        # 按创建时间排序（最新在前）
        filtered_resources.sort(key=lambda x: x["created_at"], reverse=True)
        
        # 应用分页
        total = len(filtered_resources)
        start = search_request.offset
        end = start + search_request.limit
        paginated_resources = filtered_resources[start:end]
        
        # 转换为响应格式
        resource_responses = []
        for resource in paginated_resources:
            resource_responses.append(LearningResourceResponse(**resource))
        
        return ResourceSearchResponse(
            resources=resource_responses,
            total=total,
            has_more=end < total
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"搜索学习资源失败: {str(e)}"
        )


@router.get("/recommend",
            response_model=List[LearningResourceResponse],
            summary="获取推荐资源",
            description="基于用户特点推荐学习资源")
async def get_recommended_resources(
    competency: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: int = 5,
    current_user: dict = Depends(get_current_user)
):
    """获取推荐的学习资源"""
    try:
        # 获取所有资源
        all_resources = list(learning_resources.values())
        
        # 简单的推荐逻辑
        recommended_resources = []
        
        # 如果指定了能力和难度，优先推荐匹配的资源
        if competency or difficulty:
            for resource in all_resources:
                if competency and resource["competency"] != competency:
                    continue
                if difficulty and resource["difficulty"] != difficulty:
                    continue
                recommended_resources.append(resource)
        
        # 如果没有足够的匹配资源，添加热门资源
        if len(recommended_resources) < limit:
            popular_resources = [r for r in all_resources if r not in recommended_resources]
            popular_resources.sort(key=lambda x: len(x["tags"]), reverse=True)  # 按标签数量排序
            recommended_resources.extend(popular_resources)
        
        # 限制数量
        recommended_resources = recommended_resources[:limit]
        
        # 转换为响应格式
        resource_responses = []
        for resource in recommended_resources:
            resource_responses.append(LearningResourceResponse(**resource))
        
        return resource_responses
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取推荐资源失败: {str(e)}"
        )


@router.get("/{resource_id}",
            response_model=LearningResourceResponse,
            summary="获取单个资源",
            description="获取指定ID的学习资源详情")
async def get_learning_resource(
    resource_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取单个学习资源"""
    if resource_id not in learning_resources:
        raise HTTPException(
            status_code=404,
            detail="学习资源不存在"
        )
    
    resource = learning_resources[resource_id]
    return LearningResourceResponse(**resource)


@router.put("/{resource_id}",
            response_model=LearningResourceResponse,
            summary="更新学习资源",
            description="更新指定的学习资源（管理员功能）")
async def update_learning_resource(
    resource_id: str,
    resource_data: LearningResourceCreate,
    current_user: dict = Depends(get_current_user)
):
    """更新学习资源"""
    # 检查权限
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="权限不足，只有管理员可以更新学习资源"
        )
    
    if resource_id not in learning_resources:
        raise HTTPException(
            status_code=404,
            detail="学习资源不存在"
        )
    
    try:
        # 更新资源
        resource = learning_resources[resource_id]
        resource.update({
            "title": resource_data.title,
            "description": resource_data.description,
            "url": resource_data.url,
            "category": resource_data.category,
            "competency": resource_data.competency,
            "difficulty": resource_data.difficulty,
            "tags": resource_data.tags
        })
        
        return LearningResourceResponse(**resource)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"更新学习资源失败: {str(e)}"
        )


@router.delete("/{resource_id}",
               response_model=APIResponse,
               summary="删除学习资源",
               description="删除指定的学习资源（管理员功能）")
async def delete_learning_resource(
    resource_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除学习资源"""
    # 检查权限
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="权限不足，只有管理员可以删除学习资源"
        )
    
    if resource_id not in learning_resources:
        raise HTTPException(
            status_code=404,
            detail="学习资源不存在"
        )
    
    # 删除资源
    del learning_resources[resource_id]
    
    return APIResponse(message="学习资源已删除")


@router.get("/categories/list",
            response_model=List[str],
            summary="获取资源分类列表",
            description="获取所有可用的资源分类")
async def get_resource_categories():
    """获取资源分类列表"""
    return [category.value for category in ResourceCategory]


@router.get("/competencies/list",
            response_model=List[str],
            summary="获取能力类型列表",
            description="获取所有可用的能力类型")
async def get_competency_types():
    """获取能力类型列表"""
    competency_types = [
        "professional_knowledge",
        "communication_ability", 
        "logical_thinking",
        "learning_ability",
        "stress_resilience",
        "innovation"
    ]
    return competency_types


@router.get("/difficulties/list",
            response_model=List[str],
            summary="获取难度级别列表", 
            description="获取所有可用的难度级别")
async def get_difficulty_levels():
    """获取难度级别列表"""
    return ["beginner", "intermediate", "advanced"]


@router.get("/stats/overview",
            response_model=Dict[str, Any],
            summary="获取资源统计",
            description="获取学习资源的统计信息")
async def get_resource_stats(current_user: dict = Depends(get_current_user)):
    """获取资源统计信息"""
    all_resources = list(learning_resources.values())
    
    # 按分类统计
    category_stats = {}
    for category in ResourceCategory:
        category_stats[category.value] = sum(1 for r in all_resources if r["category"] == category)
    
    # 按能力统计
    competency_stats = {}
    competencies = [
        "professional_knowledge",
        "communication_ability", 
        "logical_thinking",
        "learning_ability",
        "stress_resilience",
        "innovation"
    ]
    
    for competency in competencies:
        competency_stats[competency] = sum(1 for r in all_resources if r["competency"] == competency)
    
    # 按难度统计
    difficulty_stats = {}
    difficulties = ["beginner", "intermediate", "advanced"]
    
    for difficulty in difficulties:
        difficulty_stats[difficulty] = sum(1 for r in all_resources if r["difficulty"] == difficulty)
    
    return {
        "total_resources": len(all_resources),
        "category_distribution": category_stats,
        "competency_distribution": competency_stats,
        "difficulty_distribution": difficulty_stats,
        "latest_resources": sorted(all_resources, key=lambda x: x["created_at"], reverse=True)[:5]
    } 