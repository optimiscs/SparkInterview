"""
面试系统API路由
包括面试设置、问题生成、回答处理、分析报告等功能
"""
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, File, UploadFile
from fastapi.responses import FileResponse

from api.models import (
    InterviewSetupRequest, InterviewSetupResponse,
    InterviewQuestionRequest, InterviewQuestionResponse,
    InterviewAnswerRequest, InterviewAnswerResponse,
    InterviewStatusResponse, MultimodalAnalysisResponse,
    InterviewReportResponse, LearningPathResponse,
    FileUploadResponse, ResumeParseRequest, ResumeParseResponse,
    APIResponse
)
from api.routers.users import get_current_user
from src.workflow import create_interview_workflow
from src.models.state import create_initial_state, UserInfo
from src.models.spark_client import create_spark_model


router = APIRouter()

# 面试会话存储
interview_sessions = {}

# 后台任务状态存储
task_status = {}


def create_user_info(setup_request: InterviewSetupRequest) -> UserInfo:
    """创建用户信息对象"""
    return UserInfo(
        user_id=str(uuid.uuid4()),
        name=setup_request.user_name,
        target_position=setup_request.target_position,
        target_field=setup_request.target_field,
        resume_text=setup_request.resume_text or "",
        resume_summary={}
    )


@router.post("/setup",
             response_model=InterviewSetupResponse,
             summary="设置面试",
             description="配置面试参数并生成面试问题")
async def setup_interview(
    setup_request: InterviewSetupRequest,
    current_user: dict = Depends(get_current_user)
):
    """设置面试参数并生成问题"""
    try:
        # 创建面试会话ID
        session_id = str(uuid.uuid4())
        
        # 创建用户信息
        user_info = create_user_info(setup_request)
        
        # 创建初始状态
        initial_state = create_initial_state(session_id, user_info)
        
        # 创建面试工作流
        workflow = create_interview_workflow()
        
        # 执行设置阶段
        setup_state = workflow._setup_node(initial_state)
        
        if setup_state.get("errors"):
            raise HTTPException(
                status_code=500,
                detail=f"面试设置失败: {'; '.join(setup_state['errors'])}"
            )
        
        # 存储会话状态
        interview_sessions[session_id] = {
            "state": setup_state,
            "workflow": workflow,
            "created_at": datetime.now(),
            "user_id": current_user["id"]
        }
        
        # 构建响应
        questions = []
        for q in setup_state.get("questions", []):
            questions.append({
                "id": q.id,
                "text": q.text,
                "type": q.type.value,
                "difficulty": q.difficulty,
                "field": q.field,
                "expected_keywords": q.expected_keywords
            })
        
        return InterviewSetupResponse(
            session_id=session_id,
            user_info={
                "name": user_info.name,
                "target_position": user_info.target_position,
                "target_field": user_info.target_field,
                "resume_summary": user_info.resume_summary
            },
            questions=questions,
            estimated_duration=len(questions) * 3,  # 预计每题3分钟
            setup_completed=True
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"面试设置失败: {str(e)}"
        )


@router.post("/question",
             response_model=InterviewQuestionResponse,
             summary="获取面试问题",
             description="获取当前面试问题")
async def get_interview_question(
    request: InterviewQuestionRequest,
    current_user: dict = Depends(get_current_user)
):
    """获取面试问题"""
    session_id = request.session_id
    
    if session_id not in interview_sessions:
        raise HTTPException(
            status_code=404,
            detail="面试会话不存在"
        )
    
    session = interview_sessions[session_id]
    
    # 权限检查
    if session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此面试会话"
        )
    
    try:
        state = session["state"]
        workflow = session["workflow"]
        
        # 获取当前问题
        question_data = workflow.interviewer_agent.ask_question(state)
        
        return InterviewQuestionResponse(
            question=question_data["question"],
            question_id=question_data["question_id"],
            question_type=question_data["question_type"],
            expected_keywords=question_data.get("expected_keywords", []),
            is_final=question_data.get("is_final", False)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取问题失败: {str(e)}"
        )


