"""
WebSocket服务器 - 实时多模态分析
处理前端发送的视频帧和音频数据，进行实时分析并返回结果
"""
import asyncio
import json
import logging
import base64
import io
import uuid
from datetime import datetime
from typing import Dict, Any, Set
from concurrent.futures import ThreadPoolExecutor
import cv2
import numpy as np
from PIL import Image
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
import redis

from src.tools.realtime_analyzer import RealtimeMultimodalProcessor
from src.database.sqlite_manager import db_manager
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis客户端
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
    redis_client.ping()
    logger.info("✅ Redis连接成功 (WebSocket)")
except Exception as e:
    logger.error(f"⚠️ Redis连接失败: {e}")
    redis_client = None

# 线程池用于异步处理分析任务
executor = ThreadPoolExecutor(max_workers=4)


def verify_websocket_token(access_token: str) -> dict:
    """WebSocket专用的token验证函数"""
    try:
        if not access_token:
            return None
        
        # 清理过期会话
        db_manager.cleanup_expired_sessions()
        
        # 获取会话信息
        session = db_manager.get_session(access_token)
        if not session:
            return None
        
        # 检查会话是否过期
        if datetime.fromisoformat(session["expires_at"]) < datetime.now():
            db_manager.delete_session(access_token)
            return None
        
        # 获取用户信息
        user = db_manager.get_user_by_id(session["user_id"])
        if not user:
            db_manager.delete_session(access_token)
            return None
        
        return user
        
    except Exception as e:
        logger.error(f"Token验证失败: {e}")
        return None


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_connections: Dict[str, str] = {}  # session_id -> connection_id
        self.connection_info: Dict[str, Dict[str, Any]] = {}
        
    async def connect(self, websocket: WebSocket, connection_id: str):
        """接受WebSocket连接"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        self.connection_info[connection_id] = {
            'connected_at': datetime.now(),
            'session_id': None,
            'authenticated': False,
            'analysis_active': False
        }
        logger.info(f"🔗 WebSocket连接建立: {connection_id}")
        
    def disconnect(self, connection_id: str):
        """断开WebSocket连接"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            
        if connection_id in self.connection_info:
            session_id = self.connection_info[connection_id].get('session_id')
            if session_id and session_id in self.session_connections:
                del self.session_connections[session_id]
            del self.connection_info[connection_id]
            
        logger.info(f"🔌 WebSocket连接断开: {connection_id}")
        
    async def send_personal_message(self, message: dict, connection_id: str):
        """发送个人消息"""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_text(json.dumps(message, ensure_ascii=False))
                except Exception as e:
                    logger.error(f"❌ 发送消息失败 {connection_id}: {e}")
                    self.disconnect(connection_id)
    
    def authenticate_connection(self, connection_id: str, session_id: str):
        """认证连接"""
        if connection_id in self.connection_info:
            self.connection_info[connection_id]['session_id'] = session_id
            self.connection_info[connection_id]['authenticated'] = True
            self.session_connections[session_id] = connection_id
            logger.info(f"✅ 连接认证成功: {connection_id} -> {session_id}")
            return True
        return False
    
    def get_connection_by_session(self, session_id: str) -> str:
        """根据session_id获取connection_id"""
        return self.session_connections.get(session_id)
    
    def get_active_connections_count(self) -> int:
        """获取活跃连接数"""
        return len(self.active_connections)


# 全局连接管理器
manager = ConnectionManager()

# 实时分析处理器
realtime_processor = RealtimeMultimodalProcessor()


