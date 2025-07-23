"""
用户管理API路由
包括用户注册、登录、个人信息管理等功能
"""
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from api.models import (
    UserCreate, UserUpdate, UserResponse, 
    LoginRequest, LoginResponse,
    APIResponse, ErrorResponse
)


router = APIRouter()
security = HTTPBearer()

# 简单的内存存储，实际项目中应该使用数据库
users_db = {}
sessions_db = {}


def hash_password(password: str) -> str:
    """密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """密码验证"""
    return hash_password(password) == hashed


def create_access_token(user_id: str) -> str:
    """创建访问令牌"""
    token = str(uuid.uuid4())
    sessions_db[token] = {
        "user_id": user_id,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(days=7)
    }
    return token


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """获取当前用户"""
    token = credentials.credentials
    session = sessions_db.get(token)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的访问令牌"
        )
    
    if session["expires_at"] < datetime.now():
        del sessions_db[token]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="访问令牌已过期"
        )
    
    user = users_db.get(session["user_id"])
    if not user:
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
    # 检查邮箱是否已存在
    for user in users_db.values():
        if user["email"] == user_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱地址已被注册"
            )
    
    # 创建用户
    user_id = str(uuid.uuid4())
    new_user = {
        "id": user_id,
        "name": user_data.name,
        "email": user_data.email,
        "password": hash_password(user_data.password),
        "role": user_data.role,
        "avatar_url": None,
        "created_at": datetime.now()
    }
    
    users_db[user_id] = new_user
    
    # 返回用户信息（不包含密码）
    user_response = UserResponse(**{k: v for k, v in new_user.items() if k != "password"})
    
    return APIResponse(
        code=201,
        message="用户注册成功",
        data=user_response
    )


@router.post("/login",
             response_model=LoginResponse,
             summary="用户登录",
             description="用户身份验证并获取访问令牌")
async def login(login_data: LoginRequest):
    """用户登录"""
    # 查找用户
    user = None
    for u in users_db.values():
        if u["email"] == login_data.email:
            user = u
            break
    
    if not user or not verify_password(login_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误"
        )
    
    # 创建访问令牌
    access_token = create_access_token(user["id"])
    
    # 返回用户信息（不包含密码）
    user_response = UserResponse(**{k: v for k, v in user.items() if k != "password"})
    
    return LoginResponse(
        access_token=access_token,
        user=user_response
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
    user_id = current_user["id"]
    
    # 检查邮箱是否被其他用户使用
    if update_data.email:
        for uid, user in users_db.items():
            if uid != user_id and user["email"] == update_data.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱地址已被其他用户使用"
                )
    
    # 更新用户信息
    if update_data.name is not None:
        users_db[user_id]["name"] = update_data.name
    if update_data.email is not None:
        users_db[user_id]["email"] = update_data.email
    if update_data.avatar_url is not None:
        users_db[user_id]["avatar_url"] = update_data.avatar_url
    
    updated_user = users_db[user_id]
    user_response = UserResponse(**{k: v for k, v in updated_user.items() if k != "password"})
    
    return APIResponse(
        message="用户信息更新成功",
        data=user_response
    )


@router.post("/logout",
             response_model=APIResponse,
             summary="用户登出",
             description="注销当前登录会话")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """用户登出"""
    token = credentials.credentials
    
    if token in sessions_db:
        del sessions_db[token]
        return APIResponse(message="登出成功")
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的访问令牌"
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
    
    users = []
    for user in users_db.values():
        users.append(UserResponse(**{k: v for k, v in user.items() if k != "password"}))
    
    return users


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
    
    if user_id not in users_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    if user_id == current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账号"
        )
    
    del users_db[user_id]
    
    # 删除相关会话
    tokens_to_delete = []
    for token, session in sessions_db.items():
        if session["user_id"] == user_id:
            tokens_to_delete.append(token)
    
    for token in tokens_to_delete:
        del sessions_db[token]
    
    return APIResponse(message="用户删除成功") 