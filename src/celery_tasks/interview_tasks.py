"""
面试系统相关的Celery任务
包括多模态分析、报告生成等异步任务
"""
import logging
from datetime import datetime
from typing import Dict, Any

from celery import current_task
from src.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="src.celery_tasks.interview_tasks.process_interview_analysis")
def process_interview_analysis(self, session_id: str, task_id: str):
    """异步处理面试分析任务 - Celery版本"""
    try:
        logger.info(f"🔍 [Celery] 开始面试分析: session_id={session_id}, task_id={task_id}")
        
        # 更新任务状态
        self.update_state(
            state="PROGRESS",
            meta={"status": "正在进行多模态分析...", "progress": 10, "task_id": task_id}
        )
        
        # 导入面试会话存储（需要在这里导入以避免循环依赖）
        from api.routers.interviews import interview_sessions, task_status
        
        if session_id not in interview_sessions:
            raise Exception(f"面试会话不存在: {session_id}")
        
        session = interview_sessions[session_id]
        state = session["state"]
        workflow = session["workflow"]
        
        # 更新任务状态（使用全局状态存储）
        if task_id in task_status:
            task_status[task_id]["message"] = "执行分析节点..."
        
        # 更新Celery任务状态
        self.update_state(
            state="PROGRESS",
            meta={"status": "执行分析节点...", "progress": 50, "task_id": task_id}
        )
        
        # 执行分析
        analyzed_state = workflow._analysis_node(state)
        
        # 更新会话状态
        session["state"] = analyzed_state
        
        # 更新任务状态
        if task_id in task_status:
            task_status[task_id].update({
                "status": "completed",
                "message": "多模态分析完成",
                "completed_at": datetime.now()
            })
        
        # 更新Celery任务状态
        self.update_state(
            state="SUCCESS",
            meta={
                "status": "多模态分析完成", 
                "progress": 100,
                "task_id": task_id,
                "completed_at": datetime.now().isoformat()
            }
        )
        
        logger.info(f"✅ [Celery] 面试分析完成: session_id={session_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "task_id": task_id,
            "message": "多模态分析完成",
            "completed_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ [Celery] 面试分析失败: session_id={session_id}, 错误: {e}")
        
        # 导入面试会话存储
        try:
            from api.routers.interviews import task_status
            if task_id in task_status:
                task_status[task_id].update({
                    "status": "failed",
                    "message": f"分析失败: {str(e)}",
                    "completed_at": datetime.now()
                })
        except:
            pass
        
        # 更新Celery任务状态
        self.update_state(
            state="FAILURE",
            meta={
                "status": f"分析失败: {str(e)}", 
                "progress": 0,
                "task_id": task_id,
                "error": str(e),
                "completed_at": datetime.now().isoformat()
            }
        )
        
        raise


@celery_app.task(bind=True, name="src.celery_tasks.interview_tasks.process_interview_report")
def process_interview_report(self, session_id: str, task_id: str):
    """异步处理面试报告生成任务 - Celery版本"""
    try:
        logger.info(f"📊 [Celery] 开始生成面试报告: session_id={session_id}, task_id={task_id}")
        
        # 更新任务状态
        self.update_state(
            state="PROGRESS",
            meta={"status": "正在生成报告...", "progress": 10, "task_id": task_id}
        )
        
        # 导入面试会话存储（需要在这里导入以避免循环依赖）
        from api.routers.interviews import interview_sessions, task_status
        
        if session_id not in interview_sessions:
            raise Exception(f"面试会话不存在: {session_id}")
        
        session = interview_sessions[session_id]
        state = session["state"]
        workflow = session["workflow"]
        
        # 检查是否已完成分析
        if not state.get("multimodal_analysis"):
            raise Exception("请先完成多模态分析")
        
        # 更新任务状态（使用全局状态存储）
        if task_id in task_status:
            task_status[task_id]["message"] = "生成报告和学习路径..."
        
        # 更新Celery任务状态
        self.update_state(
            state="PROGRESS",
            meta={"status": "生成报告和学习路径...", "progress": 30, "task_id": task_id}
        )
        
        # 执行报告生成
        report_state = workflow._report_node(state)
        
        # 更新Celery任务状态
        self.update_state(
            state="PROGRESS",
            meta={"status": "生成学习路径...", "progress": 70, "task_id": task_id}
        )
        
        # 执行学习路径生成
        final_state = workflow._learning_path_node(report_state)
        
        # 更新会话状态
        session["state"] = final_state
        
        # 更新任务状态
        if task_id in task_status:
            task_status[task_id].update({
                "status": "completed",
                "message": "报告生成完成",
                "completed_at": datetime.now()
            })
        
        # 更新Celery任务状态
        self.update_state(
            state="SUCCESS",
            meta={
                "status": "报告生成完成", 
                "progress": 100,
                "task_id": task_id,
                "completed_at": datetime.now().isoformat()
            }
        )
        
        logger.info(f"✅ [Celery] 面试报告生成完成: session_id={session_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "task_id": task_id,
            "message": "报告生成完成",
            "completed_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ [Celery] 面试报告生成失败: session_id={session_id}, 错误: {e}")
        
        # 导入面试会话存储
        try:
            from api.routers.interviews import task_status
            if task_id in task_status:
                task_status[task_id].update({
                    "status": "failed",
                    "message": f"报告生成失败: {str(e)}",
                    "completed_at": datetime.now()
                })
        except:
            pass
        
        # 更新Celery任务状态
        self.update_state(
            state="FAILURE",
            meta={
                "status": f"报告生成失败: {str(e)}", 
                "progress": 0,
                "task_id": task_id,
                "error": str(e),
                "completed_at": datetime.now().isoformat()
            }
        )
        
        raise


@celery_app.task(bind=True, name="src.celery_tasks.interview_tasks.get_interview_task_info")
def get_interview_task_info(task_id: str):
    """获取面试任务信息"""
    try:
        task_result = celery_app.AsyncResult(task_id)
        
        return {
            "task_id": task_id,
            "status": task_result.status,
            "result": task_result.result,
            "info": task_result.info,
            "successful": task_result.successful(),
            "failed": task_result.failed(),
            "ready": task_result.ready()
        }
        
    except Exception as e:
        logger.error(f"❌ 获取面试任务信息失败: task_id={task_id}, 错误: {e}")
        return {
            "task_id": task_id,
            "status": "UNKNOWN",
            "error": str(e)
        }
