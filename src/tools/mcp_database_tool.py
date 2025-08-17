"""
MCP数据库工具 - 智能体专用的数据源访问工具
支持动态SQL操作和数据提取
"""
import json
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import sqlite3
import asyncio
import aiosqlite
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MCPDatabaseTool:
    """MCP数据库访问工具"""
    
    def __init__(self, db_path: str = "data/sqlite/interview_app.db"):
        self.db_path = db_path
        self._ensure_user_profile_table()
    
    def _ensure_user_profile_table(self):
        """确保用户画像表存在"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        session_id TEXT,
                        profile_data TEXT NOT NULL,
                        work_years INTEGER,
                        current_company TEXT,
                        education_level TEXT,
                        graduation_year INTEGER,
                        expected_salary TEXT,
                        technical_skills TEXT,
                        completeness_score REAL DEFAULT 0.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id 
                    ON user_profiles(user_id)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_profiles_session 
                    ON user_profiles(session_id)
                """)
                
                conn.commit()
                logger.info("✅ 用户画像表初始化完成")
                
        except Exception as e:
            logger.error(f"❌ 初始化用户画像表失败: {e}")
    
    async def insert_user_profile(self, user_id: str, session_id: str, profile_data: Dict) -> bool:
        """插入或更新用户画像数据"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 提取结构化字段
                basic_info = profile_data.get("basic_info", {})
                
                await db.execute("""
                    INSERT OR REPLACE INTO user_profiles 
                    (user_id, session_id, profile_data, work_years, current_company, 
                     education_level, graduation_year, expected_salary, technical_skills,
                     completeness_score, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    session_id,
                    json.dumps(profile_data, ensure_ascii=False),
                    basic_info.get("work_years"),
                    basic_info.get("current_company"),
                    basic_info.get("education_level"),
                    basic_info.get("graduation_year"),
                    basic_info.get("expected_salary"),
                    json.dumps(profile_data.get("technical_skills", {}), ensure_ascii=False),
                    profile_data.get("completeness_score", 0.0),
                    datetime.now().isoformat()
                ))
                
                await db.commit()
                logger.info(f"✅ 用户画像更新成功: {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ 插入用户画像失败: {e}")
            return False
    
    async def get_user_profile(self, user_id: str, session_id: str = None) -> Optional[Dict]:
        """获取用户画像数据"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if session_id:
                    cursor = await db.execute("""
                        SELECT * FROM user_profiles 
                        WHERE user_id = ? AND session_id = ?
                        ORDER BY updated_at DESC LIMIT 1
                    """, (user_id, session_id))
                else:
                    cursor = await db.execute("""
                        SELECT * FROM user_profiles 
                        WHERE user_id = ?
                        ORDER BY updated_at DESC LIMIT 1
                    """, (user_id,))
                
                row = await cursor.fetchone()
                if row:
                    # 转换为字典
                    columns = [description[0] for description in cursor.description]
                    result = dict(zip(columns, row))
                    
                    # 解析JSON字段
                    if result["profile_data"]:
                        result["profile_data"] = json.loads(result["profile_data"])
                    if result["technical_skills"]:
                        result["technical_skills"] = json.loads(result["technical_skills"])
                    
                    return result
                
                return None
                
        except Exception as e:
            logger.error(f"❌ 获取用户画像失败: {e}")
            return None
    
    async def update_specific_field(self, user_id: str, session_id: str, field: str, value: Any) -> bool:
        """更新特定字段"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 支持的直接更新字段
                direct_fields = ["work_years", "current_company", "education_level", 
                               "graduation_year", "expected_salary"]
                
                if field in direct_fields:
                    await db.execute(f"""
                        UPDATE user_profiles 
                        SET {field} = ?, updated_at = ?
                        WHERE user_id = ? AND session_id = ?
                    """, (value, datetime.now().isoformat(), user_id, session_id))
                    
                    await db.commit()
                    logger.info(f"✅ 字段 {field} 更新成功: {value}")
                    return True
                else:
                    logger.warning(f"⚠️ 不支持直接更新的字段: {field}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ 更新字段失败: {e}")
            return False
    
    async def query_missing_info_users(self, limit: int = 10) -> List[Dict]:
        """查询信息不完整的用户"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT user_id, session_id, completeness_score, 
                           work_years, current_company, education_level
                    FROM user_profiles 
                    WHERE completeness_score < 0.8
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (limit,))
                
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"❌ 查询缺失信息用户失败: {e}")
            return []
    
    async def get_completion_statistics(self) -> Dict:
        """获取用户画像完整度统计"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 总用户数
                cursor = await db.execute("SELECT COUNT(*) FROM user_profiles")
                total_users = (await cursor.fetchone())[0]
                
                # 完整度分布
                cursor = await db.execute("""
                    SELECT 
                        COUNT(CASE WHEN completeness_score >= 0.8 THEN 1 END) as high_complete,
                        COUNT(CASE WHEN completeness_score >= 0.5 AND completeness_score < 0.8 THEN 1 END) as medium_complete,
                        COUNT(CASE WHEN completeness_score < 0.5 THEN 1 END) as low_complete,
                        AVG(completeness_score) as avg_completeness
                    FROM user_profiles
                """)
                
                stats = await cursor.fetchone()
                
                return {
                    "total_users": total_users,
                    "high_complete": stats[0],
                    "medium_complete": stats[1], 
                    "low_complete": stats[2],
                    "average_completeness": round(stats[3] or 0, 2)
                }
                
        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            return {}


