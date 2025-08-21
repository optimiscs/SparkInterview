"""
职面星火 - 基于多智能体的高校生多模态模拟面试与智能评测系统
FastAPI 后端服务主入口 - 升级版本支持分层架构
"""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# 原有API路由 (保持兼容性)
from api.routers import users, interviews, assessments, resources, resume_parser
from api.routers import questions, chat, langgraph_chat, voice_recognition, video_analysis
# from api.websocket_server import websocket_endpoint  # 暂时禁用WebSocket以避免视频分析器问题
from src.config.settings import system_config

# 新架构组件 (可选集成)
try:
    # 尝试导入新架构的MCP和编排器
    import sys
    sys.path.append('./src')
    from src.mcp import enhanced_mcp_server
    from src.agent.orchestrator import InterviewOrchestrator
    NEW_ARCHITECTURE_AVAILABLE = True
    logger_arch = logging.getLogger(__name__)
    logger_arch.info("🏗️ 检测到新架构组件，启用增强功能")
except ImportError as e:
    NEW_ARCHITECTURE_AVAILABLE = False
    enhanced_mcp_server = None
    InterviewOrchestrator = None
    logger_arch = logging.getLogger(__name__)
    logger_arch.info(f"📦 新架构组件未找到，使用传统模式: {e}")


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
    """应用生命周期管理 - 支持新旧架构"""
    # 启动时执行
    arch_type = "增强分层架构" if NEW_ARCHITECTURE_AVAILABLE else "传统架构"
    logger.info(f"🚀 职面星火系统正在启动... (架构: {arch_type})")
    
    # 确保必要的目录存在
    directories = [
        "data/interviews", "data/cache", "data/chroma_db", "data/persistence",
        "data/analysis_results", "data/uploads", "data/resumes", "data/reports",
        "logs"
    ]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    # === 新架构初始化 (如果可用) ===
    if NEW_ARCHITECTURE_AVAILABLE:
        try:
            # 初始化增强MCP服务器
            await enhanced_mcp_server.initialize()
            logger.info("✅ 增强MCP服务器初始化完成")
            
            # 记录架构信息
            app.state.architecture_type = "layered_with_mcp"
            app.state.mcp_enabled = True
            app.state.enhanced_features = True
            
        except Exception as e:
            logger.error(f"❌ 新架构初始化失败: {e}")
            app.state.architecture_type = "traditional"
            app.state.mcp_enabled = False
            app.state.enhanced_features = False
    else:
        app.state.architecture_type = "traditional"
        app.state.mcp_enabled = False
        app.state.enhanced_features = False
    
    # === 传统组件初始化 (保持兼容) ===
    # 初始化最优持久化管理器
    try:
        from src.persistence.optimal_manager import persistence_manager
        await persistence_manager.initialize()
        logger.info("✅ 持久化管理器初始化完成")
        app.state.persistence_available = True
    except Exception as e:
        logger.warning(f"⚠️ 持久化管理器初始化失败，使用传统方式: {e}")
        app.state.persistence_available = False
    
    # 初始化实时多模态分析器
    try:
        from src.tools.realtime_analyzer import create_realtime_processor
        realtime_processor = create_realtime_processor()
        logger.info("✅ 实时多模态分析器初始化完成")
        app.state.realtime_analysis_available = True
    except Exception as e:
        logger.warning(f"⚠️ 实时多模态分析器初始化失败: {e}")
        app.state.realtime_analysis_available = False
    
    # 系统启动完成
    features = []
    if app.state.mcp_enabled:
        features.append("MCP协议")
    if app.state.enhanced_features:
        features.append("分层架构")
    if app.state.persistence_available:
        features.append("持久化管理")
    if app.state.realtime_analysis_available:
        features.append("实时分析")
    
    logger.info(f"🎉 系统启动完成! 架构: {app.state.architecture_type}")
    logger.info(f"📋 可用功能: {', '.join(features) if features else '基础功能'}")
    
    yield
    
    # 关闭时执行
    logger.info("🛑 系统正在关闭...")
    
    # 关闭新架构组件
    if NEW_ARCHITECTURE_AVAILABLE and hasattr(enhanced_mcp_server, 'close'):
        try:
            await enhanced_mcp_server.close()
            logger.info("✅ MCP服务器已关闭")
        except Exception as e:
            logger.warning(f"⚠️ 关闭MCP服务器失败: {e}")
    
    # 关闭持久化管理器
    try:
        from src.persistence.optimal_manager import persistence_manager
        await persistence_manager.close()
        logger.info("✅ 持久化管理器已关闭")
    except Exception as e:
        logger.warning(f"⚠️ 关闭持久化管理器失败: {e}")
    
    logger.info("✅ 系统已安全关闭")


