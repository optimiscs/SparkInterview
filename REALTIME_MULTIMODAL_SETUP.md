# 🎯 实时多模态分析系统部署指南

## 📋 系统概述

实时多模态分析系统为`职面星火`智能面试平台提供了**面试过程中的实时分析能力**，通过WebSocket实时传输视频帧和音频数据，进行多维度的智能分析并即时反馈给用户。

### 核心功能

- **🎥 实时视频分析**: 表情识别、头部姿态、视线跟踪
- **🎵 实时音频分析**: 语速检测、音调分析、情感识别
- **📊 即时反馈**: 毫秒级分析结果推送
- **🔄 智能缓存**: 优化性能，减少重复计算
- **⚡ 高并发支持**: 支持多用户同时使用

## 🚀 快速开始

### 1. 环境准备

#### 系统要求
- **操作系统**: Linux/macOS/Windows
- **Python**: 3.8+
- **内存**: 至少4GB可用内存
- **CPU**: 支持AVX指令集（用于深度学习加速）
- **摄像头**: 支持WebRTC的摄像头设备
- **麦克风**: 音频输入设备

#### 安装系统依赖

**Linux (Ubuntu/Debian)**:
```bash
# 更新包管理器
sudo apt update

# 安装系统依赖
sudo apt install -y \
    python3-dev \
    libopencv-dev \
    libportaudio2 \
    libportaudiocpp0 \
    portaudio19-dev \
    libasound2-dev \
    libpulse-dev \
    ffmpeg

# 安装Redis
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**macOS**:
```bash
# 使用Homebrew安装
brew install python opencv portaudio ffmpeg redis

# 启动Redis
brew services start redis
```

**Windows**:
```bash
# 使用Chocolatey安装
choco install python opencv ffmpeg redis-64

# 或下载官方安装包
# Python: https://www.python.org/downloads/
# OpenCV: 通过pip安装
# FFmpeg: https://ffmpeg.org/download.html
# Redis: https://redis.io/download
```

### 2. Python依赖安装

```bash
# 进入项目目录
cd /path/to/职面星火项目

# 安装实时多模态分析依赖
pip install -r requirements_realtime.txt

# 如果遇到安装问题，可以分步安装
pip install opencv-python mediapipe
pip install deepface tensorflow
pip install librosa soundfile
pip install websockets redis
```

### 3. 配置文件设置

#### 环境变量配置 (.env文件)
```bash
# 创建环境变量文件
cp .env.example .env

# 编辑配置
vim .env
```

添加以下配置：
```bash
# ==================== 实时多模态分析配置 ====================

# WebSocket配置
RT_WEBSOCKET_HOST=0.0.0.0
RT_WEBSOCKET_PORT=8000
RT_MAX_CONNECTIONS=50
RT_CONNECTION_TIMEOUT=300

# 视频分析配置
RT_VIDEO_FPS=2
RT_FRAME_WIDTH=640
RT_FRAME_HEIGHT=480
RT_VIDEO_QUALITY=0.8

# 音频分析配置
RT_AUDIO_SAMPLE_RATE=16000
RT_AUDIO_CHUNK_DURATION=3000

# AI模型配置
RT_MEDIAPIPE_CONFIDENCE=0.5
RT_DEEPFACE_BACKEND=opencv
RT_DEEPFACE_ENFORCE=False

# Redis配置
RT_REDIS_HOST=localhost
RT_REDIS_PORT=6379
RT_REDIS_DB=1
RT_REDIS_PASSWORD=

# 性能配置
RT_MAX_WORKERS=4
RT_QUEUE_SIZE=100
RT_MEMORY_LIMIT_MB=512
RT_CPU_LIMIT_PERCENT=80

# 功能开关
RT_ENABLE_VIDEO=True
RT_ENABLE_AUDIO=True
RT_ENABLE_EMOTION=True
RT_ENABLE_GAZE=True
RT_ENABLE_HEAD_POSE=True
RT_ENABLE_SPEECH_EMOTION=True

# 安全配置
RT_ENABLE_RATE_LIMIT=True
RT_MAX_REQUESTS_PER_MIN=60
RT_MAX_FRAME_SIZE_MB=5
RT_MAX_AUDIO_SIZE_MB=10
```

### 4. 启动系统

```bash
# 方式1: 直接启动
python main.py

