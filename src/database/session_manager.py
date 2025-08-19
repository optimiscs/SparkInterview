"""
会话持久化管理器
解决会话记录丢失问题，将会话元数据持久化到SQLite数据库
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class SessionManager:
    """会话持久化管理器"""
    
    def __init__(self, db_path: str = "data/sqlite/interview_app.db"):
        self.db_path = db_path
        self.ensure_database_exists()
        self.init_session_tables()
        
    def ensure_database_exists(self):
        """确保数据库目录存在"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
    def init_session_tables(self):
        """初始化会话相关数据表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 创建会话元数据表
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS interview_sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        user_name TEXT NOT NULL,
                        target_position TEXT NOT NULL,
                        target_field TEXT NOT NULL,
                        resume_text TEXT,
                        status TEXT DEFAULT 'active',
                        interview_ended BOOLEAN DEFAULT 0,
                        report_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        metadata TEXT  -- JSON格式存储额外元数据
                    )
                """)
                
                # 创建报告数据表
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS interview_reports (
                        report_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        report_data TEXT NOT NULL,  -- JSON格式的报告数据
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id)
                    )
                """)
                
                # 创建索引
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sessions_user_activity 
                    ON interview_sessions(user_id, last_activity DESC)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sessions_status 
                    ON interview_sessions(status, interview_ended)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_reports_session 
                    ON interview_reports(session_id, created_at DESC)
                """)
                
                conn.commit()
                logger.info("✅ 会话和报告数据表初始化成功")
                
        except Exception as e:
            logger.error(f"❌ 会话数据表初始化失败: {e}")
            raise
    
    def save_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """保存会话元数据到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 准备数据，处理datetime序列化
                metadata_dict = {}
                for k, v in session_data.items():
                    if k not in ['user_id', 'user_name', 'target_position', 'target_field', 
                                'status', 'interview_ended', 'report_id', 'created_at', 'last_activity', 'completed_at']:
                        # 处理datetime对象
                        if isinstance(v, datetime):
                            metadata_dict[k] = v.isoformat()
                        else:
                            metadata_dict[k] = v
                
                metadata = json.dumps(metadata_dict)
                
                # 转换时间格式
                created_at = session_data.get('created_at')
                if isinstance(created_at, datetime):
                    created_at = created_at.isoformat()
                
                last_activity = session_data.get('last_activity')
                if isinstance(last_activity, datetime):
                    last_activity = last_activity.isoformat()
                
                completed_at = session_data.get('completed_at')
                if isinstance(completed_at, datetime):
                    completed_at = completed_at.isoformat()
                
                # 使用 REPLACE 语句（相当于 INSERT OR UPDATE）
                conn.execute("""
                    REPLACE INTO interview_sessions (
                        session_id, user_id, user_name, target_position, target_field,
                        resume_text, status, interview_ended, report_id,
                        created_at, last_activity, completed_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    session_data.get('user_id'),
                    session_data.get('user_name'),
                    session_data.get('target_position'),
                    session_data.get('target_field'),
                    session_data.get('resume_text', ''),
                    session_data.get('status', 'active'),
                    session_data.get('interview_ended', False),
                    session_data.get('report_id'),
                    created_at,
                    last_activity,
                    completed_at,
                    metadata
                ))
                
                conn.commit()
                logger.debug(f"💾 会话已保存: {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ 保存会话失败: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """从数据库获取会话信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # 使用字典式访问
                cursor = conn.execute("""
                    SELECT * FROM interview_sessions WHERE session_id = ?
                """, (session_id,))
                
                row = cursor.fetchone()
                if row:
                    session_data = dict(row)
                    
                    # 解析JSON元数据
                    if session_data['metadata']:
                        try:
                            metadata = json.loads(session_data['metadata'])
                            session_data.update(metadata)
                        except json.JSONDecodeError:
                            logger.warning(f"⚠️ 解析会话元数据失败: {session_id}")
                    
                    # 转换时间格式
                    for time_field in ['created_at', 'last_activity', 'completed_at']:
                        if session_data[time_field]:
                            try:
                                session_data[time_field] = datetime.fromisoformat(session_data[time_field])
                            except ValueError:
                                logger.warning(f"⚠️ 时间格式转换失败: {time_field}")
                    
                    # 转换布尔值
                    session_data['interview_ended'] = bool(session_data['interview_ended'])
                    
                    return session_data
                
                return None
                
        except Exception as e:
            logger.error(f"❌ 获取会话失败: {e}")
            return None
    
    def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的所有会话"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM interview_sessions 
                    WHERE user_id = ? 
                    ORDER BY last_activity DESC
                """, (user_id,))
                
                sessions = []
                for row in cursor.fetchall():
                    session_data = dict(row)
                    
                    # 解析JSON元数据
                    if session_data['metadata']:
                        try:
                            metadata = json.loads(session_data['metadata'])
                            session_data.update(metadata)
                        except json.JSONDecodeError:
                            pass
                    
                    # 转换布尔值
                    session_data['interview_ended'] = bool(session_data['interview_ended'])
                    
                    sessions.append(session_data)
                
                return sessions
                
        except Exception as e:
            logger.error(f"❌ 获取用户会话列表失败: {e}")
            return []
    
    def update_session_activity(self, session_id: str) -> bool:
        """更新会话活跃时间"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE interview_sessions 
                    SET last_activity = CURRENT_TIMESTAMP 
                    WHERE session_id = ?
                """, (session_id,))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"❌ 更新会话活跃时间失败: {e}")
            return False
    
    def mark_session_completed(self, session_id: str, report_id: str = None) -> bool:
        """标记会话为已完成"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE interview_sessions 
                    SET status = 'completed', 
                        interview_ended = 1,
                        completed_at = CURRENT_TIMESTAMP,
                        report_id = ?
                    WHERE session_id = ?
                """, (report_id, session_id))
                
                conn.commit()
                logger.info(f"✅ 会话标记为已完成: {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ 标记会话完成失败: {e}")
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """从数据库删除会话"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM interview_sessions WHERE session_id = ?
                """, (session_id,))
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"🗑️ 会话已从数据库删除: {session_id}")
                    return True
                else:
                    logger.warning(f"⚠️ 会话不存在，无法删除: {session_id}")
                    return False
                
        except Exception as e:
            logger.error(f"❌ 删除会话失败: {e}")
            return False
    
    def load_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """从数据库加载所有活跃会话到内存"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM interview_sessions 
                    WHERE status != 'deleted'
                    ORDER BY last_activity DESC
                """)
                
                active_sessions = {}
                
                for row in cursor.fetchall():
                    session_data = dict(row)
                    
                    # 解析JSON元数据
                    if session_data['metadata']:
                        try:
                            metadata = json.loads(session_data['metadata'])
                            session_data.update(metadata)
                        except json.JSONDecodeError:
                            pass
                    
                    # 转换时间格式
                    for time_field in ['created_at', 'last_activity', 'completed_at']:
                        if session_data[time_field]:
                            try:
                                session_data[time_field] = datetime.fromisoformat(session_data[time_field])
                            except ValueError:
                                session_data[time_field] = datetime.now()
                    
                    # 转换布尔值
                    session_data['interview_ended'] = bool(session_data['interview_ended'])
                    
                    # 移除数据库专用字段
                    session_data.pop('metadata', None)
                    
                    active_sessions[session_data['session_id']] = session_data
                
                logger.info(f"📚 从数据库加载了 {len(active_sessions)} 个会话")
                return active_sessions
                
        except Exception as e:
            logger.error(f"❌ 从数据库加载会话失败: {e}")
            return {}
    
    def cleanup_old_sessions(self, days: int = 30) -> int:
        """清理超过指定天数的旧会话"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM interview_sessions 
                    WHERE last_activity < datetime('now', '-{} days')
                """.format(days))
                
                conn.commit()
                deleted_count = cursor.rowcount
                
                if deleted_count > 0:
                    logger.info(f"🧹 清理了 {deleted_count} 个超过 {days} 天的旧会话")
                
                return deleted_count
                
        except Exception as e:
            logger.error(f"❌ 清理旧会话失败: {e}")
            return 0
    
    def save_report(self, report_id: str, session_id: str, user_id: str, report_data: Dict[str, Any]) -> bool:
        """保存面试报告数据到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 将报告数据转换为JSON字符串
                report_json = json.dumps(report_data, ensure_ascii=False, indent=2)
                
                # 保存到数据库
                conn.execute("""
                    REPLACE INTO interview_reports (
                        report_id, session_id, user_id, report_data, created_at
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (report_id, session_id, user_id, report_json))
                
                conn.commit()
                logger.info(f"💾 报告数据已保存到数据库: {report_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ 保存报告数据失败: {e}")
            return False
    
    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """从数据库获取报告数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM interview_reports WHERE report_id = ?
                """, (report_id,))
                
                row = cursor.fetchone()
                if row:
                    # 解析JSON报告数据
                    try:
                        report_data = json.loads(row['report_data'])
                        logger.info(f"📊 从数据库获取报告成功: {report_id}")
                        return {
                            "report_id": row['report_id'],
                            "session_id": row['session_id'],
                            "user_id": row['user_id'],
                            "report_data": report_data,
                            "created_at": row['created_at']
                        }
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ 解析报告JSON数据失败: {e}")
                        return None
                
                logger.warning(f"⚠️ 报告不存在: {report_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 从数据库获取报告失败: {e}")
            return None
    
    def get_session_reports(self, session_id: str) -> List[Dict[str, Any]]:
        """获取会话的所有报告"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT report_id, created_at FROM interview_reports 
                    WHERE session_id = ? 
                    ORDER BY created_at DESC
                """, (session_id,))
                
                reports = []
                for row in cursor.fetchall():
                    reports.append({
                        "report_id": row['report_id'],
                        "created_at": row['created_at']
                    })
                
                return reports
                
        except Exception as e:
            logger.error(f"❌ 获取会话报告列表失败: {e}")
            return []

# 全局会话管理器实例
session_manager = None

def get_session_manager() -> SessionManager:
    """获取会话管理器实例（单例模式）"""
    global session_manager
    if session_manager is None:
        session_manager = SessionManager()
    return session_manager