@router.post("/answer",
             response_model=InterviewAnswerResponse,
             summary="提交面试回答",
             description="提交候选人的面试回答")
async def submit_interview_answer(
    answer_request: InterviewAnswerRequest,
    current_user: dict = Depends(get_current_user)
):
    """提交面试回答"""
    session_id = answer_request.session_id
    
    if session_id not in interview_sessions:
        raise HTTPException(
            status_code=404,
            detail="面试会话不存在"
        )
    
    session = interview_sessions[session_id]
    
    # 权限检查
    if session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此面试会话"
        )
    
    try:
        state = session["state"]
        workflow = session["workflow"]
        
        # 构建问题数据
        question_data = {
            "question": answer_request.question,
            "question_id": answer_request.question_id,
            "question_type": "behavioral",
            "expected_keywords": [],
            "is_final": False
        }
        
        # 处理回答
        result = workflow.interviewer_agent.process_answer(
            state, question_data, answer_request.answer
        )
        
        # 更新会话状态
        session["state"] = state
        
        return InterviewAnswerResponse(
            answer_recorded=result["answer_recorded"],
            follow_up_question=result.get("follow_up_question"),
            should_continue=result.get("should_continue", True),
            interview_completed=result.get("interview_completed", False)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"处理回答失败: {str(e)}"
        )


@router.get("/status/{session_id}",
            response_model=InterviewStatusResponse,
            summary="获取面试状态",
            description="获取当前面试的进度和状态")
async def get_interview_status(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取面试状态"""
    if session_id not in interview_sessions:
        raise HTTPException(
            status_code=404,
            detail="面试会话不存在"
        )
    
    session = interview_sessions[session_id]
    
    # 权限检查
    if session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此面试会话"
        )
    
    state = session["state"]
    current_index = state.get("current_question_index", 0)
    total_questions = len(state.get("questions", []))
    
    # 计算进度百分比
    progress_percentage = (current_index / total_questions * 100) if total_questions > 0 else 0
    
    # 计算已用时间
    created_at = session["created_at"]
    elapsed_time = int((datetime.now() - created_at).total_seconds())
    
    return InterviewStatusResponse(
        session_id=session_id,
        stage=state.get("stage", "setup"),
        current_question_index=current_index,
        total_questions=total_questions,
        progress_percentage=progress_percentage,
        elapsed_time=elapsed_time
    )


@router.post("/analyze/{session_id}",
             response_model=APIResponse,
             summary="开始分析",
             description="开始多模态分析（异步任务）")
async def start_analysis(
    session_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """开始多模态分析"""
    if session_id not in interview_sessions:
        raise HTTPException(
            status_code=404,
            detail="面试会话不存在"
        )
    
    session = interview_sessions[session_id]
    
    # 权限检查
    if session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此面试会话"
        )
    
    # 创建后台任务
    task_id = str(uuid.uuid4())
    task_status[task_id] = {
        "status": "running",
        "message": "正在进行多模态分析...",
        "created_at": datetime.now()
    }
    
    # 添加后台任务
    background_tasks.add_task(run_analysis_task, session_id, task_id)
    
    return APIResponse(
        message="分析任务已启动",
        data={"task_id": task_id}
    )


async def run_analysis_task(session_id: str, task_id: str):
    """运行分析任务"""
    try:
        session = interview_sessions[session_id]
        state = session["state"]
        workflow = session["workflow"]
        
        # 更新任务状态
        task_status[task_id]["message"] = "执行分析节点..."
        
        # 执行分析
        analyzed_state = workflow._analysis_node(state)
        
        # 更新会话状态
        session["state"] = analyzed_state
        
        # 更新任务状态
        task_status[task_id].update({
            "status": "completed",
            "message": "多模态分析完成",
            "completed_at": datetime.now()
        })
        
    except Exception as e:
        task_status[task_id].update({
            "status": "failed",
            "message": f"分析失败: {str(e)}",
            "completed_at": datetime.now()
        })


@router.get("/analysis/{session_id}",
            response_model=MultimodalAnalysisResponse,
            summary="获取分析结果",
            description="获取多模态分析结果")
async def get_analysis_result(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取多模态分析结果"""
    if session_id not in interview_sessions:
        raise HTTPException(
            status_code=404,
            detail="面试会话不存在"
        )
    
    session = interview_sessions[session_id]
    
    # 权限检查
    if session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此面试会话"
        )
    
    state = session["state"]
    analysis = state.get("multimodal_analysis")
    
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="分析结果不存在，请先开始分析"
        )
    
    return MultimodalAnalysisResponse(
        session_id=session_id,
        visual_analysis=analysis.visual_analysis,
        audio_analysis=analysis.audio_analysis,
        text_analysis=analysis.text_analysis,
        comprehensive_assessment=analysis.comprehensive_assessment,
        analysis_completed=True
    )