# 方式2: 使用uvicorn启动
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 方式3: 生产环境启动
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 5. 验证安装

#### 检查WebSocket连接
```bash
# 使用curl测试WebSocket端点
curl -i -N -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==" \
     -H "Sec-WebSocket-Version: 13" \
     http://localhost:8000/ws/multimodal-analysis
```

#### 检查Redis连接
```bash
# 连接Redis并测试
redis-cli -h localhost -p 6379
> ping
PONG
> select 1
OK
> exit
```

#### 浏览器测试
1. 打开浏览器访问 `http://localhost:8000`
2. 进入面试模拟页面
3. 允许摄像头和麦克风权限
4. 查看右侧实时分析面板是否正常更新

## 🔧 高级配置

### 性能优化

#### 1. GPU加速（可选）
```bash
# 安装GPU版本的TensorFlow（需要NVIDIA GPU）
pip uninstall tensorflow
pip install tensorflow-gpu

# 验证GPU支持
python -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))"
```

#### 2. 内存优化
```python
# 在src/config/realtime_config.py中调整
RT_MEMORY_LIMIT_MB=1024  # 增加内存限制
RT_MAX_WORKERS=2         # 减少工作线程（如果内存不足）
```

#### 3. CPU优化
```bash
# 设置OpenMP线程数
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
```

### 集群部署

#### 1. Redis集群配置
```bash
# Redis集群配置文件 redis-cluster.conf
port 7001
cluster-enabled yes
cluster-config-file nodes.conf
cluster-node-timeout 5000
```

#### 2. 负载均衡
```nginx
# Nginx配置
upstream websocket_backend {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}

server {
    listen 80;
    location /ws/ {
        proxy_pass http://websocket_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### 安全配置

#### 1. HTTPS/WSS配置
```python
# SSL证书配置
SSL_CERT_PATH = "/path/to/cert.pem"
SSL_KEY_PATH = "/path/to/key.pem"
```

#### 2. 访问控制
```python
# 在api/websocket_server.py中添加IP白名单
ALLOWED_IPS = ["127.0.0.1", "192.168.1.0/24"]
```

## 📊 监控和维护

### 系统监控

#### 1. 性能指标监控
```bash
# 安装监控工具
pip install psutil prometheus_client

# 启动监控端点
python -c "
from api.websocket_server import analysis_handler
stats = analysis_handler.get_performance_stats()
print(stats)
"
```

#### 2. 日志监控
```bash
# 查看实时日志
tail -f logs/realtime_analysis.log

# 查看错误日志
grep "ERROR" logs/realtime_analysis.log
```

#### 3. Redis监控
```bash
# Redis性能监控
redis-cli --latency-history -i 1

# 内存使用监控
redis-cli info memory
```

### 故障排除

#### 常见问题及解决方案

**1. WebSocket连接失败**
```bash
# 检查端口占用
netstat -tulpn | grep 8000

# 检查防火墙设置
sudo ufw status
sudo ufw allow 8000
```

**2. 视频分析失败**
```bash
# 检查OpenCV安装
python -c "import cv2; print(cv2.__version__)"

# 检查MediaPipe安装
python -c "import mediapipe as mp; print('MediaPipe OK')"
```

**3. 音频分析失败**
```bash
# 检查音频库
python -c "import librosa; print('Librosa OK')"

# 检查音频设备
arecord -l  # Linux
```

**4. 内存溢出**
```bash
# 监控内存使用
htop

# 减少并发连接数
RT_MAX_CONNECTIONS=10
RT_MAX_WORKERS=2
```

**5. DeepFace模型下载失败**
```bash
# 手动下载模型
mkdir -p ~/.deepface/weights
wget https://github.com/serengil/deepface_models/releases/download/v1.0/vgg_face_weights.h5 -O ~/.deepface/weights/vgg_face_weights.h5
```

## 🧪 测试和调试

### 单元测试

```bash
# 运行实时分析测试
python -m pytest tests/test_realtime_analysis.py -v

