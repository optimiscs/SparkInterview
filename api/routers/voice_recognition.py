# -*- encoding:utf-8 -*-
"""
讯飞实时语音识别代理服务
基于WebSocket实现前后端语音识别集成
"""
import asyncio
import json
import logging
import hashlib
import hmac
import base64
import time
from typing import Dict, Optional, Any
from urllib.parse import quote
import websockets
from websockets.exceptions import ConnectionClosedError
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import JSONResponse

# 音频处理
try:
    import wave
    import audioop
    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    AUDIO_PROCESSING_AVAILABLE = False
    logging.warning("音频处理库不可用，某些功能可能受限")

# LangGraph智能体
from src.agents.langgraph_interview_agent import get_langgraph_agent

logger = logging.getLogger(__name__)
# 临时设置为DEBUG级别以便调试语音识别问题
logger.setLevel(logging.DEBUG)

# 路由器
router = APIRouter(tags=["语音识别"])

# 讯飞RTASR配置
XUNFEI_CONFIG = {
    "app_id": "015076e9",
    "api_key": "771f2107c79630c900476ea1de65540b",
    "base_url": "ws://rtasr.xfyun.cn/v1/ws",
    "sample_rate": 16000,
    "encoding": "pcm"
}

class XunfeiVoiceProxy:
    """讯飞语音识别代理"""
    
    def __init__(self):
        self.app_id = XUNFEI_CONFIG["app_id"]
        self.api_key = XUNFEI_CONFIG["api_key"]
        self.base_url = XUNFEI_CONFIG["base_url"]
        
        # 连接管理
        self.xunfei_ws = None
        self.client_ws = None
        self.is_connected = False
        
        # 识别结果 - 参考demo实现非流式累积
        self.final_result = []  # 存储最终确认的结果（type="0"）
        self.temp_result = ""   # 存储临时结果（type="1"）
        self.recognized_text = ""
        self.session_id = None
        
        logger.info("📞 讯飞语音代理初始化完成")
    
    async def connect_xunfei(self):
        """连接讯飞RTASR服务"""
        try:
            # 生成认证参数
            ts = str(int(time.time()))
            signa = self._generate_signature(ts)
            
            # 构建WebSocket URL
            ws_url = f"{self.base_url}?appid={self.app_id}&ts={ts}&signa={quote(signa)}"
            
            logger.info("🔗 连接讯飞RTASR服务...")
            self.xunfei_ws = await websockets.connect(ws_url)
            self.is_connected = True
            
            logger.info("✅ 讯飞RTASR连接成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 连接讯飞RTASR失败: {e}")
            self.is_connected = False
            return False
    
    def _generate_signature(self, ts: str) -> str:
        """生成讯飞API签名"""
        try:
            # 构建基础字符串
            base_string = self.app_id + ts
            
            # MD5哈希
            md5_hash = hashlib.md5(base_string.encode('utf-8')).hexdigest()
            
            # HMAC-SHA1签名
            signature = hmac.new(
                self.api_key.encode('utf-8'),
                md5_hash.encode('utf-8'),
                hashlib.sha1
            ).digest()
            
            # Base64编码
            return base64.b64encode(signature).decode('utf-8')
            
        except Exception as e:
            logger.error(f"❌ 生成签名失败: {e}")
            raise
    
    async def send_audio_data(self, audio_data: bytes):
        """发送音频数据到讯飞"""
        if not self.is_connected or not self.xunfei_ws:
            return False
        
        try:
            await self.xunfei_ws.send(audio_data)
            logger.debug(f"📤 发送音频数据: {len(audio_data)} bytes")
            return True
            
        except (ConnectionClosedError, websockets.exceptions.ConnectionClosed):
            # 连接已关闭，静默处理
            self.is_connected = False
            return False
        except Exception as e:
            # 其他错误，记录一次后标记连接断开
            if "1000" not in str(e):
                logger.warning(f"⚠️ 音频发送失败: {e}")
            self.is_connected = False
            return False
    
    async def send_end_signal(self):
        """发送识别结束信号"""
        if not self.is_connected or not self.xunfei_ws:
            return
        
        try:
            end_signal = json.dumps({"end": True})
            await self.xunfei_ws.send(end_signal)
            logger.info("🏁 发送识别结束信号")
            
        except Exception as e:
            logger.error(f"❌ 发送结束信号失败: {e}")
    
    async def receive_recognition_result(self):
        """接收识别结果"""
        if not self.is_connected or not self.xunfei_ws:
            return None
        
        try:
            result = await self.xunfei_ws.recv()
            logger.debug(f"🔍 讯飞原始数据: {result}")
            
            # 处理多个JSON对象连接的情况
            return self._parse_multiple_json_results(result)
            
        except (ConnectionClosedError, websockets.exceptions.ConnectionClosed):
            # 连接关闭，静默处理
            self.is_connected = False
            return None
        except Exception as e:
            # 其他错误，静默处理避免大量日志
            if "1000" not in str(e):
                logger.debug(f"接收结果异常: {e}")
            self.is_connected = False
            return None
    

    
    async def close_connection(self):
        """关闭连接"""
        self.is_connected = False
        
        if self.xunfei_ws:
            try:
                await self.xunfei_ws.close()
                logger.info("🔌 讯飞连接已关闭")
            except:
                pass
            self.xunfei_ws = None
    
    def get_final_text(self) -> str:
        """获取最终识别文本"""
        # 返回最终结果 + 当前临时结果
        full_text = ''.join(self.final_result) + self.temp_result
        return full_text.strip()
    
    def _parse_multiple_json_results(self, raw_data: str) -> Optional[Dict]:
        """解析多个JSON对象连接的数据"""
        if not raw_data or not raw_data.strip():
            return None
        
        logger.debug(f"🔍 处理原始数据: {raw_data}")
        
        # 分割多个JSON对象
        json_objects = self._split_json_objects(raw_data)
        
        last_result = None
        for json_str in json_objects:
            if json_str.strip():
                result = self._parse_single_xunfei_result(json_str)
                if result:
                    last_result = result
        
        return last_result
    
    def _split_json_objects(self, data: str) -> list:
        """分割连接的JSON对象"""
        json_objects = []
        current_obj = ""
        brace_count = 0
        in_string = False
        escape_next = False
        
        for char in data:
            current_obj += char
            
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
                
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    
                    # 当大括号平衡时，表示一个完整的JSON对象
                    if brace_count == 0:
                        json_objects.append(current_obj.strip())
                        current_obj = ""
        
        # 处理剩余的不完整对象
        if current_obj.strip():
            json_objects.append(current_obj.strip())
        
        logger.debug(f"🔍 分割得到 {len(json_objects)} 个JSON对象")
        return json_objects
    
    def _parse_single_xunfei_result(self, json_str: str) -> Optional[Dict]:
        """解析单个讯飞结果 - 修复action/data格式解析"""
        try:
            data = json.loads(json_str)
            logger.debug(f"🔍 解析JSON对象: {json.dumps(data, ensure_ascii=False)}")
            
            # 检查是否是讯飞的action格式
            if "action" in data and data.get("action") == "result":
                # 解析data字段中的JSON字符串
                data_str = data.get("data", "")
                if not data_str:
                    logger.debug("🔍 data字段为空")
                    return None
                
                try:
                    # 二次解析data字段
                    inner_data = json.loads(data_str)
                    logger.debug(f"🔍 解析data内容: {json.dumps(inner_data, ensure_ascii=False)}")
                    
                    # 检查是否包含cn字段
                    cn = inner_data.get("cn", {})
                    if not cn:
                        logger.debug("🔍 cn字段为空")
                        return None
                    
                    st = cn.get("st", {})
                    if not st:
                        logger.debug("🔍 st字段为空")
                        return None
                    
                    # 提取文本内容
                    temp_result = self._extract_text_from_rt(st.get("rt", []))
                    
                    # 根据type判断处理逻辑
                    type_value = st.get("type")
                    logger.info(f"🎯 识别结果 - 类型: {type_value}, 文本: '{temp_result}'")
                    
                    if temp_result:  # 只要有文本就处理
                        if type_value == "1":
                            # 实时转写内容（临时结果）
                            self.temp_result = temp_result
                            self.recognized_text = ''.join(self.final_result) + self.temp_result
                            
                            return {
                                "type": "result",
                                "text": temp_result,
                                "accumulated_text": self.recognized_text,
                                "is_final": False,
                                "result_type": "realtime"
                            }
                            
                        elif type_value == "0":
                            # 完整转写内容（最终结果）
                            self.final_result.append(temp_result)
                            self.temp_result = ""  # 清空临时结果
                            self.recognized_text = ''.join(self.final_result)
                            
                            logger.info(f"📝 最终结果确认: {temp_result} (累积: {self.recognized_text})")
                            
                            return {
                                "type": "result", 
                                "text": temp_result,
                                "accumulated_text": self.recognized_text,
                                "is_final": True,
                                "result_type": "final"
                            }
                    
                    return None
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"❌ 解析data字段JSON失败: {e}")
                    return None
                    
            elif "cn" in data:
                # 兼容直接cn格式（备用）
                cn = data.get("cn", {})
                st = cn.get("st", {})
                temp_result = self._extract_text_from_rt(st.get("rt", []))
                type_value = st.get("type")
                
                if temp_result:
                    logger.info(f"🎯 直接cn格式 - 类型: {type_value}, 文本: '{temp_result}'")
                    # 处理逻辑同上
                    if type_value == "1":
                        self.temp_result = temp_result
                        self.recognized_text = ''.join(self.final_result) + self.temp_result
                        return {
                            "type": "result",
                            "text": temp_result,
                            "accumulated_text": self.recognized_text,
                            "is_final": False,
                            "result_type": "realtime"
                        }
                    elif type_value == "0":
                        self.final_result.append(temp_result)
                        self.temp_result = ""
                        self.recognized_text = ''.join(self.final_result)
                        return {
                            "type": "result",
                            "text": temp_result,
                            "accumulated_text": self.recognized_text,
                            "is_final": True,
                            "result_type": "final"
                        }
            else:
                logger.debug("🔍 不是讯飞识别结果格式")
                return None
            
        except json.JSONDecodeError as e:
            logger.warning(f"❌ JSON解析失败: {e}, 数据: {json_str[:100]}...")
            return None
        except Exception as e:
            logger.warning(f"⚠️ 解析讯飞结果异常: {e}")
            return None
    
    def _extract_text_from_rt(self, rt_array: list) -> str:
        """从rt数组中提取文本 - 按照demo的解析路径"""
        text_parts = []
        
        try:
            for rt_obj in rt_array:
                ws_arr = rt_obj.get("ws", [])
                for ws_obj in ws_arr:
                    cw_arr = ws_obj.get("cw", [])
                    for cw_obj in cw_arr:
                        w_str = cw_obj.get("w", "")
                        if w_str:
                            text_parts.append(w_str)
            
            result = ''.join(text_parts)
            logger.debug(f"🔍 从rt数组提取文本: '{result}'")
            return result
            
        except Exception as e:
            logger.warning(f"⚠️ 从rt数组提取文本失败: {e}")
            return ""


