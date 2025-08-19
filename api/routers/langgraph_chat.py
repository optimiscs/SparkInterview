"""
基于LangGraph的智能面试官API路由
使用LangGraph状态图简化感知-决策-行动逻辑
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import asyncio

from api.routers.users import get_current_user
from src.agents.langgraph_interview_agent import LangGraphInterviewAgent
from src.database.session_manager import get_session_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局智能体实例 - 延迟初始化以处理依赖问题
langgraph_agent = None

def get_langgraph_agent():
    """获取LangGraph智能体实例，延迟初始化"""
    global langgraph_agent
    
    if langgraph_agent is None:
        try:
            langgraph_agent = LangGraphInterviewAgent()
            logger.info("✅ LangGraph智能体延迟初始化成功")
        except Exception as e:
            logger.error(f"❌ LangGraph智能体初始化失败: {e}")
            langgraph_agent = False  # 标记为失败，避免重复尝试
            
    return langgraph_agent if langgraph_agent is not False else None

# 会话存储 - 现在使用数据库持久化
active_sessions = {}
# WebSocket连接管理
websocket_connections = {}

# 初始化时从数据库恢复会话
def initialize_sessions():
    """从数据库恢复会话到内存"""
    global active_sessions
    try:
        session_mgr = get_session_manager()
        active_sessions = session_mgr.load_active_sessions()
        logger.info(f"📚 从数据库恢复了 {len(active_sessions)} 个会话")
    except Exception as e:
        logger.error(f"❌ 从数据库恢复会话失败: {e}")
        active_sessions = {}

# 服务启动时恢复会话
initialize_sessions()


class LangGraphChatStartRequest(BaseModel):
    """LangGraph聊天开始请求"""
    user_name: str
    target_position: str
    target_field: str
    resume_text: str = ""


class LangGraphChatMessageRequest(BaseModel):
    """LangGraph聊天消息请求"""
    session_id: str
    message: str


class LangGraphChatResponse(BaseModel):
    """LangGraph聊天响应"""
    success: bool
    session_id: Optional[str] = None
    message: Optional[str] = None
    user_profile: Optional[Dict] = None
    completeness_score: Optional[float] = None
    missing_info: Optional[List[str]] = None
    user_emotion: Optional[str] = None
    decision: Optional[Dict] = None
    interview_stage: Optional[str] = None
    error: Optional[str] = None


@router.post("/langgraph-chat/start", response_model=LangGraphChatResponse)
async def start_langgraph_chat(
    request: LangGraphChatStartRequest,
    current_user: dict = Depends(get_current_user)
):
    """开始LangGraph智能面试会话"""
    
    # 使用延迟初始化的智能体
    agent = get_langgraph_agent()
    if not agent:
        raise HTTPException(
            status_code=503,
            detail="LangGraph智能体服务不可用，请检查依赖库安装"
        )
    
    try:
        # 创建会话ID
        session_id = str(uuid.uuid4())
        user_id = current_user["id"]
        
        logger.info(f"🚀 启动LangGraph面试会话: {session_id}")
        logger.info(f"👤 用户: {request.user_name} ({user_id})")
        logger.info(f"🎯 目标职位: {request.target_position}")
        
        # 使用LangGraph智能体开始面试
        result = await agent.start_interview(
            user_id=user_id,
            session_id=session_id,
            user_name=request.user_name,
            target_position=request.target_position,
            target_field=request.target_field,
            resume_text=request.resume_text
        )
        
        if result["success"]:
            # 准备会话信息
            session_data = {
                "user_id": user_id,
                "user_name": request.user_name,
                "target_position": request.target_position,
                "target_field": request.target_field,
                "resume_text": request.resume_text,
                "status": "active",
                "interview_ended": False,
                "created_at": datetime.now(),
                "last_activity": datetime.now()
            }
            
            # 保存到内存
            active_sessions[session_id] = session_data
            
            # 持久化到数据库
            session_mgr = get_session_manager()
            session_mgr.save_session(session_id, session_data)
            
            logger.info(f"✅ LangGraph会话创建成功并持久化: {session_id}")
            
            return LangGraphChatResponse(
                success=True,
                session_id=session_id,
                message=result["welcome_message"],
                user_profile=result["user_profile"],
                completeness_score=result["user_profile"]["completeness_score"],
                interview_stage=result["interview_stage"]
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"智能体启动失败: {result.get('error', '未知错误')}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 启动LangGraph会话失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"启动会话失败: {str(e)}"
        )


@router.post("/langgraph-chat/message", response_model=LangGraphChatResponse)
async def send_langgraph_message(
    request: LangGraphChatMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """发送LangGraph聊天消息"""
    
    # 使用延迟初始化的智能体
    agent = get_langgraph_agent()
    if not agent:
        raise HTTPException(
            status_code=503,
            detail="LangGraph智能体服务不可用，请检查依赖库安装"
        )
    
    session_id = request.session_id
    
    # 检查会话是否存在，支持从数据库恢复
    session_info = active_sessions.get(session_id)
    
    if not session_info:
        # 尝试从数据库恢复会话
        session_mgr = get_session_manager()
        session_info = session_mgr.get_session(session_id)
        
        if session_info:
            # 恢复到内存
            active_sessions[session_id] = session_info
            logger.info(f"🔄 从数据库恢复会话: {session_id}")
        else:
            raise HTTPException(
                status_code=404,
                detail="会话不存在或已过期"
            )
    
    # 权限检查
    if session_info["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此会话"
        )
    
    try:
        # 更新会话活跃时间
        session_info["last_activity"] = datetime.now()
        
        # 持久化会话活跃时间到数据库
        session_mgr = get_session_manager()
        session_mgr.update_session_activity(session_id)
        
        logger.info(f"💬 处理LangGraph消息: {request.message[:50]}...")
        
        # 获取当前用户画像（简化版，实际应从数据库加载）
        current_profile = {
            "basic_info": {
                "name": session_info["user_name"],
                "target_position": session_info["target_position"],
                "target_field": session_info["target_field"],
                "work_years": None,
                "current_company": None,
                "education_level": None,
                "graduation_year": None,
                "expected_salary": None,
            },
            "technical_skills": {},
            "completeness_score": 0.2
        }
        
        # 使用LangGraph智能体处理消息（新的统一工作流）
        result = await agent.process_message_via_langgraph(
            user_id=session_info["user_id"],
            session_id=session_id,
            user_name=session_info["user_name"],
            target_position=session_info["target_position"],
            user_message=request.message,
            user_profile=current_profile
        )
        
        if result["success"]:
            logger.info(f"✅ LangGraph消息处理成功")
            logger.info(f"🧠 用户情绪: {result.get('user_emotion', 'unknown')}")
            logger.info(f"📊 完整度: {result.get('completeness_score', 0):.1%}")
            logger.info(f"🤖 决策: {result.get('decision', {}).get('action_type', 'unknown')}")
            
            return LangGraphChatResponse(
                success=True,
                session_id=session_id,
                message=result["response"],
                user_profile=result.get("user_profile"),
                completeness_score=result.get("completeness_score"),
                missing_info=result.get("missing_info"),
                user_emotion=result.get("user_emotion"),
                decision=result.get("decision"),
                interview_stage=result.get("interview_stage")
            )
        else:
            return LangGraphChatResponse(
                success=False,
                error=result.get("error", "处理失败"),
                message=result.get("response", "抱歉，我遇到了一些问题。")
            )
    
    except Exception as e:
        logger.error(f"❌ LangGraph消息处理失败: {e}")
        return LangGraphChatResponse(
            success=False,
            error=str(e),
            message="抱歉，我遇到了一些技术问题，请稍后再试。"
        )


@router.post("/langgraph-chat/stream")
async def stream_langgraph_message(
    request: LangGraphChatMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """流式LangGraph聊天响应"""
    
    # 使用延迟初始化的智能体
    agent = get_langgraph_agent()
    if not agent:
        raise HTTPException(
            status_code=503,
            detail="LangGraph智能体服务不可用，请检查依赖库安装"
        )
    
    session_id = request.session_id
    
    # 检查会话权限
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    session_info = active_sessions[session_id]
    if session_info["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="无权访问此会话")
    
    async def generate_stream():
        """生成流式响应"""
        try:
            yield "data: " + json.dumps({
                "type": "start", 
                "session_id": session_id,
                "message": "🧠 LangGraph智能体正在感知和决策..."
            }) + "\n\n"
            
            # 模拟流式处理过程
            steps = [
                "🧠 感知用户状态...",
                "🤖 制定面试策略...", 
                "🔍 分析信息缺失...",
                "⚡ 执行智能行动...",
                "💾 更新用户画像..."
            ]
            
            for i, step in enumerate(steps):
                yield "data: " + json.dumps({
                    "type": "progress",
                    "step": i + 1,
                    "total": len(steps),
                    "message": step
                }) + "\n\n"
                await asyncio.sleep(0.5)
            
            # 获取当前用户画像
            current_profile = {
                "basic_info": {
                    "name": session_info["user_name"],
                    "target_position": session_info["target_position"], 
                    "target_field": session_info["target_field"],
                    "work_years": None,
                    "current_company": None,
                    "education_level": None,
                    "graduation_year": None,
                },
                "completeness_score": 0.2
            }
            
            # 调用LangGraph智能体（新的统一工作流）
            result = await agent.process_message_via_langgraph(
                user_id=session_info["user_id"],
                session_id=session_id,
                user_name=session_info["user_name"],
                target_position=session_info["target_position"],
                user_message=request.message,
                user_profile=current_profile
            )
            
            # 流式输出响应
            if result["success"]:
                response_text = result["response"]
                
                # 模拟逐字输出
                for i, char in enumerate(response_text):
                    yield "data: " + json.dumps({
                        "type": "chunk",
                        "content": char,
                        "index": i
                    }) + "\n\n"
                    await asyncio.sleep(0.03)  # 模拟打字效果
                
                # 发送完成信息
                yield "data: " + json.dumps({
                    "type": "complete",
                    "session_id": session_id,
                    "user_profile": result.get("user_profile"),
                    "completeness_score": result.get("completeness_score"),
                    "user_emotion": result.get("user_emotion"),
                    "decision": result.get("decision"),
                    "missing_info": result.get("missing_info")
                }) + "\n\n"
            else:
                yield "data: " + json.dumps({
                    "type": "error",
                    "error": result.get("error", "处理失败")
                }) + "\n\n"
            
            yield "data: " + json.dumps({"type": "end"}) + "\n\n"
            
        except Exception as e:
            logger.error(f"❌ 流式响应生成失败: {e}")
            yield "data: " + json.dumps({
                "type": "error",
                "error": f"生成响应失败: {str(e)}"
            }) + "\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


@router.get("/langgraph-chat/sessions")
async def get_langgraph_sessions(current_user: dict = Depends(get_current_user)):
    """获取用户的LangGraph会话列表 - 从数据库查询"""
    try:
        user_id = current_user["id"]
        
        # 直接从数据库获取会话列表，确保数据不丢失
        session_mgr = get_session_manager()
        db_sessions = session_mgr.get_user_sessions(user_id)
        
        user_sessions = []
        for session in db_sessions:
            session_item = {
                "session_id": session["session_id"],
                "user_name": session["user_name"],
                "target_position": session["target_position"],
                "target_field": session["target_field"],
                "created_at": session["created_at"] if isinstance(session["created_at"], str) else session["created_at"].isoformat(),
                "last_activity": session["last_activity"] if isinstance(session["last_activity"], str) else session["last_activity"].isoformat(),
                "status": session.get("status", "active"),
                "interview_ended": session.get("interview_ended", False),
                "report_id": session.get("report_id")
            }
            user_sessions.append(session_item)
            
            # 同步到内存（为了WebSocket和其他实时功能）
            if session["session_id"] not in active_sessions:
                active_sessions[session["session_id"]] = session
        
        logger.info(f"📋 从数据库获取用户会话: {len(user_sessions)} 个")
        
        return {
            "success": True,
            "sessions": user_sessions,
            "total": len(user_sessions)
        }
        
    except Exception as e:
        logger.error(f"❌ 获取会话列表失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取会话列表失败: {str(e)}"
        )


@router.delete("/langgraph-chat/sessions/{session_id}")
async def delete_langgraph_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除LangGraph会话"""
    try:
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        session_info = active_sessions[session_id]
        
        # 权限检查
        if session_info["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权删除此会话")
        
        # 从内存删除会话
        del active_sessions[session_id]
        
        # 从数据库删除会话
        session_mgr = get_session_manager()
        session_mgr.delete_session(session_id)
        
        # 清理智能体的会话状态缓存和消息历史
        agent = get_langgraph_agent()
        if agent:
            agent.clear_session_state(session_id)
            agent.clear_session_messages(session_id)
        
        logger.info(f"🗑️ 已从内存和数据库删除LangGraph会话: {session_id}")
        
        return {
            "success": True,
            "message": "会话已删除"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除会话失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"删除会话失败: {str(e)}"
        )


