# -*- encoding:utf-8 -*-
"""
讯飞实时语音识别代理服务
基于WebSocket实现前后端语音识别集成

音频调试功能：
- 自动保存发送给讯飞的音频流到 data/debug_audio/ 目录
- 支持PCM原始格式和WAV格式
- 用于调试语音识别漏字和末尾缺字问题

文件命名格式：
- voice_debug_YYYYMMDD_HHMMSS_sessionid.pcm
- voice_debug_YYYYMMDD_HHMMSS_sessionid.wav
"""
import asyncio
import json
import logging
import hashlib
import hmac
import base64
import time
import os
from datetime import datetime
from typing import Dict, Optional, Any, List
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

# 设置日志记录器
logger = logging.getLogger(__name__)
# 临时设置为DEBUG级别以便调试语音识别问题
logger.setLevel(logging.DEBUG)

# 音频分析工具
try:
    import librosa
    import numpy as np
    from src.tools.multimodal_analyzer import AudioAnalyzer, create_multimodal_analyzer
    LIBROSA_AVAILABLE = True
    logger.info("✅ Librosa音频分析库可用")
except ImportError as e:
    logger.warning(f"⚠️ Librosa音频分析库不可用: {e}")
    LIBROSA_AVAILABLE = False

# 会话管理和LangGraph聊天
try:
    from api.routers.langgraph_chat import active_sessions
    from src.database.session_manager import get_session_manager
    LANGGRAPH_CHAT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ LangGraph聊天模块导入失败: {e}")
    LANGGRAPH_CHAT_AVAILABLE = False

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
        
        # 音频保存功能
        self.audio_buffer = bytearray()  # 拼接所有音频数据
        self.save_audio = True  # 是否保存音频（可配置）
        self.audio_saved_path = None  # 保存的音频文件路径
        
        # 实时音频分析功能
        self.realtime_analysis_enabled = True  # 是否启用实时分析
        self.analysis_buffer = bytearray()  # 分析用的音频缓冲区
        self.analysis_buffer_size = 16000 * 2  # 2秒的音频数据 (16kHz * 2字节/样本 * 2秒)
        self.last_analysis_time = 0
        self.analysis_interval = 1.0  # 分析间隔（秒）
        self.voice_tone_history = []  # 语调历史记录
        self.max_history_length = 60  # 最多保存60个历史点（1分钟）
        
        # 延时监控
        self.last_audio_send_time = None  # 最后一次发送音频的时间
        self.first_audio_send_time = None  # 第一次发送音频的时间  
        self.audio_send_count = 0  # 发送的音频包计数
        self.result_receive_count = 0  # 接收到的结果计数
        
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
            # 记录发送时间（用于延时监控）
            current_time = time.time()
            self.last_audio_send_time = current_time
            if self.first_audio_send_time is None:
                self.first_audio_send_time = current_time
                logger.info("⏱️ 开始音频发送计时")
            
            self.audio_send_count += 1
            
            # 音频质量检测
            audio_energy = self._calculate_audio_energy(audio_data)
            is_silence = audio_energy < 1000  # 静音阈值
            
            # 发送到讯飞
            await self.xunfei_ws.send(audio_data)
            
            # 详细的音频发送日志
            if is_silence:
                logger.debug(f"📤 发送音频数据: {len(audio_data)} bytes [包#{self.audio_send_count}] 🔇 静音 (能量: {audio_energy:.1f})")
            else:
                logger.debug(f"📤 发送音频数据: {len(audio_data)} bytes [包#{self.audio_send_count}] 🔊 有声 (能量: {audio_energy:.1f})")
            
            # 每5包统计一次（小包模式需要更频繁统计）
            if self.audio_send_count % 5 == 0:
                total_duration = (current_time - self.first_audio_send_time)
                logger.info(f"📊 音频发送统计 - 包数: {self.audio_send_count}, 时长: {total_duration:.1f}s, 平均: {len(audio_data)/1024:.1f}KB/包")
                logger.info(f"🎯 期望实时识别 - 小包模式应该每0.5秒产生识别结果")
            
            # 保存音频数据到缓冲区（用于调试）
            if self.save_audio:
                self.audio_buffer.extend(audio_data)
                logger.debug(f"💾 累积音频数据: {len(self.audio_buffer)} bytes")
            
            # 添加到实时分析缓冲区
            if self.realtime_analysis_enabled:
                self.analysis_buffer.extend(audio_data)
                
                # 保持分析缓冲区大小限制
                if len(self.analysis_buffer) > self.analysis_buffer_size:
                    # 保留最新的数据
                    excess = len(self.analysis_buffer) - self.analysis_buffer_size
                    self.analysis_buffer = self.analysis_buffer[excess:]
                
                # 执行实时分析并发送结果
                analysis_result = self._perform_realtime_analysis()
                if analysis_result and self.client_ws:
                    try:
                        # 异步发送分析结果到前端
                        asyncio.create_task(self._send_voice_analysis_result(analysis_result))
                    except Exception as e:
                        logger.warning(f"⚠️ 发送语调分析结果失败: {e}")
            
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
            logger.debug("⚠️ 连接已断开，无法接收结果")
            return None
        
        try:
            # 添加接收状态日志
            logger.debug("🎧 等待讯飞返回数据...")
            result = await self.xunfei_ws.recv()
            logger.debug(f"🔍 讯飞原始数据: {result}")
            
            # 处理多个JSON对象连接的情况
            parsed_result = self._parse_multiple_json_results(result)
            if parsed_result:
                logger.debug(f"✅ 解析成功: {parsed_result.get('result_type', 'unknown')} - '{parsed_result.get('text', '')[:20]}...'")
            else:
                logger.debug("⚠️ 解析结果为空")
            
            return parsed_result
            
        except (ConnectionClosedError, websockets.exceptions.ConnectionClosed):
            # 连接关闭，记录日志
            logger.info("🔌 讯飞WebSocket连接已关闭")
            self.is_connected = False
            return None
        except Exception as e:
            # 其他错误，详细记录便于调试
            logger.warning(f"⚠️ 接收讯飞结果异常: {type(e).__name__}: {e}")
            if "1000" not in str(e):
                logger.debug(f"详细错误信息: {e}")
            self.is_connected = False
            return None
    

    
    async def close_connection(self):
        """关闭连接"""
        self.is_connected = False
        
        # 打印最终延时统计
        if self.first_audio_send_time and self.last_audio_send_time:
            total_session_time = (self.last_audio_send_time - self.first_audio_send_time) * 1000
            logger.info(f"📊 会话延时统计总结 - 总时长: {total_session_time:.1f}ms | 音频包总数: {self.audio_send_count} | 识别结果总数: {self.result_receive_count}")
        
        # 保存音频文件（用于调试）
        if self.save_audio and len(self.audio_buffer) > 0:
            await self._save_audio_to_file()
        
        # 重置延时监控状态
        self.last_audio_send_time = None
        self.first_audio_send_time = None
        self.audio_send_count = 0
        self.result_receive_count = 0
        
        if self.xunfei_ws:
            try:
                await self.xunfei_ws.close()
                logger.info("🔌 讯飞连接已关闭")
            except:
                pass
            self.xunfei_ws = None
    
    async def _save_audio_to_file(self):
        """保存音频数据到文件"""
        try:
            # 创建保存目录
            save_dir = "data/debug_audio"
            os.makedirs(save_dir, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_suffix = self.session_id[:8] if self.session_id else "unknown"
            
            # 保存为PCM原始文件
            pcm_filename = f"voice_debug_{timestamp}_{session_suffix}.pcm"
            pcm_path = os.path.join(save_dir, pcm_filename)
            
            with open(pcm_path, 'wb') as f:
                f.write(self.audio_buffer)
            
            self.audio_saved_path = pcm_path
            logger.info(f"💾 原始音频已保存: {pcm_path} ({len(self.audio_buffer)} bytes)")
            
            # 如果有wave库，同时保存为WAV文件（便于播放）
            if AUDIO_PROCESSING_AVAILABLE:
                wav_filename = f"voice_debug_{timestamp}_{session_suffix}.wav"
                wav_path = os.path.join(save_dir, wav_filename)
                
                with wave.open(wav_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # 单声道
                    wav_file.setsampwidth(2)  # 16位
                    wav_file.setframerate(16000)  # 16kHz
                    wav_file.writeframes(self.audio_buffer)
                
                logger.info(f"🎵 WAV音频已保存: {wav_path}")
                
        except Exception as e:
            logger.error(f"❌ 保存音频文件失败: {e}")
    
    def enable_audio_saving(self, enabled: bool = True):
        """启用/禁用音频保存功能"""
        self.save_audio = enabled
        if enabled:
            logger.info("💾 音频保存功能已启用")
        else:
            logger.info("🚫 音频保存功能已禁用")
    
    def get_audio_info(self) -> Dict[str, Any]:
        """获取音频保存信息"""
        return {
            "save_enabled": self.save_audio,
            "buffer_size": len(self.audio_buffer),
            "saved_path": self.audio_saved_path
        }
    
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
            # 记录结果接收时间（用于延时计算）
            receive_time = time.time()
            self.result_receive_count += 1
            
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
                        # 计算延时
                        self._calculate_and_log_latency(receive_time, type_value, temp_result)
                        
                        if type_value == "1":
                            # 实时转写内容（临时结果）
                            self.temp_result = temp_result
                            self.recognized_text = ''.join(self.final_result) + self.temp_result
                            
                            logger.info(f"🚀 收到实时结果: '{temp_result}' (累积: '{self.recognized_text}')")
                            
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
                    # 计算延时（兼容格式）
                    self._calculate_and_log_latency(receive_time, type_value, temp_result)
                    
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
    
    def _calculate_and_log_latency(self, receive_time: float, type_value: str, text: str):
        """计算并记录延时"""
        try:
            if self.last_audio_send_time is None:
                logger.debug("⚠️ 无音频发送时间记录，无法计算延时")
                return
            
            # 计算从最后一次发送音频到收到结果的延时
            latency_ms = (receive_time - self.last_audio_send_time) * 1000
            
            # 计算从开始录音到现在的总时长
            total_duration_ms = 0
            if self.first_audio_send_time:
                total_duration_ms = (receive_time - self.first_audio_send_time) * 1000
            
            # 根据结果类型选择不同的日志级别
            if type_value == "0":  # 最终结果
                logger.info(f"⏱️ 最终结果延时: {latency_ms:.1f}ms | 总时长: {total_duration_ms:.1f}ms | 文本: '{text[:20]}...' | 包计数: {self.audio_send_count} | 结果计数: {self.result_receive_count}")
            else:  # 实时结果
                logger.debug(f"⏱️ 实时结果延时: {latency_ms:.1f}ms | 总时长: {total_duration_ms:.1f}ms | 文本: '{text[:20]}...' | 包计数: {self.audio_send_count} | 结果计数: {self.result_receive_count}")
            
            # 统计信息（每10个结果打印一次统计）
            if self.result_receive_count % 10 == 0:
                avg_latency = latency_ms  # 简化，实际可以保存历史数据计算平均值
                logger.info(f"📊 延时统计 - 当前延时: {latency_ms:.1f}ms | 音频包: {self.audio_send_count} | 识别结果: {self.result_receive_count}")
                
        except Exception as e:
            logger.warning(f"⚠️ 计算延时失败: {e}")
    
    def _perform_realtime_analysis(self) -> Optional[Dict[str, Any]]:
        """执行实时音频分析"""
        if not self.realtime_analysis_enabled or not LIBROSA_AVAILABLE:
            return None
            
        try:
            if len(self.analysis_buffer) < 16000:  # 至少需要0.5秒的数据
                return None
            
            current_time = time.time()
            if current_time - self.last_analysis_time < self.analysis_interval:
                return None
            
            self.last_analysis_time = current_time
            
            # 将PCM字节数据转换为numpy数组
            audio_samples = np.frombuffer(self.analysis_buffer, dtype=np.int16).astype(np.float32)
            audio_samples = audio_samples / 32768.0  # 归一化到[-1, 1]
            
            # 分析音高 (基频)
            pitch_result = self._analyze_realtime_pitch(audio_samples, 16000)
            
            # 分析音量
            volume_result = self._analyze_realtime_volume(audio_samples)
            
            # 分析语速
            speech_rate = self._analyze_realtime_speech_rate(audio_samples, 16000)
            
            # 构建分析结果
            analysis_result = {
                'timestamp': current_time,
                'pitch': pitch_result,
                'volume': volume_result,
                'speech_rate': speech_rate,
                'buffer_length': len(audio_samples)
            }
            
            # 添加到历史记录
            self.voice_tone_history.append(analysis_result)
            
            # 保持历史记录长度限制
            if len(self.voice_tone_history) > self.max_history_length:
                self.voice_tone_history.pop(0)
            
            logger.debug(f"🎼 实时音频分析: 音高={pitch_result['mean']:.1f}Hz, 音量={volume_result['mean']:.1f}dB, 语速={speech_rate:.1f}")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ 实时音频分析失败: {e}")
            return None
    
    def _analyze_realtime_pitch(self, audio_samples: np.ndarray, sr: int) -> Dict[str, float]:
        """实时分析音高"""
        try:
            # 使用简化的音高检测（yin算法的快速近似）
            f0 = librosa.pyin(audio_samples, fmin=80, fmax=400, sr=sr)[0]
            valid_f0 = f0[~np.isnan(f0)]
            
            if len(valid_f0) > 0:
                mean_pitch = float(np.mean(valid_f0))
                pitch_variance = float(np.var(valid_f0))
                pitch_range = float(np.max(valid_f0) - np.min(valid_f0))
            else:
                mean_pitch = 0.0
                pitch_variance = 0.0
                pitch_range = 0.0
                
            return {
                'mean': mean_pitch,
                'variance': pitch_variance,
                'range': pitch_range
            }
        except:
            return {'mean': 0.0, 'variance': 0.0, 'range': 0.0}
    
    def _analyze_realtime_volume(self, audio_samples: np.ndarray) -> Dict[str, float]:
        """实时分析音量"""
        try:
            # 计算RMS
            rms = np.sqrt(np.mean(audio_samples ** 2))
            db = 20 * np.log10(max(rms, 1e-10))  # 避免log(0)
            
            return {
                'mean': float(db),
                'rms': float(rms)
            }
        except:
            return {'mean': -60.0, 'rms': 0.0}
    
    def _analyze_realtime_speech_rate(self, audio_samples: np.ndarray, sr: int) -> float:
        """实时分析语速"""
        try:
            # 简化的语速检测：检测能量峰值
            hop_length = 512
            frame_length = 2048
            
            # 计算短时能量
            energy = []
            for i in range(0, len(audio_samples) - frame_length, hop_length):
                frame = audio_samples[i:i + frame_length]
                energy.append(np.sum(frame ** 2))
            
            if len(energy) > 10:
                energy = np.array(energy)
                # 检测能量峰值（简化的语音活动检测）
                threshold = np.mean(energy) * 1.5
                peaks = np.sum(energy > threshold)
                
                # 估算语速 (每分钟的音节数)
                duration_minutes = len(audio_samples) / sr / 60
                speech_rate = peaks / max(duration_minutes, 0.01)
                return float(min(speech_rate, 300))  # 限制最大值
            
            return 0.0
        except:
            return 0.0
    
    async def _send_voice_analysis_result(self, analysis_result: Dict[str, Any]):
        """发送语调分析结果到前端"""
        try:
            if not self.client_ws:
                return
                
            # 构建发送给前端的数据
            message = {
                "type": "voice_analysis",
                "data": {
                    "timestamp": analysis_result["timestamp"],
                    "pitch_mean": analysis_result["pitch"]["mean"],
                    "pitch_variance": analysis_result["pitch"]["variance"],
                    "pitch_range": analysis_result["pitch"]["range"],
                    "volume_mean": analysis_result["volume"]["mean"],
                    "volume_rms": analysis_result["volume"]["rms"],
                    "speech_rate": analysis_result["speech_rate"],
                    "session_id": self.session_id
                },
                "history": [
                    {
                        "timestamp": item["timestamp"],
                        "pitch_mean": item["pitch"]["mean"],
                        "volume_mean": item["volume"]["mean"],
                        "speech_rate": item["speech_rate"]
                    }
                    for item in self.voice_tone_history[-10:]  # 只发送最近10个点
                ]
            }
            
            await self.client_ws.send_json(message)
            logger.debug(f"📊 发送语调分析结果: 音高={analysis_result['pitch']['mean']:.1f}Hz")
            
        except Exception as e:
            logger.error(f"❌ 发送语调分析结果失败: {e}")
    
    def get_voice_analysis_history(self) -> List[Dict[str, Any]]:
        """获取语调分析历史记录"""
        return self.voice_tone_history.copy()
    
    def clear_voice_analysis_history(self):
        """清空语调分析历史记录"""
        self.voice_tone_history.clear()
        self.analysis_buffer.clear()
        logger.info("🧹 语调分析历史记录已清空")

    def _calculate_audio_energy(self, audio_data: bytes) -> float:
        """计算音频能量（用于检测静音）"""
        try:
            if len(audio_data) < 2:
                return 0.0
            
            # 将字节数据转换为16位整数
            import struct
            samples = []
            for i in range(0, len(audio_data) - 1, 2):
                sample = struct.unpack('<h', audio_data[i:i+2])[0]  # 小端序16位
                samples.append(sample)
            
            if not samples:
                return 0.0
            
            # 计算RMS能量
            sum_of_squares = sum(sample * sample for sample in samples)
            rms = (sum_of_squares / len(samples)) ** 0.5
            
            return rms
            
        except Exception as e:
            logger.warning(f"⚠️ 计算音频能量失败: {e}")
            return 0.0


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
    result_count = 0
    no_result_count = 0
    max_no_result = 200  # 20秒无结果后记录警告（0.1s * 200）
    
    try:
        logger.info(f"🎧 开始监听识别结果 - 会话: {proxy.session_id}")
        
        while proxy.is_connected and proxy.xunfei_ws:
            try:
                # 增加超时时间，避免错过讯飞的实时结果
                result = await asyncio.wait_for(proxy.receive_recognition_result(), timeout=2.0)
                if result:
                    result_count += 1
                    no_result_count = 0  # 重置无结果计数
                    
                    logger.info(f"📥 收到识别结果 #{result_count}: {result.get('result_type', 'unknown')} - '{result.get('text', '')[:30]}...'")
                    await websocket.send_json(result)
                    
                    # 如果是最终结果，仅发送识别结果，不自动触发LangGraph
                    if result.get("type") == "result" and result.get("is_final"):
                        text = result.get("text", "").strip()
                        if text:
                            logger.info(f"✅ 最终识别文本: '{text}'")
                            
                            # 发送最终识别结果给前端
                            await websocket.send_json({
                                "type": "final_result",
                                "text": text,
                                "session_id": proxy.session_id
                            })
                            # 注意：不再自动调用integrate_with_interview_system
                            # LangGraph集成将在前端主动停止录音时触发
                    else:
                        # 实时结果，继续等待更多内容
                        logger.debug(f"🔄 实时结果，继续监听...")
                else:
                    no_result_count += 1
                    
                    # 更频繁的状态检查和日志输出
                    if no_result_count % 10 == 0:  # 每20秒检查一次（2s * 10）
                        logger.info(f"📊 监听状态 - 已收到 {result_count} 个结果，连续无结果: {no_result_count} 次")
                        logger.info(f"🔍 期望状态 - 小包模式应该每0.5秒收到实时结果(type=1)")
                        logger.debug(f"🔗 连接状态 - 代理: {proxy.is_connected}, 讯飞WS: {proxy.xunfei_ws is not None}")
                        
                        if not proxy.is_connected:
                            logger.warning("⚠️ 代理连接已断开")
                            break
                        if not proxy.xunfei_ws:
                            logger.warning("⚠️ 讯飞WebSocket连接已断开")
                            break
                
            except asyncio.TimeoutError:
                # 超时，但需要记录频率
                no_result_count += 1
                if no_result_count % 5 == 0:  # 每10秒记录一次超时
                    logger.debug(f"⏰ 监听超时 #{no_result_count} - 讯飞暂无返回数据")
                continue
            except (ConnectionClosedError, websockets.exceptions.ConnectionClosed):
                # 连接正常关闭
                logger.info("🔌 讯飞连接关闭，停止监听")
                break
            except Exception as e:
                # 其他错误，记录并退出
                logger.error(f"❌ 识别结果接收异常: {type(e).__name__}: {e}")
                break
                
    except Exception as e:
        logger.error(f"❌ 监听识别结果异常: {e}")
    
    logger.info(f"🔚 识别结果监听已停止 - 总共收到 {result_count} 个结果")


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
            logger.info("⏹️ 前端主动停止语音识别")
            await proxy.send_end_signal()
            
            # 获取累积的完整识别文本
            final_text = proxy.get_final_text()
            logger.info(f"🔍 完整识别文本: '{final_text}' (字符数: {len(final_text)})")
            
            # 发送识别完成状态
            await websocket.send_json({
                "type": "recording_stopped", 
                "text": final_text,
                "accumulated_text": final_text,
                "is_final": True,
                "message": "录音已停止，开始AI分析"
            })
            
            # 🎯 关键修改：现在在前端停止录音时才触发LangGraph感知节点
            if final_text and final_text.strip():
                logger.info("🚀 前端停止录音触发 - 开始调用LangGraph感知节点")
                ai_response = await integrate_with_interview_system(proxy, final_text)
                if ai_response and ai_response.get("success"):
                    # 将AI回复发送给前端
                    await websocket.send_json({
                        "type": "ai_response",
                        "message": ai_response["message"],
                        "user_profile": ai_response.get("user_profile"),
                        "completeness_score": ai_response.get("completeness_score"),
                        "missing_info": ai_response.get("missing_info"),
                        "user_emotion": ai_response.get("user_emotion"),
                        "decision": ai_response.get("decision"),
                        "interview_stage": ai_response.get("interview_stage"),
                        "session_id": proxy.session_id
                    })
                    logger.info("✅ LangGraph感知节点处理完成，AI回复已发送")
                else:
                    logger.warning("⚠️ LangGraph处理失败，未获得有效AI回复")
            else:
                logger.warning("⚠️ 识别文本为空，跳过LangGraph感知节点")
        
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
    """将语音识别文本集成到LangGraph面试系统"""
    try:
        if not recognized_text or not recognized_text.strip():
            logger.warning("⚠️ 识别文本为空，跳过集成")
            return None
        
        # 获取会话元数据
        session_metadata = voice_session_manager.session_metadata.get(proxy.session_id)
        if not session_metadata:
            logger.error("❌ 找不到会话元数据")
            return await generate_mock_response(recognized_text)
        
        user_id = session_metadata["user_id"]
        interview_session_id = session_metadata["interview_session_id"]
        
        logger.info(f"🤖 语音文本集成到LangGraph系统: {recognized_text[:50]}...")
        
        # 检查LangGraph模块是否可用
        if not LANGGRAPH_CHAT_AVAILABLE:
            logger.warning("⚠️ LangGraph聊天模块不可用，使用模拟响应")
            return await generate_mock_response(recognized_text)
        
        # 获取LangGraph智能体
        agent = get_langgraph_agent()
        if not agent:
            logger.warning("⚠️ LangGraph智能体不可用，使用模拟响应")
            return await generate_mock_response(recognized_text)
        
        # 检查面试会话是否存在
        session_info = active_sessions.get(interview_session_id)
        if not session_info:
            # 尝试从数据库恢复会话
            try:
                session_mgr = get_session_manager()
                session_info = session_mgr.get_session(interview_session_id)
                
                if session_info:
                    active_sessions[interview_session_id] = session_info
                    logger.info(f"🔄 从数据库恢复面试会话: {interview_session_id}")
                else:
                    logger.warning(f"⚠️ 面试会话不存在: {interview_session_id}")
                    return await generate_mock_response(recognized_text)
            except Exception as e:
                logger.error(f"❌ 恢复会话失败: {e}")
                return await generate_mock_response(recognized_text)
        
        # 构建用户画像
        current_profile = {
            "basic_info": {
                "name": session_info.get("user_name", "用户"),
                "target_position": session_info.get("target_position", "未知职位"),
                "target_field": session_info.get("target_field", "技术面试"),
            },
            "completeness_score": 0.3
        }
        
        # 调用LangGraph处理语音识别文本
        result = await agent.process_message_via_langgraph(
            user_id=user_id,
            session_id=interview_session_id,
            user_name=session_info.get("user_name", "用户"),
            target_position=session_info.get("target_position", "未知职位"),
            user_message=recognized_text,
            user_profile=current_profile
        )
        
        if result["success"]:
            logger.info("✅ LangGraph处理语音文本成功")
            return {
                "success": True,
                "message": result["response"],
                "user_profile": result.get("user_profile"),
                "completeness_score": result.get("completeness_score"),
                "missing_info": result.get("missing_info"),
                "user_emotion": result.get("user_emotion"),
                "decision": result.get("decision"),
                "interview_stage": result.get("interview_stage")
            }
        else:
            logger.warning(f"⚠️ LangGraph处理失败: {result.get('error')}")
            return await generate_mock_response(recognized_text)
        
    except Exception as e:
        logger.error(f"❌ 集成LangGraph面试系统失败: {e}")
        return await generate_mock_response(recognized_text)


async def generate_mock_response(recognized_text: str) -> dict:
    """生成模拟的面试响应（当LangGraph不可用时）"""
    try:
        logger.info(f"🎭 生成模拟响应: {recognized_text[:30]}...")
        
        # 简单的文本分析
        text_lower = recognized_text.lower()
        
        # 根据关键词生成不同的响应
        if any(word in text_lower for word in ['项目', 'project', '开发', '代码', '系统']):
            response_message = f"听起来您有丰富的项目经验。能详细介绍一下您在这个项目中遇到的最大挑战是什么吗？"
            missing_info = ["项目挑战", "解决方案", "技术栈详情"]
            emotion = "confident"
        elif any(word in text_lower for word in ['技能', 'skill', '语言', '框架', '技术']):
            response_message = f"很好，您提到了技术技能。能举个具体例子说明您是如何应用这些技术的吗？"
            missing_info = ["具体应用场景", "项目成果", "技术深度"]
            emotion = "confident"
        elif any(word in text_lower for word in ['经验', 'experience', '工作', '公司']):
            response_message = f"您的工作经验很有意思。在这段经历中，您学到了什么最重要的东西？"
            missing_info = ["核心收获", "成长经历", "团队协作"]
            emotion = "confident"
        elif any(word in text_lower for word in ['学习', '学校', '大学', '专业']):
            response_message = f"您的教育背景很棒。能谈谈您在学习过程中最印象深刻的项目或课程吗？"
            missing_info = ["学习项目", "专业技能", "实践经验"]
            emotion = "neutral"
        else:
            response_message = f"谢谢您的回答。基于您提到的内容，我想了解更多细节。能具体展开说说吗？"
            missing_info = ["详细信息", "具体例子", "相关经验"]
            emotion = "neutral"
        
        # 根据回答长度评估完整度
        completeness = min(0.8, max(0.2, len(recognized_text) / 150))
        
        return {
            "success": True,
            "message": response_message,
            "user_profile": {
                "completeness_score": completeness,
                "extracted_info": {
                    "communication_ability": "良好" if len(recognized_text) > 30 else "待观察",
                    "response_detail": "详细" if len(recognized_text) > 50 else "简洁"
                }
            },
            "completeness_score": completeness,
            "missing_info": missing_info,
            "user_emotion": emotion,
            "decision": {
                "action_type": "ask_question",
                "reasoning": "需要获取更多详细信息来完善用户画像"
            },
            "interview_stage": "information_gathering"
        }
        
    except Exception as e:
        logger.error(f"❌ 生成模拟响应失败: {e}")
        return {
            "success": True,
            "message": "谢谢您的回答，请继续分享您的想法。",
            "completeness_score": 0.3,
            "missing_info": ["更多信息"],
            "user_emotion": "neutral",
            "decision": {"action_type": "continue", "reasoning": "继续对话"},
            "interview_stage": "general"
        }


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


# ==================== 调试端点 ====================

@router.post("/debug/audio-saving/{session_id}")
async def debug_toggle_audio_saving(session_id: str, enabled: bool = True):
    """调试：控制指定会话的音频保存功能"""
    try:
        proxy = voice_session_manager.get_session(session_id)
        if not proxy:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        proxy.enable_audio_saving(enabled)
        audio_info = proxy.get_audio_info()
        
        return {
            "success": True,
            "session_id": session_id,
            "audio_info": audio_info
        }
        
    except Exception as e:
        logger.error(f"❌ 控制音频保存失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/debug/audio-info/{session_id}")
async def debug_get_audio_info(session_id: str):
    """调试：获取指定会话的音频保存信息和延时统计"""
    try:
        proxy = voice_session_manager.get_session(session_id)
        if not proxy:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        audio_info = proxy.get_audio_info()
        
        # 添加延时统计信息
        current_time = time.time()
        latency_info = {
            "audio_send_count": proxy.audio_send_count,
            "result_receive_count": proxy.result_receive_count,
            "first_audio_send_time": proxy.first_audio_send_time,
            "last_audio_send_time": proxy.last_audio_send_time,
            "session_duration_ms": 0,
            "last_latency_ms": 0
        }
        
        if proxy.first_audio_send_time:
            latency_info["session_duration_ms"] = (current_time - proxy.first_audio_send_time) * 1000
        
        if proxy.last_audio_send_time:
            latency_info["last_latency_ms"] = (current_time - proxy.last_audio_send_time) * 1000
        
        return {
            "success": True,
            "session_id": session_id,
            "audio_info": audio_info,
            "latency_info": latency_info
        }
        
    except Exception as e:
        logger.error(f"❌ 获取音频信息失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ==================== 语调分析端点 ====================

@router.post("/voice-analysis/{session_id}/toggle")
async def toggle_voice_analysis(session_id: str, enabled: bool = True):
    """开启/关闭实时语调分析"""
    try:
        proxy = voice_session_manager.get_session(session_id)
        if not proxy:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        proxy.realtime_analysis_enabled = enabled
        
        return {
            "success": True,
            "session_id": session_id,
            "voice_analysis_enabled": enabled,
            "message": f"语调分析已{'开启' if enabled else '关闭'}"
        }
        
    except Exception as e:
        logger.error(f"❌ 切换语调分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"切换语调分析失败: {str(e)}")


@router.get("/voice-analysis/{session_id}/history")
async def get_voice_analysis_history(session_id: str):
    """获取语调分析历史记录"""
    try:
        proxy = voice_session_manager.get_session(session_id)
        if not proxy:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        history = proxy.get_voice_analysis_history()
        
        return {
            "success": True,
            "session_id": session_id,
            "history": history,
            "count": len(history),
            "enabled": proxy.realtime_analysis_enabled
        }
        
    except Exception as e:
        logger.error(f"❌ 获取语调分析历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取语调分析历史失败: {str(e)}")


@router.delete("/voice-analysis/{session_id}/history")
async def clear_voice_analysis_history(session_id: str):
    """清空语调分析历史记录"""
    try:
        proxy = voice_session_manager.get_session(session_id)
        if not proxy:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        proxy.clear_voice_analysis_history()
        
        return {
            "success": True,
            "session_id": session_id,
            "message": "语调分析历史记录已清空"
        }
        
    except Exception as e:
        logger.error(f"❌ 清空语调分析历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空语调分析历史失败: {str(e)}")


@router.get("/voice-analysis/status")
async def get_voice_analysis_status():
    """获取语调分析功能状态"""
    try:
        return {
            "success": True,
            "librosa_available": LIBROSA_AVAILABLE,
            "audio_processing_available": AUDIO_PROCESSING_AVAILABLE,
            "active_sessions": len(voice_session_manager.active_sessions),
            "analysis_enabled_sessions": sum(
                1 for proxy in voice_session_manager.active_sessions.values()
                if getattr(proxy, 'realtime_analysis_enabled', False)
            )
        }
        
    except Exception as e:
        logger.error(f"❌ 获取语调分析状态失败: {e}")
        return {
            "success": False,
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
