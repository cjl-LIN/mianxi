# 面习知识库

这是一份本地 Obsidian 仓库。一个知识点就是一篇 Markdown，掌握度不写在笔记里，而写在 SQLite 的 `mastery` 表，并且按笔记 `id` 全局唯一。

## 笔记放哪里

- `points/`：随仓库提交的种子笔记
- `inbox/`：上传资料后生成的笔记（不提交内容）
- `generated/`：从 JD 或检索生成的笔记（不提交内容）
- `samples/`：用来试导入的样例，不会在启动时自动入库

## 一篇笔记

```yaml
---
id: kp-agent-loop
title: Agent Loop（代理循环）
aliases: [代理循环]
tags: [智能体]
projects: [proj-ai-pm, proj-ai-fe]
sources: ["seed:v0.2"]
created: 2026-11-12
prerequisite: [kp-context]
related: [kp-rag]
part_of: []
keywords: [观察, 推理]
questions:
  - 请解释循环和一次普通模型调用的差别。
outline: 用机制、边界和例子回答。
match: [agent]
fallback: false
---
```

正文里的 `[[kp-mcp|MCP]]` 会在启动同步时补成 `related` 边，前提是这对知识点之间还没有别的边。

关系方向以写在笔记上的字段为准：`prerequisite` 里列出的是这篇笔记的前置；`part_of` 是它属于谁；`related` 是相关。
