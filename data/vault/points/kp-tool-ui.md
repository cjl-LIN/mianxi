---
id: kp-tool-ui
title: "工具调用的前端呈现"
aliases:
  - "Tool UI"
  - "工具状态"
tags:
  - "前端"
  - "工具"
projects:
  - "proj-ai-fe"
sources:
  - "seed:v0.2"
created: 2026-11-12
prerequisite: []
related:
  - "kp-skill"
  - "kp-mcp"
part_of: []
keywords:
  - "工具状态"
  - "可见"
  - "确认"
  - "折叠"
  - "写入"
  - "结论"
questions:
  - "面试官 Agent 在后台检索知识点时，界面对候选人应该展示到什么粒度？"
  - "写操作，例如更新掌握度，在前端上怎样防止误触？"
outline: "检索时展示轻量的工具状态，例如正在查阅哪个知识点，而不是把原始 JSON 甩给用户。因为写入会改掌握度，所以要单独确认，成功和失败都要可见。例如结束面试前再看一眼将要写回的分数。如果默认展开全部参数，候选人会失去对话本身。卡片可以折叠，默认只看结论。"
match:
  - "工具状态"
  - "tool ui"
fallback: false
---

检索可以展示「正在查阅：Agent Loop」这种轻状态。写操作要放在明确的动作里，例如结束面试后的确认，成功和失败都要看得见。

工具卡片默认可折叠，只留结论。它对应的后端能力是 [[kp-skill|Skill]] 和 [[kp-mcp|MCP]]。
