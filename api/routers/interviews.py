"""
面试系统API路由
包括面试设置、问题生成、回答处理、分析报告等功能
集成语音识别功能支持实时语音面试
"""
import uuid
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

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
from src.agents.langgraph_interview_agent import get_langgraph_agent
from src.tools.xunfei_rtasr_client import AsyncXunfeiRTASRClient
from src.tools.audio_processor import AudioProcessor, RealTimeAudioProcessor

# Celery 任务导入
from src.celery_tasks.interview_tasks import process_interview_analysis, process_interview_report


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
             description="开始多模态分析（Celery异步任务）")
async def start_analysis(
    session_id: str,
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
    
    # 创建Celery任务
    task_id = str(uuid.uuid4())
    task_status[task_id] = {
        "status": "running",
        "message": "正在进行多模态分析...",
        "created_at": datetime.now()
    }
    
    # 使用Celery启动分析任务
    celery_task = process_interview_analysis.delay(session_id, task_id)
    
    return APIResponse(
        message="分析任务已启动（Celery异步处理）",
        data={
            "task_id": task_id,
            "celery_task_id": celery_task.id
        }
    )



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
             description="生成面试评估报告（Celery异步任务）")
async def generate_report(
    session_id: str,
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
    
    # 创建Celery任务
    task_id = str(uuid.uuid4())
    task_status[task_id] = {
        "status": "running",
        "message": "正在生成报告...",
        "created_at": datetime.now()
    }
    
    # 使用Celery启动报告生成任务
    celery_task = process_interview_report.delay(session_id, task_id)
    
    return APIResponse(
        message="报告生成任务已启动（Celery异步处理）",
        data={
            "task_id": task_id,
            "celery_task_id": celery_task.id
        }
    )




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
            "difficulty": resource_metadata.get("difficulty", "beginner"),
            # 扩展字段，便于前端展示
            "image": resource_metadata.get("image", ""),
            "field": resource_metadata.get("field", ""),
            "keywords": resource_metadata.get("keywords", "")
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
            description="获取任务的执行状态（兼容本地和Celery任务）")
async def get_task_status(task_id: str):
    """获取任务状态"""
    # 首先检查本地任务状态存储
    if task_id in task_status:
        return APIResponse(
            message="任务状态获取成功",
            data=task_status[task_id]
        )
    
    # 如果本地没有，尝试作为 Celery 任务 ID 查询
    try:
        from src.celery_tasks.interview_tasks import get_interview_task_info
        task_info = get_interview_task_info(task_id)
        
        return APIResponse(
            message="Celery任务状态获取成功",
            data=task_info
        )
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"任务不存在: {str(e)}"
        )


@router.get("/celery-task-status/{celery_task_id}",
            response_model=APIResponse,
            summary="获取Celery任务状态",
            description="获取Celery异步任务的详细状态")