@router.get("/langgraph-chat/sessions/{session_id}/status")
async def get_session_status(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取LangGraph会话的详细状态"""
    try:
        # 优先从内存获取，如果没有则从数据库恢复
        session_info = active_sessions.get(session_id)
        
        if not session_info:
            # 尝试从数据库恢复会话
            session_mgr = get_session_manager()
            session_info = session_mgr.get_session(session_id)
            
            if session_info:
                # 恢复到内存
                active_sessions[session_id] = session_info
                logger.info(f"🔄 从数据库恢复会话到内存: {session_id}")
            else:
                raise HTTPException(status_code=404, detail="会话不存在")
        
        # 权限检查
        if session_info["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权访问此会话")
        
        # 这里可以从LangGraph智能体获取更详细的状态
        # 暂时返回基本状态信息
        return {
            "success": True,
            "session_id": session_id,
            "session_info": {
                "user_name": session_info["user_name"],
                "target_position": session_info["target_position"],
                "target_field": session_info["target_field"],
                "created_at": session_info["created_at"].isoformat(),
                "last_activity": session_info["last_activity"].isoformat()
            },
            "agent_status": "active",
            "framework": "LangGraph + LangChain"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取会话状态失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取会话状态失败: {str(e)}"
        )


@router.post("/langgraph-chat/sessions/{session_id}/reset")
async def reset_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """重置LangGraph会话状态"""
    try:
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        session_info = active_sessions[session_id]
        
        # 权限检查
        if session_info["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权操作此会话")
        
        # 重置会话的时间戳
        session_info["last_activity"] = datetime.now()
        
        logger.info(f"🔄 重置LangGraph会话: {session_id}")
        
        return {
            "success": True,
            "message": "会话已重置",
            "session_id": session_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 重置会话失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"重置会话失败: {str(e)}"
        )


@router.get("/langgraph-chat/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """获取会话的消息历史"""
    try:
        # 检查会话权限，支持从数据库恢复
        session_info = active_sessions.get(session_id)
        
        if not session_info:
            # 尝试从数据库恢复会话
            session_mgr = get_session_manager()
            session_info = session_mgr.get_session(session_id)
            
            if session_info:
                # 恢复到内存
                active_sessions[session_id] = session_info
                logger.info(f"🔄 从数据库恢复会话: {session_id}")
            else:
                raise HTTPException(status_code=404, detail="会话不存在")
        
        if session_info["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权访问此会话")
        
        # 获取智能体实例
        agent = get_langgraph_agent()
        if not agent:
            raise HTTPException(status_code=503, detail="智能体服务不可用")
        
        # 获取消息历史
        messages = agent.get_session_messages(session_id, limit)
        message_summary = agent.get_message_history_summary(session_id)
        
        return {
            "success": True,
            "session_id": session_id,
            "messages": messages,
            "summary": message_summary,
            "total_messages": len(messages)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取会话消息失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取会话消息失败: {str(e)}"
        )


@router.post("/langgraph-chat/sessions/{session_id}/end")
async def end_interview_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """手动结束面试会话并生成报告"""
    try:
        # 检查会话权限，支持从数据库恢复
        session_info = active_sessions.get(session_id)
        
        if not session_info:
            # 尝试从数据库恢复会话
            session_mgr = get_session_manager()
            session_info = session_mgr.get_session(session_id)
            
            if session_info:
                # 恢复到内存
                active_sessions[session_id] = session_info
                logger.info(f"🔄 从数据库恢复会话: {session_id}")
            else:
                raise HTTPException(status_code=404, detail="会话不存在")
        
        if session_info["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权操作此会话")
        
        # 获取智能体实例
        agent = get_langgraph_agent()
        if not agent:
            raise HTTPException(status_code=503, detail="智能体服务不可用")
        
        logger.info(f"🏁 手动结束面试会话: {session_id}")
        
        # 调用智能体的结束面试方法
        result = await agent.end_interview_and_generate_report(
            user_id=session_info["user_id"],
            session_id=session_id,
            user_name=session_info["user_name"],
            target_position=session_info["target_position"]
        )
        
        if result["success"]:
            # 更新内存中的会话状态
            session_info["status"] = "completed"
            session_info["completed_at"] = datetime.now()
            session_info["report_id"] = result.get("report_id")
            session_info["interview_ended"] = True
            
            # 持久化到数据库
            session_mgr = get_session_manager()
            session_mgr.mark_session_completed(session_id, result.get("report_id"))
            session_mgr.save_session(session_id, session_info)  # 保存完整状态
            
            logger.info(f"✅ 面试会话结束成功并持久化: {session_id}, 报告ID: {result.get('report_id')}")
            
            return {
                "success": True,
                "session_id": session_id,
                "summary_message": result["summary_message"],
                "report_id": result.get("report_id"),
                "message": "面试已结束，报告已生成"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"结束面试失败: {result.get('error', '未知错误')}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 结束面试会话失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"结束面试失败: {str(e)}"
        )


@router.post("/langgraph-chat/sessions/{session_id}/generate-report")
async def generate_interview_report(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """生成面试报告"""
    try:
        # 检查会话权限，支持从数据库恢复
        session_info = active_sessions.get(session_id)
        
        if not session_info:
            # 尝试从数据库恢复会话
            session_mgr = get_session_manager()
            session_info = session_mgr.get_session(session_id)
            
            if session_info:
                # 恢复到内存
                active_sessions[session_id] = session_info
                logger.info(f"🔄 从数据库恢复会话: {session_id}")
            else:
                raise HTTPException(status_code=404, detail="会话不存在")
        
        if session_info["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权访问此会话")
        
        # 获取智能体实例
        agent = get_langgraph_agent()
        if not agent:
            raise HTTPException(status_code=503, detail="智能体服务不可用")
        
        logger.info(f"📊 生成面试报告: {session_id}")
        
        # 调用智能体的报告生成方法
        result = await agent.generate_interview_report(
            user_id=session_info["user_id"],
            session_id=session_id,
            user_name=session_info["user_name"],
            target_position=session_info["target_position"]
        )
        
        if result["success"]:
            logger.info(f"✅ 面试报告生成成功: {session_id}")
            
            return {
                "success": True,
                "session_id": session_id,
                "report_id": result["report_id"],
                "report_data": result.get("report_data"),
                "message": "面试报告已生成"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"生成报告失败: {result.get('error', '未知错误')}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 生成面试报告失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"生成报告失败: {str(e)}"
        )


@router.get("/langgraph-chat/reports/{report_id}")
async def get_interview_report(
    report_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取面试报告数据"""
    try:
        logger.info(f"📊 获取面试报告: {report_id}, 用户: {current_user['id']}")
        
        # 直接使用SessionManager获取报告
        session_mgr = get_session_manager()
        report = session_mgr.get_report(report_id)
        
        if report:
            # 检查权限：报告的用户ID是否匹配当前用户
            if report["user_id"] != current_user["id"]:
                logger.warning(f"⚠️ 用户权限不匹配: 报告属于 {report['user_id']}, 当前用户 {current_user['id']}")
                raise HTTPException(status_code=403, detail="无权访问此报告")
            
            logger.info(f"✅ 报告数据获取成功: {report_id}")
            
            return {
                "success": True,
                "report_id": report_id,
                "report_data": report["report_data"],
                "ai_powered": True,
                "analysis_summary": "基于讯飞星火大模型的智能分析，提供个性化面试评估和建议"
            }
        else:
            logger.warning(f"⚠️ 报告不存在: {report_id}")
            raise HTTPException(status_code=404, detail="报告不存在或已过期")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取面试报告失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取报告失败: {str(e)}"
        )


