# ScholarGuard 学术卫士

> 以LLM��核心推理引擎、面向中文学术写作与学术诚信治理的模块化平台

## 项目状态

**当前版本**: Phase 1 MVP (开发中)
**设计版本**: v2.0

## 快速开始

### 前提条件

- Docker & Docker Compose
- Node.js 20+ (前端开发)
- Python 3.12+ & uv (后端开发)

### 1. 克隆并配置环境变量

```bash
cd scholarguard
cp .env.example .env
# 编辑 .env 文件，配置数据库密码、API密钥等
```

### 2. 启动基础设施（Docker Compose）

```bash
docker-compose up -d postgres redis qdrant minio
```

### 3. 初始化数据库

```bash
cd api
uv sync                        # 安装Python依赖
source .venv/bin/activate
alembic upgrade head           # 执行数据库迁移
```

### 4. 启动后端API

```bash
cd api
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API文档访问: http://localhost:8000/docs

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端访问: http://localhost:3000

### 6. 一键启动（全部容器化）

```bash
docker-compose up -d
```

## 项目结构

```
scholarguard/
├── api/                        # 后端 (FastAPI + Python 3.12)
│   ├── app/
│   │   ├── main.py             # FastAPI 入口
│   │   ├── config.py           # 配置管理
│   │   ├── middleware/         # 认证、限流
│   │   ├── routers/            # API路由 (detect/suggest/review/research/admin)
│   │   ├── services/
│   │   │   ├── detection/      # 🟢 检测引擎 (核心)
│   │   │   ├── suggestion/     # 🟢 写作建议
│   │   │   ├── review/         # 🟢 复核与申诉
│   │   │   ├── llm_gateway/    # LLM统一网关 (LiteLLM)
│   │   │   ├── research/       # 🟡 文献研究 (Demo)
│   │   │   └── translation/    # ⚪ 翻译润色 (预留)
│   │   ├── models/             # SQLAlchemy ORM (14张表)
│   │   ├── schemas/            # Pydantic 数据验证
│   │   └── prompts/            # LLM Prompt 模板库
│   ├── migrations/             # Alembic 数据库迁移
│   └── tests/
├── frontend/                   # 前端 (React 18 + TypeScript + Vite)
├── knowledge_base/             # 社科术语库
├── eval/                       # 评测框架
├── docker-compose.yml          # 容器编排
└── .env.example                # 环境变量模板
```

## 核心架构

```
用户 → [统一工作台] → [API网关(FastAPI)]
                           ↓
              ┌─── 核心生产链 ───────────────────┐
              │ 检测引擎 → 证据融合器 → 报告生成器 │
              │ 写作建议 → 复核/申诉 → 反馈闭环   │
              └──────────────────────────────────┘
                           ↓
              [LLM网关(LiteLLM)] → Ollama/vLLM(本地) | OpenAI/Anthropic(远程)
                           ↓
              [PostgreSQL + Qdrant + MinIO + Redis]
```

## 检测引擎流水线

```
文本输入 → 预处理 → E1:LLM评议 → E2:统计因子 → 证据融合(RiskScore公式) → 解释报告
                                                      ↑
                                         E3:材料证据(预留) + E4:人工证据(复核)
```

**RiskScore公式** (白箱可见):
```
RiskScore = w1×LLMConfidence + w2×StatScore + w3×SemanticGap + w4×MaterialMismatch - w5×HumanCredit
```
参数可配置、版本化、支持回滚。

## API端点

| 端点 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/api/v1/detect` | POST | 提交AI检测 | 🟢 |
| `/api/v1/detect/{task_id}` | GET | 查询检测结果 | 🟢 |
| `/api/v1/suggest` | POST | 获取写作建议 | 🟢 |
| `/api/v1/review/{id}` | POST | 提交复核 | 🟢 |
| `/api/v1/appeal/{id}` | POST | 提交申诉 | 🟢 |
| `/api/v1/feedback` | POST | 提交反馈 | 🟢 |
| `/api/v1/research/query` | POST | 文献检索 | 🟡 Demo |
| `/api/v1/models` | GET | 模型列表 | 🟢 |
| `/api/v1/admin/formula-params` | GET/PUT | 公式参数 | 🟢 |
| `/health` | GET | 健康检查 | 🟢 |

完整API文档: http://localhost:8000/docs

## 技术栈

| 层次 | 技术 |
|------|------|
| 后端 | FastAPI + Python 3.12 + SQLAlchemy 2.0 + Celery |
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS |
| LLM | LiteLLM → Ollama/vLLM(本地) + OpenAI/Anthropic(远程) |
| 数据库 | PostgreSQL 15 + Qdrant + MinIO + Redis |
| 部署 | Docker Compose / Kubernetes |

## 开发

```bash
# 后端测试
cd api && source .venv/bin/activate
pytest

# 代码检查
ruff check app/

# 前端开发
cd frontend && npm run dev
```

## 许可证

内部项目，未公开发布。
