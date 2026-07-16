# PaperFeed — 个人 arXiv 论文推荐系统 · 实施规格 v1.0

> **给 Claude Code 的说明**:本文档是唯一需求来源。请严格按第 12 节的里程碑顺序实施,每个里程碑完成后运行其验收标准再进入下一个。遇到本文档未覆盖的细节,选择最简单的实现并在代码注释中标注 `SPEC-GAP:`。**严格遵守第 14 节的禁止事项,不要过度工程。**

---

## 1. 项目目标与非目标

**这是什么**:一个单用户的 arXiv 论文推荐系统。每天自动抓取新论文,根据用户行为(点击/收藏/点踩/停留)持续学习偏好,以信息流形式推送。项目定位是 MLE 转行作品集,核心展示对象是**完整的 ML 生命周期**:数据管道 → 特征 → 训练 → 评估 → 部署 → 监控 → 自动迭代。

**目标**(按优先级):
1. 端到端闭环先跑通(V0 规则打分即可),尽早开始积累行为数据;
2. 事件日志带特征快照,保证 training-serving 一致性;
3. 可复现的实验体系:MLflow 追踪、时间切分离线评估、interleaving 在线对比;
4. 全部跑在免费额度内。

**非目标**(明确不做):多用户系统、注册登录、实时流处理、深度召回模型(V4 前)、论文全文解析、移动 App。

## 2. 技术栈与关键决策记录(ADR)

| # | 决策 | 选择 | 理由 |
|---|------|------|------|
| A1 | 前端 | Next.js 14+ (App Router) @ Vercel 免费层 | 部署零配置,单用户流量远在额度内 |
| A2 | 数据库 | Neon Postgres 免费层 + pgvector | 一库三用:业务数据、向量检索、MLflow backend |
| A3 | 在线 API | FastAPI @ Hugging Face Spaces (Docker Space, 免费 CPU) | 免费层 2 vCPU/16GB;Python 生态贴合 ML 服务 |
| A4 | 在线服务不加载 embedding 模型 | 画像向量预计算存库,召回仅需 pgvector 查询 | 在线镜像无 torch,启动快、内存小;体现推理成本意识 |
| A5 | 定时任务 | GitHub Actions scheduled workflows | 免费额度充足;抓取/向量化/再训练全部离线跑 |
| A6 | Embedding 模型 | `allenai/specter2_base` + `allenai/specter2` adapter,768 维,CPU 推理 | 论文专用模型(引文信号训练);每日数百篇 CPU 足够 |
| A7 | 排序模型 | 规则 → LightGBM(V2 起) | 单用户样本量小(月均 2-3k),强正则浅模型是正确取舍 |
| A8 | 实验追踪 | MLflow,backend store = Neon,artifact store = Cloudflare R2(S3 兼容,免费 10GB) | 零成本跑通工业标准 MLOps 工具链 |
| A9 | 引用数据 | Semantic Scholar Graph API(免费) | 提供 citation count、引文图召回所需的 references/citations |
| A10 | Python 工具链 | uv + ruff + pytest + pydantic v2 + SQLAlchemy 2.0 + Alembic | 现代标准配置 |
| A11 | 鉴权 | 单一 Bearer Token(环境变量) | 单用户,不做用户体系 |
| A12 | LLM 标注 | 延后至 M6 可选项(Claude Haiku 打结构化标签) | 非闭环必需,先不引入付费依赖 |

## 3. 系统架构总览

```
[GitHub Actions cron]                          [Hugging Face Spaces]        [Vercel]
 ingest → enrich → embed ──┐                   FastAPI 在线服务              Next.js 前端
 profile_update (每日)      ├──▶ Neon Postgres ◀── 召回→特征→打分→MMR ◀────── 信息流 UI
 train → evaluate (每周)    │    (papers/向量/    │  写 impressions           埋点事件
        │                  │     事件/registry)  ◀──────────────────────────  /feedback
        ▼                  │
 Cloudflare R2 (模型文件) ──┘  在线服务按 model_registry 拉取 production 版本模型
```

数据流閉环:前端曝光与反馈 → 事件表 → (每日)画像更新 / (每周)再训练 → 新模型注册 → 在线服务热加载 → 下一次请求生效。

## 4. Monorepo 目录结构

