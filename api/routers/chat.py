"""
实时聊天系统API路由
支持基于LangChain的智能面试对话和流式响应
"""
import json
import uuid
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.routers.users import get_current_user
from src.workflow import create_interview_workflow
from src.models.state import create_initial_state, UserInfo
from src.models.spark_client import create_spark_model

logger = logging.getLogger(__name__)

router = APIRouter()

# 聊天会话存储
chat_sessions = {}
# WebSocket连接管理
websocket_connections = {}


class ChatMessage(BaseModel):
    """聊天消息模型"""
    role: str  # "user" 或 "assistant"
    content: str
    timestamp: datetime = None
    session_id: str = None
    
    def __init__(self, **data):
        if data.get('timestamp') is None:
            data['timestamp'] = datetime.now()
        super().__init__(**data)


class ChatStartRequest(BaseModel):
    """开始聊天请求"""
    user_name: str
    target_position: str
    target_field: str
    resume_text: str = ""


class ChatMessageRequest(BaseModel):
    """发送消息请求"""
    session_id: str
    message: str
    message_type: str = "text"  # text, audio, video


class ChatResponse(BaseModel):
    """聊天响应"""
    session_id: str
    message: ChatMessage
    is_complete: bool = False
    interview_stage: str = "conversation"


class ChatSession:
    """聊天会话管理类"""
    
    def __init__(self, session_id: str, user_info: UserInfo):
        self.session_id = session_id
        self.user_info = user_info
        self.messages: List[ChatMessage] = []
        self.workflow = create_interview_workflow()
        self.state = create_initial_state(session_id, user_info)
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        
        # 初始化智能面试官
        self._initialize_interviewer()
    
    def _initialize_interviewer(self):
        """初始化AI面试官"""
        welcome_message = ChatMessage(
            role="assistant",
            content=f"您好 {self.user_info.name}！我是您的AI面试官。我看到您应聘的是{self.user_info.target_position}职位，让我们开始面试吧。请先简单介绍一下自己。",
            session_id=self.session_id
        )
        self.messages.append(welcome_message)
    
    async def process_user_message(self, message: str) -> AsyncGenerator[str, None]:
        """处理用户消息并生成流式响应"""
        # 添加用户消息
        user_msg = ChatMessage(
            role="user",
            content=message,
            session_id=self.session_id
        )
        self.messages.append(user_msg)
        self.last_activity = datetime.now()
        
        # 更新状态中的对话历史
        self.state["messages"] = [
            {"role": msg.role, "content": msg.content} 
            for msg in self.messages
        ]
        
        # 使用LangChain工作流生成响应
        try:
            # 调用面试官智能体
            response_generator = self._generate_ai_response()
            
            full_response = ""
            async for chunk in response_generator:
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk, 'session_id': self.session_id})}\n\n"
            
            # 添加AI响应到消息历史
            ai_msg = ChatMessage(
                role="assistant",
                content=full_response,
                session_id=self.session_id
            )
            self.messages.append(ai_msg)
            
            # 发送完成标识
            yield f"data: {json.dumps({'type': 'complete', 'session_id': self.session_id})}\n\n"
            
        except Exception as e:
            error_response = f"抱歉，我遇到了一些技术问题：{str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'content': error_response, 'session_id': self.session_id})}\n\n"
    
    async def _generate_ai_response(self) -> AsyncGenerator[str, None]:
        """使用LangChain生成AI响应"""
        try:
            # 构建完整的对话上下文
            conversation_context = self._build_conversation_context()
            
            # 创建星火模型实例
            spark_model = create_spark_model()
            
            # 构建消息格式
            messages = [
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": conversation_context}
            ]
            
            logger.info(f"发送给AI模型的消息: {conversation_context[:200]}...")
            
            # 流式生成响应
            response_stream = spark_model.stream(messages)
            
            response_chunks = []
            for chunk in response_stream:
                content = ""
                if hasattr(chunk, 'content') and chunk.content:
                    content = chunk.content
                elif isinstance(chunk, str):
                    content = chunk
                    
                if content:
                    response_chunks.append(content)
                    yield content
            
            # 记录完整响应用于调试
            full_response = ''.join(response_chunks)
            logger.info(f"AI完整响应: {full_response[:300]}...")
                
        except Exception as e:
            error_msg = f"抱歉，我遇到了一些技术问题。让我们继续其他话题吧。"
            logger.error(f"AI响应生成失败: {str(e)}")
            yield error_msg
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return f"""你是一名经验丰富的AI面试官，正在面试应聘{self.user_info.target_position}职位的候选人。

面试官背景：
- 姓名：李诚
- 专业领域：{self.user_info.target_field}
- 风格：专业、友好、深度

候选人信息：
- 姓名：{self.user_info.name}
- 目标职位：{self.user_info.target_position}
- 简历摘要：{self.user_info.resume_text[:200]}...

面试要求：
1. 保持专业且友好的态度
2. 根据候选人回答调整问题难度
3. 关注技能匹配度和实际经验
4. 适时给予积极反馈和建议
5. 确保面试流程连贯有序
6. 每次回应控制在100-200字内
7. 可以询问具体的项目经验和技术细节

请以面试官的身份进行对话，根据对话历史提出相关问题或给出回应。"""

    def _build_conversation_context(self) -> str:
        """构建对话上下文"""
        if len(self.messages) <= 1:
            return "请开始自我介绍，包括您的工作经历和技术背景。"
        
        context = "对话历史：\n"
        # 只取最近8轮对话，避免上下文过长
        recent_messages = self.messages[-16:]  # 8轮对话=16条消息
        
        for msg in recent_messages:
            role_name = "候选人" if msg.role == "user" else "面试官"
            context += f"{role_name}: {msg.content}\n"
        
        context += "\n现在请根据以上对话历史，作为面试官给出合适的回应："
        return context


