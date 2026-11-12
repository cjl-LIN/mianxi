# 面习架构

本地两个进程，加一个 SQLite 文件和一份 Obsidian 仓库。网页不直接读笔记。

## 目录

```text
apps/api        FastAPI。启动时建表、写入演示项目、把仓库投影进 SQLite
apps/web        Vite + React + TypeScript
data/app.db     运行时生成，不提交
data/vault      知识库。points/ 提交，inbox/ 与 generated/ 只提交目录
docs            PRD 与本篇
scripts/dev.sh  同时启动 API 和网页
```

## 怎么跑

```bash
apps/api/.venv/bin/uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8741
```

```bash
cd apps/web && npm run dev
```

网页固定在 43123，并把 `/api` 代理到 8741。一条命令是 `./scripts/dev.sh`。

测试：

```bash
cd apps/api && .venv/bin/python -m pytest -q
```

## 启动时做什么

1. 执行 `apps/api/app/schema.sql`（只建不存在的表）
2. 若演示项目不存在则插入「AI 产品经理」「AI Native 前端」
3. 扫描 `data/vault/points`、`inbox`、`generated` 里的 Markdown，更新知识点投影和从该笔记声明的边
4. 若掌握度表是空的，写入三条演示记录和对应提醒

笔记是内容的来源。应用里关联或取消关联项目时，会同时改数据库和笔记 frontmatter 的 `projects`。启动同步只会把 frontmatter 里的项目合并进数据库，不会因为你在应用里多关联了一个项目就把这条关联删掉。

## 表

| 表 | 作用 |
| --- | --- |
| `projects` | 项目名称、方向、JD |
| `knowledge_points` | 笔记投影：标题、别名、关键词、问题、提纲、正文路径 |
| `project_knowledge` | 知识点与项目的多对多 |
| `knowledge_edges` | `from_id` 的笔记把 `to_id` 标成 prerequisite / related / part_of |
| `sessions` / `messages` | 一场面试和逐条发言。候选人消息有 `modality` |
| `answer_scores` | 四项分数和错漏、更好的讲法 |
| `mastery` | 每个知识点一行 |
| `reminders` | 聊天式提醒：缺口或到期复习 |

关系查询示例：

```sql
SELECT e.to_id, kp.title
FROM knowledge_edges e
JOIN knowledge_points kp ON kp.id = e.to_id
WHERE e.from_id = 'kp-agent-loop' AND e.relation = 'prerequisite';
```

`prerequisite` 的含义是：`to_id` 是 `from_id` 的前置。`part_of` 是 `from_id` 属于 `to_id`。相关边两个方向都算数，图上只画声明过的那一条，避免双向各画一根。

## 掌握度

模拟面试的选题会跳过等级为 `mastered` 或 `fluent` 的点。复习场次可以指定它们。评分写回的永远是 `mastery.knowledge_id` 这一行，所以两个项目看到的是同一份分数。

间隔见 [v0.2](prd/v0.2.md)。时区是 Asia/Shanghai。

## API

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/api/health` | 进程、是否接了模型、知识点数量 |
| GET/POST | `/api/projects` | 列表，或从名称和 JD 创建 |
| GET/DELETE | `/api/projects/{id}` | 详情（含选题计划）或删除 |
| POST | `/api/projects/{id}/collect` | 按 JD 匹配本地笔记，可选检索 |
| POST | `/api/projects/{id}/link` | 把已有知识点挂到项目 |
| POST | `/api/projects/{id}/unlink` | 取消挂接 |
| GET | `/api/knowledge` | 搜索。`unlinked=1` 时排除已挂上的 |
| GET | `/api/knowledge/{id}` | 正文、关系和掌握度 |
| GET | `/api/graph` | 节点和边，可按项目 |
| POST | `/api/ingest` | `multipart`：`project_id` + `file` |
| POST | `/api/sessions` | `{project_id, style, mode, knowledge_ids}` |
| GET | `/api/sessions/{id}` | 对话、当前题、已有报告 |
| POST | `/api/sessions/{id}/turn` | `{content, modality}` |
| POST | `/api/sessions/{id}/finish` | 评分并更新掌握度。重复调用不重复记分 |
| GET | `/api/dashboard` | 今日掌握、练习量、缺口、提醒 |
| GET | `/api/reviews` | `filter=due\|overdue\|today\|upcoming\|unscheduled\|all` |
| GET | `/api/history` | `sort` 为 time / overall / relevance / correctness / completeness / reasoning |
| GET/POST | `/api/reminders` | `scope=due\|open`；`POST /{id}/dismiss` 标成已读 |

## 模型与检索

`apps/api/app/llm.py` 读取环境变量。模型请求发到 `OPENAI_BASE_URL/chat/completions`。检索请求发到 Tavily。两者都超时失败时，面试和采集继续走本地逻辑。

内置评分看关键词覆盖、篇幅、以及「因为 / 所以 / 例如」这类推理标记。它用来保证没有密钥时流程是通的，不是正式的阅卷模型。

## 语音

`messages.modality` 为 `text` 或 `voice`。网页上的勾选只是把转写标成 voice。下一步接麦克风时，把识别结果送到同一个 `turn` 接口即可，不必新开一套评分。

## 种子

`data/vault/points` 里是提交的笔记。`scripts/gen_seed_vault.py` 会覆盖这个目录，只在要重做种子时运行。演示项目的 id 是 `proj-ai-pm` 和 `proj-ai-fe`。
