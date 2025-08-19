"""
用户画像生成相关的Celery任务
"""
import logging
from datetime import datetime
from typing import Dict, Any

from src.celery_app import celery_app
from src.data.resume_dao import get_resume_dao

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="src.celery_tasks.profile_tasks.process_user_profile_generation")
def process_user_profile_generation(
    self,
    profile_id: str,
    resume_id: str, 
    user_id: str,
    user_name: str,
    target_position: str,
    target_field: str,
    resume_data: Dict
):
    """异步处理用户画像生成 - Celery任务版本"""
    try:
        logger.info(f"🧠 [Celery] 开始生成用户画像: {profile_id}")
        
        # 更新任务状态
        self.update_state(
            state="PROGRESS",
            meta={"status": "正在分析简历信息...", "progress": 20}
        )
        
        # 构建基础画像数据
        profile_data = {
            "profile_id": profile_id,
            "resume_id": resume_id,
            "user_id": user_id,
            "profile_data": {
                "basic_info": {
                    "name": user_name,
                    "target_position": target_position,
                    "target_field": target_field
                },
                "personalized_welcome": {
                    "greeting": f"您好 {user_name}！很高兴在今天的面试中与您相遇。我注意到您应聘的是{target_position}职位，相信您一定有很多精彩的经历要分享。让我们开始愉快的交流吧！",
                    "tone": "friendly"
                },
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "generation_mode": "celery_worker"
                }
            },
            "status": "completed",
            "created_at": datetime.now().isoformat(),
            "worker_info": {
                "task_id": self.request.id,
                "worker_hostname": self.request.hostname,
                "processed_by": "celery_worker"
            }
        }
        
        # 更新进度
        self.update_state(
            state="PROGRESS",
            meta={"status": "正在保存用户画像...", "progress": 80}
        )
        
        # 保存画像数据
        dao = get_resume_dao()
        dao.save_profile(profile_id, profile_data)
        
        logger.info(f"✅ [Celery] 用户画像生成完成: {profile_id}")
        
        return {
            "status": "completed",
            "profile_id": profile_id,
            "profile_data": profile_data["profile_data"],
            "task_id": self.request.id
        }
        
    except Exception as e:
        logger.error(f"❌ [Celery] 用户画像生成失败: {profile_id} - {e}")
        raise