```
paperfeed/
├── apps/web/                  # Next.js 前端
├── services/api/              # FastAPI 在线服务(独立 Dockerfile,不含 torch)
│   ├── app/main.py
│   ├── app/routers/{feed,feedback,admin}.py
│   ├── app/recsys/{recall,features,scoring,rerank,interleave}.py
│   └── Dockerfile
├── pipelines/                 # 离线任务,每个是可独立运行的 python -m 入口
│   ├── ingest.py              # arXiv 抓取
│   ├── enrich.py              # Semantic Scholar 引用数据
│   ├── embed.py               # SPECTER2 向量化(仅此模块依赖 torch/adapters)
│   ├── profile_update.py      # 画像向量重算
│   ├── build_dataset.py       # 从事件日志构造训练样本
│   ├── train.py               # LightGBM 训练 + MLflow 记录
│   ├── evaluate.py            # 离线评估 + 达标自动注册 staging
│   └── metrics_rollup.py      # 每日指标汇总(CTR、drift)
├── packages/core/             # 共享:ORM 模型、特征定义、配置
│   ├── models.py              # SQLAlchemy 模型(唯一 schema 定义处)
│   ├── features.py            # 特征计算(在线离线共用同一份代码 — 一致性关键)
│   └── config.py              # pydantic-settings;含 ARXIV_CATEGORIES 等
├── migrations/                # Alembic
├── .github/workflows/
│   ├── ci.yml                 # ruff + pytest,PR 触发
│   ├── daily.yml              # cron '0 2 * * *':ingest→enrich→embed→profile_update→metrics_rollup
│   └── weekly_train.yml       # cron '0 3 * * 1':build_dataset→train→evaluate
├── pyproject.toml             # uv 管理;torch/adapters 放 [project.optional-dependencies] pipelines 组
└── README.md
```

**依赖隔离规则**:`services/api` 的依赖组禁止包含 torch、transformers、lightgbm 之外的重型库(lightgbm 推理需要);`pipelines` 组才装 torch。

## 5. 数据库 Schema(Alembic 初始迁移按此实现)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE papers (
  arxiv_id        TEXT PRIMARY KEY,          -- '2501.12345',不含版本后缀
  latest_version  INT NOT NULL DEFAULT 1,    -- v2 更新时 upsert 并 +1
  title           TEXT NOT NULL,
  abstract        TEXT NOT NULL,
  authors         JSONB NOT NULL,            -- [{"name": "..."}]
  categories      TEXT[] NOT NULL,
  primary_category TEXT NOT NULL,
  published_at    TIMESTAMPTZ NOT NULL,
  arxiv_updated_at TIMESTAMPTZ NOT NULL,
  pdf_url         TEXT,
  s2_paper_id     TEXT,
  citation_count  INT,
  citation_velocity REAL,                    -- 引用数 / 发布月数,enrich 计算
  embedding       vector(768),
  embedding_model TEXT,                      -- 'specter2@<adapter_rev>'
  created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_papers_emb ON papers USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_papers_pub ON papers (published_at DESC);

CREATE TABLE user_profile (
  profile_id      TEXT PRIMARY KEY DEFAULT 'default',
  embedding       vector(768),
  interaction_count INT DEFAULT 0,
  config          JSONB,                     -- 衰减参数覆盖、种子关键词
  updated_at      TIMESTAMPTZ
);

