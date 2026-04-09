"""
解析器 — 从模型输出中提取结构化数据。
"""

from __future__ import annotations

import re

from brain_worker.schema import Plan, Step, Review


def parse_plan(raw: str) -> Plan:
    """从 Markdown 格式解析计划"""
    goal_m = re.search(r"## GOAL\s*\n(.+?)(?=\n## )", raw, re.DOTALL)
    goal = goal_m.group(1).strip() if goal_m else "完成用户任务"

    ctx_m = re.search(r"## CONTEXT\s*\n(.+?)(?=\n## STEP)", raw, re.DOTALL)
    context = ctx_m.group(1).strip() if ctx_m else ""

    step_pattern = r"## STEP (\d+):\s*(.+?)\n(.*?)(?=\n## STEP \d+:|\Z)"
    steps = []
    for m in re.finditer(step_pattern, raw, re.DOTALL):
        idx = int(m.group(1))
        title = m.group(2).strip()
        body = m.group(3).strip()

        # 解析 DEPENDS
        depends_on: list[int] = []
        dep_m = re.search(r"DEPENDS:\s*(.+)", body)
        if dep_m:
            dep_str = dep_m.group(1).strip()
            if dep_str not in ("无", "none", "无依赖", ""):
                depends_on = [int(x.strip()) for x in dep_str.split(",") if x.strip().isdigit()]

        # 解析 ACCEPTANCE
        acceptance = ""
        acc_m = re.search(r"ACCEPTANCE:\s*(.+)", body)
        if acc_m:
            acceptance = acc_m.group(1).strip()

        # 指令：去掉元数据行
        instruction = re.sub(r"^DEPENDS:.*\n?", "", body, flags=re.MULTILINE)
        instruction = re.sub(r"^ACCEPTANCE:.*\n?", "", instruction, flags=re.MULTILINE).strip()

        steps.append(Step(
            index=idx, title=title, instruction=instruction,
            depends_on=depends_on, acceptance=acceptance,
        ))

    if not steps:
        steps = [Step(index=1, title="执行任务", instruction=raw)]

    return Plan(goal=goal, context=context, steps=steps)


def parse_review(raw: str) -> Review:
    """从审查员输出中解析审查结果"""
    passed = "PASS" in raw.split("\n")[0] if raw else True

    score_m = re.search(r"SCORE:\s*(\d+)", raw)
    score = int(score_m.group(1)) if score_m else 7

    feedback_m = re.search(r"FEEDBACK:\s*(.+?)(?=\nCORRECTION:|\Z)", raw, re.DOTALL)
    feedback = feedback_m.group(1).strip() if feedback_m else ""

    correction_m = re.search(r"CORRECTION:\s*(.+)", raw, re.DOTALL)
    correction = correction_m.group(1).strip() if correction_m else ""
    if correction == "无":
        correction = ""

    return Review(passed=passed, score=score, feedback=feedback, correction=correction)
