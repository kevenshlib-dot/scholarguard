# ScholarGuard 学术卫士

> 以LLM为核心推理引擎、面向中文学术写作与学术诚信治理的模块化平台

## 项目状态

**当前版本**: Phase 1 MVP (开发中)
**设计版本**: v2.0
**检测体系**: 双指标体系 — AI特征占比(NHPR)为主 + AI相似度为辅

## 核心特性

### 双指标检测体系

ScholarGuard 采用独创的**双指标体系**进行AI内容检测，区别于市场上所有竞品的单一概率评分：

| 指标 | 类型 | 说明 |
|------|------|------|
| **AI特征占比 (NHPR)** | 主要指标 | 衡量文本中检测到具有AI生成特征的片段比例。基于困惑度平滑性、token概率分布、结构模板化、连接词密度、段落均匀性等客观统计特征，可解释性强。 |
| **AI相似度** | 辅助参考 | 传统AI生成概率估计（LLM置信度+统计分加权融合）。存在固有不确定性，不作为单一判定依据，附带不确定性声明。 |

**NHPR 风险等级**:

| NHPR | 等级 | 含义 |
|------|------|------|
| < 20% | low | 基本无AI特征，符合人类写作模式 |
| 20%-40% | medium | 存在部分AI特征，建议关注 |
| 40%-60% | high | 较多AI特征，建议人工复核 |
| > 60% | critical | 大量AI特征，高度疑似AI生成 |

**NHPR 计算公式**:
```
NHPR = 0.30 × FlaggedSegmentCoverage     # 可疑片段文本覆盖率
     + 0.25 × PatternFlagsIntensity       # 模式标志强度
     + 0.25 × StatisticalScore            # 统计特征分数
     + 0.20 × NonHumanSourceProb          # 来源分类非人概率

若LLM提供直接估计: NHPR = 0.40×LLM_NHPR + 0.60×Computed_NHPR
```

### AI特征模式类型

每个可疑片段会标注具体的AI特征类型：

| 类型 | 说明 |
|------|------|
| `perplexity_smooth` | 困惑度平滑 — 各句困惑度异常均匀，缺乏人类写作的自然波动 |
| `token_concentrated` | token概率集中 — 倾向高概率词选择，缺少低频词/口语化表达 |
| `structure_templated` | 模板化结构 — 固定的"首先…其次…最后"等套路 |
| `connector_overuse` | 连接词过度使用 — 学术连接词密度异常 |
| `uniformity` | 均匀性 — 段落长度、句式复杂度过于一致 |

### 其他功能

- **多粒度检测**: 整文 / 段落 / 句子级别
- **多学科支持**: 政治学、经济学、社会学、法学、通用
- **中英文支持**: 自动语言检测
- **写作优化建议**: 表达自然化、论证补强、结构优化
- **人工复核与申诉**: Human-in-the-loop 工作流
- **管理后台**: 模型配置、公式参数调优、审计日志
- **PDF报告**: 可下载的完整检测报告

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

### 5. 启动Celery Worker

```bash
cd api
source .venv/bin/activate
celery -A app.worker worker --loglevel=info --concurrency=2
```

### 6. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端访问: http://localhost:3000

### 7. 一键启动（全部容器化）

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
│   │   ├── worker.py           # Celery 应用配置
│   │   ├── middleware/         # 认证、限流
│   │   ├── routers/            # API路由 (detect/suggest/review/research/admin)
│   │   ├── services/
│   │   │   ├── detection/      # 检测引擎 (核心)
│   │   │   │   ├── engine.py   # 检测主流程 + NHPR计算
│   │   │   │   ├── fusion.py   # 证据融合器
│   │   │   │   ├── stats.py    # 轻量统计因子计算器
│   │   │   │   └── preprocessor.py  # 文本预处理
│   │   │   ├── suggestion/     # 写作建议
│   │   │   ├── review/         # 复核与申诉
│   │   │   ├── llm_gateway/    # LLM统一网关 (LiteLLM)
│   │   │   ├── research/       # 文献研究 (Demo)
│   │   │   └── translation/    # 翻译润色 (预留)
│   │   ├── models/             # SQLAlchemy ORM
│   │   ├── schemas/            # Pydantic 数据验证
│   │   ├── prompts/            # LLM Prompt 模板库
│   │   └── tasks/              # Celery异步任务
│   ├── migrations/             # Alembic 数据库迁移
│   └── tests/
├── frontend/                   # 前端 (React 18 + TypeScript + Vite)
│   └── src/
│       ├── pages/detect/       # 检测页 + 检测报告页
│       ├── pages/suggest/      # 写作建议页
│       ├── pages/admin/        # 管理后台
│       ├── components/         # 通用组件
│       └── services/api.ts     # API调用层
├── knowledge_base/             # 社科术语库
├── eval/                       # 评测框架
├── docker-compose.yml          # 容器编排
└── .env.example                # 环境变量模板
```

## 核心架构

```
用户 → [统一工作台] → [API网关(FastAPI)]
                           ↓
              ┌─── 核心检测流水线 ────────────────────────┐
              │ 预处理 → LLM评议(含NHPR分析) → 统计因子   │
              │              ↓                            │
              │      NHPR计算(主要指标)                    │
              │    + 证据融合(辅助AI相似度)                 │
              │              ↓                            │
              │         报告生成器                         │
              └──────────────────────────────────────────┘
                           ↓
              [LLM网关(LiteLLM)] → Ollama/vLLM(本地) | Gemini/OpenAI/Anthropic(远程)
                           ↓
              [PostgreSQL + Qdrant + MinIO + Redis]