# 创建FastAPI应用实例
app = FastAPI(
    title="职面星火 - 智能面试评测系统 (增强版)",
    description="""
    ## 🎯 系统简介
    
    职面星火是一个基于多智能体的高校生多模态模拟面试与智能评测系统，采用讯飞星火大模型驱动，
    集成计算机视觉、语音处理和自然语言理解技术，为用户提供全方位的面试训练和能力评估服务。
    
    ## 🏗️ 架构特性
    
    - **📦 渐进式架构**: 支持传统架构和新分层架构平滑迁移
    - **🔗 MCP协议**: Model Context Protocol标准化工具访问 (增强版)
    - **🎭 编排器模式**: 统一业务逻辑协调和状态管理 (增强版)
    - **⚡ 异步增强**: 全面async/await支持，提升并发性能
    - **🔧 配置驱动**: 动态配置管理和热更新能力
    
    ## 🚀 核心功能
    
    - **智能面试模拟**: 基于LangGraph多智能体协作的动态面试对话
    - **多模态分析**: 视觉、听觉、文本三维度实时分析 (增强版支持)
    - **能力评估**: 专业知识、技能匹配、表达能力等五大维度评估
    - **个性化报告**: 生成可视化雷达图和改进建议
    - **学习路径推荐**: 基于评估结果的定制化学习资源
    - **实时语音面试**: WebRTC音视频流处理
    
    ## 🔧 技术架构 (混合模式)
    
    ### 传统架构组件
    - **大模型**: 讯飞星火4.0认知大模型
    - **多智能体**: LangGraph状态驱动工作流编排
    - **多模态AI**: MediaPipe + DeepFace + Librosa
    - **向量数据库**: ChromaDB存储题库和资源
    - **可视化**: ECharts动态图表生成
    
    ### 增强架构组件 (可选启用)
    - **分层架构**: API → Agent → Capabilities → Tools → Clients
    - **MCP协议**: 标准化工具和资源访问接口
    - **编排器**: 统一业务流程协调
    - **增强配置**: 动态配置和监控体系
    - **性能优化**: 缓存、连接池、错误恢复
    
    ## 📋 兼容性说明
    
    - ✅ **向后兼容**: 完整保留原有API和功能
    - 🔄 **渐进升级**: 可选择性启用新架构特性
    - 📊 **双重支持**: 传统模式和增强模式并存
    - 🛡️ **平滑迁移**: 零停机时间架构升级
    """,
    version="1.5.0",  # 升级版本号
    contact={
        "name": "职面星火开发团队",
        "email": "support@zhimianxinghuo.tech",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    },
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置受信任主机中间件 (增强版)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # 生产环境应该限制具体主机
)


# === 异常处理器 (增强版) ===
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理器"""
    logger.error(f"HTTP异常: {exc.status_code} - {exc.detail} - 路径: {request.url}")
    return {
        "error": True,
        "status_code": exc.status_code,
        "message": exc.detail,
        "path": str(request.url),
        "timestamp": "2024-01-01T00:00:00Z",
        "architecture": getattr(app.state, 'architecture_type', 'unknown')
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证异常处理器"""
    logger.error(f"请求验证错误: {exc} - 路径: {request.url}")
    return {
        "error": True,
        "status_code": 422,
        "message": "请求参数验证失败",
        "details": exc.errors(),
        "path": str(request.url),
        "timestamp": "2024-01-01T00:00:00Z"
    }


