"""
简历分析相关的Celery任务
包括JD匹配、STAR检测、并行基础分析等
"""
import logging
from datetime import datetime
from typing import Dict, Any

from celery import current_task
from src.celery_app import celery_app
from src.data.resume_dao import get_resume_dao
from src.workflows.resume_analysis_workflow import get_resume_analysis_workflow

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="src.celery_tasks.analysis_tasks.process_jd_matching_analysis")
def process_jd_matching_analysis(self, jd_analysis_id: str, resume_id: str, resume_data: Dict, jd_content: str):
    """异步处理JD匹配分析 - Celery任务版本"""
    try:
        logger.info(f"🔍 [Celery] 开始JD匹配分析: {jd_analysis_id}")
        
        # 更新任务状态
        self.update_state(
            state="PROGRESS",
            meta={"status": "正在进行JD匹配分析...", "progress": 10}
        )
        
        # 使用工作流进行JD匹配分析
        workflow = get_resume_analysis_workflow()
        
        # 注意：这里需要同步调用，因为Celery任务本身是在独立进程中
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                workflow.analyze_jd_matching(
                    resume_id=resume_id,
                    resume_data=resume_data,
                    jd_content=jd_content,
                    analysis_id=jd_analysis_id
                )
            )
        finally:
            loop.close()
        
        # 更新进度
        self.update_state(
            state="PROGRESS", 
            meta={"status": "正在保存分析结果...", "progress": 80}
        )
        
        # 保存结果到数据库
        dao = get_resume_dao()
        if result["success"]:
            # 保存JD匹配分析结果
            analysis_data = {
                "analysis_id": jd_analysis_id,
                "resume_id": resume_id,
                "analysis_type": "jd_matching",
                "status": "completed",
                "jd_matching": result["result"],
                "timestamp": datetime.now().isoformat(),
                "worker_info": {
                    "task_id": self.request.id,
                    "worker_hostname": self.request.hostname,
                    "processed_by": "celery_worker"
                }
            }
            dao.save_analysis(jd_analysis_id, analysis_data)
            
            logger.info(f"✅ [Celery] JD匹配分析完成: {jd_analysis_id}")
            
            return {
                "status": "completed",
                "analysis_id": jd_analysis_id,
                "result": result["result"],
                "task_id": self.request.id
            }
        else:
            # 保存失败状态
            error_data = {
                "analysis_id": jd_analysis_id,
                "resume_id": resume_id,
                "analysis_type": "jd_matching",
                "status": "failed",
                "error": result.get("error", "未知错误"),
                "timestamp": datetime.now().isoformat(),
                "worker_info": {
                    "task_id": self.request.id,
                    "worker_hostname": self.request.hostname,
                    "processed_by": "celery_worker"
                }
            }
            dao.save_analysis(jd_analysis_id, error_data)
            
            logger.error(f"❌ [Celery] JD匹配分析失败: {jd_analysis_id}")
            raise Exception(f"JD匹配分析失败: {result.get('error', '未知错误')}")
        
    except Exception as e:
        logger.error(f"❌ [Celery] JD匹配分析异常: {jd_analysis_id} - {e}")
        
        # 保存异常状态
        dao = get_resume_dao()
        error_data = {
            "analysis_id": jd_analysis_id,
            "resume_id": resume_id,
            "analysis_type": "jd_matching",
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "worker_info": {
                "task_id": self.request.id,
                "worker_hostname": self.request.hostname,
                "processed_by": "celery_worker"
            }
        }
        dao.save_analysis(jd_analysis_id, error_data)
        
        # 重新抛出异常，让Celery记录任务失败
        raise

@celery_app.task(bind=True, name="src.celery_tasks.analysis_tasks.process_star_analysis")
def process_star_analysis(self, star_analysis_id: str, resume_id: str, resume_data: Dict):
    """异步处理STAR原则检测 - Celery任务版本"""
    try:
        logger.info(f"⭐ [Celery] 开始STAR原则检测: {star_analysis_id}")
        
        # 更新任务状态
        self.update_state(
            state="PROGRESS",
            meta={"status": "正在进行STAR原则检测...", "progress": 10}
        )
        
        # 使用工作流进行STAR分析
        workflow = get_resume_analysis_workflow()
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                workflow.analyze_star_principle(
                    resume_id=resume_id,
                    resume_data=resume_data,
                    analysis_id=star_analysis_id
                )
            )
        finally:
            loop.close()
        
        # 更新进度
        self.update_state(
            state="PROGRESS",
            meta={"status": "正在保存检测结果...", "progress": 80}
        )
        
        # 保存结果到数据库
        dao = get_resume_dao()
        if result["success"]:
            # 保存STAR检测结果
            analysis_data = {
                "analysis_id": star_analysis_id,
                "resume_id": resume_id,
                "analysis_type": "star_principle",
                "status": "completed",
                "star_principle": result["result"],
                "timestamp": datetime.now().isoformat(),
                "worker_info": {
                    "task_id": self.request.id,
                    "worker_hostname": self.request.hostname,
                    "processed_by": "celery_worker"
                }
            }
            dao.save_analysis(star_analysis_id, analysis_data)
            
            logger.info(f"✅ [Celery] STAR原则检测完成: {star_analysis_id}")
            
            return {
                "status": "completed",
                "analysis_id": star_analysis_id,
                "result": result["result"],
                "task_id": self.request.id
            }
        else:
            # 保存失败状态
            error_data = {
                "analysis_id": star_analysis_id,
                "resume_id": resume_id,
                "analysis_type": "star_principle",
                "status": "failed",
                "error": result.get("error", "未知错误"),
                "timestamp": datetime.now().isoformat(),
                "worker_info": {
                    "task_id": self.request.id,
                    "worker_hostname": self.request.hostname,
                    "processed_by": "celery_worker"
                }
            }
            dao.save_analysis(star_analysis_id, error_data)
            
            logger.error(f"❌ [Celery] STAR原则检测失败: {star_analysis_id}")
            raise Exception(f"STAR原则检测失败: {result.get('error', '未知错误')}")
        
    except Exception as e:
        logger.error(f"❌ [Celery] STAR原则检测异常: {star_analysis_id} - {e}")
        
        # 保存异常状态
        dao = get_resume_dao()
        error_data = {
            "analysis_id": star_analysis_id,
            "resume_id": resume_id,
            "analysis_type": "star_principle",
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "worker_info": {
                "task_id": self.request.id,
                "worker_hostname": self.request.hostname,
                "processed_by": "celery_worker"
            }
        }
        dao.save_analysis(star_analysis_id, error_data)
        
        raise