@router.post("/chat/start", response_model=ChatResponse)
async def start_chat_session(
    request: ChatStartRequest,
    current_user: dict = Depends(get_current_user)
):
    """开始新的聊天会话"""
    try:
        # 创建会话ID
        session_id = str(uuid.uuid4())
        
        # 创建用户信息
        user_info = UserInfo(
            user_id=current_user["id"],
            name=request.user_name,
            target_position=request.target_position,
            target_field=request.target_field,
            resume_text=request.resume_text,
            resume_summary={}
        )
        
        # 创建聊天会话
        chat_session = ChatSession(session_id, user_info)
        chat_sessions[session_id] = chat_session
        
        # 返回初始响应（欢迎消息）
        welcome_message = chat_session.messages[0]
        
        return ChatResponse(
            session_id=session_id,
            message=welcome_message,
            is_complete=False,
            interview_stage="introduction"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"创建聊天会话失败: {str(e)}"
        )


@router.post("/chat/message")
async def send_chat_message(
    request: ChatMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """发送聊天消息并获取流式响应"""
    if request.session_id not in chat_sessions:
        raise HTTPException(
            status_code=404,
            detail="聊天会话不存在"
        )
    
    chat_session = chat_sessions[request.session_id]
    
    # 权限检查
    if chat_session.user_info.user_id != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此聊天会话"
        )
    
    try:
        # 创建Server-Sent Events响应
        async def generate_response():
            yield "data: {\"type\": \"start\", \"session_id\": \"" + request.session_id + "\"}\n\n"
            
            async for chunk in chat_session.process_user_message(request.message):
                yield chunk
                
            yield "data: {\"type\": \"end\"}\n\n"
        
        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"处理消息失败: {str(e)}"
        )


@router.get("/chat/history/{session_id}")
async def get_chat_history(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取聊天历史"""
    if session_id not in chat_sessions:
        raise HTTPException(
            status_code=404,
            detail="聊天会话不存在"
        )
    
    chat_session = chat_sessions[session_id]
    
    # 权限检查
    if chat_session.user_info.user_id != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此聊天会话"
        )
    
    return {
        "session_id": session_id,
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in chat_session.messages
        ],
        "created_at": chat_session.created_at.isoformat(),
        "last_activity": chat_session.last_activity.isoformat()
    }


@router.websocket("/chat/ws/{session_id}")
async def websocket_chat_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket聊天端点"""
    await websocket.accept()
    
    if session_id not in chat_sessions:
        await websocket.send_json({"type": "error", "message": "会话不存在"})
        await websocket.close()
        return
    
    chat_session = chat_sessions[session_id]
    websocket_connections[session_id] = websocket
    
    try:
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "WebSocket连接已建立"
        })
        
        while True:
            # 接收消息
            data = await websocket.receive_json()
            
            if data.get("type") == "message":
                message = data.get("message", "")
                
                # 发送开始处理标识
                await websocket.send_json({
                    "type": "processing_start",
                    "session_id": session_id
                })
                
                # 处理消息并流式发送响应
                full_response = ""
                async for chunk in chat_session.process_user_message(message):
                    # 解析chunk数据
                    if chunk.startswith("data: "):
                        chunk_data = chunk[6:].strip()
                        if chunk_data:
                            try:
                                parsed_chunk = json.loads(chunk_data)
                                if parsed_chunk.get("type") == "chunk":
                                    full_response += parsed_chunk.get("content", "")
                                    await websocket.send_json({
                                        "type": "chunk",
                                        "content": parsed_chunk.get("content", ""),
                                        "session_id": session_id
                                    })
                                elif parsed_chunk.get("type") == "complete":
                                    await websocket.send_json({
                                        "type": "complete",
                                        "full_response": full_response,
                                        "session_id": session_id
                                    })
                                elif parsed_chunk.get("type") == "error":
                                    await websocket.send_json({
                                        "type": "error",
                                        "message": parsed_chunk.get("content", ""),
                                        "session_id": session_id
                                    })
                            except json.JSONDecodeError:
                                continue
                
    except WebSocketDisconnect:
        if session_id in websocket_connections:
            del websocket_connections[session_id]
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"WebSocket错误: {str(e)}",
            "session_id": session_id
        })
        await websocket.close()


@router.get("/chat/sessions")
async def get_user_chat_sessions(
    current_user: dict = Depends(get_current_user)
):
    """获取用户的所有聊天会话"""
    user_sessions = []
    for session_id, session in chat_sessions.items():
        if session.user_info.user_id == current_user["id"]:
            user_sessions.append({
                "session_id": session_id,
                "target_position": session.user_info.target_position,
                "target_field": session.user_info.target_field,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "message_count": len(session.messages)
            })
    
    # 按最后活动时间排序
    user_sessions.sort(key=lambda x: x["last_activity"], reverse=True)
    return {"sessions": user_sessions}


@router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除聊天会话"""
    if session_id not in chat_sessions:
        raise HTTPException(
            status_code=404,
            detail="聊天会话不存在"
        )
    
    chat_session = chat_sessions[session_id]
    
    # 权限检查
    if chat_session.user_info.user_id != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此聊天会话"
        )
    
    # 关闭WebSocket连接（如果存在）
    if session_id in websocket_connections:
        try:
            await websocket_connections[session_id].close()
        except:
            pass
        del websocket_connections[session_id]
    
    # 删除会话
    del chat_sessions[session_id]
    
    return {"message": "聊天会话已删除"}
