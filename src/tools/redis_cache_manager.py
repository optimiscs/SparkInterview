"""
Redis缓存管理器 - 用于面试会话状态管理
提供简单高效的会话状态缓存功能
"""
import redis
import json
import logging
import os
from typing import Dict, Any, Optional
from datetime import timedelta

logger = logging.getLogger(__name__)


class RedisCacheManager:
    """Redis缓存管理器 - 专门用于面试会话状态管理"""
    
    def __init__(self, host: str = None, port: int = None, db: int = None):
        """初始化Redis连接"""
        self.host = host or os.getenv('REDIS_HOST', 'localhost')
        self.port = port or int(os.getenv('REDIS_PORT', 6379))
        self.db = db or int(os.getenv('REDIS_DB', 0))
        
        # 连接配置
        self.redis_client = None
        self.connected = False
        
        # 默认过期时间配置
        self.DEFAULT_SESSION_TTL = timedelta(hours=4)  # 会话状态4小时过期
        self.DEFAULT_INTERVIEW_TTL = timedelta(hours=8)  # 面试数据8小时过期
        
        # 键前缀配置
        self.SESSION_PREFIX = "interview:session:"
        self.STAGE_PREFIX = "interview:stage:"
        
        self._init_connection()
    
    def _init_connection(self):
        """初始化Redis连接"""
        try:
            # 创建Redis连接池
            pool = redis.ConnectionPool(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=True,  # 自动解码为字符串
                max_connections=20,     # 连接池大小
                health_check_interval=30  # 健康检查间隔
            )
            
            self.redis_client = redis.Redis(connection_pool=pool)
            
            # 测试连接
            self.redis_client.ping()
            self.connected = True
            logger.info(f"✅ Redis连接成功: {self.host}:{self.port}/{self.db}")
            
        except redis.ConnectionError:
            logger.warning(f"⚠️ Redis连接失败: {self.host}:{self.port} - 将使用内存缓存降级")
            self.connected = False
            self._init_fallback_cache()
        except Exception as e:
            logger.error(f"❌ Redis初始化异常: {e}")
            self.connected = False
            self._init_fallback_cache()
    
    def _init_fallback_cache(self):
        """初始化内存降级缓存"""
        self._fallback_cache = {}
        logger.info("🔄 启用内存缓存降级模式")
    
    def _get_session_key(self, session_id: str) -> str:
        """生成会话状态键"""
        return f"{self.SESSION_PREFIX}{session_id}"
    
    def _get_stage_key(self, session_id: str) -> str:
        """生成面试阶段键"""
        return f"{self.STAGE_PREFIX}{session_id}"
    
    # ==================== 面试阶段状态管理 ====================
    
    def set_interview_stage(self, session_id: str, formal_started: bool, ttl: timedelta = None) -> bool:
        """设置面试阶段状态"""
        try:
            key = self._get_stage_key(session_id)
            stage_data = {
                "formal_interview_started": formal_started,
                "session_id": session_id
            }
            
            if self.connected:
                # 使用Redis
                ttl_seconds = int((ttl or self.DEFAULT_SESSION_TTL).total_seconds())
                result = self.redis_client.setex(
                    key, 
                    ttl_seconds, 
                    json.dumps(stage_data)
                )
                
                logger.info(f"💾 Redis面试阶段状态: {session_id} -> {formal_started} (TTL: {ttl_seconds}s)")
                return bool(result)
            else:
                # 降级到内存缓存
                self._fallback_cache[key] = stage_data
                logger.info(f"💾 内存面试阶段状态: {session_id} -> {formal_started}")
                return True
                
        except Exception as e:
            logger.error(f"❌ 设置面试阶段状态失败: {e}")
            return False
    
    def get_interview_stage(self, session_id: str) -> bool:
        """获取面试阶段状态"""
        try:
            key = self._get_stage_key(session_id)
            
            if self.connected:
                # 从Redis获取
                data = self.redis_client.get(key)
                if data:
                    stage_data = json.loads(data)
                    formal_started = stage_data.get("formal_interview_started", False)
                    logger.info(f"🔍 Redis获取面试阶段: {session_id} -> {formal_started}")
                    return formal_started
            else:
                # 从内存缓存获取
                data = self._fallback_cache.get(key)
                if data:
                    formal_started = data.get("formal_interview_started", False)
                    logger.info(f"🔍 内存获取面试阶段: {session_id} -> {formal_started}")
                    return formal_started
            
            # 默认值：未开始正式面试
            logger.info(f"🔍 面试阶段状态不存在: {session_id} -> False")
            return False
            
        except Exception as e:
            logger.error(f"❌ 获取面试阶段状态失败: {e}")
            return False
    
    def clear_interview_stage(self, session_id: str) -> bool:
        """清理面试阶段状态"""
        try:
            key = self._get_stage_key(session_id)
            
            if self.connected:
                # 从Redis删除
                result = self.redis_client.delete(key)
                logger.info(f"🧹 Redis清理面试阶段: {session_id}")
                return bool(result)
            else:
                # 从内存缓存删除
                if key in self._fallback_cache:
                    del self._fallback_cache[key]
                    logger.info(f"🧹 内存清理面试阶段: {session_id}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"❌ 清理面试阶段状态失败: {e}")
            return False
    
    # ==================== 会话数据管理 ====================
    
    def set_session_data(self, session_id: str, data: Dict[str, Any], ttl: timedelta = None) -> bool:
        """设置会话数据"""
        try:
            key = self._get_session_key(session_id)
            
            if self.connected:
                # 使用Redis
                ttl_seconds = int((ttl or self.DEFAULT_INTERVIEW_TTL).total_seconds())
                result = self.redis_client.setex(
                    key, 
                    ttl_seconds, 
                    json.dumps(data, ensure_ascii=False)
                )
                logger.info(f"💾 Redis会话数据: {session_id} (TTL: {ttl_seconds}s)")
                return bool(result)
            else:
                # 降级到内存缓存
                self._fallback_cache[key] = data
                logger.info(f"💾 内存会话数据: {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ 设置会话数据失败: {e}")
            return False
    
    def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话数据"""
        try:
            key = self._get_session_key(session_id)
            
            if self.connected:
                # 从Redis获取
                data = self.redis_client.get(key)
                if data:
                    return json.loads(data)
            else:
                # 从内存缓存获取
                return self._fallback_cache.get(key)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 获取会话数据失败: {e}")
            return None
    
    def clear_session_data(self, session_id: str) -> bool:
        """清理会话数据"""
        try:
            key = self._get_session_key(session_id)
            
            if self.connected:
                # 从Redis删除
                result = self.redis_client.delete(key)
                logger.info(f"🧹 Redis清理会话: {session_id}")
                return bool(result)
            else:
                # 从内存缓存删除
                if key in self._fallback_cache:
                    del self._fallback_cache[key]
                    logger.info(f"🧹 内存清理会话: {session_id}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"❌ 清理会话数据失败: {e}")
            return False
    
    # ==================== 工具方法 ====================
    
    def extend_session_ttl(self, session_id: str, ttl: timedelta = None) -> bool:
        """延长会话TTL"""
        try:
            if not self.connected:
                return True  # 内存缓存无需TTL管理
            
            stage_key = self._get_stage_key(session_id)
            session_key = self._get_session_key(session_id)
            ttl_seconds = int((ttl or self.DEFAULT_SESSION_TTL).total_seconds())
            
            # 延长面试阶段状态TTL
            self.redis_client.expire(stage_key, ttl_seconds)
            # 延长会话数据TTL
            self.redis_client.expire(session_key, ttl_seconds)
            
            logger.info(f"⏰ 延长会话TTL: {session_id} -> {ttl_seconds}s")
            return True
            
        except Exception as e:
            logger.error(f"❌ 延长会话TTL失败: {e}")
            return False
    
    def get_session_count(self) -> int:
        """获取当前会话数量"""
        try:
            if self.connected:
                # Redis模式：统计键数量
                pattern = f"{self.STAGE_PREFIX}*"
                keys = self.redis_client.keys(pattern)
                return len(keys)
            else:
                # 内存模式：统计内存中的键数量
                stage_keys = [k for k in self._fallback_cache.keys() if k.startswith(self.STAGE_PREFIX)]
                return len(stage_keys)
                
        except Exception as e:
            logger.error(f"❌ 获取会话数量失败: {e}")
            return 0
    
    def is_connected(self) -> bool:
        """检查Redis连接状态"""
        return self.connected
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            if self.connected:
                # Redis健康检查
                ping_result = self.redis_client.ping()
                session_count = self.get_session_count()
                
                return {
                    "status": "healthy",
                    "backend": "redis",
                    "host": f"{self.host}:{self.port}",
                    "ping": ping_result,
                    "active_sessions": session_count
                }
            else:
                # 内存模式健康检查
                session_count = self.get_session_count()
                
                return {
                    "status": "fallback",
                    "backend": "memory",
                    "active_sessions": session_count,
                    "warning": "Redis不可用，使用内存缓存"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }


# 创建全局缓存管理器实例
_cache_manager = None

def get_cache_manager() -> RedisCacheManager:
    """获取全局缓存管理器实例"""
    global _cache_manager
    
    if _cache_manager is None:
        _cache_manager = RedisCacheManager()
        logger.info("✅ 创建全局Redis缓存管理器")
    
    return _cache_manager


# 便捷函数
def set_interview_stage(session_id: str, formal_started: bool) -> bool:
    """设置面试阶段状态"""
    return get_cache_manager().set_interview_stage(session_id, formal_started)

def get_interview_stage(session_id: str) -> bool:
    """获取面试阶段状态"""
    return get_cache_manager().get_interview_stage(session_id)

def clear_session_cache(session_id: str) -> bool:
    """清理会话缓存"""
    cache_manager = get_cache_manager()
    result1 = cache_manager.clear_interview_stage(session_id)
    result2 = cache_manager.clear_session_data(session_id)
    return result1 or result2
