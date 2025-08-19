# -*- encoding:utf-8 -*-
"""
讯飞实时语音识别客户端
基于原始rtasr_python3_demo.py改进的生产级实现
"""
import asyncio
import hashlib
import hmac
import base64
import json
import time
import threading
import logging
from typing import Optional, Callable, Dict, Any
from urllib.parse import quote
import websocket
from websocket import WebSocketApp
from queue import Queue, Empty

logger = logging.getLogger(__name__)


class XunfeiRTASRClient:
    """讯飞实时语音识别客户端 - 生产级实现"""
    
    def __init__(self, app_id: str, api_key: str, 
                 on_result: Optional[Callable] = None,
                 on_error: Optional[Callable] = None,
                 on_started: Optional[Callable] = None,
                 on_finished: Optional[Callable] = None):
        """
        初始化讯飞RTASR客户端
        
        Args:
            app_id: 应用ID
            api_key: API密钥
            on_result: 结果回调函数
            on_error: 错误回调函数
            on_started: 开始回调函数
            on_finished: 完成回调函数
        """
        self.app_id = app_id
        self.api_key = api_key
        self.base_url = "ws://rtasr.xfyun.cn/v1/ws"
        
        # 回调函数
        self.on_result = on_result or self._default_result_handler
        self.on_error = on_error or self._default_error_handler
        self.on_started = on_started or self._default_started_handler
        self.on_finished = on_finished or self._default_finished_handler
        
        # 连接状态
        self.ws = None
        self.is_connected = False
        self.is_recording = False
        
        # 结果存储
        self.recognized_text = ""
        self.results_queue = Queue()
        
        # 线程管理
        self.receive_thread = None
        self.send_thread = None
        self.audio_queue = Queue()
        
        # 结束标记
        self.end_tag = json.dumps({"end": True})
        
        logger.info("🎤 讯飞RTASR客户端初始化完成")
    
    def _generate_signature(self, ts: str) -> str:
        """生成API签名"""
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
    
    def connect(self) -> bool:
        """建立WebSocket连接"""
        try:
            if self.is_connected:
                logger.warning("⚠️ 连接已存在")
                return True
            
            # 生成认证参数
            ts = str(int(time.time()))
            signa = self._generate_signature(ts)
            
            # 构建WebSocket URL
            ws_url = f"{self.base_url}?appid={self.app_id}&ts={ts}&signa={quote(signa)}"
            
            logger.info("🔗 连接讯飞RTASR服务...")
            
            # 创建WebSocket连接
            self.ws = websocket.WebSocketApp(
                ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_websocket_error,
                on_close=self._on_close
            )
            
            # 启动连接（非阻塞）
            self.ws_thread = threading.Thread(target=self.ws.run_forever)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
            # 等待连接建立
            max_wait = 10  # 最大等待10秒
            wait_count = 0
            while not self.is_connected and wait_count < max_wait:
                time.sleep(0.1)
                wait_count += 0.1
            
            if self.is_connected:
                logger.info("✅ 讯飞RTASR连接成功")
                return True
            else:
                logger.error("❌ 连接超时")
                return False
                
        except Exception as e:
            logger.error(f"❌ 连接失败: {e}")
            return False
    
    def _on_open(self, ws):
        """WebSocket连接打开"""
        logger.info("🤝 WebSocket连接已建立")
        self.is_connected = True
        
        # 启动发送线程
        self.send_thread = threading.Thread(target=self._send_worker)
        self.send_thread.daemon = True
        self.send_thread.start()
    
    def _on_message(self, ws, message):
        """接收到消息"""
        try:
            result = json.loads(message)
            self._handle_result(result)
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ 解析消息JSON失败: {e}")
        except Exception as e:
            logger.error(f"❌ 处理消息失败: {e}")
    
    def _on_websocket_error(self, ws, error):
        """WebSocket错误"""
        logger.error(f"❌ WebSocket错误: {error}")
        self.is_connected = False
        self.on_error(f"WebSocket错误: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket连接关闭"""
        logger.info(f"🔌 WebSocket连接关闭: {close_status_code} - {close_msg}")
        self.is_connected = False
        self.is_recording = False
        
        # 处理最终结果
        if self.recognized_text:
            self.on_finished(self.recognized_text)
    
    def _handle_result(self, result: Dict[str, Any]):
        """处理识别结果"""
        try:
            action = result.get("action")
            
            if action == "started":
                logger.info("🎯 握手成功")
                self.on_started()
                
            elif action == "result":
                # 提取识别文本
                text = result.get("data", "")
                if text:
                    self.recognized_text = text
                    
                    # 将结果放入队列
                    self.results_queue.put({
                        "text": text,
                        "timestamp": time.time(),
                        "is_final": result.get("is_final", False)
                    })
                    
                    # 调用结果回调
                    self.on_result(text, result.get("is_final", False))
                    
                    logger.debug(f"📝 识别结果: {text}")
                
            elif action == "error":
                error_desc = result.get("desc", "未知错误")
                logger.error(f"❌ 识别错误: {error_desc}")
                self.on_error(f"识别错误: {error_desc}")
                
        except Exception as e:
            logger.error(f"❌ 处理识别结果失败: {e}")
    
    def _send_worker(self):
        """发送工作线程"""
        try:
            while self.is_connected:
                try:
                    # 从队列获取音频数据
                    audio_data = self.audio_queue.get(timeout=1.0)
                    
                    if audio_data is None:  # 结束信号
                        break
                    
                    if isinstance(audio_data, str) and audio_data == "END":
                        # 发送结束标记
                        self.ws.send(self.end_tag)
                        logger.info("🏁 发送结束标记")
                        break
                    
                    # 发送音频数据
                    if self.ws and self.is_connected:
                        self.ws.send(audio_data, websocket.ABNF.OPCODE_BINARY)
                        logger.debug(f"📤 发送音频数据: {len(audio_data)} bytes")
                    
                except Empty:
                    continue
                except Exception as e:
                    logger.error(f"❌ 发送音频数据失败: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"❌ 发送工作线程异常: {e}")
    
    def send_audio_data(self, audio_data: bytes):
        """发送音频数据"""
        if not self.is_connected:
            logger.warning("⚠️ 连接未建立，无法发送音频数据")
            return False
        
        try:
            self.audio_queue.put(audio_data)
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加音频数据到队列失败: {e}")
            return False
    
    def send_audio_file(self, file_path: str, chunk_size: int = 1280):
        """发送音频文件"""
        try:
            if not self.is_connected:
                logger.error("❌ 连接未建立")
                return False
            
            logger.info(f"📁 开始发送音频文件: {file_path}")
            
            with open(file_path, 'rb') as file:
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    
                    self.send_audio_data(chunk)
                    time.sleep(0.04)  # 控制发送速率
            
            # 发送结束信号
            self.stop_recording()
            
            logger.info("✅ 音频文件发送完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 发送音频文件失败: {e}")
            return False
    
    def start_recording(self):
        """开始录音"""
        if not self.is_connected:
            logger.error("❌ 连接未建立，无法开始录音")
            return False
        
        self.is_recording = True
        logger.info("🎤 开始录音")
        return True
    
    def stop_recording(self):
        """停止录音"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        # 发送结束信号
        self.audio_queue.put("END")
        
        logger.info("⏹️ 停止录音")
    
    def get_results(self) -> list:
        """获取所有识别结果"""
        results = []
        
        try:
            while not self.results_queue.empty():
                results.append(self.results_queue.get_nowait())
        except Empty:
            pass
        
        return results
    
    def get_final_text(self) -> str:
        """获取最终识别文本"""
        return self.recognized_text
    
    def disconnect(self):
        """断开连接"""
        logger.info("🔌 断开讯飞RTASR连接...")
        
        self.is_connected = False
        self.is_recording = False
        
        # 停止发送线程
        if self.audio_queue:
            self.audio_queue.put(None)
        
        # 关闭WebSocket
        if self.ws:
            self.ws.close()
        
        # 等待线程结束
        if self.send_thread and self.send_thread.is_alive():
            self.send_thread.join(timeout=2)
        
        if hasattr(self, 'ws_thread') and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=2)
        
        logger.info("✅ 连接已断开")
    
    # 默认回调函数
    def _default_started_handler(self):
        logger.info("🎯 识别开始")
    
    def _default_result_handler(self, text: str, is_final: bool):
        logger.info(f"📝 识别结果: {text} (final: {is_final})")
    
    def _default_error_handler(self, error: str):
        logger.error(f"❌ 识别错误: {error}")
    
    def _default_finished_handler(self, final_text: str):
        logger.info(f"✅ 识别完成: {final_text}")
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()


class AsyncXunfeiRTASRClient:
    """异步版本的讯飞RTASR客户端"""
    
    def __init__(self, app_id: str, api_key: str):
        self.app_id = app_id
        self.api_key = api_key
        self.sync_client = XunfeiRTASRClient(app_id, api_key)
        
        # 异步回调
        self.result_callbacks = []
        self.error_callbacks = []
        
        # 设置同步客户端的回调
        self.sync_client.on_result = self._on_sync_result
        self.sync_client.on_error = self._on_sync_error
    
    def _on_sync_result(self, text: str, is_final: bool):
        """同步结果回调"""
        for callback in self.result_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(text, is_final))
                else:
                    callback(text, is_final)
            except Exception as e:
                logger.error(f"❌ 结果回调执行失败: {e}")
    
    def _on_sync_error(self, error: str):
        """同步错误回调"""
        for callback in self.error_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(error))
                else:
                    callback(error)
            except Exception as e:
                logger.error(f"❌ 错误回调执行失败: {e}")
    
    def add_result_callback(self, callback: Callable):
        """添加结果回调"""
        self.result_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable):
        """添加错误回调"""
        self.error_callbacks.append(callback)
    
    async def connect(self) -> bool:
        """异步连接"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_client.connect)
    
    async def send_audio_data(self, audio_data: bytes) -> bool:
        """异步发送音频数据"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_client.send_audio_data, audio_data)
    
    async def send_audio_file(self, file_path: str) -> bool:
        """异步发送音频文件"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_client.send_audio_file, file_path)
    
    async def start_recording(self) -> bool:
        """异步开始录音"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_client.start_recording)
    
    async def stop_recording(self):
        """异步停止录音"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.sync_client.stop_recording)
    
    async def disconnect(self):
        """异步断开连接"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.sync_client.disconnect)
    
    def get_final_text(self) -> str:
        """获取最终文本"""
        return self.sync_client.get_final_text()
    
    def get_results(self) -> list:
        """获取结果列表"""
        return self.sync_client.get_results()
    
    @property
    def is_connected(self) -> bool:
        """连接状态"""
        return self.sync_client.is_connected
    
    @property
    def is_recording(self) -> bool:
        """录音状态"""
        return self.sync_client.is_recording


# 使用示例和测试
async def test_xunfei_client():
    """测试讯飞客户端"""
    app_id = "015076e9"
    api_key = "771f2107c79630c900476ea1de65540b"
    
    # 测试同步客户端
    def on_result(text, is_final):
        print(f"结果: {text} (final: {is_final})")
    
    def on_error(error):
        print(f"错误: {error}")
    
    client = XunfeiRTASRClient(
        app_id=app_id,
        api_key=api_key,
        on_result=on_result,
        on_error=on_error
    )
    
    try:
        # 连接
        if client.connect():
            print("连接成功")
            
            # 可以发送音频文件进行测试
            # client.send_audio_file("test_audio.pcm")
            
            # 等待一段时间
            time.sleep(5)
        
    finally:
        client.disconnect()


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_xunfei_client())
