"""
编排器 — 驱动完整的 Plan → Execute → Review → Synthesize 流程。

用法:
    orch = Orchestrator(planner_model=..., executor_model=...)
    result = orch.run("实现一个LRU Cache")

    # 自定义: 用不同的审查模型
    orch = Orchestrator(
        planner_model=big,
        executor_model=small,
        reviewer_model=big,       # 默认复用 planner_model
        synthesizer_model=big,    # 默认复用 planner_model
    )

    # 自定义: 关闭审查
    orch = Orchestrator(..., review=False)

    # 自定义: 修改 prompt
    from brain_worker.prompts import Prompts
    class MyPrompts(Prompts):
        PLANNER = "你是一个产品经理..."
    orch = Orchestrator(..., prompts=MyPrompts)
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

from brain_worker.models import BaseModel
from brain_worker.parsers import parse_plan, parse_review
from brain_worker.prompts import Prompts
from brain_worker.schema import Plan, Step, StepStatus, Review


# ─── 日志回调 ─────────────────────────────────────────────────────────────────

@dataclass
class Event:
    """流程事件，传给 on_event 回调"""
    phase: str          # "plan" | "execute" | "review" | "synthesize"
    step_index: int     # 0 表示非步骤事件
    event: str          # "start" | "done" | "pass" | "fail" | "retry" | "parallel"
    message: str        # 人类可读描述
    elapsed: float = 0  # 耗时（秒）
    data: dict = field(default_factory=dict)  # 附加数据


def _default_logger(evt: Event):
    icons = {
        "start": ".", "done": "+", "pass": "+",
        "fail": "X", "retry": "~", "parallel": ">",
    }
    icon = icons.get(evt.event, ".")
    step_tag = f"步骤{evt.step_index} " if evt.step_index else ""
    print(f"  [{icon}] [{evt.phase}] {step_tag}{evt.message}")


# ─── 编排器 ───────────────────────────────────────────────────────────────────

class Orchestrator:
    def __init__(
        self,
        planner_model: BaseModel,
        executor_model: BaseModel,
        reviewer_model: BaseModel | None = None,
        synthesizer_model: BaseModel | None = None,
        prompts: type[Prompts] = Prompts,
        review: bool = True,
        max_retries: int = 2,
        max_parallel: int = 3,
        on_event: Callable[[Event], None] = _default_logger,
    ):
        self.planner = planner_model
        self.executor = executor_model
        self.reviewer = reviewer_model or planner_model
        self.synthesizer = synthesizer_model or planner_model
        self.prompts = prompts
        self.review_enabled = review
        self.max_retries = max_retries
        self.max_parallel = max_parallel
        self.on_event = on_event

    def _emit(self, phase: str, step_index: int, event: str, message: str,
              elapsed: float = 0, **data):
        self.on_event(Event(phase, step_index, event, message, elapsed, data))

    # ── Phase 1: Plan ────────────────────────────────────────────────────────

    def plan(self, task: str) -> Plan:
        self._emit("plan", 0, "start", f"规划中... ({self.planner})")
        t0 = time.time()
        raw = self.planner.call(self.prompts.PLANNER, task)
        elapsed = time.time() - t0
        p = parse_plan(raw)
        self._emit("plan", 0, "done",
                    f"规划完成: {len(p.steps)} 步, 目标: {p.goal}", elapsed)
        return p

    # ── Phase 2+3: Execute + Review ──────────────────────────────────────────

    def _execute_step(self, step: Step, context: str, dep_outputs: dict[int, str],
                      correction: str | None = None) -> str:
        user_msg = self.prompts.executor_instruction(
            context, step.index, step.title, step.instruction,
            dep_outputs, correction,
        )
        return self.executor.call(self.prompts.EXECUTOR, user_msg)

    def _review_step(self, step: Step, output: str) -> Review:
        user_msg = self.prompts.review_instruction(
            step.instruction, step.acceptance, output,
        )
        raw = self.reviewer.call(self.prompts.REVIEWER, user_msg)
        return parse_review(raw)

    def _execute_with_review(self, step: Step, context: str,
                             dep_outputs: dict[int, str]) -> None:
        step.status = StepStatus.RUNNING
        correction = None

        for attempt in range(1, self.max_retries + 2):
            step.attempts = attempt
            tag = f"{step.title}" + (f" (重试{attempt-1})" if attempt > 1 else "")
            self._emit("execute", step.index, "start", f"{tag} → {self.executor}")

            t0 = time.time()
            output = self._execute_step(step, context, dep_outputs, correction)
            elapsed = time.time() - t0
            self._emit("execute", step.index, "done",
                        f"执行完成 ({elapsed:.1f}s, {len(output)}字符)", elapsed)

            if not self.review_enabled:
                step.status = StepStatus.PASSED
                step.output = output
                return

            # 审查
            self._emit("review", step.index, "start", f"审查中 → {self.reviewer}")
            t0 = time.time()
            review = self._review_step(step, output)
            review_elapsed = time.time() - t0

            if review.passed:
                step.status = StepStatus.PASSED
                step.output = output
                self._emit("review", step.index, "pass",
                            f"通过 ({review.score}/10, {review_elapsed:.1f}s)", review_elapsed)
                return
            else:
                self._emit("review", step.index, "fail",
                            f"未通过 ({review.score}/10): {review.feedback}", review_elapsed)
                if attempt <= self.max_retries:
                    step.status = StepStatus.RETRYING
                    correction = review.correction
                    self._emit("review", step.index, "retry",
                                f"修正: {correction[:200]}")
                else:
                    step.status = StepStatus.PASSED
                    step.output = output
                    self._emit("review", step.index, "done", "重试用尽，接受当前结果")
                    return

    # ── Scheduling ───────────────────────────────────────────────────────────

    def _get_ready(self, steps: list[Step], completed: set[int]) -> list[Step]:
        return [
            s for s in steps
            if s.status == StepStatus.PENDING and all(d in completed for d in s.depends_on)
        ]

    def execute_all(self, plan: Plan) -> dict[int, str]:
        completed: set[int] = set()
        outputs: dict[int, str] = {}

        while len(completed) < len(plan.steps):
            ready = self._get_ready(plan.steps, completed)
            if not ready:
                for s in plan.steps:
                    if s.status == StepStatus.PENDING:
                        s.status = StepStatus.FAILED
                        completed.add(s.index)
                break

            if len(ready) > 1:
                self._emit("execute", 0, "parallel", f"并行执行 {len(ready)} 个步骤")
                with ThreadPoolExecutor(max_workers=min(len(ready), self.max_parallel)) as pool:
                    futures = {}
                    for step in ready:
                        dep_out = {i: outputs[i] for i in step.depends_on if i in outputs}
                        f = pool.submit(self._execute_with_review, step, plan.context, dep_out)
                        futures[f] = step
                    for f in as_completed(futures):
                        step = futures[f]
                        try:
                            f.result()
                        except Exception as e:
                            step.status = StepStatus.FAILED
                            self._emit("execute", step.index, "fail", f"异常: {e}")
                        completed.add(step.index)
                        if step.output:
                            outputs[step.index] = step.output
            else:
                step = ready[0]
                dep_out = {i: outputs[i] for i in step.depends_on if i in outputs}
                self._execute_with_review(step, plan.context, dep_out)
                completed.add(step.index)
                if step.output:
                    outputs[step.index] = step.output

        return outputs

    # ── Phase 4: Synthesize ──────────────────────────────────────────────────

    def synthesize(self, plan: Plan, outputs: dict[int, str]) -> str:
        if len(outputs) <= 1:
            return list(outputs.values())[0] if outputs else ""

        self._emit("synthesize", 0, "start", f"整合中 → {self.synthesizer}")
        t0 = time.time()

        step_data = [
            (s.index, s.title, outputs.get(s.index, "(未完成)"))
            for s in plan.steps
        ]
        user_msg = self.prompts.synthesize_instruction(plan.goal, step_data)
        result = self.synthesizer.call(self.prompts.SYNTHESIZER, user_msg)

        elapsed = time.time() - t0
        self._emit("synthesize", 0, "done", f"整合完成 ({elapsed:.1f}s)", elapsed)
        return result

    # ── 完整流程 ─────────────────────────────────────────────────────────────

    def run(self, task: str) -> str:
        """完整流程: 规划 → 执行+审查 → 整合"""
        plan = self.plan(task)
        outputs = self.execute_all(plan)

        passed = sum(1 for s in plan.steps if s.status == StepStatus.PASSED)
        failed = sum(1 for s in plan.steps if s.status == StepStatus.FAILED)
        self._emit("execute", 0, "done", f"全部完成: {passed} 通过, {failed} 失败")

        return self.synthesize(plan, outputs)

    def run_with_plan(self, task: str) -> tuple[Plan, str]:
        """返回 (plan, result) 以便调用方检查中间状态"""
        plan = self.plan(task)
        outputs = self.execute_all(plan)
        result = self.synthesize(plan, outputs)
        return plan, result
