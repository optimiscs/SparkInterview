#!/usr/bin/env python3
"""
SQLite数据库管理器 - 用于用户和会话管理
"""
import sqlite3
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)

class SQLiteManager:
    """SQLite数据库管理器"""
    
    def __init__(self, db_path: str = "data/sqlite/interview_app.db"):
        """初始化SQLite数据库"""
        self.db_path = db_path
        self._local = threading.local()
        
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 初始化数据库表
        self._init_database()
        print(f"✅ SQLite数据库初始化成功: {db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取线程安全的数据库连接"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row  # 返回字典格式的行
            # 启用外键约束
            self._local.connection.execute("PRAGMA foreign_keys = ON")
        return self._local.connection
    
    @contextmanager
    def get_db_cursor(self):
        """获取数据库游标的上下文管理器"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            cursor.close()
    
    def _init_database(self):
        """初始化数据库表结构"""
        with self.get_db_cursor() as cursor:
            # 创建用户表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'student',
                    avatar_url TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            # 创建会话表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    expires_at DATETIME NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    user_agent TEXT,
                    ip_address TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            ''')
            
            # 创建索引以提高查询性能
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON user_sessions (user_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions (expires_at)
            ''')
            
            print("✅ 数据库表结构初始化完成")
    
    # 用户管理方法
    def create_user(self, user_data: Dict) -> str:
        """创建新用户"""
        try:
            with self.get_db_cursor() as cursor:
                now = datetime.now()
                cursor.execute('''
                    INSERT INTO users (id, name, email, password, role, avatar_url, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_data['id'],
                    user_data['name'],
                    user_data['email'],
                    user_data['password'],
                    user_data['role'],
                    user_data.get('avatar_url'),
                    now,
                    now
                ))
                
                print(f"✅ 用户创建成功: {user_data['email']}")
                return user_data['id']
                
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: users.email" in str(e):
                raise ValueError("邮箱地址已被注册")
            raise ValueError(f"用户创建失败: {e}")
        except Exception as e:
            logger.error(f"创建用户失败: {e}")
            raise
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """根据邮箱获取用户"""
        try:
            with self.get_db_cursor() as cursor:
                cursor.execute('''
                    SELECT * FROM users WHERE email = ? AND is_active = 1
                ''', (email,))
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"查询用户失败: {e}")
            return None
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """根据ID获取用户"""
        try:
            with self.get_db_cursor() as cursor:
                cursor.execute('''
                    SELECT * FROM users WHERE id = ? AND is_active = 1
                ''', (user_id,))
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"查询用户失败: {e}")
            return None
    
    def update_user(self, user_id: str, update_data: Dict) -> bool:
        """更新用户信息"""
        try:
            # 构建动态更新SQL
            set_clauses = []
            values = []
            
            for field in ['name', 'email', 'avatar_url']:
                if field in update_data and update_data[field] is not None:
                    set_clauses.append(f"{field} = ?")
                    values.append(update_data[field])
            
            if not set_clauses:
                return True  # 没有需要更新的字段
            
            # 添加更新时间
            set_clauses.append("updated_at = ?")
            values.append(datetime.now())
            values.append(user_id)
            
            with self.get_db_cursor() as cursor:
                sql = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?"
                cursor.execute(sql, values)
                
                if cursor.rowcount > 0:
                    print(f"✅ 用户信息更新成功: {user_id}")
                    return True
                return False
                
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: users.email" in str(e):
                raise ValueError("邮箱地址已被其他用户使用")
            raise ValueError(f"用户更新失败: {e}")
        except Exception as e:
            logger.error(f"更新用户失败: {e}")
            raise
    
    def delete_user(self, user_id: str) -> bool:
        """删除用户（软删除）"""
        try:
            with self.get_db_cursor() as cursor:
                # 软删除用户
                cursor.execute('''
                    UPDATE users SET is_active = 0, updated_at = ? WHERE id = ?
                ''', (datetime.now(), user_id))
                
                # 删除相关会话
                cursor.execute('''
                    UPDATE user_sessions SET is_active = 0 WHERE user_id = ?
                ''', (user_id,))
                
                if cursor.rowcount > 0:
                    print(f"✅ 用户删除成功: {user_id}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"删除用户失败: {e}")
            return False
    
    def get_all_users(self) -> List[Dict]:
        """获取所有活跃用户"""
        try:
            with self.get_db_cursor() as cursor:
                cursor.execute('''
                    SELECT * FROM users WHERE is_active = 1 ORDER BY created_at DESC
                ''')
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"查询用户列表失败: {e}")
            return []
    
    # 会话管理方法
    def create_session(self, session_data: Dict) -> str:
        """创建用户会话"""
        try:
            with self.get_db_cursor() as cursor:
                cursor.execute('''
                    INSERT INTO user_sessions (token, user_id, created_at, expires_at, user_agent, ip_address)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    session_data['token'],
                    session_data['user_id'],
                    session_data['created_at'],
                    session_data['expires_at'],
                    session_data.get('user_agent'),
                    session_data.get('ip_address')
                ))
                
                print(f"✅ 会话创建成功: {session_data['user_id']}")
                return session_data['token']
                
        except Exception as e:
            logger.error(f"创建会话失败: {e}")
            raise
    
    def get_session(self, token: str) -> Optional[Dict]:
        """获取会话信息"""
        try:
            with self.get_db_cursor() as cursor:
                cursor.execute('''
                    SELECT * FROM user_sessions 
                    WHERE token = ? AND is_active = 1
                ''', (token,))
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"查询会话失败: {e}")
            return None
    
    def delete_session(self, token: str) -> bool:
        """删除会话"""
        try:
            with self.get_db_cursor() as cursor:
                cursor.execute('''
                    UPDATE user_sessions SET is_active = 0 WHERE token = ?
                ''', (token,))
                
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"删除会话失败: {e}")
            return False
    
    def delete_user_sessions(self, user_id: str) -> int:
        """删除用户的所有会话"""
        try:
            with self.get_db_cursor() as cursor:
                cursor.execute('''
                    UPDATE user_sessions SET is_active = 0 WHERE user_id = ?
                ''', (user_id,))
                
                return cursor.rowcount
                
        except Exception as e:
            logger.error(f"删除用户会话失败: {e}")
            return 0
    
    def cleanup_expired_sessions(self) -> int:
        """清理过期的会话"""
        try:
            with self.get_db_cursor() as cursor:
                cursor.execute('''
                    UPDATE user_sessions 
                    SET is_active = 0 
                    WHERE expires_at < ? AND is_active = 1
                ''', (datetime.now(),))
                
                count = cursor.rowcount
                if count > 0:
                    print(f"✅ 清理了 {count} 个过期会话")
                return count
                
        except Exception as e:
            logger.error(f"清理过期会话失败: {e}")
            return 0
    
    def get_user_sessions(self, user_id: str) -> List[Dict]:
        """获取用户的活跃会话"""
        try:
            with self.get_db_cursor() as cursor:
                cursor.execute('''
                    SELECT * FROM user_sessions 
                    WHERE user_id = ? AND is_active = 1 AND expires_at > ?
                    ORDER BY created_at DESC
                ''', (user_id, datetime.now()))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"查询用户会话失败: {e}")
            return []
    
    # 数据库维护方法
    def get_database_stats(self) -> Dict:
        """获取数据库统计信息"""
        try:
            with self.get_db_cursor() as cursor:
                stats = {}
                
                # 用户统计
                cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_active = 1")
                stats['active_users'] = cursor.fetchone()['count']
                
                cursor.execute("SELECT COUNT(*) as count FROM users")
                stats['total_users'] = cursor.fetchone()['count']
                
                # 会话统计
                cursor.execute("SELECT COUNT(*) as count FROM user_sessions WHERE is_active = 1")
                stats['active_sessions'] = cursor.fetchone()['count']
                
                cursor.execute('''
                    SELECT COUNT(*) as count FROM user_sessions 
                    WHERE is_active = 1 AND expires_at > ?
                ''', (datetime.now(),))
                stats['valid_sessions'] = cursor.fetchone()['count']
                
                # 角色统计
                cursor.execute('''
                    SELECT role, COUNT(*) as count FROM users 
                    WHERE is_active = 1 GROUP BY role
                ''')
                role_stats = cursor.fetchall()
                stats['users_by_role'] = {row['role']: row['count'] for row in role_stats}
                
                return stats
                
        except Exception as e:
            logger.error(f"获取数据库统计失败: {e}")
            return {}
    
    def close_connection(self):
        """关闭数据库连接"""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            delattr(self._local, 'connection')

# 全局数据库管理器实例
db_manager = SQLiteManager() 