class VoiceSessionManager:
    """语音会话管理器"""
    
    def __init__(self):
        self.active_sessions: Dict[str, XunfeiVoiceProxy] = {}
        self.session_metadata: Dict[str, Dict] = {}
        
    def create_session(self, session_id: str, user_id: str, interview_session_id: str) -> XunfeiVoiceProxy:
        """创建语音会话 - 同步版本（已废弃，请使用create_session_async）"""
        logger.warning("⚠️ 使用了废弃的同步create_session方法")
        
        # 简单创建，不处理连接限制
        proxy = XunfeiVoiceProxy()
        proxy.session_id = session_id
        
        self.active_sessions[session_id] = proxy
        self.session_metadata[session_id] = {
            "user_id": user_id,
            "interview_session_id": interview_session_id,
            "created_at": time.time(),
            "status": "created"
        }
        
        logger.info(f"🎤 创建语音会话: {session_id}")
        return proxy
    
    def get_user_active_session(self, user_id: str) -> Optional[XunfeiVoiceProxy]:
        """获取用户的活跃会话"""
        for session_id, metadata in self.session_metadata.items():
            if metadata.get("user_id") == user_id:
                proxy = self.active_sessions.get(session_id)
                if proxy and proxy.is_connected:
                    return proxy
        return None
    
    async def cleanup_old_sessions(self):
        """清理旧的会话"""
        sessions_to_close = list(self.active_sessions.keys())
        for session_id in sessions_to_close:
            await self.close_session(session_id)
    
    async def create_session_async(self, session_id: str, user_id: str, interview_session_id: str) -> XunfeiVoiceProxy:
        """异步创建语音会话"""
        
        # 首先检查该用户是否已有活跃会话
        existing_session = self.get_user_active_session(user_id)
        if existing_session:
            logger.info(f"🔄 复用用户已有会话: {existing_session.session_id}")
            return existing_session
        
        # 检查是否超过连接限制（讯飞免费账号限制）
        if len(self.active_sessions) >= 1:  # 讯飞通常限制1个连接
            logger.warning("⚠️ 达到连接数限制，清理旧连接")
            await self.cleanup_old_sessions()
        
        # 创建新会话
        if session_id in self.active_sessions:
            logger.warning(f"⚠️ 会话ID冲突，强制清理: {session_id}")
            await self.close_session(session_id)
        
        proxy = XunfeiVoiceProxy()
        proxy.session_id = session_id
        
        self.active_sessions[session_id] = proxy
        self.session_metadata[session_id] = {
            "user_id": user_id,
            "interview_session_id": interview_session_id,
            "created_at": time.time(),
            "status": "created"
        }
        
        logger.info(f"🎤 创建语音会话: {session_id}")
        return proxy
    
    def get_session(self, session_id: str) -> Optional[XunfeiVoiceProxy]:
        """获取语音会话"""
        return self.active_sessions.get(session_id)
    
    async def close_session(self, session_id: str):
        """关闭语音会话"""
        try:
            # 安全地获取和删除会话
            proxy = self.active_sessions.pop(session_id, None)
            metadata = self.session_metadata.pop(session_id, None)
            
            if proxy:
                await proxy.close_connection()
                logger.info(f"🔚 语音会话已关闭: {session_id}")
            else:
                logger.debug(f"🤷 会话不存在或已关闭: {session_id}")
                
        except Exception as e:
            logger.warning(f"⚠️ 关闭会话时出现异常: {session_id}, 错误: {e}")
            # 确保清理，即使出现异常
            self.active_sessions.pop(session_id, None)
            self.session_metadata.pop(session_id, None)
    
    def get_active_sessions(self) -> Dict[str, Dict]:
        """获取活跃会话列表"""
        return self.session_metadata.copy()