-- 一次刷新 = 一个 request_id;每个展示位一行,含打分时的完整特征快照
CREATE TABLE impressions (
  impression_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id      UUID NOT NULL,
  paper_id        TEXT NOT NULL REFERENCES papers(arxiv_id),
  position        INT NOT NULL,              -- 1-based
  recall_source   TEXT NOT NULL,             -- 'vector'|'graph'|'fresh'|'explore'
  model_version   TEXT NOT NULL,             -- 关联 model_registry.version
  score           REAL NOT NULL,
  features        JSONB NOT NULL,            -- 特征快照,训练时直接用,禁止事后重算
  interleave_arm  TEXT,                      -- 'prod'|'challenger'|NULL
  shown_at        TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_impr_time ON impressions (shown_at);
CREATE INDEX idx_impr_paper ON impressions (paper_id);

CREATE TABLE feedback (
  id              BIGSERIAL PRIMARY KEY,
  impression_id   UUID NOT NULL REFERENCES impressions(impression_id),
  event_type      TEXT NOT NULL,  -- 'visible'|'click_abstract'|'click_pdf'|'save'|'dismiss'|'dwell'
  value           REAL,           -- dwell 时为毫秒数,其余 NULL
  created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_fb_impr ON feedback (impression_id);

CREATE TABLE model_registry (
  version         TEXT PRIMARY KEY,          -- 'rule-v0' | 'lgbm-20260801-a1b2'
  model_type      TEXT NOT NULL,             -- 'rule'|'lightgbm'
  artifact_uri    TEXT,                      -- R2 s3:// 路径;rule 型为 NULL
  metrics         JSONB,                     -- {"ndcg@10": ..., "auc": ...}
  status          TEXT NOT NULL DEFAULT 'staging',  -- staging|production|archived
  created_at      TIMESTAMPTZ DEFAULT now()
);
-- 初始迁移中 INSERT ('rule-v0','rule',NULL,NULL,'production')

CREATE TABLE metrics_daily (
  day             DATE PRIMARY KEY,
  impressions     INT, clicks INT, saves INT, dismisses INT,
  ctr             REAL,
  profile_drift   REAL,   -- 当日画像与 30 天前画像的余弦距离
  model_version   TEXT
);
```

## 6. 离线管道规格(pipelines/)

所有任务:幂等可重跑、独立入口 `python -m pipelines.<name>`、结构化日志(json lines)、失败时非零退出让 Actions 报警。

### 6.1 ingest.py — arXiv 抓取(每日)
- 数据源:arXiv API `http://export.arxiv.org/api/query`,类目来自配置 `ARXIV_CATEGORIES`(默认 `cs.LG,cs.AI,cs.CL,stat.ML`)。
- 拉取近 3 天该类目论文(窗口冗余保证不漏),分页 100 条/页,**请求间隔 ≥3 秒**(arXiv 礼貌规则)。
- 按 arxiv_id(去版本号)UPSERT:已存在且 `arxiv_updated_at` 变新 → 更新字段、`latest_version+1`、**清空 embedding**(触发重新向量化)。
- 摘要清洗:去换行、合并空白、去 LaTeX 注释残留。

### 6.2 enrich.py — 引用数据(每日,跟在 ingest 后)
- Semantic Scholar Graph API,batch 端点每次 ≤100 个 ID,字段 `paperId,citationCount,references.paperId`。
- 刷新对象:发布 ≤180 天的论文。`citation_velocity = citation_count / max(发布月数, 0.5)`。
- 无 API key 时限速 1 req/s 并容忍 429(指数退避,最多 5 次);申请了 key(免费)则放 `S2_API_KEY`。
- 将 references 中**已在 papers 表内**的引用关系写入辅助表 `citations(src_id, dst_id, PRIMARY KEY(src_id,dst_id))`(在迁移中一并建表)。

### 6.3 embed.py — 向量化(每日)
- 对 `embedding IS NULL` 的论文,输入 `title + tokenizer.sep_token + abstract`,SPECTER2(base + proximity adapter),CPU,batch 32,向量 L2 归一化后入库。
- GitHub Actions 中用 `actions/cache` 缓存 `~/.cache/huggingface`(模型约 440MB,避免每次下载)。

### 6.4 profile_update.py — 画像重算(每日)
公式见 8.2。全量重算(单用户事件量小,不做增量),写回 user_profile。

### 6.5 build_dataset.py / train.py / evaluate.py — 每周训练链
见第 9 节。

### 6.6 metrics_rollup.py — 指标汇总(每日)
汇总前一日 impressions/feedback 写入 metrics_daily;profile_drift = 1 − cos(当前画像, 30 天前画像快照)(画像快照另存 `profile_history(day, embedding)` 表,迁移中建)。

## 7. 在线服务 API 规格(services/api)

所有端点要求 Header `Authorization: Bearer $API_TOKEN`。

### GET /feed?n=20
返回推荐流。内部流程:
1. **召回**(目标约 300 候选,去重,排除:已收藏、已 dismiss、近 72h 已曝光 ≥2 次的论文):
   - vector 路:pgvector 按画像向量余弦 top-200,限发布 ≤30 天;
   - graph 路:引用了"用户强正反馈论文集合"的论文,或与之共被引,top-50(用 citations 表 join);
   - fresh 路:近 48h 新论文按 citation_velocity top-50;
   - explore 路:近 7 天论文随机 30。
2. **特征拼装**:调 `packages/core/features.py`(特征表见 9.2)。
3. **打分**:按 model_registry 中 status='production' 的模型;若存在 status='staging' 且开启 interleaving(admin 开关),用 team-draft interleaving 混排两个模型的排序结果,每条记 interleave_arm。
4. **重排**:MMR(λ=0.7,相似度用 embedding 余弦)取 top n;第 15±2 位强制放 1 条 explore 路候选(如有)。
5. **写 impressions**(特征快照、score、position、recall_source、model_version、interleave_arm),同一事务。
6. 响应:`{request_id, items: [{impression_id, paper: {...}, position, reason}]}`。`reason` 为可解释文案:vector 路 → "与你收藏的《XX》相关"(取画像贡献最大的已收藏论文标题,简化实现:与该候选余弦最高的已收藏论文);graph 路 → "引用了你读过的《XX》";fresh → "今日新发布";explore → "探索推荐"。

### POST /feedback
Body `{impression_id, event_type, value?}`,校验 event_type 枚举,写 feedback 表。批量:接受数组。

### GET /saved · GET /stats
收藏列表;stats 返回 metrics_daily 近 90 天 + 当前 production/staging 模型信息(给前端 dashboard)。

### POST /admin/reload-model · POST /admin/interleave?on=true
重新从 registry 拉取 production/staging 模型(从 R2 下载到本地缓存);开关 interleaving。服务启动时及每 10 分钟轮询 registry 检查版本变化。

### 冷启动(interaction_count < 10 时)
/feed 降级为 fresh 路 + citation_velocity 排序。前端 Onboarding 引导用户输入 3-5 个关键词,`POST /admin/seed-profile` 将其存入 user_profile.config;次日的 profile_update 任务(离线,有 SPECTER2)将关键词编码为向量并取均值作为初始画像。前端提示"个性化推荐将于明日生效"。

## 8. 推荐算法规格

### 8.1 V0 规则打分(初始 production 模型 'rule-v0')
```
score = 0.60 · cos_sim(profile, paper)
      + 0.25 · exp(−hours_since_published / 72)
      + 0.15 · min(log1p(citation_count)/log1p(100), 1.0)
```
画像为空(冷启动)时 cos_sim 项取 0.5 常数。

### 8.2 画像向量更新
```
profile = normalize( Σ_i  w(type_i) · 0.5^(Δdays_i/30) · e_i )
w: save=+3.0, click_pdf=+2.0, click_abstract=+1.0, dwell>20s=+1.0(与click不重复计,取max), dismiss=−1.5
```
仅统计近 180 天事件;负权重项先聚合后参与求和,结果再归一化。

### 8.3 MMR 重排
`MMR(d) = λ·score(d) − (1−λ)·max_{s∈已选} cos(e_d, e_s)`,λ=0.7。同一 primary_category 连续出现 ≥3 条时跳选下一候选。

## 9. ML 迭代路线(V0→V4)

| 版本 | 内容 | 进入条件 |
|------|------|----------|
| V0 | 规则打分,上线攒数据 | M2 完成 |
| V1 | 画像自学习(8.2 已含) | M4 完成 |
| V2 | LightGBM 排序 | 累计 impressions ≥ 2000 |
| V3 | 周自动再训练 + interleaving 上线对比 | V2 离线胜出 |
| V4(可选) | 序列模型(SASRec 思路)vs LightGBM 对比实验 | 样本 ≥1 万,仅做离线对比写博客 |

### 9.1 样本构造(build_dataset.py)
- 单位:impression。标签:save/click_pdf → 2;click_abstract 或 dwell≥20000ms → 1;有 visible 但无交互 → 0;**无 visible 事件的 impression 丢弃**(未真实看到)。
- LightGBM 用 `label_gain=[0,1,3]` 的 lambdarank,`group` = request_id。
- 特征直接取 impressions.features 快照,**禁止重算**。

### 9.2 特征表(features.py 单一实现,在线离线共用)
| 特征 | 说明 |
|------|------|
| cos_profile | 画像余弦相似度 |
| hours_since_pub / log_citations / citation_velocity | 新鲜度与引用 |
| cat_match_cnt / primary_cat_is_top1 | 类目与用户高频类目匹配 |
| author_seen_cnt | 作者出现在正反馈论文中的次数 |
| max_sim_saved / mean_sim_last5_clicked | 与收藏集最大相似度 / 与最近5次点击均值相似度 |
| recall_source(one-hot 4 维) | 召回来源 |
| hour_of_day / is_weekend | 上下文 |
| position | **仅训练用**;推理时置常数 5(position-bias 处理) |

### 9.3 评估协议(evaluate.py)
- 切分:按时间,最后 14 天为验证集。指标:NDCG@10(主)、AUC、Recall@20。
- 基线对比:同一验证集上回放 rule-v0 公式得分。挑战者 NDCG@10 相对基线 **+5% 以上** → 自动注册 staging 并开启 interleaving。
- 在线判定:interleaving 累计 ≥200 次点击或满 14 天后,challenger 点击占比 >52% → 提升 production,否则 archived。判定由 weekly workflow 末尾一步自动执行并输出报告。
- 所有 run 记入 MLflow(参数、指标、特征重要性图、模型文件 → R2)。

## 10. 前端规格(apps/web)

页面:Feed(主页)、Saved、Stats、Onboarding(冷启动关键词引导,仅 interaction_count<10 时出现)。

Feed 卡片:标题、作者(截断)、类目 badge、摘要(默认折叠 3 行,点击展开=click_abstract)、推荐理由(reason)、按钮:收藏 / 不感兴趣 / PDF(新窗口=click_pdf)。

埋点:IntersectionObserver 曝光 ≥50% 且 ≥1s → `visible`;卡片展开到收起/离开视口的时长 → `dwell`;事件本地缓冲,`navigator.sendBeacon` 批量发 /feedback。API_TOKEN 经 Next.js API route 代理注入,不暴露给浏览器。

Stats 页:CTR 折线(近 90 天)、模型版本时间线、profile_drift 曲线,用 recharts。**此页是作品集截图素材,值得做整洁。**

## 11. MLOps 配置

- MLflow:`MLFLOW_TRACKING_URI = Neon 连接串(postgresql+psycopg://)`,artifact root `s3://paperfeed-mlflow`(R2 endpoint 经 `MLFLOW_S3_ENDPOINT_URL` 指定)。查看:本地 `mlflow ui --backend-store-uri $DATABASE_URL`。
- CI(ci.yml):ruff check + ruff format --check + pytest;PR 必须绿。
- 密钥全部走 GitHub Secrets / HF Spaces Secrets / Vercel env,代码中零硬编码。

## 12. 里程碑与验收标准(按序实施)

| 里程碑 | 内容 | 验收标准(DoD) |
|--------|------|----------------|
| M0 | repo 脚手架、pyproject(uv)、Alembic 初始迁移、ci.yml | `alembic upgrade head` 对 Neon 成功;CI 绿;README 含架构图 |
| M1 | ingest + enrich + embed + citations 表 + daily.yml | 手动触发 workflow 后:papers 有当日论文、embedding 非空、citations 有边;重跑无重复 |
| M2 | FastAPI:/feed(V0)+ /feedback + impressions 落库 + HF Spaces 部署 | curl /feed 返回 20 条且 DB 有对应 impressions(含特征快照);/feedback 写入成功 |
| M3 | Next.js 前端全部页面 + 埋点 + Vercel 部署 | 手机浏览器完整走通:刷 feed → 展开 → 收藏 → 事件入库可查 |
| M4 | profile_update + metrics_rollup 接入 daily.yml;冷启动引导 | 造 10 条正反馈后运行任务,画像非空且 /feed 排序明显偏向相关主题 |
| M5 | build_dataset/train/evaluate + MLflow + R2 + weekly_train.yml + interleaving + 模型热加载 | 用合成数据(测试 fixture 生成 3000 条 impressions)全链路跑通:训练→MLflow 有 run→staging 注册→interleaving 混排→判定脚本输出报告 |
| M6 | Stats 页、drift 展示、README 完善;可选:LLM 标签、周报邮件 | Stats 页可截图;README 含指标与实验结论占位 |

## 13. 环境变量与需要用户手动创建的资源

用户手动:Neon 项目(取 DATABASE_URL)、HF Space(Docker,绑 GitHub 自动部署或 workflow push)、Cloudflare R2 bucket `paperfeed-mlflow`(取 access key)、Vercel 项目、GitHub Secrets 配置。

```
DATABASE_URL, API_TOKEN(自生成随机串), S2_API_KEY(可选),
R2_ENDPOINT_URL, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
ARXIV_CATEGORIES(默认 cs.LG,cs.AI,cs.CL,stat.ML), HF_TOKEN(部署用)
```

## 14. 工程规范与禁止事项

规范:全量 type hints;pydantic 校验一切外部输入;核心逻辑(特征计算、样本构造、MMR、interleaving、画像更新)必须有单元测试;数据库操作走 SQLAlchemy,不拼 SQL 字符串(pgvector 检索可用原生 SQL 但需参数化)。

**禁止**(除非本文档修订):
- 不引入 LangChain/LlamaIndex/向量数据库 SaaS(pgvector 够用);
- 不引入消息队列、Redis、Celery(cron + 同步任务够用);
- 不拆微服务,在线服务保持单容器;
- 不做多用户/OAuth;
- 不在在线服务安装 torch;
- 不训练深度模型(V4 离线实验除外);
- 特征计算不允许出现第二份实现。

## 15. 修订记录
- v1.0(2026-07-14):初版,由项目讨论定稿。
- v1.1(2026-07-16):**A3 修订** — Hugging Face Spaces 取消免费 Docker Space(改为 PRO 专属),在线 API 托管改为 Render 免费层(Docker Web Service,`render.yaml`,push main 自动部署)。取舍:免费实例闲置 15 分钟休眠,冷启动约 1 分钟,单用户可接受。其余架构不变(容器内容、鉴权、端口均兼容)。
