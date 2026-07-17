# PaperFeed

[![CI](https://github.com/JunbaoLiang/paperfeed/actions/workflows/ci.yml/badge.svg)](https://github.com/JunbaoLiang/paperfeed/actions/workflows/ci.yml)
[![Daily pipeline](https://github.com/JunbaoLiang/paperfeed/actions/workflows/daily.yml/badge.svg)](https://github.com/JunbaoLiang/paperfeed/actions/workflows/daily.yml)

个人 arXiv 论文推荐系统 — 展示**完整 ML 生命周期**的作品集项目:数据管道 → 特征 → 训练 → 评估 → 部署 → 监控 → 自动迭代,全部跑在免费额度内。

**🔗 在线地址:[paperfeed-mauve.vercel.app](https://paperfeed-mauve.vercel.app)** · [运行统计](https://paperfeed-mauve.vercel.app/stats) · [API 健康检查](https://paperfeed.onrender.com/healthz)

每天自动抓取 cs.LG / cs.AI / cs.CL / stat.ML 新论文,根据行为反馈(点击 / 收藏 / 点踩 / 停留)持续学习偏好,以信息流形式推送。

## 核心设计

- **Training-serving 一致性**:特征计算只有一份实现(`packages/core/features.py`);在线打分时把特征快照写进 `impressions.features`,训练直接读快照、禁止重算;
- **自动模型迭代闭环**:曝光攒够 2000 条后,每周自动训练 LightGBM lambdarank → 时间切分离线评估(NDCG@10 对比规则基线,+5% 才晋级)→ team-draft interleaving 线上对比(点击占比 >52% 自动升 production)→ 在线服务 10 分钟内热加载新模型;
- **推理成本意识**:在线镜像不装 torch——SPECTER2 向量化全部离线做,画像向量预计算入库,在线召回只是 pgvector 查询;
- **位置偏差处理**:position 仅作训练特征,推理时固定为常数。

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
| 前端 | Next.js 16 (App Router) + Tailwind + recharts @ Vercel |
| 在线 API | FastAPI @ Render 免费层(Docker,无 torch 轻量镜像) |
| 数据库 | Neon Postgres + pgvector(业务数据 + HNSW 向量检索 + MLflow backend 一库三用) |
| Embedding | SPECTER2(论文专用模型,768 维,CPU 离线推理) |
| 排序 | 规则打分(V0)→ LightGBM lambdarank(V2+,label_gain=[0,1,3]) |
| 召回 | 四路:pgvector 语义 / 引文图 / 新鲜度 / 探索,MMR 重排 |
| 实验追踪 | MLflow(backend = Neon,artifacts = Cloudflare R2) |
| 定时任务 | GitHub Actions scheduled workflows |
| Python 工具链 | uv + ruff + pytest + pydantic v2 + SQLAlchemy 2.0 + Alembic |

## ML 迭代路线

| 版本 | 内容 | 状态 |
|------|------|------|
| V0 | 规则打分(相似度 + 新鲜度 + 引用量),上线攒数据 | ✅ 已上线(2026-07) |
| V1 | 画像自学习:行为加权 + 30 天半衰期时间衰减 | ✅ 已上线 |
| V2 | LightGBM lambdarank 排序 | ⏳ 等累计 impressions ≥ 2000 自动触发 |
| V3 | 周自动再训练 + interleaving 在线对比 | 代码就绪,随 V2 启用 |
| V4 | 序列模型 vs LightGBM 离线对比实验 | 等样本 ≥ 1 万 |

## 实验结果

> 占位:线上数据积累中,V2 首次训练后填入。

| 模型 | NDCG@10 | AUC | Recall@20 | 线上 CTR |
|------|---------|-----|-----------|----------|
| rule-v0(基线) | – | – | – | – |
| lgbm-\*(挑战者) | – | – | – | – |

## Monorepo 结构

```
apps/web/          Next.js 前端(Feed / Saved / Stats / Onboarding + 埋点)
services/api/      FastAPI 在线服务(四路召回→特征→打分→MMR→曝光落库)
pipelines/         离线任务,每个可独立运行:python -m pipelines.<name>
packages/core/     共享:ORM 模型、特征定义(在线离线唯一实现)、画像与规则打分
migrations/        Alembic
.github/workflows/ ci / daily(数据管道)/ weekly_train(训练链)
docs/DEPLOY.md     从零部署指南(Neon / R2 / Render / Vercel)
paperfeed_spec.md  实施规格(唯一需求源,含 ADR 与修订记录)
```

## 本地开发

```bash
uv sync --extra pipelines          # 含离线管道依赖(torch CPU 版)
cp .env.example .env               # 填 DATABASE_URL 等
uv run alembic upgrade head        # 初始化 schema(含 pgvector)
uv run python -m pipelines.ingest  # 手动跑一次抓取
uv run uvicorn services.api.app.main:app --reload   # 在线服务
cd apps/web && npm install && npm run dev            # 前端
```

测试与检查:

```bash
uv run pytest        # 48 项:特征/画像/MMR/interleaving/标签/评估指标 + 合成数据全链路
uv run ruff check .
```

## 工程规范

- 离线任务幂等可重跑、结构化 JSON 日志、失败非零退出触发 Actions 报警;对外部 API(arXiv / Semantic Scholar)限速礼貌重试,瞬时故障跳过自愈;
- 全量 type hints,pydantic 校验一切外部输入,数据库操作走 SQLAlchemy(pgvector 检索参数化);
- 密钥零硬编码,全部经 GitHub Secrets / Render / Vercel 环境变量注入;
- 规格驱动:`paperfeed_spec.md` 是唯一需求源,偏离处以 `SPEC-GAP:` 注释标注,平台变更记入 ADR 修订(见 spec §15)。