@celery_app.task(bind=True, name="src.celery_tasks.analysis_tasks.process_parallel_basic_analysis")
def process_parallel_basic_analysis(self, basic_analysis_id: str, resume_id: str, resume_data: Dict, user_data: Dict):
    """异步处理并行基础分析 - Celery任务版本"""
    try:
        logger.info(f"🚀 [Celery] 开始并行基础分析: {basic_analysis_id}")
        
        # 更新任务状态
        self.update_state(
            state="PROGRESS",
            meta={"status": "正在进行并行基础分析...", "progress": 10}
        )
        
        # 更新简历分析状态为处理中
        dao = get_resume_dao()
        dao.update_analysis_status(resume_id, "PROCESSING")
        
        # 更新进度
        self.update_state(
            state="PROGRESS",
            meta={"status": "正在执行STAR检测和用户画像生成...", "progress": 30}
        )
        
        # 使用工作流进行并行基础分析
        workflow = get_resume_analysis_workflow()
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                workflow.analyze_basic_parallel(
                    resume_id=resume_id,
                    resume_data=resume_data,
                    user_data=user_data
                )
            )
        finally:
            loop.close()
        
        # 更新进度
        self.update_state(
            state="PROGRESS",
            meta={"status": "正在保存分析结果...", "progress": 80}
        )
        
        # 保存结果到数据库
        if result["success"]:
            # 分别保存STAR分析和用户画像结果
            results = result["results"]
            
            # 保存STAR分析结果
            if results["star_analysis"]["success"]:
                star_data = {
                    "analysis_id": result.get("star_analysis_id"),
                    "resume_id": resume_id,
                    "analysis_type": "star_principle",
                    "status": "completed",
                    "star_principle": results["star_analysis"]["result"],
                    "timestamp": datetime.now().isoformat(),
                    "worker_info": {
                        "task_id": self.request.id,
                        "worker_hostname": self.request.hostname,
                        "processed_by": "celery_worker"
                    }
                }
                dao.save_analysis(result.get("star_analysis_id"), star_data)
            
            # 保存用户画像结果
            if results["user_profile"]["success"]:
                profile_data = results["user_profile"]["result"]
                profile_data["worker_info"] = {
                    "task_id": self.request.id,
                    "worker_hostname": self.request.hostname,
                    "processed_by": "celery_worker"
                }
                dao.save_profile(result.get("profile_id"), profile_data)
            
            # 更新简历分析状态为完成
            dao.update_analysis_status(resume_id, "COMPLETED")
            
            logger.info(f"✅ [Celery] 并行基础分析完成: {basic_analysis_id}")
            
            return {
                "status": "completed", 
                "basic_analysis_id": basic_analysis_id,
                "star_analysis_id": result.get("star_analysis_id"),
                "profile_id": result.get("profile_id"),
                "task_id": self.request.id
            }
        else:
            # 保存失败状态
            dao.update_analysis_status(resume_id, "FAILED")
            logger.error(f"❌ [Celery] 并行基础分析失败: {basic_analysis_id}")
            
            raise Exception(f"并行基础分析失败: {result.get('error', '未知错误')}")
        
    except Exception as e:
        logger.error(f"❌ [Celery] 并行基础分析异常: {basic_analysis_id} - {e}")
        
        # 保存异常状态
        dao = get_resume_dao()
        dao.update_analysis_status(resume_id, "FAILED")
        
        raise

# 任务状态查询辅助函数
def get_task_info(task_id: str) -> Dict[str, Any]:
    """获取Celery任务信息"""
    try:
        from celery.result import AsyncResult
        task = AsyncResult(task_id, app=celery_app)
        
        return {
            "task_id": task_id,
            "status": task.status,
            "result": task.result,
            "info": task.info,
            "ready": task.ready(),
            "successful": task.successful() if task.ready() else False,
            "failed": task.failed() if task.ready() else False
        }
    except Exception as e:
        logger.error(f"获取任务信息失败: {task_id} - {e}")
        return {
            "task_id": task_id,
            "status": "UNKNOWN",
            "error": str(e)
        }