@router.post("/report/{session_id}",
             response_model=APIResponse,
             summary="生成报告",
             description="生成面试评估报告（异步任务）")
async def generate_report(
    session_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """生成面试报告"""
    if session_id not in interview_sessions:
        raise HTTPException(
            status_code=404,
            detail="面试会话不存在"
        )
    
    session = interview_sessions[session_id]
    
    # 权限检查
    if session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此面试会话"
        )
    
    # 检查是否已完成分析
    state = session["state"]
    if not state.get("multimodal_analysis"):
        raise HTTPException(
            status_code=400,
            detail="请先完成多模态分析"
        )
    
    # 创建后台任务
    task_id = str(uuid.uuid4())
    task_status[task_id] = {
        "status": "running",
        "message": "正在生成报告...",
        "created_at": datetime.now()
    }
    
    # 添加后台任务
    background_tasks.add_task(run_report_task, session_id, task_id)
    
    return APIResponse(
        message="报告生成任务已启动",
        data={"task_id": task_id}
    )


async def run_report_task(session_id: str, task_id: str):
    """运行报告生成任务"""
    try:
        session = interview_sessions[session_id]
        state = session["state"]
        workflow = session["workflow"]
        
        # 更新任务状态
        task_status[task_id]["message"] = "生成报告和学习路径..."
        
        # 执行报告生成
        report_state = workflow._report_node(state)
        
        # 执行学习路径生成
        final_state = workflow._learning_path_node(report_state)
        
        # 更新会话状态
        session["state"] = final_state
        
        # 更新任务状态
        task_status[task_id].update({
            "status": "completed",
            "message": "报告生成完成",
            "completed_at": datetime.now()
        })
        
    except Exception as e:
        task_status[task_id].update({
            "status": "failed",
            "message": f"报告生成失败: {str(e)}",
            "completed_at": datetime.now()
        })


@router.get("/report/{session_id}",
            response_model=InterviewReportResponse,
            summary="获取面试报告",
            description="获取面试评估报告")
async def get_interview_report(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取面试报告"""
    if session_id not in interview_sessions:
        raise HTTPException(
            status_code=404,
            detail="面试会话不存在"
        )
    
    session = interview_sessions[session_id]
    
    # 权限检查
    if session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此面试会话"
        )
    
    state = session["state"]
    report = state.get("interview_report")
    
    if not report:
        raise HTTPException(
            status_code=404,
            detail="报告不存在，请先生成报告"
        )
    
    return InterviewReportResponse(
        session_id=session_id,
        overall_score=report.overall_score,
        detailed_scores=report.detailed_scores,
        strengths=report.strengths,
        weaknesses=report.weaknesses,
        recommendations=report.recommendations,
        radar_chart_path=report.radar_chart_path,
        detailed_report=state.get("metadata", {}).get("detailed_report"),
        report_generated_at=datetime.now()
    )


@router.get("/learning-path/{session_id}",
            response_model=LearningPathResponse,
            summary="获取学习路径",
            description="获取个性化学习路径推荐")
async def get_learning_path(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取学习路径推荐"""
    if session_id not in interview_sessions:
        raise HTTPException(
            status_code=404,
            detail="面试会话不存在"
        )
    
    session = interview_sessions[session_id]
    
    # 权限检查
    if session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此面试会话"
        )
    
    state = session["state"]
    learning_resources = state.get("learning_resources", [])
    metadata = state.get("metadata", {})
    
    # 转换学习资源格式
    resources = []
    for resource in learning_resources:
        resource_metadata = resource.get("metadata", {})
        resources.append({
            "title": resource_metadata.get("title", ""),
            "description": resource_metadata.get("description", ""),
            "url": resource_metadata.get("url", ""),
            "type": resource_metadata.get("type", "article"),
            "competency": resource_metadata.get("competency", ""),
            "difficulty": resource_metadata.get("difficulty", "beginner")
        })
    
    return LearningPathResponse(
        session_id=session_id,
        weak_areas=metadata.get("weak_areas", []),
        learning_resources=resources,
        learning_plan=metadata.get("learning_plan"),
        estimated_study_time=len(resources) * 2  # 预计每个资源2小时
    )


