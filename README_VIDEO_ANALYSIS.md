# 实时多模态视频分析功能说明

## 概述

已成功为职面星火面试系统添加了真正的实时多模态视频分析功能，替换了原本的模拟数据。新系统集成了MediaPipe、DeepFace等专业工具，提供真实的视觉分析能力。

## 🚀 新增功能

### 1. 后端视频分析服务 (`api/routers/video_analysis.py`)

- **实时视频流处理**: WebSocket接收并处理前端视频帧
- **多模态分析集成**: 调用`multimodal_analyzer.py`进行真实分析
- **头部姿态分析**: 使用MediaPipe检测俯仰、偏航、翻滚角度
- **视线追踪**: 实时检测眼神接触和视线方向
- **情绪分析**: 集成DeepFace进行面部情绪识别
- **会话管理**: 支持多用户并发分析会话

### 2. 前端视频分析管理器 (`frontend/js/video-analysis-manager.js`)

- **视频帧捕获**: 从用户摄像头实时捕获视频帧
- **WebSocket通信**: 与后端视频分析服务实时通信
- **UI更新**: 实时更新右侧分析面板显示真实数据
- **状态管理**: 管理分析会话的开始、停止、重置等状态
- **历史记录**: 保存分析历史供后续查看

### 3. 页面集成 (`frontend/interview.html`)

- **自动初始化**: 摄像头开启时自动初始化视频分析
- **seamless集成**: 与现有的摄像头控制和面试流程无缝集成
- **状态同步**: 视频分析状态与摄像头状态同步

## 🔧 技术架构

```
前端摄像头 → 帧捕获 → WebSocket → 后端分析服务
                ↓                        ↓
            Canvas处理            MultimodalAnalyzer
                ↓                        ↓
            Base64编码      ← MediaPipe + DeepFace
                ↑                        ↓
            UI更新     ←    分析结果     ← RealTimeAnalysisManager
```

## 📊 分析功能详情

### 微表情洞察
- **自信度**: 基于面部情绪的正面表情比例
- **紧张度**: 基于恐惧、愤怒等负面情绪强度
- **专注度**: 基于眼神接触比例和头部稳定性

### 体态语言分析
- **眼神接触**: 实时计算与摄像头的眼神接触比例
- **头部稳定性**: 基于头部姿态变化的稳定性评估
- **姿态评分**: 综合自信度和头部稳定性的姿态评分

### 实时建议
- 动态生成基于当前表现的优化建议
- 支持成功、信息、警告、错误四种类型的建议
- 根据分析结果智能推荐改进措施

## 🚀 使用方法

### 1. 启动系统
```bash
cd SparkInterview
python main.py
```

### 2. 访问面试页面
打开浏览器访问 `http://localhost:8000/frontend/interview.html`

### 3. 开启摄像头
点击页面右上角的"摄像头"按钮，允许摄像头权限

### 4. 查看实时分析
- 右侧分析面板会显示实时的多模态分析结果
- 包括微表情、体态语言、质量评估等数据
- 分析结果每秒更新2次（可调节）

## 📋 API接口

### 创建视频分析会话
```http
POST /api/v1/video/create-video-session
Content-Type: application/json

{
  "user_id": "user123"
}
```

### WebSocket视频分析
```
ws://localhost:8000/api/v1/video/video-analysis/{session_id}
```

**发送数据格式:**
- 视频帧: Base64编码的图像数据
- 控制命令: JSON格式，如`{"command": "start_analysis"}`

**接收数据格式:**
```json
{
  "type": "analysis_update",
  "timestamp": 1640000000.0,
  "micro_expressions": {
    "dominant_emotion": "happy",
    "confidence": 85.0,
    "tension": 25.0,
    "focus": 92.0
  },
  "body_language": {
    "eye_contact_ratio": 78.0,
    "head_stability": 88.0,
    "posture_score": 85.0
  },
  "suggestions": [
    {
      "type": "success",
      "message": "表现出色！保持当前的自信状态"
    }
  ]
}
```

## ⚠️ 重要说明

### 依赖库要求
- **MediaPipe**: 用于面部关键点检测和头部姿态分析
- **DeepFace**: 用于情绪分析（可选，不可用时会跳过情绪分析）
- **OpenCV**: 用于图像处理
- **NumPy**: 用于数值计算

### 性能考虑
- 默认分析频率: 2 FPS（每秒2帧）
- 帧缓存大小: 最多30帧
- WebSocket连接: 支持多用户并发
- 自动资源清理: 会话结束时自动释放资源

### 浏览器兼容性
- 需要支持WebRTC的现代浏览器
- 需要摄像头权限
- 建议使用Chrome、Firefox或Edge最新版本

## 🔧 配置选项

可以通过修改配置来调整分析行为：

```python
# video_analysis.py 中的配置
FRAME_RATE = 2  # 分析帧率
MAX_BUFFER_SIZE = 30  # 最大缓存帧数
ANALYSIS_INTERVAL = 1.0  # 最小分析间隔（秒）
```

```javascript
// video-analysis-manager.js 中的配置
this.frameRate = 2; // 前端捕获帧率
this.analysisHistory.maxLength = 100; // 历史记录最大长度
```

## 🐛 故障排除

### 常见问题

1. **DeepFace不可用**
   - 安装: `pip install deepface`
   - 首次运行会下载预训练模型

2. **摄像头权限被拒绝**
   - 检查浏览器摄像头权限设置
   - 确保使用HTTPS或localhost

3. **WebSocket连接失败**
   - 确认后端服务正常运行
   - 检查防火墙设置

4. **分析结果不更新**
   - 检查浏览器控制台错误信息
   - 确认摄像头正常工作

### 调试模式

在浏览器控制台查看详细日志：
```javascript
// 获取当前分析状态
window.videoAnalysisFunctions.getCurrentVideoAnalysis()

// 切换分析状态
window.videoAnalysisFunctions.toggleVideoAnalysis()
```

## 🎯 后续优化建议

1. **性能优化**: 可以添加帧跳跃和动态帧率调节
2. **分析精度**: 可以集成更多的情绪和姿态分析模型
3. **历史分析**: 添加会话结束后的分析报告生成
4. **个性化**: 根据用户特点调整分析阈值
5. **多语言**: 支持多语言的建议消息

## 📄 更新记录

- **v1.0.0** (2024-01-01): 初始版本，实现基础多模态分析功能
- 支持实时头部姿态分析
- 支持视线追踪和眼神接触检测  
- 集成DeepFace情绪分析
- 提供实时优化建议
- 完整的前后端WebSocket通信
