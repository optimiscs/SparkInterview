# 🚀 Celery版本启动指南

## 为什么需要单独启动Celery？

**问题解决：**
- ✅ 解决异步分析任务阻塞主线程的问题
- ✅ 用户界面响应更快，可以正常切换页面
- ✅ 支持多任务并行处理

**架构说明：**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │     Redis       │    │  Celery Worker  │
│   主服务器       │───▶│   消息代理       │◀───│   异步任务处理   │
│   (用户界面)     │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 启动步骤

### 1. 激活conda环境
```bash
conda activate xinghuo
```

### 2. 启动Redis (消息代理)
```bash
./start_redis.sh
```

### 3. 启动Celery Worker (异步任务处理)
```bash
# 方法1：使用启动脚本（推荐）
./start_celery_worker.sh

# 方法2：手动启动
export PYTHONPATH="$(pwd):${PYTHONPATH}"
celery -A src.celery_app worker --loglevel=info --concurrency=2 --pool=solo
```

### 4. 启动FastAPI服务器 (用户界面)
```bash
python main.py
```

## 验证启动成功

### 1. 检查Redis
```bash
redis-cli ping
# 应返回: PONG
```

### 2. 检查Celery健康状态
```bash
curl -X GET "http://localhost:8000/api/v1/resume/celery/health"
```

### 3. 检查任务队列
```bash
# 查看队列状态
celery -A src.celery_app inspect active
```

## 任务类型

- **analysis队列**: JD匹配分析、STAR原则检测
- **profile队列**: 用户画像生成

## 常见问题

### Q1: ModuleNotFoundError: No module named 'src'
**解决**: 确保在`79014382源码`目录下启动，并设置PYTHONPATH

### Q2: Redis连接失败
**解决**: 先启动Redis服务 `./start_redis.sh`

### Q3: Celery任务一直PENDING
**解决**: 检查Celery Worker是否正常运行

## 开发建议

1. **开发环境**: 每次开发时按顺序启动Redis → Celery → FastAPI
2. **生产环境**: 可以使用systemd或supervisor管理进程
3. **监控**: 可以使用Flower监控Celery任务状态