class MCPQueryBuilder:
    """MCP智能查询构建器"""
    
    @staticmethod
    def build_info_extraction_query(missing_fields: List[str]) -> str:
        """构建信息提取查询"""
        field_conditions = []
        
        for field in missing_fields:
            if field == "work_years":
                field_conditions.append("work_years IS NULL")
            elif field == "current_company":
                field_conditions.append("current_company IS NULL")
            elif field == "education_level":
                field_conditions.append("education_level IS NULL")
        
        if field_conditions:
            return f"""
                SELECT user_id, session_id, completeness_score
                FROM user_profiles 
                WHERE ({' OR '.join(field_conditions)})
                ORDER BY updated_at DESC
                LIMIT 20
            """
        return "SELECT * FROM user_profiles LIMIT 0"
    
    @staticmethod
    def build_user_matching_query(criteria: Dict) -> str:
        """构建用户匹配查询"""
        conditions = []
        
        if criteria.get("min_experience"):
            conditions.append(f"work_years >= {criteria['min_experience']}")
        
        if criteria.get("education_level"):
            conditions.append(f"education_level = '{criteria['education_level']}'")
        
        if criteria.get("min_completeness"):
            conditions.append(f"completeness_score >= {criteria['min_completeness']}")
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        return f"""
            SELECT user_id, work_years, education_level, completeness_score
            FROM user_profiles 
            {where_clause}
            ORDER BY completeness_score DESC, updated_at DESC
        """


class MCPIntegrationTool:
    """MCP集成工具 - 智能体使用的高级接口"""
    
    def __init__(self):
        self.db_tool = MCPDatabaseTool()
        self.query_builder = MCPQueryBuilder()
    
    async def intelligent_info_collection(self, user_id: str, session_id: str, 
                                        conversation_history: List[str]) -> Dict:
        """智能信息收集 - 从对话中提取结构化信息"""
        
        # 获取当前用户画像
        current_profile = await self.db_tool.get_user_profile(user_id, session_id)
        
        if not current_profile:
            # 如果没有画像，创建基础画像
            base_profile = {
                "basic_info": {
                    "work_years": None,
                    "current_company": None,
                    "education_level": None,
                    "graduation_year": None,
                    "expected_salary": None
                },
                "technical_skills": {},
                "completeness_score": 0.0
            }
            await self.db_tool.insert_user_profile(user_id, session_id, base_profile)
            current_profile = {"profile_data": base_profile}
        
        # 分析对话历史，提取信息
        extracted_info = self._extract_from_conversation(conversation_history)
        
        # 更新画像
        updated_profile = current_profile["profile_data"]
        has_updates = False
        
        for key, value in extracted_info.items():
            if key in updated_profile["basic_info"] and updated_profile["basic_info"][key] is None:
                updated_profile["basic_info"][key] = value
                has_updates = True
                
                # 同时更新数据库中的特定字段
                await self.db_tool.update_specific_field(user_id, session_id, key, value)
        
        if has_updates:
            # 重新计算完整度
            total_fields = len(updated_profile["basic_info"])
            filled_fields = sum(1 for v in updated_profile["basic_info"].values() if v is not None)
            updated_profile["completeness_score"] = filled_fields / total_fields
            
            # 更新完整画像
            await self.db_tool.insert_user_profile(user_id, session_id, updated_profile)
        
        return {
            "updated": has_updates,
            "extracted_info": extracted_info,
            "current_completeness": updated_profile["completeness_score"],
            "missing_fields": [k for k, v in updated_profile["basic_info"].items() if v is None]
        }
    
    def _extract_from_conversation(self, conversation: List[str]) -> Dict:
        """从对话中提取结构化信息（简化版NLP）"""
        extracted = {}
        
        # 合并所有对话内容
        full_text = " ".join(conversation).lower()
        
        # 工作年限提取
        import re
        year_patterns = [
            r'(\d+)\s*年.*?经验',
            r'工作.*?(\d+)\s*年',
            r'(\d+)\s*年.*?工作',
            r'有.*?(\d+)\s*年.*?经验'
        ]
        
        for pattern in year_patterns:
            match = re.search(pattern, full_text)
            if match:
                extracted["work_years"] = int(match.group(1))
                break
        
        # 教育水平提取
        if "博士" in full_text:
            extracted["education_level"] = "博士"
        elif "硕士" in full_text or "研究生" in full_text:
            extracted["education_level"] = "硕士"
        elif "本科" in full_text or "大学" in full_text:
            extracted["education_level"] = "本科"
        
        # 公司信息提取（简化）
        company_keywords = ["公司", "企业", "集团", "科技", "有限"]
        for keyword in company_keywords:
            if keyword in full_text:
                # 这里可以用更复杂的NER模型提取公司名
                extracted["current_company"] = f"提到了{keyword}相关的工作单位"
                break
        
        return extracted
    
    async def get_completion_strategy(self, user_id: str, session_id: str) -> Dict:
        """获取信息完善策略"""
        profile = await self.db_tool.get_user_profile(user_id, session_id)
        
        if not profile:
            return {"strategy": "collect_basic_info", "priority_fields": ["work_years", "education_level"]}
        
        basic_info = profile["profile_data"]["basic_info"]
        missing_fields = [k for k, v in basic_info.items() if v is None]
        completeness = profile.get("completeness_score", 0.0)
        
        # 根据完整度制定策略
        if completeness < 0.3:
            return {
                "strategy": "urgent_collection",
                "priority_fields": ["work_years", "education_level"],
                "message": "信息严重不足，需要立即收集基础信息"
            }
        elif completeness < 0.7:
            return {
                "strategy": "gradual_collection", 
                "priority_fields": missing_fields[:2],
                "message": "信息基本完整，可以在面试过程中自然地收集剩余信息"
            }
        else:
            return {
                "strategy": "maintain",
                "priority_fields": [],
                "message": "信息相对完整，专注于面试质量"
            }


# 创建全局实例
mcp_db_tool = MCPDatabaseTool()
mcp_integration = MCPIntegrationTool()