class RealtimeAnalysisHandler:
    """实时分析处理器"""
    
    def __init__(self):
        self.processing_queue = asyncio.Queue(maxsize=100)
        self.results_cache = {}  # 缓存最近的分析结果
        
    async def handle_video_frame(self, connection_id: str, frame_data: dict):
        """处理视频帧"""
        try:
            # 解码base64图像
            frame_base64 = frame_data['frame'].split(',')[1]  # 移除data:image/jpeg;base64,前缀
            frame_bytes = base64.b64decode(frame_base64)
            
            # 转换为OpenCV格式
            image = Image.open(io.BytesIO(frame_bytes))
            frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # 添加到处理队列
            analysis_task = {
                'type': 'video',
                'connection_id': connection_id,
                'data': frame,
                'timestamp': frame_data['timestamp'],
                'metadata': {
                    'width': frame_data.get('width', 640),
                    'height': frame_data.get('height', 480)
                }
            }
            
            # 异步处理（避免阻塞）
            asyncio.create_task(self._process_video_analysis(analysis_task))
            
        except Exception as e:
            logger.error(f"❌ 视频帧处理失败 {connection_id}: {e}")
            await manager.send_personal_message({
                'type': 'error',
                'data': f'视频帧处理失败: {str(e)}'
            }, connection_id)
    
    async def handle_audio_chunk(self, connection_id: str, audio_data: dict):
        """处理音频片段"""
        try:
            # 解码base64音频
            audio_base64 = audio_data['audio']
            audio_bytes = base64.b64decode(audio_base64)
            
            # 添加到处理队列
            analysis_task = {
                'type': 'audio',
                'connection_id': connection_id,
                'data': audio_bytes,
                'timestamp': audio_data['timestamp'],
                'metadata': {
                    'duration': audio_data.get('duration', 3000),
                    'format': 'webm'
                }
            }
            
            # 异步处理
            asyncio.create_task(self._process_audio_analysis(analysis_task))
            
        except Exception as e:
            logger.error(f"❌ 音频片段处理失败 {connection_id}: {e}")
            await manager.send_personal_message({
                'type': 'error',
                'data': f'音频片段处理失败: {str(e)}'
            }, connection_id)
    
    async def _process_video_analysis(self, task: dict):
        """异步处理视频分析"""
        try:
            connection_id = task['connection_id']
            frame = task['data']
            
            # 使用线程池执行CPU密集型任务
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                executor, 
                realtime_processor.analyze_video_frame, 
                frame
            )
            
            if result:
                # 缓存结果
                self.results_cache[f"{connection_id}_video"] = {
                    'result': result,
                    'timestamp': task['timestamp']
                }
                
                # 发送分析结果
                await manager.send_personal_message({
                    'type': 'visual_analysis',
                    'data': result,
                    'timestamp': task['timestamp']
                }, connection_id)
                
                logger.debug(f"🎥 视频分析完成: {connection_id}")
            
        except Exception as e:
            logger.error(f"❌ 视频分析处理失败: {e}")
    
    async def _process_audio_analysis(self, task: dict):
        """异步处理音频分析"""
        try:
            connection_id = task['connection_id']
            audio_bytes = task['data']
            
            # 使用线程池执行CPU密集型任务
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                executor, 
                realtime_processor.analyze_audio_chunk, 
                audio_bytes
            )
            
            if result:
                # 缓存结果
                self.results_cache[f"{connection_id}_audio"] = {
                    'result': result,
                    'timestamp': task['timestamp']
                }
                
                # 发送分析结果
                await manager.send_personal_message({
                    'type': 'audio_analysis',
                    'data': result,
                    'timestamp': task['timestamp']
                }, connection_id)
                
                logger.debug(f"🎵 音频分析完成: {connection_id}")
            
        except Exception as e:
            logger.error(f"❌ 音频分析处理失败: {e}")
    
    def get_latest_results(self, connection_id: str) -> dict:
        """获取最新的分析结果"""
        video_key = f"{connection_id}_video"
        audio_key = f"{connection_id}_audio"
        
        return {
            'video': self.results_cache.get(video_key, {}).get('result'),
            'audio': self.results_cache.get(audio_key, {}).get('result'),
            'timestamp': datetime.now().isoformat()
        }


