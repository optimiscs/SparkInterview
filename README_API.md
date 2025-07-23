# 职面星火 - FastAPI 后端服务文档

## 📖 项目简介

职面星火是一个基于多智能体的高校生多模态模拟面试与智能评测系统。本项目使用 FastAPI 构建 REST API 服务，为前端提供完整的后端支持。

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- 推荐使用虚拟环境

### 2. 安装依赖

```bash
cd 86014223源码
pip install -r requirements.txt
```

### 3. 配置环境变量

复制配置文件并填写必要的配置：
```bash
cp config.env.template config.env
```

编辑 `config.env` 文件，填写讯飞星火大模型的 API 密钥：
```bash
SPARK_APP_ID=your_app_id
SPARK_API_SECRET=your_api_secret
```

### 4. 启动服务

```bash
python main.py
```

服务将在 `http://localhost:8000` 启动。

### 5. 访问API文档

启动服务后，可以访问以下地址：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### 6. API测试页面

访问 http://localhost:8000/frontend/api-test.html 进行API功能测试。

## 📋 API 接口概览

### 用户管理 (`/api/v1`)

| 接口 | 方法 | 描述 |
|------|------|------|
| `/register` | POST | 用户注册 |
| `/login` | POST | 用户登录 |
| `/logout` | POST | 用户登出 |
| `/profile` | GET | 获取用户信息 |
| `/profile` | PUT | 更新用户信息 |

### 面试系统 (`/api/v1`)

| 接口 | 方法 | 描述 |
|------|------|------|
| `/setup` | POST | 设置面试 |
| `/question` | POST | 获取面试问题 |
| `/answer` | POST | 提交面试回答 |
| `/status/{session_id}` | GET | 获取面试状态 |
| `/analyze/{session_id}` | POST | 开始多模态分析 |
| `/analysis/{session_id}` | GET | 获取分析结果 |
| `/report/{session_id}` | POST | 生成面试报告 |
| `/report/{session_id}` | GET | 获取面试报告 |
| `/learning-path/{session_id}` | GET | 获取学习路径推荐 |

### 能力评估 (`/api/v1`)

| 接口 | 方法 | 描述 |
|------|------|------|
| `/start` | POST | 开始能力评估 |
| `/answer` | POST | 提交评估答案 |
| `/submit` | POST | 提交完整评估 |
| `/result/{session_id}` | GET | 获取评估结果 |
| `/history` | GET | 获取评估历史 |

### 学习资源 (`/api/v1`)

| 接口 | 方法 | 描述 |
|------|------|------|
| `/search` | POST | 搜索学习资源 |
| `/recommend` | GET | 获取推荐资源 |
| `/{resource_id}` | GET | 获取单个资源 |
| `/create` | POST | 创建学习资源(管理员) |
| `/stats/overview` | GET | 获取资源统计 |

## 🔒 认证机制

API 使用 Bearer Token 认证：

1. 用户通过 `/login` 接口登录获取 `access_token`
2. 在后续请求的 Header 中添加：`Authorization: Bearer <access_token>`
3. Token 默认有效期为 7 天

## 📝 使用示例

### 1. 用户注册登录

```javascript
// 注册
const registerResponse = await fetch('/api/v1/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        name: "张三",
        email: "zhangsan@example.com", 
        password: "123456",
        role: "student"
    })
});

// 登录
const loginResponse = await fetch('/api/v1/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        email: "zhangsan@example.com",
        password: "123456"
    })
});

const { access_token, user } = await loginResponse.json();
```

### 2. 面试流程

```javascript
// 设置面试
const setupResponse = await fetch('/api/v1/setup', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    },
    body: JSON.stringify({
        user_name: "张三",
        target_position: "后端工程师",
        target_field: "Backend",
        resume_text: "我是一名计算机专业的学生...",
        question_count: 8
    })
});

const { session_id } = await setupResponse.json();

// 获取问题
const questionResponse = await fetch('/api/v1/question', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    },
    body: JSON.stringify({ session_id })
});

// 提交答案
const answerResponse = await fetch('/api/v1/answer', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    },
    body: JSON.stringify({
        session_id,
        question_id: "q_1",
        question: "请介绍一下您的技术背景",
        answer: "我主要使用Python和Java进行开发..."
    })
});
```

