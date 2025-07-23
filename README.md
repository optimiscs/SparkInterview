# 多模态面试评测智能体系统

基于LangGraph和讯飞星火大模型的智能面试评测系统，支持自动化面试流程、多模态分析和个性化反馈。

## 🚀 系统特色

- **智能面试流程**: 基于LangGraph的状态驱动工作流，实现完整的面试自动化
- **多模态分析**: 集成视觉、听觉、文本分析，全面评估候选人表现
- **智能追问**: 讯飞星火4.0 Ultra模型驱动的动态追问机制
- **个性化反馈**: 自动生成能力雷达图和详细评估报告
- **学习路径推荐**: 基于薄弱环节的个性化学习资源推荐

## 📋 系统架构

### 核心组件

```
┌─────────────────────────────────────────────────────────┐
│                   LangGraph 工作流                      │
├─────────────────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌────────┐ │
│  │面试设置   │→ │面试执行   │→ │多模态分析 │→ │报告生成│ │
│  │智能体     │  │智能体     │  │节点       │  │节点    │ │
│  └───────────┘  └───────────┘  └───────────┘  └────────┘ │
│                                        ↓                │
│                                  ┌───────────┐         │
│                                  │学习路径   │         │
│                                  │推荐节点   │         │
│                                  └───────────┘         │
└─────────────────────────────────────────────────────────┘
```

### 技术栈

- **核心框架**: LangGraph + LangChain
- **大语言模型**: 讯飞星火认知大模型 (Pro版 + 4.0 Ultra版)
- **向量数据库**: ChromaDB
- **多模态分析**: MediaPipe + DeepFace + Librosa
- **可视化**: Matplotlib + Plotly
- **文档处理**: PyPDF2 + python-docx

## 🛠️ 安装配置

### 1. 环境要求

- Python 3.8+
- 讯飞星火API密钥

### 2. 安装依赖

```bash
# 克隆项目
git clone <repository-url>
cd interview-agent

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置API密钥

```bash
# 复制配置模板
cp config.env.template config.env

# 编辑配置文件，填入您的讯飞星火API信息
nano config.env
```

在 `config.env` 中填入：

```bash
SPARK_APP_ID=your_app_id
SPARK_API_KEY=your_api_key
SPARK_API_SECRET=your_api_secret
```

### 4. 运行系统

```bash
python main.py
```

## 🎯 使用指南

### 基本流程

1. **启动系统**: 运行 `python main.py`
2. **输入信息**: 填写姓名、目标岗位、技术领域等基本信息
3. **开始面试**: 系统自动生成面试问题并进行对话
4. **智能追问**: 系统根据回答质量进行针对性追问
5. **多模态分析**: 自动分析文本内容、模拟视觉和听觉特征
6. **生成报告**: 输出详细的评估报告和能力雷达图
7. **学习推荐**: 基于薄弱环节推荐个性化学习资源

### 示例对话

```
🤵 面试官: 请介绍一下您在机器学习项目中的经验，特别是您负责的具体工作。

👤 您的回答: 我参与了一个推荐系统项目，主要负责算法优化...

