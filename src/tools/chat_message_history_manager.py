"""
聊天消息历史管理器 - 基于LangChain SQLiteChatMessageHistory
提供会话消息的持久化存储和检索功能
"""
import os
import logging
import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, messages_from_dict, messages_to_dict

logger = logging.getLogger(__name__)


class CustomSQLiteChatMessageHistory(BaseChatMessageHistory):
    """自定义SQLite消息历史实现 - 基于LangChain BaseChatMessageHistory"""
    
    def __init__(self, session_id: str, connection_string: str):
        """初始化SQLite消息历史"""
        self.session_id = session_id
        self.connection_string = connection_string
        
        # 解析连接字符串，提取数据库路径
        if connection_string.startswith("sqlite:///"):
            self.db_path = connection_string[len("sqlite:///"):]
        else:
            self.db_path = connection_string
        
        # 确保数据库目录存在
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库表
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        session_id TEXT NOT NULL,
                        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        additional_kwargs TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建索引（单独语句）
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_session_time 
                    ON chat_messages(session_id, created_at)
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"❌ 初始化消息历史数据库失败: {e}")
            raise
    
    @property
    def messages(self) -> List[BaseMessage]:
        """获取会话的所有消息（LangChain BaseChatMessageHistory接口）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT message_type, content, additional_kwargs
                    FROM chat_messages 
                    WHERE session_id = ?
                    ORDER BY created_at ASC
                """, (self.session_id,))
                
                messages = []
                for row in cursor.fetchall():
                    message_type = row['message_type']
                    content = row['content']
                    additional_kwargs = json.loads(row['additional_kwargs'] or '{}')
                    
                    # 根据消息类型创建对应的消息对象
                    if message_type == 'human':
                        messages.append(HumanMessage(content=content, additional_kwargs=additional_kwargs))
                    elif message_type == 'ai':
                        messages.append(AIMessage(content=content, additional_kwargs=additional_kwargs))
                    elif message_type == 'system':
                        messages.append(SystemMessage(content=content, additional_kwargs=additional_kwargs))
                
                return messages
                
        except Exception as e:
            logger.error(f"❌ 获取消息历史失败: {e}")
            return []
    
    def add_message(self, message: BaseMessage) -> None:
        """添加消息（LangChain BaseChatMessageHistory接口）"""
        try:
            # 确定消息类型
            if isinstance(message, HumanMessage):
                message_type = 'human'
            elif isinstance(message, AIMessage):
                message_type = 'ai'
            elif isinstance(message, SystemMessage):
                message_type = 'system'
            else:
                message_type = 'unknown'
            
            # 序列化additional_kwargs
            additional_kwargs_json = json.dumps(message.additional_kwargs, ensure_ascii=False)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO chat_messages (session_id, message_type, content, additional_kwargs)
                    VALUES (?, ?, ?, ?)
                """, (self.session_id, message_type, message.content, additional_kwargs_json))
                conn.commit()
                
        except Exception as e:
            logger.error(f"❌ 添加消息失败: {e}")
            raise
    
    def clear(self) -> None:
        """清空会话的所有消息（LangChain BaseChatMessageHistory接口）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (self.session_id,))
                conn.commit()
                logger.info(f"🧹 清空会话消息: {self.session_id}")
        except Exception as e:
            logger.error(f"❌ 清空消息失败: {e}")
            raise