@router.get("/langgraph-chat/health")
async def langgraph_health_check():
    """LangGraph服务健康检查"""
    agent = get_langgraph_agent()
    if not agent:
        return {
            "status": "unhealthy",
            "message": "LangGraph智能体未初始化或依赖库缺失",
            "active_sessions": len(active_sessions),
            "framework": "LangGraph + LangChain (未可用)"
        }
    
    # 获取缓存健康状态
    cache_health = agent.get_cache_health() if agent else {"status": "unavailable"}
    
    return {
        "status": "healthy",
        "message": "LangGraph智能体运行正常",
        "active_sessions": len(active_sessions),
        "framework": "LangGraph + LangChain",
        "cache": cache_health,
        "version": {
            "langgraph": ">=0.2.0",
            "langchain": ">=0.3.0",
            "redis_cache": "enabled"
        }
    }


@router.websocket("/langgraph-chat/ws/{session_id}")
async def websocket_langgraph_endpoint(websocket: WebSocket, session_id: str):
    """LangGraph实时WebSocket端点"""
    await websocket.accept()
    
    try:
        # 检查会话是否存在
        if session_id not in active_sessions:
            await websocket.send_json({
                "type": "error",
                "message": "会话不存在或已过期"
            })
            await websocket.close()
            return
        
        # 注册WebSocket连接
        websocket_connections[session_id] = websocket
        
        logger.info(f"🔌 WebSocket连接已建立: {session_id}")
        
        # 发送连接确认
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "LangGraph智能体WebSocket连接已建立",
            "framework": "LangGraph + LangChain"
        })
        
        # 监听客户端消息
        while True:
            try:
                data = await websocket.receive_json()
                await handle_websocket_message(session_id, data, websocket)
                
            except WebSocketDisconnect:
                logger.info(f"🔌 WebSocket连接断开: {session_id}")
                break
            except Exception as e:
                logger.error(f"❌ WebSocket消息处理失败: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"消息处理失败: {str(e)}"
                })
    
    except Exception as e:
        logger.error(f"❌ WebSocket连接失败: {e}")
    finally:
        # 清理连接
        if session_id in websocket_connections:
            del websocket_connections[session_id]


