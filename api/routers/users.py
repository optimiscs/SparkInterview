"""
用户管理API路由 - 使用SQLite数据库存储
包括用户注册、登录、个人信息管理等功能
"""
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from api.models import (
    UserCreate, UserUpdate, UserResponse, 
    LoginRequest, LoginResponse,
    APIResponse, ErrorResponse
)
from src.database.sqlite_manager import db_manager

router = APIRouter()
security = HTTPBearer()

def hash_password(password: str) -> str:
    """密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """密码验证"""
    return hash_password(password) == hashed

def create_access_token(user_id: str, request: Request = None) -> str:
    """创建访问令牌"""
    token = str(uuid.uuid4())
    
    # 获取请求信息
    user_agent = request.headers.get("user-agent", "Unknown") if request else "Unknown"
    ip_address = request.client.host if request and request.client else "Unknown"
    
    session_data = {
        "token": token,
        "user_id": user_id,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(days=7),
        "user_agent": user_agent,
        "ip_address": ip_address
    }
    
    db_manager.create_session(session_data)
    return token

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """获取当前用户"""
    token = credentials.credentials
    
    # 清理过期会话
    db_manager.cleanup_expired_sessions()
    
    # 获取会话信息
    session = db_manager.get_session(token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的访问令牌"
        )
    
    # 检查会话是否过期
    if datetime.fromisoformat(session["expires_at"]) < datetime.now():
        db_manager.delete_session(token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="访问令牌已过期"
        )
    
    # 获取用户信息
    user = db_manager.get_user_by_id(session["user_id"])
    if not user:
        db_manager.delete_session(token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )
    
    return user

@router.post("/register", 
             response_model=APIResponse,
             summary="用户注册",
             description="创建新用户账号")
async def register(user_data: UserCreate):
    """用户注册"""
    try:
        # 创建用户数据
        user_id = str(uuid.uuid4())
        new_user_data = {
            "id": user_id,
            "name": user_data.name,
            "email": user_data.email,
            "password": hash_password(user_data.password),
            "role": user_data.role,
            "avatar_url": None
        }
        
        # 存储到数据库
        db_manager.create_user(new_user_data)
        
        # 获取完整用户信息
        created_user = db_manager.get_user_by_id(user_id)
        if not created_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="用户创建失败"
            )
        
        # 返回用户信息（不包含密码）
        user_response = UserResponse(**{k: v for k, v in created_user.items() if k != "password"})
        
        return APIResponse(
            code=201,
            message="用户注册成功",
            data=user_response
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册失败: {str(e)}"
        )

@router.post("/login",
             response_model=LoginResponse,
             summary="用户登录",
             description="用户身份验证并获取访问令牌")
async def login(login_data: LoginRequest, request: Request):
    """用户登录"""
    try:
        # 查找用户
        user = db_manager.get_user_by_email(login_data.email)
        
        if not user or not verify_password(login_data.password, user["password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="邮箱或密码错误"
            )
        
        # 创建访问令牌
        access_token = create_access_token(user["id"], request)
        
        # 返回用户信息（不包含密码）
        user_response = UserResponse(**{k: v for k, v in user.items() if k != "password"})
        
        return LoginResponse(
            access_token=access_token,
            user=user_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登录失败: {str(e)}"
        )

@router.get("/profile",
            response_model=UserResponse,
            summary="获取用户信息",
            description="获取当前登录用户的详细信息")
async def get_profile(current_user: dict = Depends(get_current_user)):
    """获取用户个人信息"""
    return UserResponse(**{k: v for k, v in current_user.items() if k != "password"})

@router.put("/profile",
            response_model=APIResponse,
            summary="更新用户信息",
            description="更新当前登录用户的个人信息")
async def update_profile(
    update_data: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    """更新用户个人信息"""
    try:
        user_id = current_user["id"]
        
        # 构建更新数据
        update_dict = {}
        if update_data.name is not None:
            update_dict["name"] = update_data.name
        if update_data.email is not None:
            update_dict["email"] = update_data.email
        if update_data.avatar_url is not None:
            update_dict["avatar_url"] = update_data.avatar_url
        
        # 更新用户信息
        success = db_manager.update_user(user_id, update_dict)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 获取更新后的用户信息
        updated_user = db_manager.get_user_by_id(user_id)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取更新后的用户信息失败"
            )
        
        user_response = UserResponse(**{k: v for k, v in updated_user.items() if k != "password"})
        
        return APIResponse(
            message="用户信息更新成功",
            data=user_response
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败: {str(e)}"
        )

@router.post("/logout",
             response_model=APIResponse,
             summary="用户登出",
             description="注销当前登录会话")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """用户登出"""
    try:
        token = credentials.credentials
        
        success = db_manager.delete_session(token)
        
        if success:
            return APIResponse(message="登出成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的访问令牌"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登出失败: {str(e)}"
        )

@router.get("/users",
            response_model=List[UserResponse],
            summary="获取用户列表",
            description="获取所有用户列表（管理员功能）")
async def get_users(current_user: dict = Depends(get_current_user)):
    """获取用户列表（管理员功能）"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    try:
        users = db_manager.get_all_users()
        user_responses = []
        
        for user in users:
            user_responses.append(
                UserResponse(**{k: v for k, v in user.items() if k != "password"})
            )
        
        return user_responses
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户列表失败: {str(e)}"
        )

