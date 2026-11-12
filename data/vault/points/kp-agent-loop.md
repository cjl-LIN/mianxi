---
id: kp-agent-loop
title: "Agent Loop（代理循环）"
aliases:
  - "代理循环"
  - "ReAct"
tags:
  - "智能体"
  - "机制"
projects:
  - "proj-ai-pm"
  - "proj-ai-fe"
sources:
  - "seed:v0.2"
created: 2026-11-12
prerequisite:
  - "kp-context"
related:
  - "kp-rag"
part_of: []
keywords:
  - "观察"
  - "推理"
  - "行动"
  - "工具"
  - "停止条件"
  - "状态"
  - "循环"
questions:
  - "请解释 Agent Loop 和一次普通大模型调用的本质区别，并说明循环里至少要有哪些状态。"
  - "如果客服 Agent 连续三轮都没解决问题，停止条件、升级策略和用户能看见的反馈你怎么设计？"
outline: "Agent Loop 是把观察、推理、行动串成循环，行动常常是调用工具，并把新的结果写回状态。因为没有停止条件，所以循环会一直转。例如步数上限、任务完成或升级人工都要事先写好。如果三轮失败，首先保留已尝试路径，然后告诉用户。"
match:
  - "agent loop"
  - "代理循环"
  - "agent"
fallback: false
---

Agent Loop 是智能体把一次任务跑成闭环的方式：观察当前状态，推理下一步，执行行动（直接回答或调用工具），再把新的观察写回状态，直到停止条件成立。

一次普通的大模型调用没有可重复的状态，也没有义务决定还要不要继续。循环里至少要能回答：现在知道什么、下一步做什么、做完如何判断结束。

失败时留下已尝试的路径，避免下一轮从零开始。工具怎么接进来见 [[kp-mcp|MCP]]，动作本身见 [[kp-skill|Skill]]，上下文怎么裁见 [[kp-context|上下文工程]]。