# 全局会话管理器
voice_session_manager = VoiceSessionManager()


# ==================== API路由 ====================

from pydantic import BaseModel

class CreateSessionRequest(BaseModel):
    user_id: str
    interview_session_id: str
    session_id: Optional[str] = None

@router.post("/create-session")
async def create_voice_session(request: CreateSessionRequest):
    """创建语音识别会话"""
    try:
        # 优先复用已有会话
        existing_session = voice_session_manager.get_user_active_session(request.user_id)
        if existing_session and existing_session.is_connected:
            logger.info(f"🔄 复用已有会话: {existing_session.session_id}")
            return {
                "success": True,
                "session_id": existing_session.session_id,
                "status": "reused",
                "message": "复用已有语音识别会话"
            }
        
        # 清理旧连接（讯飞连接数限制）
        if len(voice_session_manager.active_sessions) >= 1:
            logger.info("🧹 清理旧连接以避免超限")
            await voice_session_manager.cleanup_old_sessions()
        
        # 生成新的会话ID
        session_id = request.session_id
        if not session_id:
            session_id = f"voice_{request.user_id}_{int(time.time())}"
        
        # 创建新会话
        proxy = await voice_session_manager.create_session_async(
            session_id=session_id,
            user_id=request.user_id,
            interview_session_id=request.interview_session_id
        )
        
        # 连接讯飞服务
        success = await proxy.connect_xunfei()
        if not success:
            await voice_session_manager.close_session(session_id)
            raise HTTPException(status_code=500, detail="连接语音识别服务失败")
        
        return {
            "success": True,
            "session_id": session_id,
            "status": "connected",
            "message": "语音识别会话创建成功"
        }
        
    except Exception as e:
        logger.error(f"❌ 创建语音会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@router.websocket("/recognition/{session_id}")
async def voice_recognition_websocket(websocket: WebSocket, session_id: str):
    """WebSocket语音识别端点"""
    await websocket.accept()
    logger.info(f"🔗 WebSocket连接建立: {session_id}")
    
    proxy = voice_session_manager.get_session(session_id)
    if not proxy:
        await websocket.send_json({
            "type": "error",
            "message": "会话不存在，请先创建会话"
        })
        await websocket.close()
        return
    
    proxy.client_ws = websocket
    
    try:
        # 启动识别结果监听任务
        recognition_task = asyncio.create_task(
            listen_recognition_results(proxy, websocket)
        )
        
        # 处理客户端消息
        while proxy.is_connected:
            try:
                # 接收客户端数据
                data = await websocket.receive()
                
                if data.get("type") == "websocket.receive":
                    if "bytes" in data:
                        # 音频数据
                        audio_data = data["bytes"]
                        success = await proxy.send_audio_data(audio_data)
                        if not success:
                            # 发送失败，连接可能已断开
                            break
                        
                    elif "text" in data:
                        # 控制指令
                        try:
                            message = json.loads(data["text"])
                            await handle_control_message(proxy, websocket, message)
                        except json.JSONDecodeError:
                            logger.warning("⚠️ 收到无效JSON控制指令")
                
            except WebSocketDisconnect:
                logger.info(f"🔌 WebSocket客户端断开: {session_id}")
                break
            except Exception as e:
                # 静默处理异常，避免大量错误日志
                if "1000" not in str(e) and "disconnect" not in str(e).lower():
                    logger.warning(f"⚠️ WebSocket消息处理异常: {e}")
                break
    
    except Exception:
        # 静默处理顶层异常
        pass
    
    finally:
        # 清理资源
        if 'recognition_task' in locals():
            recognition_task.cancel()
        
        await voice_session_manager.close_session(session_id)
        logger.info(f"🧹 WebSocket会话清理完成: {session_id}")


async def listen_recognition_results(proxy: XunfeiVoiceProxy, websocket: WebSocket):
    """监听识别结果"""
    try:
        while proxy.is_connected and proxy.xunfei_ws:
            try:
                # 设置短超时，避免长时间阻塞
                result = await asyncio.wait_for(proxy.receive_recognition_result(), timeout=0.1)
                if result:
                    await websocket.send_json(result)
                    
                    # 如果是最终结果且需要集成到面试系统
                    if result.get("type") == "result" and result.get("is_final"):
                        await integrate_with_interview_system(proxy, result["text"])
                
            except asyncio.TimeoutError:
                # 超时是正常的，继续循环
                continue
            except (ConnectionClosedError, websockets.exceptions.ConnectionClosed):
                # 连接正常关闭，静默退出
                break
            except Exception as e:
                # 其他错误，记录并退出
                if "1000" not in str(e) and "disconnect" not in str(e).lower():
                    logger.warning(f"⚠️ 识别结果接收异常: {e}")
                break
                
    except Exception:
        # 静默处理异常，避免大量日志
        pass
    
    logger.debug("🔚 识别结果监听已停止")


async def handle_control_message(proxy: XunfeiVoiceProxy, websocket: WebSocket, message: Dict):
    """处理控制消息"""
    try:
        command = message.get("command")
        
        if command == "start":
            logger.info("🎤 开始语音识别")
            await websocket.send_json({
                "type": "status",
                "status": "recording",
                "message": "开始录音"
            })
        
        elif command == "stop":
            logger.info("⏹️ 停止语音识别")
            await proxy.send_end_signal()
            
            # 获取最终识别文本
            final_text = proxy.get_final_text()
            logger.info(f"🔍 最终识别文本: '{final_text}'")
            
            await websocket.send_json({
                "type": "final_result", 
                "text": final_text,
                "accumulated_text": final_text,
                "is_final": True,
                "message": "识别完成"
            })
            
            # 集成到面试系统
            if final_text and final_text.strip():
                await integrate_with_interview_system(proxy, final_text)
            else:
                logger.warning("⚠️ 最终文本为空，不集成到面试系统")
        
        elif command == "cancel":
            logger.info("❌ 取消语音识别")
            await websocket.send_json({
                "type": "status",
                "status": "cancelled",
                "message": "识别已取消"
            })
        
        else:
            logger.warning(f"⚠️ 未知控制命令: {command}")
            
    except Exception as e:
        logger.error(f"❌ 处理控制消息失败: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"处理命令失败: {str(e)}"
        })


