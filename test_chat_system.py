#!/usr/bin/env python3
"""
职面星火聊天系统测试脚本
演示如何使用基于LangChain的智能聊天功能
"""

import asyncio
import json
import logging
import websockets
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatSystemTester:
    """聊天系统测试客户端"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.ws_url = base_url.replace("http", "ws")
        self.session_id = None
        self.access_token = None
    
    async def login_user(self):
        """模拟用户登录获取token"""
        # 这里应该实现真实的登录逻辑
        # 为了演示目的，我们使用模拟token
        self.access_token = "demo_token_for_testing"
        logger.info("✅ 用户登录成功")
    
    async def start_chat_session(self):
        """开始聊天会话"""
        import aiohttp
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "user_name": "测试用户",
            "target_position": "前端开发工程师", 
            "target_field": "前端开发",
            "resume_text": "具有3年前端开发经验，熟悉React、Vue、TypeScript等技术栈"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/v1/chat/start",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.session_id = data['session_id']
                        logger.info(f"✅ 聊天会话创建成功: {self.session_id}")
                        logger.info(f"AI欢迎消息: {data['message']['content']}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ 创建会话失败: {error_text}")
                        return False
        except Exception as e:
            logger.error(f"❌ 创建会话异常: {e}")
            return False
    
    async def test_websocket_chat(self):
        """测试WebSocket聊天功能"""
        if not self.session_id:
            logger.error("❌ 没有有效的会话ID")
            return
        
        ws_url = f"{self.ws_url}/api/v1/chat/ws/{self.session_id}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                logger.info("🔌 WebSocket连接已建立")
                
                # 接收连接确认消息
                welcome_msg = await websocket.recv()
                logger.info(f"📨 收到连接消息: {welcome_msg}")
                
                # 测试对话
                test_messages = [
                    "您好，我想应聘前端开发工程师的职位。",
                    "我有3年的React开发经验，参与过多个大型项目。",
                    "我最擅长的是组件化开发和状态管理。",
                    "关于Vue框架，我也有2年的使用经验。",
                    "我对TypeScript和前端工程化也比较熟悉。"
                ]
                
                for i, message in enumerate(test_messages):
                    logger.info(f"\n🗣️ 发送消息 {i+1}: {message}")
                    
                    # 发送消息
                    await websocket.send(json.dumps({
                        "type": "message",
                        "message": message
                    }))
                    
                    # 接收AI响应
                    full_response = ""
                    async for ws_message in websocket:
                        try:
                            data = json.loads(ws_message)
                            
                            if data.get("type") == "processing_start":
                                logger.info("🤖 AI开始处理...")
                            
                            elif data.get("type") == "chunk":
                                chunk = data.get("content", "")
                                full_response += chunk
                                print(chunk, end="", flush=True)
                            
                            elif data.get("type") == "complete":
                                logger.info(f"\n✅ AI回复完成")
                                logger.info(f"📝 完整回复: {full_response}")
                                break
                            
                            elif data.get("type") == "error":
                                logger.error(f"❌ AI回复错误: {data.get('message')}")
                                break
                                
                        except json.JSONDecodeError as e:
                            logger.error(f"❌ 消息解析失败: {e}")
                            continue
                    
                    # 等待一会儿再发送下一条消息
                    await asyncio.sleep(2)
                
                logger.info("✅ WebSocket聊天测试完成")
                
        except Exception as e:
            logger.error(f"❌ WebSocket聊天测试失败: {e}")
    
    async def test_http_streaming_chat(self):
        """测试HTTP流式聊天"""
        if not self.session_id:
            logger.error("❌ 没有有效的会话ID")
            return
        
        import aiohttp
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "session_id": self.session_id,
            "message": "请问贵公司对前端开发有什么具体要求？",
            "message_type": "text"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/v1/chat/message",
                    headers=headers,
                    json=payload
                ) as response:
                    
                    if response.status == 200:
                        logger.info("🌊 开始接收流式响应...")
                        
                        async for line in response.content:
                            line = line.decode('utf-8').strip()
                            if line.startswith('data: '):
                                try:
                                    data_str = line[6:]  # 去掉 'data: ' 前缀
                                    if data_str:
                                        data = json.loads(data_str)
                                        if data.get("type") == "chunk":
                                            print(data.get("content", ""), end="", flush=True)
                                        elif data.get("type") == "complete":
                                            logger.info("\n✅ HTTP流式响应完成")
                                            break
                                except json.JSONDecodeError:
                                    continue
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ HTTP流式聊天失败: {error_text}")
                        
        except Exception as e:
            logger.error(f"❌ HTTP流式聊天异常: {e}")
    
    async def get_chat_history(self):
        """获取聊天历史"""
        if not self.session_id:
            return
        
        import aiohttp
        
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/v1/chat/history/{self.session_id}",
                    headers=headers
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info("📚 聊天历史:")
                        for msg in data['messages']:
                            timestamp = msg['timestamp']
                            role = "用户" if msg['role'] == 'user' else "AI面试官"
                            content = msg['content'][:50] + "..." if len(msg['content']) > 50 else msg['content']
                            logger.info(f"  {timestamp} [{role}]: {content}")
                    else:
                        logger.error("❌ 获取聊天历史失败")
                        
        except Exception as e:
            logger.error(f"❌ 获取聊天历史异常: {e}")

async def main():
    """主测试函数"""
    logger.info("🚀 开始测试职面星火聊天系统")
    logger.info("=" * 50)
    
    tester = ChatSystemTester()
    
    # 1. 模拟用户登录
    await tester.login_user()
    
    # 2. 开始聊天会话
    success = await tester.start_chat_session()
    if not success:
        logger.error("❌ 无法创建聊天会话，测试终止")
        return
    
    # 3. 测试WebSocket聊天
    logger.info("\n" + "="*50)
    logger.info("🔌 测试WebSocket实时聊天")
    logger.info("="*50)
    await tester.test_websocket_chat()
    
    # 4. 测试HTTP流式聊天
    logger.info("\n" + "="*50)
    logger.info("🌊 测试HTTP流式聊天")
    logger.info("="*50)
    await tester.test_http_streaming_chat()
    
    # 5. 获取聊天历史
    logger.info("\n" + "="*50)
    logger.info("📚 获取聊天历史")
    logger.info("="*50)
    await tester.get_chat_history()
    
    logger.info("\n✅ 聊天系统测试完成！")

if __name__ == "__main__":
    asyncio.run(main())