# 全局分析处理器
analysis_handler = RealtimeAnalysisHandler()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket端点处理器"""
    connection_id = str(uuid.uuid4())
    
    try:
        # 建立连接
        await manager.connect(websocket, connection_id)
        
        # 发送连接确认
        await manager.send_personal_message({
            'type': 'connected',
            'data': {
                'connection_id': connection_id,
                'timestamp': datetime.now().isoformat()
            }
        }, connection_id)
        
        # 消息处理循环
        while True:
            try:
                # 接收消息
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # 处理不同类型的消息
                await handle_message(connection_id, message)
                
            except WebSocketDisconnect:
                logger.info(f"🔌 客户端主动断开连接: {connection_id}")
                break
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON解析错误 {connection_id}: {e}")
                await manager.send_personal_message({
                    'type': 'error',
                    'data': 'JSON格式错误'
                }, connection_id)
                
            except Exception as e:
                logger.error(f"❌ 消息处理错误 {connection_id}: {e}")
                await manager.send_personal_message({
                    'type': 'error',
                    'data': f'服务器内部错误: {str(e)}'
                }, connection_id)
    
    except Exception as e:
        logger.error(f"❌ WebSocket连接错误 {connection_id}: {e}")
    
    finally:
        # 清理连接
        manager.disconnect(connection_id)


async def handle_message(connection_id: str, message: dict):
    """处理WebSocket消息"""
    message_type = message.get('type')
    data = message.get('data', {})
    
    logger.debug(f"📨 收到消息 {connection_id}: {message_type}")
    
    try:
        if message_type == 'auth':
            await handle_auth(connection_id, data)
            
        elif message_type == 'video_frame':
            await analysis_handler.handle_video_frame(connection_id, data)
            
        elif message_type == 'audio_chunk':
            await analysis_handler.handle_audio_chunk(connection_id, data)
            
        elif message_type == 'get_status':
            await handle_get_status(connection_id)
            
        elif message_type == 'ping':
            await manager.send_personal_message({
                'type': 'pong',
                'data': {'timestamp': datetime.now().isoformat()}
            }, connection_id)
            
        else:
            logger.warning(f"⚠️ 未知消息类型 {connection_id}: {message_type}")
            await manager.send_personal_message({
                'type': 'error',
                'data': f'未知消息类型: {message_type}'
            }, connection_id)
    
    except Exception as e:
        logger.error(f"❌ 消息处理失败 {connection_id}: {e}")
        await manager.send_personal_message({
            'type': 'error',
            'data': f'消息处理失败: {str(e)}'
        }, connection_id)


async def handle_auth(connection_id: str, auth_data: dict):
    """处理认证"""
    try:
        session_id = auth_data.get('session_id')
        access_token = auth_data.get('access_token')
        
        if not session_id or not access_token:
            raise ValueError('缺少session_id或access_token')
        
        # 验证token（使用WebSocket专用验证）
        user_info = verify_websocket_token(access_token)
        if not user_info:
            raise ValueError('token验证失败')
        
        # 认证连接
        success = manager.authenticate_connection(connection_id, session_id)
        
        if success:
            await manager.send_personal_message({
                'type': 'auth_success',
                'data': {
                    'session_id': session_id,
                    'user_id': user_info.get('id'),
                    'authenticated_at': datetime.now().isoformat()
                }
            }, connection_id)
            
            logger.info(f"✅ 用户认证成功: {connection_id} -> {user_info.get('name')}")
        else:
            raise ValueError('连接认证失败')
    
    except Exception as e:
        logger.error(f"❌ 认证失败 {connection_id}: {e}")
        await manager.send_personal_message({
            'type': 'auth_error',
            'data': str(e)
        }, connection_id)


async def handle_get_status(connection_id: str):
    """处理状态查询"""
    try:
        conn_info = manager.connection_info.get(connection_id, {})
        latest_results = analysis_handler.get_latest_results(connection_id)
        
        status = {
            'connection_id': connection_id,
            'authenticated': conn_info.get('authenticated', False),
            'session_id': conn_info.get('session_id'),
            'connected_at': conn_info.get('connected_at', datetime.now()).isoformat(),
            'analysis_active': conn_info.get('analysis_active', False),
            'latest_results': latest_results,
            'server_stats': {
                'active_connections': manager.get_active_connections_count(),
                'processing_queue_size': analysis_handler.processing_queue.qsize()
            }
        }
        
        await manager.send_personal_message({
            'type': 'status',
            'data': status
        }, connection_id)
        
    except Exception as e:
        logger.error(f"❌ 状态查询失败 {connection_id}: {e}")
        await manager.send_personal_message({
            'type': 'error',
            'data': f'状态查询失败: {str(e)}'
        }, connection_id)


# 导出管理器供其他模块使用
__all__ = ['websocket_endpoint', 'manager', 'analysis_handler'] 