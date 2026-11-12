---
id: kp-role-proj-ai-fe
title: "岗位理解：AI Native 前端"
aliases:
  - "AI Native 前端岗位"
tags:
  - "岗位"
projects:
  - "proj-ai-fe"
sources:
  - "seed:v0.2"
created: 2026-11-12
prerequisite: []
related:
  - "kp-streaming-ui"
part_of: []
keywords:
  - "流式"
  - "取消"
  - "幂等"
  - "空状态"
  - "工具状态"
questions:
  - "这个前端岗位最容易被忽视的体验问题是什么？你用哪段经历证明你处理过。"
  - "如果两周只能补三块，你如何在流式、工具状态和失败态之间排优先级？"
outline: "这个岗位要把流式、取消、工具状态和幂等写回做成可验收的界面。因为生成会被打断，所以过期响应不能写进新的一轮。例如空状态和错误态要和主路径一起交，而不是等视觉稿。如果只演示能打字发送，面试官会继续追问超时之后怎么办。"
match: []
fallback: false
---

这个岗位把 Agent 的状态翻译成候选人看得懂的界面：流式输出、可取消、工具状态可见，以及评分写回的幂等。

准备一个你处理过的失败态。空状态、长回答和超时重试要比动画更重要。