# 运行WebSocket测试
python -m pytest tests/test_websocket.py -v
```

### 性能测试

```bash
# 创建测试脚本
cat > test_performance.py << 'EOF'
import asyncio
import websockets
import json
import time
import base64
from PIL import Image
import io

async def test_websocket_performance():
    uri = "ws://localhost:8000/ws/multimodal-analysis"
    
    async with websockets.connect(uri) as websocket:
        # 认证
        auth_msg = {
            "type": "auth",
            "data": {
                "session_id": "test_session",
                "access_token": "test_token"
            }
        }
        await websocket.send(json.dumps(auth_msg))
        
        # 发送测试帧
        for i in range(100):
            # 创建测试图像
            img = Image.new('RGB', (640, 480), color='red')
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG')
            img_data = base64.b64encode(buffer.getvalue()).decode()
            
            frame_msg = {
                "type": "video_frame",
                "data": {
                    "frame": f"data:image/jpeg;base64,{img_data}",
                    "timestamp": int(time.time() * 1000),
                    "width": 640,
                    "height": 480
                }
            }
            
            start_time = time.time()
            await websocket.send(json.dumps(frame_msg))
            response = await websocket.recv()
            end_time = time.time()
            
            print(f"Frame {i}: {(end_time - start_time) * 1000:.2f}ms")

# 运行测试
asyncio.run(test_websocket_performance())
EOF

python test_performance.py
```

### 调试模式

```bash
# 启用调试日志
export RT_LOG_LEVEL=DEBUG
export RT_LOG_WEBSOCKET=True
export RT_LOG_PERFORMANCE=True

# 启动调试模式
python main.py
```

## 📈 扩展和定制

### 添加新的分析功能

1. **扩展视觉分析**
```python
# 在src/tools/realtime_analyzer.py中添加新方法
def analyze_micro_expressions(self, frame):
    # 微表情分析逻辑
    pass
```

2. **扩展音频分析**
```python
# 添加语音识别功能
def analyze_speech_content(self, audio_data):
    # 语音识别和内容分析
    pass
```

3. **添加自定义指标**
```python
# 在WebSocket消息处理中添加新的消息类型
elif message_type == 'custom_analysis':
    await handle_custom_analysis(connection_id, data)
```

### 集成第三方服务

1. **集成云端AI服务**
```python
# 集成阿里云、腾讯云等AI服务
from alibabacloud_facebody20191230.client import Client as FacebodyClient
```

2. **集成实时通信服务**
```python
# 集成WebRTC服务
from aiortc import RTCPeerConnection, RTCSessionDescription
```

## 🔐 安全考虑

### 数据隐私保护

1. **本地处理优先**: 尽可能在本地进行分析，减少数据传输
2. **数据加密**: 对敏感数据进行加密存储
3. **访问控制**: 实施严格的身份验证和授权机制
4. **日志审计**: 记录所有访问和操作日志

### 合规性要求

- **GDPR合规**: 支持数据删除和导出请求
- **CCPA合规**: 提供数据使用透明度
- **等保合规**: 满足网络安全等级保护要求

## 📞 技术支持

### 社区支持
- **GitHub Issues**: [项目Issues页面]
- **技术论坛**: [论坛地址]
- **微信群**: [二维码]

### 商业支持
- **邮箱**: support@zhimianxinghuo.tech
- **电话**: 400-XXX-XXXX
- **在线客服**: [客服链接]

---

## ⚡ 快速故障排除清单

✅ **启动前检查**:
- [ ] Python 3.8+ 已安装
- [ ] Redis 服务运行正常
- [ ] 所有依赖包已安装
- [ ] 配置文件格式正确
- [ ] 端口8000未被占用

✅ **运行时检查**:
- [ ] WebSocket连接成功
- [ ] 摄像头权限已授权
- [ ] 麦克风权限已授权
- [ ] Redis连接正常
- [ ] 日志无ERROR信息

✅ **性能检查**:
- [ ] CPU使用率 < 80%
- [ ] 内存使用率 < 80%
- [ ] 网络延迟 < 100ms
- [ ] 帧率稳定在目标值
- [ ] 无内存泄漏

🎉 **恭喜！您的实时多模态分析系统已成功部署！** 