🤵 面试官: 您提到了推荐系统，能具体说说您使用了哪些算法，以及是如何评估模型效果的吗？
```

## 📊 评估维度

系统从以下5个维度对候选人进行评估：

- **专业知识水平**: 技术概念理解、专业深度
- **技能匹配度**: 与岗位要求的符合程度
- **语言表达能力**: 回答的逻辑性、清晰度
- **逻辑思维能力**: STAR法则运用、结构化思考
- **应变抗压能力**: 面试表现的稳定性、自信度

## 🔧 系统配置

### 模型配置

不同模块采用不同版本的星火模型以平衡性能和成本：

| 模块 | 模型版本 | 用途 | 成本考量 |
|------|----------|------|----------|
| 面试设置智能体 | Spark Pro | 简历解析、问题筛选 | 高性价比 |
| 面试官智能体 | Spark 4.0 Ultra | 对话交互、动态追问 | 最佳体验 |
| 综合分析节点 | Spark 4.0 Ultra | 多模态评估 | 准确性优先 |
| 报告生成节点 | Spark Pro | 报告生成 | 成本效益 |
| 学习路径节点 | Spark Pro | 资源推荐 | 高效率 |

### 向量数据库

系统使用ChromaDB存储：
- 面试题库（按领域、难度分类）
- 学习资源库（按能力维度分类）

## 📁 项目结构

```
interview-agent/
├── src/                          # 源代码
│   ├── agents/                   # 智能体模块
│   │   ├── setup_agent.py       # 面试设置智能体
│   │   └── interviewer_agent.py # 面试官智能体
│   ├── nodes/                    # 确定性节点
│   │   ├── analysis_node.py     # 综合分析节点
│   │   ├── report_node.py       # 报告生成节点
│   │   └── learning_path_node.py # 学习路径节点
│   ├── models/                   # 数据模型
│   │   ├── state.py             # 状态定义
│   │   └── spark_client.py      # 星火模型客户端
│   ├── tools/                    # 工具模块
│   │   ├── resume_parser.py     # 简历解析工具
│   │   └── vector_search.py     # 向量搜索工具
│   ├── config/                   # 配置模块
│   └── workflow.py              # 工作流定义
├── data/                         # 数据目录
│   ├── chroma_db/               # 向量数据库
│   ├── cache/                   # 缓存文件
│   └── interview_results/       # 面试结果
├── main.py                      # 主程序入口
├── requirements.txt             # 依赖列表
└── README.md                    # 项目文档
```

## 🧪 扩展开发

### 添加新的面试问题

```python
from src.tools.vector_search import create_question_bank_manager

# 创建题库管理器
question_manager = create_question_bank_manager()

# 添加新问题
new_questions = [
    {
        "text": "请解释什么是微服务架构？",
        "field": "Backend",
        "difficulty": "middle",
        "type": "technical",
        "expected_keywords": ["微服务", "架构", "分布式"]
    }
]

question_manager.add_questions(new_questions)
```

### 添加学习资源

```python
from src.tools.vector_search import create_learning_resource_manager

# 创建资源管理器
resource_manager = create_learning_resource_manager()

# 添加新资源
new_resources = [
    {
        "title": "深入理解Spring Boot",
        "description": "Spring Boot框架的深入学习指南",
        "url": "https://example.com/springboot-guide",
        "type": "course",
        "competency": "professional_knowledge",
        "difficulty": "intermediate"
    }
]

resource_manager.add_resources(new_resources)
```

### 自定义评估维度

修改 `src/nodes/analysis_node.py` 中的评估维度：

```python
self.assessment_dimensions = {
    "technical_skills": "技术技能",
    "problem_solving": "问题解决能力",
    "team_collaboration": "团队协作能力",
    # 添加新的评估维度
}
```

## 🚨 注意事项

1. **API配置**: 确保正确配置讯飞星火API密钥
2. **网络连接**: 系统需要稳定的网络连接调用API
3. **依赖安装**: 某些依赖（如音视频处理库）可能需要系统级安装
4. **数据隐私**: 面试数据会保存在本地，请注意数据安全

## 🔮 未来规划

- [ ] **真实多模态分析**: 集成实时视频和音频分析
- [ ] **流式处理**: 支持实时音视频流分析
- [ ] **模型热插拔**: 支持多种大语言模型切换
- [ ] **分布式部署**: 支持大规模并发面试
- [ ] **Web界面**: 开发用户友好的Web管理界面

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request来帮助改进项目！

## 📞 联系方式

如有问题或建议，请通过以下方式联系：

- 邮箱: support@zhimianxinghuo.tech 


---

⚡ **快速开始**: `pip install -r requirements.txt && python main.py` 