@router.get("/task-status/{task_id}",
            response_model=APIResponse,
            summary="获取任务状态",
            description="获取后台任务的执行状态")
async def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id not in task_status:
        raise HTTPException(
            status_code=404,
            detail="任务不存在"
        )
    
    return APIResponse(
        message="任务状态获取成功",
        data=task_status[task_id]
    )


@router.post("/upload-resume",
             response_model=FileUploadResponse,
             summary="上传简历",
             description="上传简历文件用于解析")
async def upload_resume(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """上传简历文件"""
    # 检查文件类型
    allowed_types = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="只支持PDF和DOCX格式的简历文件"
        )
    
    # 保存文件
    import os
    os.makedirs("data/resumes", exist_ok=True)
    
    file_path = f"data/resumes/{current_user['id']}_{file.filename}"
    
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    return FileUploadResponse(
        filename=file.filename,
        file_path=file_path,
        file_size=len(content),
        upload_time=datetime.now()
    )


@router.post("/parse-resume",
             response_model=ResumeParseResponse,
             summary="解析简历",
             description="解析上传的简历文件")
async def parse_resume(
    parse_request: ResumeParseRequest,
    current_user: dict = Depends(get_current_user)
):
    """解析简历"""
    try:
        from src.tools.resume_parser import create_resume_parser_tool
        
        parser = create_resume_parser_tool()
        result = parser._run(parse_request.file_path, parse_request.extract_format)
        
        # 解析结果
        import json
        parsed_data = json.loads(result)
        
        if parsed_data.get("error"):
            return ResumeParseResponse(
                success=False,
                error=parsed_data["message"]
            )
        
        return ResumeParseResponse(
            success=True,
            data=parsed_data
        )
        
    except Exception as e:
        return ResumeParseResponse(
            success=False,
            error=f"简历解析失败: {str(e)}"
        )


@router.get("/radar-chart/{session_id}",
            response_class=FileResponse,
            summary="获取雷达图",
            description="获取能力评估雷达图文件")
async def get_radar_chart(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取雷达图文件"""
    if session_id not in interview_sessions:
        raise HTTPException(
            status_code=404,
            detail="面试会话不存在"
        )
    
    session = interview_sessions[session_id]
    
    # 权限检查
    if session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此面试会话"
        )
    
    state = session["state"]
    report = state.get("interview_report")
    
    if not report or not report.radar_chart_path:
        raise HTTPException(
            status_code=404,
            detail="雷达图不存在"
        )
    
    import os
    if not os.path.exists(report.radar_chart_path):
        raise HTTPException(
            status_code=404,
            detail="雷达图文件不存在"
        )
    
    return FileResponse(
        path=report.radar_chart_path,
        media_type='image/png',
        filename=f"radar_chart_{session_id}.png"
    )


@router.delete("/sessions/{session_id}",
               response_model=APIResponse,
               summary="删除面试会话",
               description="删除指定的面试会话数据")
async def delete_interview_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除面试会话"""
    if session_id not in interview_sessions:
        raise HTTPException(
            status_code=404,
            detail="面试会话不存在"
        )
    
    session = interview_sessions[session_id]
    
    # 权限检查
    if session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="无权访问此面试会话"
        )
    
    # 删除会话
    del interview_sessions[session_id]
    
    return APIResponse(message="面试会话已删除") 