@app.exception_handler(StarletteHTTPException)
async def starlette_exception_handler(request: Request, exc: StarletteHTTPException):
    """Starlette异常处理器"""
    logger.error(f"Starlette异常: {exc.status_code} - {exc.detail} - 路径: {request.url}")
    return {
        "error": True,
        "status_code": exc.status_code,
        "message": exc.detail,
        "path": str(request.url),
        "timestamp": "2024-01-01T00:00:00Z"
    }

# === API路由注册 ===
logger.info("正在注册API路由...")

# === 新架构路由 (v2) ===
if NEW_ARCHITECTURE_AVAILABLE:
    try:
        # 导入新架构路由
        from src.api.routers import interviews as interviews_v2, users as users_v2, chat as chat_v2
        from src.api.routers import resources as resources_v2, resume_parser as resume_parser_v2
        from src.api.routers import questions as questions_v2, assessments as assessments_v2
        
        # 注册v2路由（增强版）
        app.include_router(users_v2.router, prefix="/api/v2", tags=["👤 用户管理 (v2)"])
        app.include_router(interviews_v2.router, prefix="/api/v2", tags=["🎯 面试管理 (v2)"])
        app.include_router(assessments_v2.router, prefix="/api/v2", tags=["📊 评测管理 (v2)"])
        app.include_router(resources_v2.router, prefix="/api/v2", tags=["📚 资源管理 (v2)"])
        app.include_router(resume_parser_v2.router, prefix="/api/v2", tags=["📄 简历解析 (v2)"])
        app.include_router(questions_v2.router, prefix="/api/v2", tags=["❓ 题库管理 (v2)"])
        app.include_router(chat_v2.router, prefix="/api/v2", tags=["💬 智能对话 (v2)"])
        
        logger.info("新架构路由 (v2) 已成功注册")
    except ImportError as e:
        logger.warning(f"无法加载新架构路由: {e}")

# === 传统路由 (v1) - 向后兼容 ===
# 注册旧版路由
app.include_router(users.router, prefix="/api/v1", tags=["👤 用户管理 (v1)"])
app.include_router(interviews.router, prefix="/api/v1/interviews", tags=["🎯 面试系统 (v1)"])
app.include_router(assessments.router, prefix="/api/v1", tags=["📊 能力评估 (v1)"])
app.include_router(resources.router, prefix="/api/v1", tags=["📚 学习资源 (v1)"])
app.include_router(resume_parser.router, prefix="/api/v1/resume", tags=["📄 简历解析 (v1)"])
app.include_router(questions.router, prefix="/api/v1", tags=["❓ 题目生成 (v1)"])
app.include_router(chat.router, prefix="/api/v1", tags=["💬 智能聊天 (v1)"])
app.include_router(langgraph_chat.router, prefix="/api/v1", tags=["💬 LangGraph智能体 (v1)"])
app.include_router(voice_recognition.router, prefix="/api/v1/voice", tags=["🎤 语音识别 (v1)"])
app.include_router(video_analysis.router, prefix="/api/v1/video", tags=["📹 视频分析 (v1)"])

logger.info("传统架构路由 (v1) 已注册完成")