### 3. 能力评估

```javascript
// 开始评估
const startResponse = await fetch('/api/v1/start', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    },
    body: JSON.stringify({
        assessment_type: "technical",
        user_id: user.id,
        difficulty_level: "middle"
    })
});

const { session_id, questions } = await startResponse.json();

// 提交评估答案
const submitResponse = await fetch('/api/v1/submit', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    },
    body: JSON.stringify({
        session_id,
        answers: {
            "tech_1": "选项B",
            "tech_2": "选项A", 
            "tech_3": "我会设计一个基于哈希的短链接服务..."
        }
    })
});
```

## 🏗️ 项目结构

```
86014223源码/
├── main.py              # FastAPI应用入口
├── requirements.txt     # 项目依赖
├── config.env          # 环境配置
├── api/                # API模块
│   ├── models.py       # Pydantic数据模型
│   └── routers/        # API路由
│       ├── users.py    # 用户管理
│       ├── interviews.py # 面试系统
│       ├── assessments.py # 能力评估
│       └── resources.py # 学习资源
├── src/                # 核心业务逻辑
│   ├── agents/         # 智能体
│   ├── models/         # 数据模型
│   ├── nodes/          # 处理节点
│   ├── tools/          # 工具模块
│   └── workflow.py     # 工作流
├── frontend/           # 前端文件
│   ├── api-test.html   # API测试页面
│   └── ...             # 其他前端文件
└── data/               # 数据存储
    ├── cache/          # 缓存文件
    ├── interviews/     # 面试记录
    └── chroma_db/      # 向量数据库
```

## 🛠️ 技术栈

- **Web框架**: FastAPI + Uvicorn
- **大语言模型**: 讯飞星火认知大模型
- **多智能体**: LangGraph + LangChain
- **向量数据库**: ChromaDB
- **多模态AI**: MediaPipe + DeepFace + Librosa
- **数据验证**: Pydantic
- **可视化**: Matplotlib + Plotly

## 📚 开发指南

### 添加新的API接口

1. 在 `api/models.py` 中定义请求/响应模型
2. 在对应的路由文件中添加接口函数
3. 更新API文档

### 扩展智能体功能

1. 在 `src/agents/` 中创建新的智能体
2. 在 `src/workflow.py` 中集成新智能体
3. 在API路由中暴露相关接口

### 添加新的分析节点

1. 在 `src/nodes/` 中创建分析节点
2. 实现 `analyze()` 方法
3. 在工作流中注册节点

## 🔍 调试和测试

### 启用调试模式

在 `main.py` 中设置：
```python
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,    # 热重载
        log_level="debug"  # 调试日志
    )
```

### 查看日志

日志文件位置：`logs/interview_agent.log`

### API测试

使用提供的测试页面：http://localhost:8000/frontend/api-test.html

或使用 curl 测试：
```bash
# 健康检查
curl http://localhost:8000/health

# 查看API文档
curl http://localhost:8000/openapi.json
```

## ⚠️ 注意事项

1. **开发环境**: 当前使用内存存储，生产环境需要使用实际数据库
2. **API密钥**: 请妥善保管讯飞星火的API密钥
3. **跨域配置**: 生产环境中需要限制CORS Origins
4. **文件上传**: 大文件上传需要配置适当的限制
5. **性能优化**: 大规模使用时需要考虑缓存和数据库优化

## 📞 技术支持

如有问题，请查看：
- API文档：http://localhost:8000/docs
- 项目日志：`logs/interview_agent.log`
- 技术文档：项目源码注释

---

**职面星火开发团队** 
📧 support@zhimianxinghuo.tech 