# 面习

本地优先的面试练习。粘贴一份岗位描述，建成一个项目，围绕知识点做模拟面试；分数写回掌握度。掌握度按知识点记一份，不按项目各记一份。

Mianxi is a local-first interview practice app. Paste a job description, keep knowledge as Markdown, run a mock interview, and review on a spaced schedule. No account and no hosted database.

## 跑起来

需要 Python 3.12+ 和 Node.js 22+。两个进程：

```bash
python3 -m venv apps/api/.venv
apps/api/.venv/bin/pip install -r apps/api/requirements.txt
apps/api/.venv/bin/uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8741
```

另开一个终端：

```bash
cd apps/web
npm install
npm run dev
```

也可以在仓库根目录一条命令启动（会自动建虚拟环境并安装依赖）：

```bash
./scripts/dev.sh
```

- 网页：<http://127.0.0.1:43123>
- API：<http://127.0.0.1:8741>
- API 文档：<http://127.0.0.1:8741/docs>

打开网页后，进入「AI 产品经理」或「AI Native 前端」，开始一场模拟面试。没有模型密钥时，面试官使用内置脚本，结束时仍会打分并更新掌握度。

Run the API on port 8741 and the web app on port 43123. The web dev server proxies `/api` to the API. Open http://127.0.0.1:43123 .

## 第一次会看到什么

启动时如果数据库是空的，会写入两个演示项目，以及三条演示掌握度：评测与标注今天到期，RAG 几天后复习，流式生成界面已掌握。所以总览和复习表不是空的。删掉 `data/app.db` 再启动会按种子重新生成。数据库文件不进 git。

演示项目共用 Agent Loop、MCP、Skill、上下文工程。在其中一个项目里掌握之后，另一个项目的模拟面试不再出这道题，只在到期复习时出现。

## 不配密钥也能用

复制 `.env.example` 为 `.env` 只在你要接模型或检索时需要。

| 变量 | 作用 |
| --- | --- |
| `OPENAI_API_KEY` 或 `INTERVIEW_LLM_API_KEY` | 追问和评分改走兼容 OpenAI 的接口。失败时退回脚本。 |
| `OPENAI_BASE_URL` / `OPENAI_MODEL` | 接口地址和模型名，默认 `https://api.openai.com/v1` 与 `gpt-4o-mini`。 |
| `TAVILY_API_KEY` | 「按 JD 补齐知识点」时额外检索。没有密钥就只用本地笔记。 |

## 试一条导入

项目页可以上传 `data/vault/samples/sample-import.md`。支持 txt、md，以及带文字层的 pdf。

## 测试

```bash
cd apps/api
.venv/bin/python -m pytest -q
```

## 文档

- [口述 PRD v0.1](docs/prd/v0.1.md)
- [当前 PRD v0.2](docs/prd/v0.2.md)
- [架构](docs/architecture.md)
- [知识库说明](data/vault/README.md)
