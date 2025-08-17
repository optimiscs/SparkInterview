"""
职面星火 - 最优数据持久化管理器
实现 SQLite + Redis + File 三层架构
"""

import os
import json
import gzip
import asyncio
import aiosqlite
import aioredis
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

class OptimalPersistenceManager:
    """最优数据持久化管理器"""
    
    def __init__(self):
        self.db_path = "data/persistence/analysis.db"
        self.redis_url = "redis://localhost:6379"
        self.backup_dir = "data/analysis_results"
        
        # 确保目录存在
        os.makedirs("data/persistence", exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        
        self.redis = None
        self._init_db_task = None
    
    async def initialize(self):
        """初始化数据库和Redis连接"""
        try:
            # 初始化SQLite数据库
            await self._init_database()
            
            # 初始化Redis连接 (兼容aioredis 1.3.1)
            try:
                # 解析Redis URL
                import urllib.parse
                parsed = urllib.parse.urlparse(self.redis_url)
                host = parsed.hostname or 'localhost'
                port = parsed.port or 6379
                db = int(parsed.path.lstrip('/')) if parsed.path and parsed.path != '/' else 0
                
                self.redis = await aioredis.create_redis_pool(
                    f'redis://{host}:{port}',
                    db=db,
                    encoding='utf-8'
                )
                await self.redis.ping()
                logger.info("✅ Redis连接成功")
            except Exception as e:
                logger.warning(f"⚠️ Redis连接失败，使用内存缓存: {e}")
                self.redis = None
            
            logger.info("✅ 持久化管理器初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 持久化管理器初始化失败: {e}")
            raise
    
    async def _init_database(self):
        """初始化SQLite数据库表结构"""
        async with aiosqlite.connect(self.db_path) as db:
            # 创建任务表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS resume_analysis_tasks (
                    task_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    file_name TEXT,
                    file_size INTEGER,
                    domain TEXT,
                    position TEXT,
                    experience TEXT,
                    status TEXT DEFAULT 'processing',
                    progress INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP NULL
                )
            """)
            
            # 创建结果表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS resume_analysis_results (
                    task_id TEXT PRIMARY KEY,
                    basic_info TEXT,
                    skills TEXT,
                    projects TEXT,
                    experience TEXT,
                    education TEXT,
                    analysis TEXT,
                    raw_content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES resume_analysis_tasks(task_id)
                )
            """)
            
            # 创建会话表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    task_ids TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """)
            
            # 创建索引
            await db.execute("CREATE INDEX IF NOT EXISTS idx_task_status ON resume_analysis_tasks(status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_task_created ON resume_analysis_tasks(created_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_session_expires ON user_sessions(expires_at)")
            
            await db.commit()
            logger.info("✅ 数据库表结构初始化完成")
    
    async def save_task(self, task_id: str, **kwargs):
        """保存任务信息"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 构建更新字段
                fields = []
                values = []
                for key, value in kwargs.items():
                    if key in ['user_id', 'file_name', 'file_size', 'domain', 'position', 'experience', 'status', 'progress']:
                        fields.append(f"{key} = ?")
                        values.append(value)
                
                if 'status' in kwargs and kwargs['status'] == 'completed':
                    fields.append("completed_at = ?")
                    values.append(datetime.now().isoformat())
                
                fields.append("updated_at = ?")
                values.append(datetime.now().isoformat())
                values.append(task_id)
                
                # 使用INSERT OR REPLACE
                await db.execute(f"""
                    INSERT OR REPLACE INTO resume_analysis_tasks 
                    (task_id, {', '.join(kwargs.keys())}, updated_at)
                    VALUES (?, {', '.join(['?'] * len(kwargs))}, ?)
                """, [task_id] + list(kwargs.values()) + [datetime.now().isoformat()])
                
                await db.commit()
                
                # 同步到Redis缓存
                if self.redis:
                    await self.redis.hset(f"task:info:{task_id}", mapping=kwargs)
                    await self.redis.expire(f"task:info:{task_id}", 3600)
                
                logger.info(f"✅ 任务信息保存成功: {task_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ 保存任务信息失败: {e}")
            return False
    
    async def save_analysis_result(self, task_id: str, result: dict):
        """三层保存分析结果"""
        try:
            # 压缩JSON数据
            compressed_result = await self._compress_data(result)
            
            # 1. 立即存入Redis缓存（最快访问）
            if self.redis:
                await self.redis.set(
                    f"task:result:{task_id}", 
                    json.dumps(result, ensure_ascii=False),
                    ex=86400  # 24小时过期
                )
                logger.info(f"✅ Redis缓存保存成功: {task_id}")
            
            # 2. 异步存入SQLite数据库（持久化）
            asyncio.create_task(self._save_to_database(task_id, result))
            
            # 3. 异步备份到文件（灾难恢复）
            asyncio.create_task(self._save_to_file(task_id, result))
            
            # 4. 更新任务状态
            await self.save_task(task_id, status='completed', progress=100)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存分析结果失败: {e}")
            return False
    
    async def _save_to_database(self, task_id: str, result: dict):
        """保存到SQLite数据库"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO resume_analysis_results 
                    (task_id, basic_info, skills, projects, experience, education, analysis, raw_content)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    task_id,
                    json.dumps(result.get('basic_info', {}), ensure_ascii=False),
                    json.dumps(result.get('skills', []), ensure_ascii=False),
                    json.dumps(result.get('projects', []), ensure_ascii=False),
                    json.dumps(result.get('experience', []), ensure_ascii=False),
                    json.dumps(result.get('education', {}), ensure_ascii=False),
                    json.dumps(result.get('analysis', {}), ensure_ascii=False),
                    result.get('raw_content', '')
                ])
                await db.commit()
                logger.info(f"✅ 数据库保存成功: {task_id}")
        except Exception as e:
            logger.error(f"❌ 数据库保存失败: {e}")
    
    async def _save_to_file(self, task_id: str, result: dict):
        """保存到文件备份"""
        try:
            file_path = os.path.join(self.backup_dir, f"{task_id}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ 文件备份成功: {file_path}")
        except Exception as e:
            logger.error(f"❌ 文件备份失败: {e}")
    
    async def get_analysis_result(self, task_id: str) -> Optional[dict]:
        """三层读取分析结果"""
        try:
            # 1. 先从Redis读取（最快）
            if self.redis:
                cached_result = await self.redis.get(f"task:result:{task_id}")
                if cached_result:
                    result = json.loads(cached_result)
                    logger.info(f"✅ 从Redis缓存获取: {task_id}")
                    return result
            
            # 2. 从SQLite数据库读取
            result = await self._get_from_database(task_id)
            if result:
                # 缓存到Redis
                if self.redis:
                    await self.redis.set(
                        f"task:result:{task_id}",
                        json.dumps(result, ensure_ascii=False),
                        ex=1800  # 30分钟过期
                    )
                logger.info(f"✅ 从数据库获取: {task_id}")
                return result
            
            # 3. 从文件备份读取（兜底）
            result = await self._get_from_file(task_id)
            if result:
                # 恢复到Redis和数据库
                if self.redis:
                    await self.redis.set(
                        f"task:result:{task_id}",
                        json.dumps(result, ensure_ascii=False),
                        ex=1800
                    )
                asyncio.create_task(self._save_to_database(task_id, result))
                logger.info(f"✅ 从文件备份恢复: {task_id}")
                return result
            
            logger.warning(f"⚠️ 未找到分析结果: {task_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ 获取分析结果失败: {e}")
            return None
    
    async def _get_from_database(self, task_id: str) -> Optional[dict]:
        """从数据库获取结果"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT basic_info, skills, projects, experience, education, analysis, raw_content
                    FROM resume_analysis_results WHERE task_id = ?
                """, [task_id]) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return {
                            'basic_info': json.loads(row[0]) if row[0] else {},
                            'skills': json.loads(row[1]) if row[1] else [],
                            'projects': json.loads(row[2]) if row[2] else [],
                            'experience': json.loads(row[3]) if row[3] else [],
                            'education': json.loads(row[4]) if row[4] else {},
                            'analysis': json.loads(row[5]) if row[5] else {},
                            'raw_content': row[6] or ''
                        }
            return None
        except Exception as e:
            logger.error(f"❌ 数据库读取失败: {e}")
            return None
    
    async def _get_from_file(self, task_id: str) -> Optional[dict]:
        """从文件备份获取结果"""
        try:
            file_path = os.path.join(self.backup_dir, f"{task_id}.json")
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"❌ 文件读取失败: {e}")
            return None
    
    async def get_task_status(self, task_id: str) -> Optional[dict]:
        """获取任务状态"""
        try:
            # 先从Redis获取
            if self.redis:
                cached_info = await self.redis.hgetall(f"task:info:{task_id}")
                if cached_info:
                    return {k.decode(): v.decode() for k, v in cached_info.items()}
            
            # 从数据库获取
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT status, progress, created_at, updated_at, completed_at
                    FROM resume_analysis_tasks WHERE task_id = ?
                """, [task_id]) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return {
                            'status': row[0],
                            'progress': row[1],
                            'created_at': row[2],
                            'updated_at': row[3],
                            'completed_at': row[4]
                        }
            return None
        except Exception as e:
            logger.error(f"❌ 获取任务状态失败: {e}")
            return None
    
    async def cleanup_expired_data(self, days: int = 7):
        """清理过期数据"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # 清理数据库
            async with aiosqlite.connect(self.db_path) as db:
                # 获取要删除的task_id
                async with db.execute("""
                    SELECT task_id FROM resume_analysis_tasks 
                    WHERE created_at < ? OR (status = 'failed' AND created_at < ?)
                """, [cutoff_date.isoformat(), (datetime.now() - timedelta(days=1)).isoformat()]) as cursor:
                    expired_tasks = await cursor.fetchall()
                
                # 删除相关数据
                await db.execute("DELETE FROM resume_analysis_results WHERE task_id IN (SELECT task_id FROM resume_analysis_tasks WHERE created_at < ?)", [cutoff_date.isoformat()])
                await db.execute("DELETE FROM resume_analysis_tasks WHERE created_at < ?", [cutoff_date.isoformat()])
                await db.commit()
                
                # 清理Redis缓存
                if self.redis and expired_tasks:
                    for task_id_tuple in expired_tasks:
                        task_id = task_id_tuple[0]
                        await self.redis.delete(f"task:result:{task_id}")
                        await self.redis.delete(f"task:info:{task_id}")
                
                # 清理文件备份
                for task_id_tuple in expired_tasks:
                    task_id = task_id_tuple[0]
                    file_path = os.path.join(self.backup_dir, f"{task_id}.json")
                    if os.path.exists(file_path):
                        os.remove(file_path)
                
                logger.info(f"✅ 清理过期数据完成，删除 {len(expired_tasks)} 个任务")
                
        except Exception as e:
            logger.error(f"❌ 清理过期数据失败: {e}")
    
    async def _compress_data(self, data: dict) -> bytes:
        """压缩数据"""
        json_str = json.dumps(data, ensure_ascii=False)
        return gzip.compress(json_str.encode('utf-8'))
    
    async def _decompress_data(self, compressed_data: bytes) -> dict:
        """解压数据"""
        json_str = gzip.decompress(compressed_data).decode('utf-8')
        return json.loads(json_str)
    
    async def get_statistics(self) -> dict:
        """获取统计信息"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 总任务数
                async with db.execute("SELECT COUNT(*) FROM resume_analysis_tasks") as cursor:
                    total_tasks = (await cursor.fetchone())[0]
                
                # 完成任务数
                async with db.execute("SELECT COUNT(*) FROM resume_analysis_tasks WHERE status = 'completed'") as cursor:
                    completed_tasks = (await cursor.fetchone())[0]
                
                # 今日任务数
                today = datetime.now().date()
                async with db.execute("SELECT COUNT(*) FROM resume_analysis_tasks WHERE DATE(created_at) = ?", [today.isoformat()]) as cursor:
                    today_tasks = (await cursor.fetchone())[0]
                
                return {
                    'total_tasks': total_tasks,
                    'completed_tasks': completed_tasks,
                    'success_rate': completed_tasks / total_tasks * 100 if total_tasks > 0 else 0,
                    'today_tasks': today_tasks
                }
        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            return {}
    
    async def close(self):
        """关闭连接"""
        if self.redis:
            await self.redis.close()

# 全局实例
persistence_manager = OptimalPersistenceManager() 