async def get_celery_task_status(celery_task_id: str):
    """获取Celery任务状态"""
    try:
        from src.celery_app import celery_app
        
        task_result = celery_app.AsyncResult(celery_task_id)
        
        return APIResponse(
            message="Celery任务状态获取成功",
            data={
                "task_id": celery_task_id,
                "status": task_result.status,
                "result": task_result.result,
                "info": task_result.info,
                "successful": task_result.successful(),
                "failed": task_result.failed(),
                "ready": task_result.ready(),
                "traceback": task_result.traceback if task_result.failed() else None
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取Celery任务状态失败: {str(e)}"
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


# ==================== 语音识别集成端点 ====================

# 语音会话存储
voice_interview_sessions = {}

# 讯飞配置
XUNFEI_CONFIG = {
    "app_id": "015076e9",
    "api_key": "771f2107c79630c900476ea1de65540b"
}


@router.post("/voice/setup",
             summary="设置语音面试",
             description="创建语音识别面试会话，集成LangGraph智能体")
async def setup_voice_interview(
    setup_request: InterviewSetupRequest,
    current_user: dict = Depends(get_current_user)
):
    """设置语音面试"""
    try:
        # 创建面试会话ID
        session_id = str(uuid.uuid4())
        voice_session_id = f"voice_{session_id}"
        
        # 获取LangGraph智能体
        agent = get_langgraph_agent()
        if not agent:
            raise HTTPException(
                status_code=500,
                detail="语音面试智能体初始化失败"
            )
        
        # 启动面试会话
        result = await agent.start_interview(
            user_id=current_user["id"],
            session_id=session_id,
            user_name=setup_request.user_name,
            target_position=setup_request.target_position,
            target_field=setup_request.target_field,
            resume_text=setup_request.resume_text or ""
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"面试会话创建失败: {result.get('error', '未知错误')}"
            )
        
        # 创建语音处理器
        audio_processor = RealTimeAudioProcessor()
        
        # 创建讯飞语音客户端
        voice_client = AsyncXunfeiRTASRClient(
            app_id=XUNFEI_CONFIG["app_id"],
            api_key=XUNFEI_CONFIG["api_key"]
        )
        
        # 存储语音面试会话
        voice_interview_sessions[voice_session_id] = {
            "session_id": session_id,
            "voice_session_id": voice_session_id,
            "user_id": current_user["id"],
            "agent": agent,
            "voice_client": voice_client,
            "audio_processor": audio_processor,
            "user_profile": result["user_profile"],
            "is_active": True,
            "created_at": datetime.now()
        }
        
        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "voice_session_id": voice_session_id,
            "welcome_message": result["welcome_message"],
            "user_profile": result["user_profile"],
            "interview_stage": result["interview_stage"]
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"语音面试设置失败: {str(e)}"
        )


@router.websocket("/voice/interview/{voice_session_id}")
async def voice_interview_websocket(websocket: WebSocket, voice_session_id: str):
    """语音面试WebSocket端点"""
    await websocket.accept()
    
    # 验证会话
    if voice_session_id not in voice_interview_sessions:
        await websocket.send_json({
            "type": "error",
            "message": "语音面试会话不存在"
        })
        await websocket.close()
        return
    
    session = voice_interview_sessions[voice_session_id]
    agent = session["agent"]
    voice_client = session["voice_client"]
    audio_processor = session["audio_processor"]
    
    try:
        # 连接讯飞语音服务
        await voice_client.connect()
        
        # 设置回调函数
        voice_client.add_result_callback(
            lambda text, is_final: handle_voice_result(
                websocket, session, text, is_final
            )
        )
        
        voice_client.add_error_callback(
            lambda error: handle_voice_error(websocket, error)
        )
        
        await websocket.send_json({
            "type": "connected",
            "message": "语音面试连接成功"
        })
        
        # 处理WebSocket消息
        while True:
            try:
                data = await websocket.receive()
                
                if data.get("type") == "websocket.receive":
                    if "bytes" in data:
                        # 处理音频数据
                        await handle_audio_data(websocket, session, data["bytes"])
                        
                    elif "text" in data:
                        # 处理控制消息
                        message = json.loads(data["text"])
                        await handle_voice_control(websocket, session, message)
                
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"语音面试异常: {str(e)}"
        })
    
    finally:
        # 清理资源
        await cleanup_voice_session(voice_session_id)


async def handle_audio_data(websocket: WebSocket, session: dict, audio_data: bytes):
    """处理音频数据"""
    try:
        voice_client = session["voice_client"]
        audio_processor = session["audio_processor"]
        
        # 处理音频块
        result = audio_processor.process_chunk(audio_data)
        
        if result.get("error"):
            await websocket.send_json({
                "type": "audio_error",
                "message": result["error"]
            })
            return
        
        # 发送有效的音频块到讯飞
        for chunk_data in result.get("processed_chunks", []):
            if chunk_data["has_speech"]:
                await voice_client.send_audio_data(chunk_data["data"])
        
        # 发送状态更新
        await websocket.send_json({
            "type": "audio_status",
            "has_speech": result.get("has_speech", False),
            "buffer_size": result.get("buffer_size", 0)
        })
        
    except Exception as e:
        await websocket.send_json({
            "type": "audio_error",
            "message": f"音频处理失败: {str(e)}"
        })


