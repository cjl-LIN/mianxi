---
id: kp-context
title: "上下文工程"
aliases:
  - "Context Engineering"
  - "提示词与上下文"
tags:
  - "上下文"
  - "提示词"
projects:
  - "proj-ai-pm"
  - "proj-ai-fe"
sources:
  - "seed:v0.2"
created: 2026-11-12
prerequisite: []
related: []
part_of: []
keywords:
  - "上下文"
  - "优先级"
  - "压缩"
  - "系统提示"
  - "冲突"
  - "最近一轮"
questions:
  - "上下文窗口有限时，你会按什么优先级保留信息？请结合一场多轮面试说明。"
  - "系统提示、检索片段和候选人刚才的回答冲突时，以谁为准？"
outline: "上下文要排优先级：最近一轮问答、评分规则、检索片段，更早的寒暄可以压缩。因为窗口有限，所以不能把历史原样堆进去。例如三轮之前的寒暄收成一句。如果系统提示和候选人的事实冲突，安全边界以系统提示为准，事实以可信来源为准。"
match:
  - "上下文"
  - "context engineering"
fallback: false
---

上下文工程决定这一轮模型真正看见什么。优先级一般是：当前问题与最近一轮回答、必须遵守的规则、检索到的片段，然后才是更早的寒暄。超长时做压缩，而不是丢掉最近一轮。

冲突时，安全与角色边界以系统提示为准，事实以可信知识源为准，对话目标以候选人刚刚的澄清为准。Agent Loop 依赖它来保持状态可读，见 [[kp-agent-loop|Agent Loop]]。
