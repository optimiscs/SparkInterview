"""
简历数据访问层 (Data Access Object)
消除文件操作冗余，提供统一的数据访问接口
"""
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class ResumeDAO:
    """简历数据访问对象"""
    
    def __init__(self):
        """初始化数据目录"""
        self.resume_dir = Path("data/resumes")
        self.analysis_dir = Path("data/resume_analysis")
        self.profile_dir = Path("data/user_profiles")
        
        # 确保目录存在
        self.resume_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_dir.mkdir(parents=True, exist_ok=True)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("✅ 简历数据访问层初始化完成")
    
    # ==================== 简历CRUD操作 ====================
    
    def save_resume(self, resume_id: str, resume_data: Dict[str, Any]) -> bool:
        """保存简历数据（支持版本控制）"""
        try:
            resume_file = self.resume_dir / f"{resume_id}.json"
            
            # 添加版本控制元数据
            current_time = datetime.now().isoformat()
            resume_data["updated_at"] = current_time
            
            if "created_at" not in resume_data:
                resume_data["created_at"] = current_time
                resume_data["version"] = "v1"
                resume_data["version_history"] = []
            else:
                # 更新版本
                old_version = resume_data.get("version", "v1")
                new_version_num = int(old_version.replace("v", "")) + 1 if old_version.startswith("v") else 1
                new_version = f"v{new_version_num}"
                
                # 记录版本历史
                if "version_history" not in resume_data:
                    resume_data["version_history"] = []
                
                resume_data["version_history"].append({
                    "version": old_version,
                    "updated_at": resume_data.get("updated_at", current_time),
                    "change_summary": "简历内容更新"
                })
                
                resume_data["version"] = new_version
            
            # 添加分析状态
            if "analysis_status" not in resume_data:
                resume_data["analysis_status"] = "PROCESSING"
            
            # 生成版本ID
            resume_data["version_id"] = f"{resume_id}_{resume_data['version']}"
            
            with open(resume_file, 'w', encoding='utf-8') as f:
                json.dump(resume_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 简历已保存: {resume_id} (版本: {resume_data['version']})")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存简历失败: {resume_id} - {e}")
            return False
    
    def get_resume(self, resume_id: str) -> Optional[Dict[str, Any]]:
        """获取简历数据"""
        try:
            resume_file = self.resume_dir / f"{resume_id}.json"
            
            if not resume_file.exists():
                logger.warning(f"⚠️ 简历不存在: {resume_id}")
                return None
            
            with open(resume_file, 'r', encoding='utf-8') as f:
                resume_data = json.load(f)
            
            logger.debug(f"📖 简历读取成功: {resume_id}")
            return resume_data
            
        except Exception as e:
            logger.error(f"❌ 读取简历失败: {resume_id} - {e}")
            return None
    
    def get_resume_with_permission_check(self, resume_id: str, user_id: str) -> Dict[str, Any]:
        """获取简历并检查权限"""
        resume_data = self.get_resume(resume_id)
        
        if not resume_data:
            raise HTTPException(status_code=404, detail="简历不存在")
        
        if resume_data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="无权访问此简历")
        
        return resume_data
    
    def delete_resume(self, resume_id: str, user_id: str) -> bool:
        """删除简历"""
        try:
            # 先验证权限
            resume_data = self.get_resume_with_permission_check(resume_id, user_id)
            
            # 删除简历文件
            resume_file = self.resume_dir / f"{resume_id}.json"
            if resume_file.exists():
                resume_file.unlink()
            
            # 删除相关分析文件
            self._delete_related_analysis(resume_id)
            
            # 删除相关画像文件
            self._delete_related_profile(resume_id)
            
            logger.info(f"🗑️ 简历已删除: {resume_id}")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ 删除简历失败: {resume_id} - {e}")
            return False
    
    def list_user_resumes(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的所有简历"""
        try:
            user_resumes = []
            
            for resume_file in self.resume_dir.glob("*.json"):
                try:
                    with open(resume_file, 'r', encoding='utf-8') as f:
                        resume_data = json.load(f)
                    
                    if resume_data.get("user_id") == user_id:
                        # 只返回列表需要的字段
                        resume_summary = {
                            "id": resume_file.stem,  # 使用id字段保持一致性
                            "resume_id": resume_file.stem,  # 保留resume_id以向后兼容
                            "version_name": resume_data.get("version_name", ""),
                            "target_position": resume_data.get("target_position", ""),
                            "created_at": resume_data.get("created_at", ""),
                            "updated_at": resume_data.get("updated_at", ""),
                            "status": resume_data.get("status", "active"),
                            "has_analysis": self._has_analysis(resume_file.stem),
                            "has_profile": self._has_profile(resume_file.stem),
                            "version": resume_data.get("version", "v1"),
                            "analysis_status": resume_data.get("analysis_status", "COMPLETED")
                        }
                        user_resumes.append(resume_summary)
                        
                except Exception as e:
                    logger.warning(f"⚠️ 读取简历文件失败: {resume_file} - {e}")
                    continue
            
            # 按更新时间排序
            user_resumes.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
            
            logger.info(f"📋 用户 {user_id} 的简历列表: {len(user_resumes)} 个简历")
            return user_resumes
            
        except Exception as e:
            logger.error(f"❌ 获取用户简历列表失败: {user_id} - {e}")
            return []
    
    def get_user_latest_resume(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户最新的简历"""
        try:
            user_resumes = self.list_user_resumes(user_id)
            
            if not user_resumes:
                return None
            
            # 获取最新简历的完整数据
            latest_resume_id = user_resumes[0]["resume_id"]
            return self.get_resume(latest_resume_id)
            
        except Exception as e:
            logger.error(f"❌ 获取用户最新简历失败: {user_id} - {e}")
            return None
    
    # ==================== 分析结果操作 ====================
    
    def save_analysis(self, analysis_id: str, analysis_data: Dict[str, Any]) -> bool:
        """保存分析结果（支持版本关联）"""
        try:
            analysis_file = self.analysis_dir / f"{analysis_id}.json"
            
            # 添加元数据
            analysis_data["saved_at"] = datetime.now().isoformat()
            
            # 确保包含版本信息
            if "resume_id" in analysis_data:
                resume_data = self.get_resume(analysis_data["resume_id"])
                if resume_data:
                    analysis_data["resume_version"] = resume_data.get("version", "v1")
                    analysis_data["version_id"] = resume_data.get("version_id")
            
            with open(analysis_file, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 分析结果已保存: {analysis_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存分析结果失败: {analysis_id} - {e}")
            return False
    
    def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """获取分析结果"""
        try:
            analysis_file = self.analysis_dir / f"{analysis_id}.json"
            
            if not analysis_file.exists():
                return None
            
            with open(analysis_file, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
            
            logger.debug(f"📊 分析结果读取成功: {analysis_id}")
            return analysis_data
            
        except Exception as e:
            logger.error(f"❌ 读取分析结果失败: {analysis_id} - {e}")
            return None
    
    def get_resume_analysis(self, resume_id: str) -> Optional[Dict[str, Any]]:
        """获取简历的最新分析结果"""
        try:
            # 查找该简历相关的分析文件
            analysis_files = list(self.analysis_dir.glob(f"*{resume_id}*.json"))
            
            if not analysis_files:
                return None
            
            # 按修改时间排序，获取最新的
            analysis_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            latest_analysis_file = analysis_files[0]
            
            with open(latest_analysis_file, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
            
            logger.debug(f"📊 简历分析结果读取成功: {resume_id}")
            return analysis_data
            
        except Exception as e:
            logger.error(f"❌ 读取简历分析结果失败: {resume_id} - {e}")
            return None
    
    def delete_analysis(self, analysis_id: str) -> bool:
        """删除分析结果"""
        try:
            analysis_file = self.analysis_dir / f"{analysis_id}.json"
            
            if analysis_file.exists():
                analysis_file.unlink()
                logger.info(f"🗑️ 分析结果已删除: {analysis_id}")
                return True
            else:
                logger.warning(f"⚠️ 分析结果不存在: {analysis_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 删除分析结果失败: {analysis_id} - {e}")
            return False
    
    # ==================== 用户画像操作 ====================
    
    def save_profile(self, profile_id: str, profile_data: Dict[str, Any]) -> bool:
        """保存用户画像"""
        try:
            profile_file = self.profile_dir / f"{profile_id}.json"
            
            # 添加元数据
            profile_data["saved_at"] = datetime.now().isoformat()
            
            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 用户画像已保存: {profile_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存用户画像失败: {profile_id} - {e}")
            return False
    
    def get_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """获取用户画像"""
        try:
            profile_file = self.profile_dir / f"{profile_id}.json"
            
            if not profile_file.exists():
                return None
            
            with open(profile_file, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
            
            logger.debug(f"👤 用户画像读取成功: {profile_id}")
            return profile_data
            
        except Exception as e:
            logger.error(f"❌ 读取用户画像失败: {profile_id} - {e}")
            return None
    
    def get_resume_profile(self, resume_id: str) -> Optional[Dict[str, Any]]:
        """根据简历ID获取关联的用户画像"""
        try:
            # 方法1：从简历数据中获取profile_id
            resume_data = self.get_resume(resume_id)
            if resume_data and resume_data.get("profile_id"):
                return self.get_profile(resume_data["profile_id"])
            
            # 方法2：查找以resume_id开头的画像文件
            profile_files = list(self.profile_dir.glob(f"profile_{resume_id}_*.json"))
            
            if not profile_files:
                return None
            
            # 获取最新的画像文件
            profile_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            latest_profile_file = profile_files[0]
            
            with open(latest_profile_file, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
            
            logger.debug(f"👤 简历画像读取成功: {resume_id}")
            return profile_data
            
        except Exception as e:
            logger.error(f"❌ 读取简历画像失败: {resume_id} - {e}")
            return None
    
    # ==================== 版本控制方法 ====================
    
    def update_analysis_status(self, resume_id: str, status: str) -> bool:
        """更新简历的分析状态"""
        try:
            resume_data = self.get_resume(resume_id)
            if not resume_data:
                return False
            
            resume_data["analysis_status"] = status
            resume_data["analysis_updated_at"] = datetime.now().isoformat()
            
            return self.save_resume(resume_id, resume_data)
            
        except Exception as e:
            logger.error(f"❌ 更新分析状态失败: {resume_id} - {e}")
            return False
    
    def get_resume_by_version(self, resume_id: str, version: str) -> Optional[Dict[str, Any]]:
        """根据版本获取简历（暂时返回最新版本，未来可扩展）"""
        return self.get_resume(resume_id)
    
    def mark_jd_analysis_stale(self, resume_id: str, old_version: str) -> bool:
        """将旧版本的JD分析标记为过时"""
        try:
            analysis_files = list(self.analysis_dir.glob(f"jd_analysis_{resume_id}_*.json"))
            
            for analysis_file in analysis_files:
                with open(analysis_file, 'r', encoding='utf-8') as f:
                    analysis_data = json.load(f)
                
                # 如果是旧版本的分析，标记为过时
                if analysis_data.get("resume_version", "v1") == old_version:
                    analysis_data["status"] = "STALE"
                    analysis_data["stale_reason"] = f"简历已更新至新版本"
                    analysis_data["marked_stale_at"] = datetime.now().isoformat()
                    
                    with open(analysis_file, 'w', encoding='utf-8') as f:
                        json.dump(analysis_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ 已标记旧版本JD分析为过时: {resume_id} v{old_version}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 标记JD分析过时失败: {resume_id} - {e}")
            return False
    
    # ==================== 辅助方法 ====================
    
    def _has_analysis(self, resume_id: str) -> bool:
        """检查简历是否有分析结果"""
        try:
            analysis_files = list(self.analysis_dir.glob(f"*{resume_id}*.json"))
            return len(analysis_files) > 0
        except:
            return False
    
    def _has_profile(self, resume_id: str) -> bool:
        """检查简历是否有用户画像"""
        try:
            # 检查简历文件中的profile_id
            resume_data = self.get_resume(resume_id)
            if resume_data and resume_data.get("profile_id"):
                profile_file = self.profile_dir / f"{resume_data['profile_id']}.json"
                return profile_file.exists()
            
            # 检查以resume_id开头的画像文件
            profile_files = list(self.profile_dir.glob(f"profile_{resume_id}_*.json"))
            return len(profile_files) > 0
        except:
            return False
    
    def _delete_related_analysis(self, resume_id: str):
        """删除简历相关的分析文件"""
        try:
            analysis_files = list(self.analysis_dir.glob(f"*{resume_id}*.json"))
            for analysis_file in analysis_files:
                analysis_file.unlink()
                logger.debug(f"🗑️ 删除分析文件: {analysis_file.name}")
        except Exception as e:
            logger.warning(f"⚠️ 删除相关分析文件失败: {e}")
    
    def _delete_related_profile(self, resume_id: str):
        """删除简历相关的画像文件"""
        try:
            profile_files = list(self.profile_dir.glob(f"profile_{resume_id}_*.json"))
            for profile_file in profile_files:
                profile_file.unlink()
                logger.debug(f"🗑️ 删除画像文件: {profile_file.name}")
        except Exception as e:
            logger.warning(f"⚠️ 删除相关画像文件失败: {e}")
    
    def cleanup_temp_files(self, max_age_days: int = 7):
        """清理临时文件和过期分析结果"""
        try:
            from datetime import timedelta
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            
            cleaned_count = 0
            
            # 清理过期的分析文件
            for analysis_file in self.analysis_dir.glob("*.json"):
                try:
                    file_time = datetime.fromtimestamp(analysis_file.stat().st_mtime)
                    if file_time < cutoff_time:
                        analysis_file.unlink()
                        cleaned_count += 1
                        logger.debug(f"🧹 清理过期分析文件: {analysis_file.name}")
                except Exception as e:
                    logger.warning(f"⚠️ 清理文件失败: {analysis_file.name} - {e}")
            
            if cleaned_count > 0:
                logger.info(f"🧹 清理完成，删除了 {cleaned_count} 个过期文件")
            
        except Exception as e:
            logger.error(f"❌ 清理临时文件失败: {e}")
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        try:
            stats = {
                "resume_count": len(list(self.resume_dir.glob("*.json"))),
                "analysis_count": len(list(self.analysis_dir.glob("*.json"))),
                "profile_count": len(list(self.profile_dir.glob("*.json"))),
                "total_size_mb": 0
            }
            
            # 计算总大小
            total_size = 0
            for directory in [self.resume_dir, self.analysis_dir, self.profile_dir]:
                for file_path in directory.glob("*.json"):
                    total_size += file_path.stat().st_size
            
            stats["total_size_mb"] = round(total_size / (1024 * 1024), 2)
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ 获取存储统计失败: {e}")
            return {"error": str(e)}


# 创建全局DAO实例
_dao_instance = None

def get_resume_dao() -> ResumeDAO:
    """获取简历数据访问对象实例"""
    global _dao_instance
    
    if _dao_instance is None:
        _dao_instance = ResumeDAO()
    
    return _dao_instance
