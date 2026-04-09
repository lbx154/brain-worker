"""
Brain-Worker Framework
======================
大模型规划 + 小模型执行的可插拔编排框架。

核心抽象:
  - Model:         模型调用适配器（Anthropic / OpenAI Responses / OpenAI Chat / 自定义）
  - Planner:       规划器 — 将任务拆解为步骤
  - Executor:      执行器 — 按指令执行单个步骤
  - Reviewer:      审查器 — 判断执行结果是否合格
  - Synthesizer:   整合器 — 将多步结果合并为最终成果
  - Orchestrator:  编排器 — 串联以上组件，驱动完整流程

用法:
    from brain_worker import Orchestrator, AnthropicModel, ResponsesModel

    planner_model = AnthropicModel(base_url="...", model="claude-opus-4.6")
    executor_model = ResponsesModel(base_url="...", model="gpt-5-mini")

    orch = Orchestrator(planner_model=planner_model, executor_model=executor_model)
    result = orch.run("实现一个LRU Cache")
    print(result)
"""

from brain_worker.models import AnthropicModel, ResponsesModel, ChatCompletionsModel
from brain_worker.pipeline import Orchestrator
from brain_worker.schema import Plan, Step, StepStatus, Review

__all__ = [
    "AnthropicModel",
    "ResponsesModel",
    "ChatCompletionsModel",
    "Orchestrator",
    "Plan",
    "Step",
    "StepStatus",
    "Review",
]