```

## 检测引擎流水线

```
文本输入 → 预处理 → E1:LLM评议(含NHPR) → E2:统计因子 → NHPR计算 + 证据融合 → 报告
                                                            ↑
                                           E3:材料证据(预留) + E4:人工证据(复核)
```

**双指标输出**:
- **NHPR (主要)**: `0.30×片段覆盖率 + 0.25×模式标志 + 0.25×统计分 + 0.20×来源分类`
- **AI相似度 (辅助)**: `w1×LLMConfidence + w2×StatScore` (白箱可见、参数可配置)

参数可配置、版本化、支持回滚。管理后台可调整所有权重和阈值。

## API端点

| 端点 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/api/v1/detect` | POST | 提交AI检测（返回NHPR+AI相似度） | ✅ |
| `/api/v1/detect/{task_id}` | GET | 查询检测结果 | ✅ |
| `/api/v1/detect/{task_id}/heatmap` | POST | 生成段落热力图 | ✅ |
| `/api/v1/detect/batch` | POST | 批量检测 | ✅ |
| `/api/v1/suggest` | POST | 获取写作建议 | ✅ |
| `/api/v1/feedback` | POST | 提交反馈 | ✅ |
| `/api/v1/reviews` | GET | 复核列表 | ✅ |
| `/api/v1/reviews/{id}/decide` | POST | 提交复核决定 | ✅ |
| `/api/v1/research/search` | POST | 文献检索 | Demo |
| `/api/v1/models/config` | GET/PUT | 模型配置 | ✅ |
| `/api/v1/models/test` | POST | 测试模型连接 | ✅ |
| `/api/v1/admin/formula-params` | GET/PUT | 公式参数 | ✅ |
| `/api/v1/admin/audit-logs` | GET | 审计日志 | ✅ |
| `/api/v1/admin/users` | GET | 用户管理 | ✅ |
| `/health` | GET | 健康检查 | ✅ |

完整API文档: http://localhost:8000/docs

## 模型配置

支持本地和远程LLM模型，通过管理后台动态配置：

| 模型 | 类型 | 配置方式 |
|------|------|---------|
| Ollama (qwen2.5等) | 本地 | 设置 Ollama 服务地址 |
| vLLM (自部署) | 本地 | 设置 vLLM 服务地址 |
| Gemini 2.5 Pro/Flash | 远程 | 配置 Google API Key |
| OpenAI GPT-4o | 远程 | 配置 OpenAI API Key |
| Anthropic Claude | 远程 | 配置 Anthropic API Key |

API密钥通过 Redis 跨进程持久化存储，Celery Worker 可实时读取最新配置。

## 技术栈

| 层次 | 技术 |
|------|------|
| 后端 | FastAPI + Python 3.12 + SQLAlchemy 2.0 + Celery |
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS |
| LLM | LiteLLM → Ollama/vLLM(本地) + Gemini/OpenAI/Anthropic(远程) |
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

# 前端构建
cd frontend && npm run build
```

## 数据库迁移

```bash
cd api && source .venv/bin/activate

# 查看当前版本
alembic current

# 升级到最新
alembic upgrade head

# 查看迁移历史
alembic history
```

## 许可证

内部项目，未公开发布。