@router.delete("/users/{user_id}",
               response_model=APIResponse,
               summary="删除用户",
               description="删除指定用户（管理员功能）")
async def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """删除用户（管理员功能）"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    if user_id == current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账号"
        )
    
    try:
        # 检查用户是否存在
        target_user = db_manager.get_user_by_id(user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 删除用户
        success = db_manager.delete_user(user_id)
        
        if success:
            return APIResponse(message="用户删除成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="用户删除失败"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除用户失败: {str(e)}"
        )

# 新增的管理员功能接口
@router.get("/admin/stats",
            summary="获取系统统计信息",
            description="获取用户和会话统计信息（管理员功能）")
async def get_system_stats(current_user: dict = Depends(get_current_user)):
    """获取系统统计信息（管理员功能）"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    try:
        stats = db_manager.get_database_stats()
        return APIResponse(
            message="获取统计信息成功",
            data=stats
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计信息失败: {str(e)}"
        )

@router.get("/sessions",
            summary="获取用户会话",
            description="获取当前用户的所有活跃会话")
async def get_user_sessions(current_user: dict = Depends(get_current_user)):
    """获取用户的活跃会话"""
    try:
        sessions = db_manager.get_user_sessions(current_user["id"])
        
        # 处理会话数据，隐藏敏感信息
        session_responses = []
        for session in sessions:
            session_data = {
                "token": session["token"][:8] + "***",  # 只显示前8位
                "created_at": session["created_at"],
                "expires_at": session["expires_at"],
                "user_agent": session.get("user_agent", "Unknown"),
                "ip_address": session.get("ip_address", "Unknown")
            }
            session_responses.append(session_data)
        
        return APIResponse(
            message="获取会话信息成功",
            data=session_responses
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取会话信息失败: {str(e)}"
        )

@router.delete("/sessions/all",
               response_model=APIResponse,
               summary="登出所有设备",
               description="删除当前用户的所有会话（除当前会话外）")
async def logout_all_sessions(
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """登出所有其他设备"""
    try:
        current_token = credentials.credentials
        
        # 获取用户所有会话
        sessions = db_manager.get_user_sessions(current_user["id"])
        
        # 删除除当前会话外的所有会话
        deleted_count = 0
        for session in sessions:
            if session["token"] != current_token:
                if db_manager.delete_session(session["token"]):
                    deleted_count += 1
        
        return APIResponse(
            message=f"成功登出 {deleted_count} 个其他设备的会话"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登出其他设备失败: {str(e)}"
        )

@router.post("/admin/cleanup",
             response_model=APIResponse,
             summary="清理过期会话",
             description="清理所有过期的会话（管理员功能）")
async def cleanup_expired_sessions(current_user: dict = Depends(get_current_user)):
    """清理过期会话（管理员功能）"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    try:
        cleaned_count = db_manager.cleanup_expired_sessions()
        return APIResponse(
            message=f"成功清理 {cleaned_count} 个过期会话"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理过期会话失败: {str(e)}"
        ) 