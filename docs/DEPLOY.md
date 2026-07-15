# 部署指南

全部资源都在免费额度内。按顺序执行一次即可,之后由 GitHub Actions 自动运转。

## 1. Neon(数据库)

1. 在 [neon.tech](https://neon.tech) 创建项目(免费层),复制连接串(形如 `postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require`)。
2. 本地初始化 schema:

```bash
cp .env.example .env        # 填入 DATABASE_URL
uv sync --extra pipelines
uv run alembic upgrade head
```

3. 首次灌数据(也可以直接手动触发 daily workflow):

```bash
uv run python -m pipelines.ingest
uv run python -m pipelines.enrich
uv run python -m pipelines.embed     # 首次会下载 SPECTER2(~440MB)
```

## 2. Cloudflare R2(模型与 MLflow artifacts)

1. R2 控制台创建 bucket:`paperfeed-mlflow`。
2. 创建 API Token(Object Read & Write),记下 `Access Key ID` / `Secret Access Key` 和 endpoint(`https://<account_id>.r2.cloudflarestorage.com`)。

## 3. GitHub 仓库配置

Settings → Secrets and variables → Actions:

| 类型 | 名称 | 值 |
|------|------|----|
| Secret | `DATABASE_URL` | Neon 连接串 |
| Secret | `S2_API_KEY` | (可选)Semantic Scholar key |
| Secret | `R2_ENDPOINT_URL` | R2 endpoint |
| Secret | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | R2 密钥 |
| Secret | `MLFLOW_TRACKING_URI` | (可选)不填则用 DATABASE_URL |
| Secret | `HF_TOKEN` | (用 Space 自动部署时)HF write token |
| Variable | `ARXIV_CATEGORIES` | 如 `cs.LG,cs.AI,cs.CL,stat.ML` |
| Variable | `HF_SPACE_ID` | 如 `yourname/paperfeed-api` |

推送后,手动触发一次 **Daily pipeline** workflow 验证 M1(papers 有当日论文、embedding 非空)。

## 4. Hugging Face Space(在线 API)

1. 创建 Space:类型 **Docker**,硬件 CPU basic(免费)。
2. Space Settings → Variables and secrets,添加:
   - `DATABASE_URL`(secret)
   - `API_TOKEN`(secret,自己生成随机串:`openssl rand -hex 32`)
   - `R2_ENDPOINT_URL` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`(secret,V2 模型热加载用)
3. 部署方式二选一:
   - 配好 `HF_SPACE_ID` + `HF_TOKEN` 后,GitHub 的 **Deploy API to HF Space** workflow 自动推送;
   - 或手动:`cp services/api/Dockerfile Dockerfile`,加上 Docker Space 的 README front-matter 后推到 Space 的 git。
4. 验证:`curl -H "Authorization: Bearer $API_TOKEN" https://<space>.hf.space/feed?n=20`。

## 5. Vercel(前端)

1. Import GitHub 仓库,**Root Directory 选 `apps/web`**。
2. 环境变量:
   - `PAPERFEED_API_URL` = HF Space 地址(如 `https://yourname-paperfeed-api.hf.space`)
   - `PAPERFEED_API_TOKEN` = 与 Space 相同的 API_TOKEN
3. Deploy,手机打开首页走通:刷 feed → 展开摘要 → 收藏 → 在 Neon 里查 `feedback` 表确认事件入库(M3 验收)。

## 6. MLflow 查看

```bash
MLFLOW_S3_ENDPOINT_URL=$R2_ENDPOINT_URL mlflow ui --backend-store-uri "$DATABASE_URL"
```

## 冷启动

前端首次使用会引导输入 3-5 个关键词(写入 `user_profile.config`),次日 daily pipeline 的 profile_update 将其编码为初始画像;交互满 10 次后自动切换为行为画像。