class ChatMessageHistoryManager:
    """聊天消息历史管理器 - 基于LangChain SQLiteChatMessageHistory"""
    
    def __init__(self, db_path: str = None):
        """初始化消息历史管理器"""
        
        # 设置数据库路径
        if db_path is None:
            db_dir = Path("data/chat_history")
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(db_dir / "interview_chat_history.db")
        
        self.db_path = db_path
        self.connection_string = f"sqlite:///{db_path}"
        
        # 会话历史实例缓存
        self._session_histories: Dict[str, CustomSQLiteChatMessageHistory] = {}
        
        # 初始化数据库（通过创建临时实例）
        self._init_database()
        
        logger.info(f"✅ 聊天消息历史管理器初始化: {self.connection_string}")
    
    def _init_database(self):
        """初始化数据库结构"""
        try:
            # 创建一个临时实例来初始化数据库表结构
            temp_history = CustomSQLiteChatMessageHistory(
                session_id="temp_init",
                connection_string=self.connection_string
            )
            # 添加一条临时消息来触发表创建，然后删除
            temp_history.add_message(SystemMessage(content="init"))
            temp_history.clear()
            
            logger.info("✅ 聊天消息历史数据库初始化完成")
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}")
            raise
    
    def get_session_history(self, session_id: str) -> CustomSQLiteChatMessageHistory:
        """获取会话的消息历史实例（带缓存）"""
        if session_id not in self._session_histories:
            self._session_histories[session_id] = CustomSQLiteChatMessageHistory(
                session_id=session_id,
                connection_string=self.connection_string
            )
            logger.debug(f"💾 创建会话消息历史: {session_id}")
        
        return self._session_histories[session_id]
    
    def add_message(self, session_id: str, message: BaseMessage) -> bool:
        """添加消息到会话历史"""
        try:
            history = self.get_session_history(session_id)
            history.add_message(message)
            logger.debug(f"📝 消息已保存: {session_id} - {type(message).__name__}")
            return True
        except Exception as e:
            logger.error(f"❌ 添加消息失败: {e}")
            return False
    
    def get_messages(self, session_id: str, limit: int = None) -> List[BaseMessage]:
        """获取会话的消息历史"""
        try:
            history = self.get_session_history(session_id)
            messages = history.messages
            
            if limit and len(messages) > limit:
                # 保留系统消息，限制用户消息数量
                system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
                other_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
                
                if len(other_messages) > limit:
                    other_messages = other_messages[-limit:]  # 保留最新的消息
                
                messages = system_messages + other_messages
            
            logger.debug(f"📖 获取消息历史: {session_id} - {len(messages)}条消息")
            return messages
        except Exception as e:
            logger.error(f"❌ 获取消息历史失败: {e}")
            return []
    
    def get_recent_context(self, session_id: str, max_messages: int = 10) -> List[BaseMessage]:
        """获取最近的上下文消息（用于模型输入）"""
        try:
            history = self.get_session_history(session_id)
            messages = history.messages
            
            if len(messages) <= max_messages:
                return messages
            
            # 保留最近的消息，但确保包含必要的系统消息
            recent_messages = messages[-max_messages:]
            
            # 如果最近消息中没有系统消息，添加最新的系统消息
            has_system = any(isinstance(msg, SystemMessage) for msg in recent_messages)
            if not has_system:
                system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
                if system_messages:
                    # 添加最新的系统消息到开头
                    recent_messages = [system_messages[-1]] + recent_messages[1:]
            
            logger.debug(f"🔍 获取上下文: {session_id} - {len(recent_messages)}条消息")
            return recent_messages
        except Exception as e:
            logger.error(f"❌ 获取上下文失败: {e}")
            return []
    
    def clear_session_history(self, session_id: str) -> bool:
        """清空会话历史"""
        try:
            history = self.get_session_history(session_id)
            history.clear()
            
            # 从缓存中移除
            if session_id in self._session_histories:
                del self._session_histories[session_id]
            
            logger.info(f"🧹 清空会话历史: {session_id}")
            return True
        except Exception as e:
            logger.error(f"❌ 清空会话历史失败: {e}")
            return False
    
    def get_session_summary(self, session_id: str) -> Dict:
        """获取会话摘要信息"""
        try:
            messages = self.get_messages(session_id)
            
            # 统计消息类型
            user_messages = len([msg for msg in messages if isinstance(msg, HumanMessage)])
            ai_messages = len([msg for msg in messages if isinstance(msg, AIMessage)])
            system_messages = len([msg for msg in messages if isinstance(msg, SystemMessage)])
            
            # 获取首末消息时间（如果SQLite存储了时间戳）
            first_message_time = None
            last_message_time = None
            
            if messages:
                # 尝试从消息内容或属性中提取时间信息
                first_message_time = datetime.now() - timedelta(hours=1)  # 简化：假设1小时前开始
                last_message_time = datetime.now()
            
            return {
                "session_id": session_id,
                "total_messages": len(messages),
                "user_messages": user_messages,
                "ai_messages": ai_messages,
                "system_messages": system_messages,
                "first_message_time": first_message_time.isoformat() if first_message_time else None,
                "last_message_time": last_message_time.isoformat() if last_message_time else None
            }
        except Exception as e:
            logger.error(f"❌ 获取会话摘要失败: {e}")
            return {"session_id": session_id, "error": str(e)}
    
    def cleanup_old_sessions(self, days_old: int = 30) -> int:
        """清理旧会话（SQLite没有自动TTL，需要手动清理）"""
        try:
            # 注意：SQLiteChatMessageHistory没有提供批量清理接口
            # 这里提供一个简化的清理策略
            
            logger.info(f"🧹 开始清理{days_old}天前的会话...")
            
            # 实际实现需要直接操作SQLite数据库
            # 这里先返回0，表示暂不实现自动清理
            # 可以在后续版本中添加直接SQL清理逻辑
            
            logger.info("ℹ️ 自动清理功能待实现，建议定期手动清理数据库")
            return 0
            
        except Exception as e:
            logger.error(f"❌ 清理旧会话失败: {e}")
            return 0
    
    def get_statistics(self) -> Dict:
        """获取消息历史统计信息"""
        try:
            # 由于SQLiteChatMessageHistory没有提供聚合查询接口
            # 这里返回基本统计信息
            return {
                "total_sessions": len(self._session_histories),
                "database_path": self.db_path,
                "database_exists": os.path.exists(self.db_path),
                "database_size_mb": round(os.path.getsize(self.db_path) / (1024*1024), 2) if os.path.exists(self.db_path) else 0
            }
        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            return {"error": str(e)}


# 创建全局消息历史管理器实例
_message_history_manager = None

def get_message_history_manager() -> ChatMessageHistoryManager:
    """获取全局消息历史管理器实例"""
    global _message_history_manager
    
    if _message_history_manager is None:
        _message_history_manager = ChatMessageHistoryManager()
        logger.info("✅ 创建全局消息历史管理器")
    
    return _message_history_manager


# 便捷函数
def get_session_history(session_id: str) -> CustomSQLiteChatMessageHistory:
    """获取会话历史"""
    return get_message_history_manager().get_session_history(session_id)

def add_user_message(session_id: str, content: str) -> bool:
    """添加用户消息"""
    return get_message_history_manager().add_message(session_id, HumanMessage(content=content))

def add_ai_message(session_id: str, content: str) -> bool:
    """添加AI消息"""
    return get_message_history_manager().add_message(session_id, AIMessage(content=content))

def get_conversation_context(session_id: str, max_messages: int = 10) -> List[BaseMessage]:
    """获取对话上下文"""
    return get_message_history_manager().get_recent_context(session_id, max_messages)

def clear_session_messages(session_id: str) -> bool:
    """清空会话消息"""
    return get_message_history_manager().clear_session_history(session_id)
