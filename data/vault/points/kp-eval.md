---
id: kp-eval
title: "评测与标注"
aliases:
  - "Evaluation"
  - "标注"
  - "评估集"
tags:
  - "评测"
  - "质量"
projects:
  - "proj-ai-pm"
sources:
  - "seed:v0.2"
created: 2026-11-12
prerequisite: []
related:
  - "kp-agent-loop"
  - "kp-metrics"
part_of: []
keywords:
  - "评测集"
  - "标注"
  - "维度"
  - "锚点"
  - "一致率"
  - "回归"
questions:
  - "给面试回答打分，为什么不能只看像不像标准答案？你会设计哪些维度，又如何让标注一致？"
  - "提示词改了一版之后，你如何用评测集防止能力回退？"
outline: "开放式回答要拆维度，而不是看像不像标准答案。因为标注员会分歧，所以每个维度要有锚点例，并先量一致率。例如相关、正确、完整、推理四档。如果改了提示词，就用固定评测集做回归，下降超过阈值就不发。"
match:
  - "评测"
  - "标注"
  - "evaluation"
fallback: false
---

开放式回答不要用「像不像范文」做唯一标准。把分数拆成相关性、正确性、完整度、推理，并为每个维度写锚点例。先做小范围双人标注，量一致率，分歧写进指南。

上线前留一份黄金评测集。提示词或模型一改就回归，下降超过阈值就不发。它用来判断 [[kp-agent-loop|Agent Loop]] 是不是真的变好。
