"""
职面星火 - 基于多智能体的高校生多模态模拟面试与智能评测系统
FastAPI 后端服务主入口
"""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from api.routers import users, interviews, assessments, resources, resume_parser
from api.routers import questions, chat, langgraph_chat, voice_recognition
# from api.websocket_server import websocket_endpoint  # 暂时禁用WebSocket以避免视频分析器问题
from src.config.settings import system_config


# 配置日志
logging.basicConfig(
    level=getattr(logging, system_config.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(system_config.log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("🚀 职面星火系统正在启动...")
    
    # 确保必要的目录存在
    os.makedirs("data/interviews", exist_ok=True)
    os.makedirs("data/cache", exist_ok=True)
    os.makedirs("data/chroma_db", exist_ok=True)
    os.makedirs("data/persistence", exist_ok=True)
    os.makedirs("data/analysis_results", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # 初始化最优持久化管理器
    try:
        from src.persistence.optimal_manager import persistence_manager
        await persistence_manager.initialize()
        logger.info("✅ 持久化管理器初始化完成")
    except Exception as e:
        logger.warning(f"⚠️ 持久化管理器初始化失败，使用传统方式: {e}")

    # 启动时尝试自动同步学习资源到向量库（可关闭 AUTO_INGEST_LEARNING_RESOURCES）
    try:
        AUTO = os.environ.get("AUTO_INGEST_LEARNING_RESOURCES", "true").lower() == "true"
        data_path = os.environ.get("LEARNING_RESOURCES_JSON", "data/learning_resources/learning_resources.json")
        if AUTO and os.path.exists(data_path):
            from src.tools.vector_search import create_learning_resource_manager
            import json
            lrm = create_learning_resource_manager()
            with open(data_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
                if isinstance(raw, list) and raw:
                    result = lrm.upsert_resources(raw, source="user_json_v1", version=os.environ.get("RES_VER","startup"), remove_stale=False)
                    logger.info(f"✅ 学习资源已自动同步到向量库: upsert={result['upserted']}, removed={result['removed']}")
                else:
                    logger.info("ℹ️ 学习资源文件为空，跳过同步")
        else:
            logger.info("ℹ️ 跳过自动学习资源入库(配置关闭或文件不存在)")
    except Exception as e:
        logger.warning(f"⚠️ 自动同步学习资源失败: {e}")
    
    # 初始化实时多模态分析器
    try:
        from src.tools.realtime_analyzer import create_realtime_processor
        realtime_processor = create_realtime_processor()
        logger.info("✅ 实时多模态分析器初始化完成")
    except Exception as e:
        logger.warning(f"⚠️ 实时多模态分析器初始化失败: {e}")
    
    logger.info("✅ 系统启动完成")
    
    yield
    
    # 关闭时执行
    logger.info("🛑 系统正在关闭...")
    
    # 关闭持久化管理器
    try:
        from src.persistence.optimal_manager import persistence_manager
        await persistence_manager.close()
        logger.info("✅ 持久化管理器已关闭")
    except Exception as e:
        logger.warning(f"⚠️ 关闭持久化管理器失败: {e}")


# 创建FastAPI应用实例
app = FastAPI(
    title="职面星火 - 智能面试评测系统",
    description="""
    ## 🎯 系统简介
    
    职面星火是一个基于多智能体的高校生多模态模拟面试与智能评测系统，采用讯飞星火大模型驱动，
    集成计算机视觉、语音处理和自然语言理解技术，为用户提供全方位的面试训练和能力评估服务。
    
    ## 🚀 核心功能
    
    - **智能面试模拟**: 基于LangGraph多智能体协作的动态面试对话
    - **多模态分析**: 视觉、听觉、文本三维度实时分析
    - **能力评估**: 专业知识、技能匹配、表达能力等五大维度评估
    - **个性化报告**: 生成可视化雷达图和改进建议
    - **学习路径推荐**: 基于评估结果的定制化学习资源
    
    ## 🔧 技术架构
    
    - **大模型**: 讯飞星火4.0认知大模型
    - **多智能体**: LangGraph状态驱动工作流编排
    - **多模态AI**: MediaPipe + DeepFace + Librosa
    - **向量数据库**: ChromaDB存储题库和资源
    - **可视化**: ECharts动态图表生成
    """,
    version="1.0.0",
    contact={
        "name": "职面星火开发团队",
        "email": "support@zhimianxinghuo.tech",
    },
    license_info={
        "name": "MIT License",
    },
    lifespan=lifespan
)

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册API路由
app.include_router(users.router, prefix="/api/v1", tags=["用户管理"])
app.include_router(interviews.router, prefix="/api/v1/interviews", tags=["面试系统"])
app.include_router(assessments.router, prefix="/api/v1", tags=["能力评估"])
app.include_router(resources.router, prefix="/api/v1", tags=["学习资源"])
app.include_router(resume_parser.router, prefix="/api/v1/resume", tags=["简历解析"])
app.include_router(questions.router, prefix="/api/v1", tags=["题目生成"])
app.include_router(chat.router, prefix="/api/v1", tags=["智能聊天"])
app.include_router(langgraph_chat.router, prefix="/api/v1", tags=["LangGraph智能体"])
app.include_router(voice_recognition.router, prefix="/api/v1/voice", tags=["语音识别"])

# 注册WebSocket路由 - 暂时禁用
# @app.websocket("/ws/multimodal-analysis")
# async def websocket_multimodal_analysis(websocket: WebSocket):
#     """实时多模态分析WebSocket端点"""
#     await websocket_endpoint(websocket)

# 根路径重定向到首页
@app.get("/", include_in_schema=False)
async def root():
    """重定向到前端首页"""
    return RedirectResponse(url="/index.html")

# 健康检查接口
@app.get("/health", tags=["系统监控"])
async def health_check():
    """系统健康检查"""
    return {
        "status": "healthy",
        "message": "职面星火系统运行正常",
        "version": "1.0.0"
    }

# 挂载静态文件服务（放在最后，避免覆盖API路由）
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
app.mount("/", StaticFiles(directory=".", html=True), name="root")


if __name__ == "__main__":
    import uvicorn
    
    logger.info("🔥 启动开发服务器...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["src", "api", "frontend"]
    ) 