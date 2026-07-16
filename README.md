# PaperFeed

个人 arXiv 论文推荐系统 — 一个完整 ML 生命周期的作品集项目:**数据管道 → 特征 → 训练 → 评估 → 部署 → 监控 → 自动迭代**,全部跑在免费额度内。

每天自动抓取新论文,根据行为反馈(点击 / 收藏 / 点踩 / 停留)持续学习偏好,以信息流形式推送。

## 架构

```
[GitHub Actions cron]                          [Render 免费层]               [Vercel]
 ingest → enrich → embed ──┐                   FastAPI 在线服务              Next.js 前端
 profile_update (每日)      ├──▶ Neon Postgres ◀── 召回→特征→打分→MMR ◀────── 信息流 UI
 train → evaluate (每周)    │    (papers/向量/    │  写 impressions           埋点事件
        │                  │     事件/registry)  ◀──────────────────────────  /feedback
        ▼                  │
 Cloudflare R2 (模型文件) ──┘  在线服务按 model_registry 拉取 production 版本模型
```

数据闭环:前端曝光与反馈 → 事件表 → (每日)画像更新 / (每周)再训练 → 新模型注册 → 在线服务热加载 → 下一次请求生效。

## 技术栈

| 层 | 选择 |
|----|------|
| 前端 | Next.js (App Router) @ Vercel |
| 在线 API | FastAPI @ Render 免费层(Docker,无 torch,轻量镜像) |
| 数据库 | Neon Postgres + pgvector(业务数据 + 向量检索 + MLflow backend 一库三用) |
| Embedding | SPECTER2(论文专用,768 维,CPU 离线推理) |
| 排序 | 规则打分(V0)→ LightGBM lambdarank(V2+) |
| 实验追踪 | MLflow(backend = Neon,artifacts = Cloudflare R2) |
| 定时任务 | GitHub Actions scheduled workflows |
| Python 工具链 | uv + ruff + pytest + pydantic v2 + SQLAlchemy 2.0 + Alembic |

## Monorepo 结构

```
apps/web/          Next.js 前端(Feed / Saved / Stats / Onboarding)
services/api/      FastAPI 在线服务(召回→特征→打分→MMR→曝光落库)
pipelines/         离线任务(python -m pipelines.<name>)
packages/core/     共享:ORM 模型、特征定义(在线离线唯一实现)、配置
migrations/        Alembic
.github/workflows/ ci / daily(数据管道)/ weekly_train(训练链)
```

## 快速开始

```bash
# 1. 安装依赖(含离线管道)
uv sync --extra pipelines

# 2. 配置环境变量
cp .env.example .env   # 填入 Neon 的 DATABASE_URL 等

# 3. 初始化数据库
uv run alembic upgrade head

# 4. 抓取论文(首次)
uv run python -m pipelines.ingest
uv run python -m pipelines.enrich
uv run python -m pipelines.embed

# 5. 本地起在线服务
uv run uvicorn services.api.app.main:app --reload

# 6. 前端
cd apps/web && npm install && npm run dev
```

测试与检查:

```bash
uv run pytest
uv run ruff check .
```

## ML 迭代路线

| 版本 | 内容 | 进入条件 |
|------|------|----------|
| V0 | 规则打分,上线攒数据 | ✅ |
| V1 | 画像自学习(行为加权 + 时间衰减) | ✅ |
| V2 | LightGBM lambdarank 排序 | 累计 impressions ≥ 2000 |
| V3 | 周自动再训练 + interleaving 在线对比 | V2 离线胜出 |
| V4 | 序列模型 vs LightGBM 离线对比实验 | 样本 ≥ 1 万 |

## 实验结果

> 占位:待线上运行积累数据后填入(NDCG@10 / AUC / CTR 曲线 / interleaving 判定结论)。

| 模型 | NDCG@10 | AUC | Recall@20 | 线上 CTR |
|------|---------|-----|-----------|----------|
| rule-v0(基线) | – | – | – | – |
| lgbm-\* | – | – | – | – |

## 工程规范

- 特征计算只有一份实现(`packages/core/features.py`),在线打分时快照进 `impressions.features`,训练直接读快照——保证 training-serving 一致性;
- 在线服务镜像不含 torch(`services/api/Dockerfile` 只装基础依赖组);
- 核心逻辑(特征、画像更新、MMR、interleaving、样本构造、评估指标)全部有单元测试;
- 离线任务全部幂等可重跑,结构化 JSON 日志,失败非零退出触发 Actions 报警。

## 部署

需要手动创建的资源:Neon 项目、HF Space(Docker)、Cloudflare R2 bucket `paperfeed-mlflow`、Vercel 项目,以及对应的 GitHub Secrets。**逐步指南见 [docs/DEPLOY.md](docs/DEPLOY.md)。**