async def handle_voice_result(websocket: WebSocket, session: dict, text: str, is_final: bool):
    """处理语音识别结果"""
    try:
        # 发送实时识别结果
        await websocket.send_json({
            "type": "voice_result",
            "text": text,
            "is_final": is_final
        })
        
        # 如果是最终结果，发送给LangGraph智能体
        if is_final and text.strip():
            await process_voice_message(websocket, session, text)
            
    except Exception as e:
        await websocket.send_json({
            "type": "voice_error",
            "message": f"语音结果处理失败: {str(e)}"
        })


async def handle_voice_error(websocket: WebSocket, error: str):
    """处理语音识别错误"""
    await websocket.send_json({
        "type": "voice_error",
        "message": f"语音识别错误: {error}"
    })


async def handle_voice_control(websocket: WebSocket, session: dict, message: dict):
    """处理语音控制消息"""
    try:
        command = message.get("command")
        voice_client = session["voice_client"]
        
        if command == "start_recording":
            await voice_client.start_recording()
            await websocket.send_json({
                "type": "recording_status",
                "status": "recording",
                "message": "开始录音"
            })
        
        elif command == "stop_recording":
            await voice_client.stop_recording()
            
            # 获取最终文本
            final_text = voice_client.get_final_text()
            if final_text.strip():
                await process_voice_message(websocket, session, final_text)
            
            await websocket.send_json({
                "type": "recording_status",
                "status": "stopped",
                "message": "录音结束",
                "final_text": final_text
            })
        
        elif command == "end_interview":
            await end_voice_interview(websocket, session)
        
        else:
            await websocket.send_json({
                "type": "control_error",
                "message": f"未知控制命令: {command}"
            })
            
    except Exception as e:
        await websocket.send_json({
            "type": "control_error",
            "message": f"控制命令处理失败: {str(e)}"
        })


async def process_voice_message(websocket: WebSocket, session: dict, user_message: str):
    """处理语音消息，发送给LangGraph智能体"""
    try:
        agent = session["agent"]
        session_id = session["session_id"]
        user_id = session["user_id"]
        user_profile = session["user_profile"]
        
        # 发送消息给LangGraph智能体
        result = await agent.process_message(
            user_id=user_id,
            session_id=session_id,
            user_name=user_profile["basic_info"]["name"],
            target_position=user_profile["basic_info"]["target_position"],
            user_message=user_message,
            user_profile=user_profile
        )
        
        if result["success"]:
            # 更新用户档案
            session["user_profile"] = result["user_profile"]
            
            # 发送AI回复
            await websocket.send_json({
                "type": "ai_response",
                "message": result["response"],
                "user_emotion": result.get("user_emotion", "neutral"),
                "completeness_score": result.get("completeness_score", 0),
                "missing_info": result.get("missing_info", []),
                "interview_stage": result.get("interview_stage", "active")
            })
        else:
            await websocket.send_json({
                "type": "ai_error",
                "message": f"智能体处理失败: {result.get('error', '未知错误')}"
            })
        
    except Exception as e:
        await websocket.send_json({
            "type": "ai_error",
            "message": f"消息处理失败: {str(e)}"
        })


async def end_voice_interview(websocket: WebSocket, session: dict):
    """结束语音面试"""
    try:
        agent = session["agent"]
        session_id = session["session_id"]
        user_id = session["user_id"]
        user_profile = session["user_profile"]
        
        # 生成面试报告
        report_result = await agent.end_interview_and_generate_report(
            user_id=user_id,
            session_id=session_id,
            user_name=user_profile["basic_info"]["name"],
            target_position=user_profile["basic_info"]["target_position"]
        )
        
        if report_result["success"]:
            await websocket.send_json({
                "type": "interview_ended",
                "summary_message": report_result["summary_message"],
                "report_id": report_result.get("report_id"),
                "report_data": report_result.get("report_data")
            })
        else:
            await websocket.send_json({
                "type": "interview_ended",
                "summary_message": "面试已结束，感谢您的参与！",
                "error": report_result.get("error")
            })
        
        # 标记会话为非活跃
        session["is_active"] = False
        
    except Exception as e:
        await websocket.send_json({
            "type": "interview_error",
            "message": f"结束面试失败: {str(e)}"
        })


