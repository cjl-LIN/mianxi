---
id: kp-mcp
title: "MCP（模型上下文协议）"
aliases:
  - "Model Context Protocol"
  - "模型上下文协议"
tags:
  - "协议"
  - "工具"
projects:
  - "proj-ai-pm"
  - "proj-ai-fe"
sources:
  - "seed:v0.2"
created: 2026-11-12
prerequisite: []
related:
  - "kp-skill"
  - "kp-agent-loop"
part_of: []
keywords:
  - "协议"
  - "客户端"
  - "服务端"
  - "工具"
  - "资源"
  - "权限"
  - "标准接口"
questions:
  - "MCP 解决的是什么问题？它和每个产品各写一套工具插件相比，产品上的收益是什么？"
  - "如果面试练习产品要通过 MCP 暴露「检索知识点」和「写入复习结果」，你怎么划分工具、资源和权限？"
outline: "MCP 用统一协议把工具和资源从客户端接到服务端，换模型时不用重写集成。因为写入有副作用，所以权限要比只读资源更高。例如检索知识点是资源，更新掌握度是工具。如果没有标准接口，每个宿主都会各做一套插件。"
match:
  - "mcp"
  - "模型上下文协议"
fallback: false
---

MCP 把模型可用的工具、资源和提示词收成一套协议。客户端是宿主，服务端提供能力，两边通过标准接口说话，而不是每个产品各写一套插件。

只读的资料适合做成资源；会改数据的动作做成工具，并给更高的确认门槛。和循环的关系是：循环决定何时行动，MCP 决定行动如何被安全地接进来。参见 [[kp-skill|Skill]]。
