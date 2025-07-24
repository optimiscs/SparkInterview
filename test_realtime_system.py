#!/usr/bin/env python3
"""
实时多模态分析系统独立测试
"""
import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 创建简化的FastAPI应用
app = FastAPI(
    title="实时多模态分析测试",
    description="测试实时多模态分析功能",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 导入WebSocket处理器
try:
    from api.websocket_server import websocket_endpoint
    websocket_available = True
    print("✅ WebSocket服务器导入成功")
except Exception as e:
    print(f"❌ WebSocket服务器导入失败: {e}")
    websocket_available = False

# 注册WebSocket路由
if websocket_available:
    @app.websocket("/ws/multimodal-analysis")
    async def websocket_multimodal_analysis(websocket: WebSocket):
        """实时多模态分析WebSocket端点"""
        await websocket_endpoint(websocket)
else:
    @app.websocket("/ws/multimodal-analysis")
    async def websocket_multimodal_analysis_fallback(websocket: WebSocket):
        """备用WebSocket端点"""
        await websocket.accept()
        await websocket.send_text('{"type": "error", "data": "WebSocket服务不可用"}')
        await websocket.close()

# 健康检查
@app.get("/health")
async def health_check():
    """系统健康检查"""
    return {
        "status": "healthy",
        "websocket_available": websocket_available,
        "message": "实时多模态分析系统运行正常"
    }

# 静态文件服务
try:
    app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
    app.mount("/", StaticFiles(directory=".", html=True), name="root")
    print("✅ 静态文件服务已配置")
except Exception as e:
    print(f"⚠️ 静态文件服务配置失败: {e}")

# 根路径
@app.get("/")
async def root():
    """根路径"""
    return {"message": "实时多模态分析系统", "websocket": websocket_available}

if __name__ == "__main__":
    print("🚀 启动实时多模态分析测试服务器...")
    print("📍 访问地址: http://localhost:8000")
    print("🔌 WebSocket地址: ws://localhost:8000/ws/multimodal-analysis")
    print("❤️ 健康检查: http://localhost:8000/health")
    print("📁 前端页面: http://localhost:8000/frontend/interview-simulation.html")
    print("---")
    
    uvicorn.run(
        "test_realtime_system:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    ) 