async def cleanup_voice_session(voice_session_id: str):
    """清理语音会话"""
    try:
        if voice_session_id in voice_interview_sessions:
            session = voice_interview_sessions[voice_session_id]
            
            # 断开语音客户端
            if session.get("voice_client"):
                await session["voice_client"].disconnect()
            
            # 清理会话状态
            del voice_interview_sessions[voice_session_id]
            
    except Exception as e:
        # 记录清理错误，但不抛出异常
        pass


@router.get("/voice/sessions",
            summary="获取活跃语音面试会话",
            description="获取当前用户的活跃语音面试会话列表")
async def get_voice_sessions(current_user: dict = Depends(get_current_user)):
    """获取活跃语音面试会话"""
    try:
        user_sessions = []
        
        for voice_session_id, session in voice_interview_sessions.items():
            if session["user_id"] == current_user["id"] and session["is_active"]:
                user_sessions.append({
                    "voice_session_id": voice_session_id,
                    "session_id": session["session_id"],
                    "created_at": session["created_at"],
                    "user_name": session["user_profile"]["basic_info"]["name"],
                    "target_position": session["user_profile"]["basic_info"]["target_position"]
                })
        
        return JSONResponse({
            "success": True,
            "sessions": user_sessions,
            "count": len(user_sessions)
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取语音会话失败: {str(e)}"
        )


@router.delete("/voice/sessions/{voice_session_id}",
               summary="关闭语音面试会话",
               description="手动关闭指定的语音面试会话")
async def close_voice_session(
    voice_session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """关闭语音面试会话"""
    try:
        if voice_session_id not in voice_interview_sessions:
            raise HTTPException(
                status_code=404,
                detail="语音面试会话不存在"
            )
        
        session = voice_interview_sessions[voice_session_id]
        
        # 权限检查
        if session["user_id"] != current_user["id"]:
            raise HTTPException(
                status_code=403,
                detail="无权访问此语音面试会话"
            )
        
        # 清理会话
        await cleanup_voice_session(voice_session_id)
        
        return JSONResponse({
            "success": True,
            "message": "语音面试会话已关闭"
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"关闭语音会话失败: {str(e)}"
        )


@router.get("/voice/health",
            summary="语音面试服务健康检查",
            description="检查语音识别和面试智能体服务状态")
async def voice_interview_health():
    """语音面试服务健康检查"""
    try:
        # 检查LangGraph智能体
        agent = get_langgraph_agent()
        agent_status = "healthy" if agent else "unhealthy"
        
        # 检查活跃会话数
        active_sessions = len([s for s in voice_interview_sessions.values() if s["is_active"]])
        
        # 检查讯飞配置
        xunfei_configured = bool(XUNFEI_CONFIG["app_id"] and XUNFEI_CONFIG["api_key"])
        
        return JSONResponse({
            "success": True,
            "service": "voice_interview",
            "status": "healthy" if agent_status == "healthy" and xunfei_configured else "unhealthy",
            "components": {
                "langgraph_agent": agent_status,
                "xunfei_configured": xunfei_configured,
                "active_sessions": active_sessions
            },
            "config": {
                "app_id": XUNFEI_CONFIG["app_id"],
                "api_configured": bool(XUNFEI_CONFIG["api_key"])
            }
        })
        
    except Exception as e:
        return JSONResponse({
            "success": False,
            "service": "voice_interview",
            "status": "unhealthy",
            "error": str(e)
        }) 