# === API版本信息端点 ===
@app.get("/api", tags=["📋 API信息"])
async def api_versions():
    """API版本信息和架构状态"""
    return {
        "system": "职面星火智能面试系统",
        "version": "1.5.0",
        "api_versions": {
            "v1": {
                "description": "传统API版本",
                "status": "stable",
                "base_url": "/api/v1",
                "features": ["基础功能", "向后兼容", "直接调用"]
            },
            "v2": {
                "description": "增强API版本",
                "status": "available" if NEW_ARCHITECTURE_AVAILABLE else "unavailable",
                "base_url": "/api/v2",
                "features": ["分层架构", "MCP协议", "编排器模式", "异步增强"] if NEW_ARCHITECTURE_AVAILABLE else []
            }
        },
        "current_architecture": getattr(app.state, 'architecture_type', 'traditional'),
        "features": {
            "mcp_enabled": getattr(app.state, 'mcp_enabled', False),
            "enhanced_features": getattr(app.state, 'enhanced_features', False),
            "new_architecture": NEW_ARCHITECTURE_AVAILABLE
        },
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        },
        "endpoints": {
            "health": "/health",
            "architecture": "/api/v1/architecture",
            "mcp_tools": "/api/v1/mcp/tools" if NEW_ARCHITECTURE_AVAILABLE else None,
            "mcp_resources": "/api/v1/mcp/resources" if NEW_ARCHITECTURE_AVAILABLE else None
        }
    }

# 注册WebSocket路由 - 暂时禁用
# @app.websocket("/ws/multimodal-analysis")
# async def websocket_multimodal_analysis(websocket: WebSocket):
#     """实时多模态分析WebSocket端点"""
#     await websocket_endpoint(websocket)

# === 系统端点 ===
# 根路径重定向
@app.get("/", include_in_schema=False)
async def root():
    """根路径重定向"""
    # 如果有新架构，重定向到API文档，否则重定向到首页
    if NEW_ARCHITECTURE_AVAILABLE:
        return RedirectResponse(url="/docs")
    else:
        return RedirectResponse(url="/index.html")

# 增强健康检查接口
@app.get("/health", tags=["🔍 系统监控"])
async def health_check():
    """系统健康检查 - 支持架构状态"""
    try:
        # 基础状态
        health_info = {
            "status": "healthy",
            "message": "职面星火系统运行正常",
            "version": "1.5.0",
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        # 架构信息
        if hasattr(app.state, 'architecture_type'):
            health_info.update({
                "architecture": {
                    "type": app.state.architecture_type,
                    "mcp_enabled": getattr(app.state, 'mcp_enabled', False),
                    "enhanced_features": getattr(app.state, 'enhanced_features', False)
                },
                "services": {
                    "persistence": getattr(app.state, 'persistence_available', False),
                    "realtime_analysis": getattr(app.state, 'realtime_analysis_available', False),
                    "mcp_server": getattr(app.state, 'mcp_enabled', False)
                }
            })
            
            # 功能特性
            features = ["传统API"]
            if app.state.mcp_enabled:
                features.append("MCP协议")
            if app.state.enhanced_features:
                features.append("分层架构")
            if getattr(app.state, 'persistence_available', False):
                features.append("持久化管理")
            if getattr(app.state, 'realtime_analysis_available', False):
                features.append("实时分析")
            
            health_info["features"] = features
        else:
            health_info.update({
                "architecture": {"type": "initializing"},
                "features": ["传统API"]
            })
        
        return health_info
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "version": "1.5.0",
            "timestamp": "2024-01-01T00:00:00Z"
        }


# === MCP协议端点 (增强版) ===
if NEW_ARCHITECTURE_AVAILABLE:
    @app.get("/api/v1/mcp/tools", tags=["🔧 MCP协议"])
    async def list_mcp_tools():
        """列出所有可用的MCP工具"""
        try:
            result = await enhanced_mcp_server.handle_request("tools/list", {})
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取MCP工具失败: {str(e)}")

    @app.post("/api/v1/mcp/tools/call", tags=["🔧 MCP协议"])
    async def call_mcp_tool(request: dict):
        """调用MCP工具"""
        try:
            result = await enhanced_mcp_server.handle_request("tools/call", request)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"调用MCP工具失败: {str(e)}")

    @app.get("/api/v1/mcp/resources", tags=["🔧 MCP协议"])
    async def list_mcp_resources():
        """列出所有可用的MCP资源"""
        try:
            result = await enhanced_mcp_server.handle_request("resources/list", {})
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取MCP资源失败: {str(e)}")

    @app.get("/api/v1/mcp/server/stats", tags=["🔧 MCP协议"])
    async def get_mcp_server_stats():
        """获取MCP服务器统计信息"""
        try:
            result = await enhanced_mcp_server.handle_request("server/stats", {})
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取MCP统计失败: {str(e)}")


