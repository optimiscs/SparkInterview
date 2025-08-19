"""
Celery应用配置
解决异步分析任务阻塞主线程的问题
"""
import os
from celery import Celery

# 创建Celery应用实例
celery_app = Celery(
    "resume_analysis_worker",
    broker="redis://localhost:6379/0",  # Redis作为消息代理
    backend="redis://localhost:6379/0",  # Redis作为结果后端
    include=[
        "src.celery_tasks.analysis_tasks",  # 包含分析任务
        "src.celery_tasks.profile_tasks",   # 包含画像任务
        "src.celery_tasks.interview_tasks"  # 包含面试任务
    ]
)

# Celery配置
celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    
    # 任务路由配置
    task_routes={
        "src.celery_tasks.analysis_tasks.process_jd_matching_analysis": {"queue": "analysis"},
        "src.celery_tasks.analysis_tasks.process_star_analysis": {"queue": "analysis"}, 
        "src.celery_tasks.analysis_tasks.process_parallel_basic_analysis": {"queue": "analysis"},
        "src.celery_tasks.profile_tasks.process_user_profile_generation": {"queue": "profile"},
        "src.celery_tasks.interview_tasks.process_interview_analysis": {"queue": "interview"},
        "src.celery_tasks.interview_tasks.process_interview_report": {"queue": "interview"}
    },
    
    # 并发配置
    worker_concurrency=2,  # 每个worker进程数
    worker_prefetch_multiplier=1,  # 预取任务数
    
    # 任务过期配置
    task_soft_time_limit=300,  # 5分钟软限制
    task_time_limit=600,       # 10分钟硬限制
    
    # 结果过期时间
    result_expires=3600,  # 1小时后过期
    
    # 任务确认配置
    task_acks_late=True,
    worker_disable_rate_limits=True,
    
    # 错误处理
    task_reject_on_worker_lost=True,
    
    # 监控配置
    worker_send_task_events=True,
    task_send_sent_event=True
)

# 自动发现任务
celery_app.autodiscover_tasks([
    "src.celery_tasks.analysis_tasks",
    "src.celery_tasks.profile_tasks",
    "src.celery_tasks.interview_tasks"
])

# 日志配置
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.info("🚀 Celery应用初始化完成")

# 健康检查任务
@celery_app.task(name="src.celery_app.health_check")
def health_check():
    """Celery健康检查任务"""
    return {"status": "healthy", "message": "Celery worker正常运行"}

if __name__ == "__main__":
    celery_app.start()