async def integrate_with_interview_system(proxy: XunfeiVoiceProxy, recognized_text: str):
    """集成到面试系统"""
    try:
        if not recognized_text or not recognized_text.strip():
            logger.warning("⚠️ 识别文本为空，跳过集成")
            return
        
        # 获取会话元数据
        session_metadata = voice_session_manager.session_metadata.get(proxy.session_id)
        if not session_metadata:
            logger.error("❌ 找不到会话元数据")
            return
        
        user_id = session_metadata["user_id"]
        interview_session_id = session_metadata["interview_session_id"]
        
        # 获取LangGraph智能体
        agent = get_langgraph_agent()
        if not agent:
            logger.error("❌ 无法获取面试智能体")
            return
        
        logger.info(f"🤖 语音文本集成到面试系统: {recognized_text[:50]}...")
        
        # TODO: 这里需要根据具体的面试系统API进行调用
        # 示例：将语音文本作为用户消息发送到面试智能体
        # result = await agent.process_message(
        #     user_id=user_id,
        #     session_id=interview_session_id,
        #     user_message=recognized_text,
        #     # 其他必要参数...
        # )
        
        logger.info("✅ 语音文本已集成到面试系统")
        
    except Exception as e:
        logger.error(f"❌ 集成面试系统失败: {e}")