async def handle_websocket_message(session_id: str, data: Dict, websocket: WebSocket):
    """处理WebSocket消息"""
    try:
        message_type = data.get("type")
        
        if message_type == "message":
            # 处理聊天消息
            user_message = data.get("message", "")
            
            # 发送处理开始标识
            await websocket.send_json({
                "type": "processing_start",
                "session_id": session_id,
                "message": "🧠 LangGraph智能体开始感知和决策..."
            })
            
            # 获取会话信息
            session_info = active_sessions[session_id]
            
            # 构建当前用户画像（简化版）
            current_profile = {
                "basic_info": {
                    "name": session_info["user_name"],
                    "target_position": session_info["target_position"],
                    "target_field": session_info["target_field"],
                    "work_years": None,
                    "current_company": None,
                    "education_level": None,
                },
                "completeness_score": 0.2
            }
            
            # 调用LangGraph智能体处理
            agent = get_langgraph_agent()
            if not agent:
                await websocket.send_json({
                    "type": "error",
                    "message": "智能体服务不可用"
                })
                return
                
            result = await agent.process_message_via_langgraph(
                user_id=session_info["user_id"],
                session_id=session_id,
                user_name=session_info["user_name"],
                target_position=session_info["target_position"],
                user_message=user_message,
                user_profile=current_profile
            )
            
            # 发送处理步骤
            steps = [
                "🧠 感知用户状态和缺失信息",
                "🤖 基于感知结果制定策略",
                "🔍 分析并提取结构化信息",
                "⚡ 执行智能行动和回应"
            ]
            
            for i, step in enumerate(steps):
                await websocket.send_json({
                    "type": "processing_step",
                    "step": i + 1,
                    "total": len(steps),
                    "message": step
                })
                await asyncio.sleep(0.5)
            
            # 发送最终结果
            if result["success"]:
                await websocket.send_json({
                    "type": "message_complete",
                    "session_id": session_id,
                    "response": result["response"],
                    "user_profile": result.get("user_profile"),
                    "completeness_score": result.get("completeness_score"),
                    "missing_info": result.get("missing_info"),
                    "user_emotion": result.get("user_emotion"),
                    "decision": result.get("decision"),
                    "interview_stage": result.get("interview_stage")
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": result.get("response", "处理失败"),
                    "error": result.get("error")
                })
                
        elif message_type == "ping":
            # 心跳检查
            await websocket.send_json({
                "type": "pong",
                "timestamp": datetime.now().isoformat()
            })
            
        elif message_type == "get_status":
            # 获取当前状态
            session_info = active_sessions.get(session_id, {})
            await websocket.send_json({
                "type": "status_update",
                "session_id": session_id,
                "session_info": {
                    "user_name": session_info.get("user_name"),
                    "target_position": session_info.get("target_position"),
                    "created_at": session_info.get("created_at", datetime.now()).isoformat(),
                    "last_activity": session_info.get("last_activity", datetime.now()).isoformat()
                },
                "framework": "LangGraph + LangChain"
            })
            
    except Exception as e:
        logger.error(f"❌ 处理WebSocket消息失败: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"处理失败: {str(e)}"
        })