# 架构信息端点
@app.get("/api/v1/architecture", tags=["🏗️ 系统架构"])
async def get_architecture_info():
    """获取系统架构信息"""
    architecture_info = {
        "system_name": "职面星火智能面试系统",
        "version": "1.5.0",
        "architecture_type": getattr(app.state, 'architecture_type', 'traditional'),
        "features_available": {
            "new_architecture": NEW_ARCHITECTURE_AVAILABLE,
            "mcp_protocol": getattr(app.state, 'mcp_enabled', False),
            "enhanced_features": getattr(app.state, 'enhanced_features', False),
            "persistence_manager": getattr(app.state, 'persistence_available', False),
            "realtime_analysis": getattr(app.state, 'realtime_analysis_available', False)
        }
    }
    
    if NEW_ARCHITECTURE_AVAILABLE:
        architecture_info.update({
            "layers": {
                "api_layer": {
                    "description": "HTTP接口层，处理请求响应",
                    "status": "active",
                    "routes": ["传统API", "增强API"]
                },
                "orchestration_layer": {
                    "description": "编排层，协调业务逻辑",
                    "status": "available" if getattr(app.state, 'enhanced_features', False) else "disabled",
                    "components": ["InterviewOrchestrator", "工作流管理"]
                },
                "capability_layer": {
                    "description": "能力层，提供AI推理和分析",
                    "status": "available" if getattr(app.state, 'enhanced_features', False) else "disabled",
                    "components": ["推理模块", "多模态分析"]
                },
                "tool_layer": {
                    "description": "工具层，提供辅助功能",
                    "status": "available" if getattr(app.state, 'enhanced_features', False) else "disabled",
                    "components": ["资源检索", "数据处理"]
                },
                "client_layer": {
                    "description": "客户端层，封装外部服务",
                    "status": "active",
                    "components": ["讯飞星火客户端", "数据库连接"]
                }
            },
            "communication_protocols": {
                "mcp": {
                    "description": "Model Context Protocol",
                    "enabled": getattr(app.state, 'mcp_enabled', False),
                    "features": ["工具注册", "资源管理", "标准化接口"]
                },
                "traditional": {
                    "description": "传统直接调用",
                    "enabled": True,
                    "features": ["向后兼容", "直接API调用"]
                }
            }
        })
    else:
        architecture_info.update({
            "layers": {
                "api_layer": {"description": "HTTP接口层", "status": "active"},
                "business_layer": {"description": "业务逻辑层", "status": "active"},
                "data_layer": {"description": "数据访问层", "status": "active"}
            },
            "note": "运行在传统架构模式，新架构组件未检测到"
        })
    
    return architecture_info

# 挂载静态文件服务（放在最后，避免覆盖API路由）
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
app.mount("/", StaticFiles(directory=".", html=True), name="root")


if __name__ == "__main__":
    import uvicorn
    
    # 打印启动信息
    logger.info("🔥 启动职面星火智能面试系统...")
    logger.info(f"架构类型: {getattr(app.state, 'architecture_type', '初始化中')}")
    logger.info(f"新架构可用: {NEW_ARCHITECTURE_AVAILABLE}")
    
    # 启动参数
    uvicorn_config = {
        "app": "main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "reload": True,
        "reload_dirs": ["api", "frontend"] + (["src"] if NEW_ARCHITECTURE_AVAILABLE else []),
        "log_level": "info"
    }
    
    logger.info(f"服务器启动配置: {uvicorn_config}")
    uvicorn.run(**uvicorn_config) 