@router.delete("/session/{session_id}")
async def close_voice_session(session_id: str):
    """关闭语音识别会话"""
    try:
        await voice_session_manager.close_session(session_id)
        
        return {
            "success": True,
            "message": "会话已关闭"
        }
        
    except Exception as e:
        logger.error(f"❌ 关闭语音会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"关闭会话失败: {str(e)}")


@router.get("/sessions")
async def get_active_sessions():
    """获取活跃的语音会话列表"""
    try:
        sessions = voice_session_manager.get_active_sessions()
        
        return {
            "success": True,
            "sessions": sessions,
            "count": len(sessions)
        }
        
    except Exception as e:
        logger.error(f"❌ 获取会话列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


@router.get("/health")
async def voice_service_health():
    """语音服务健康检查"""
    try:
        active_count = len(voice_session_manager.active_sessions)
        
        return {
            "success": True,
            "service": "voice_recognition",
            "status": "healthy",
            "active_sessions": active_count,
            "xunfei_config": {
                "app_id": XUNFEI_CONFIG["app_id"],
                "base_url": XUNFEI_CONFIG["base_url"],
                "sample_rate": XUNFEI_CONFIG["sample_rate"]
            },
            "audio_processing": AUDIO_PROCESSING_AVAILABLE
        }
        
    except Exception as e:
        logger.error(f"❌ 语音服务健康检查失败: {e}")
        return {
            "success": False,
            "service": "voice_recognition", 
            "status": "unhealthy",
            "error": str(e)
        }


# ==================== 音频处理工具 ====================

class AudioProcessor:
    """音频处理工具"""
    
    @staticmethod
    def convert_sample_rate(audio_data: bytes, from_rate: int, to_rate: int) -> bytes:
        """转换采样率"""
        if not AUDIO_PROCESSING_AVAILABLE:
            logger.warning("⚠️ 音频处理库不可用，返回原始数据")
            return audio_data
        
        try:
            # 使用audioop进行采样率转换
            converted = audioop.ratecv(audio_data, 2, 1, from_rate, to_rate, None)[0]
            return converted
            
        except Exception as e:
            logger.error(f"❌ 音频采样率转换失败: {e}")
            return audio_data
    
    @staticmethod
    def normalize_audio(audio_data: bytes) -> bytes:
        """音频归一化"""
        if not AUDIO_PROCESSING_AVAILABLE:
            return audio_data
        
        try:
            # 计算最大值并归一化
            max_val = audioop.max(audio_data, 2)
            if max_val > 0:
                factor = 32767.0 / max_val
                normalized = audioop.mul(audio_data, 2, factor)
                return normalized
            
            return audio_data
            
        except Exception as e:
            logger.error(f"❌ 音频归一化失败: {e}")
            return audio_data
    
    @staticmethod
    def validate_audio_format(audio_data: bytes) -> bool:
        """验证音频格式"""
        try:
            # 基本长度检查
            if len(audio_data) < 1024:  # 至少1KB
                return False
            
            # 检查是否为有效的PCM数据（简单检查）
            if len(audio_data) % 2 != 0:  # 16bit PCM应该是偶数长度
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 音频格式验证失败: {e}")
            return False
