"""
提示词模板 — 各角色的 system prompt。
可继承 Prompts 类覆盖任意模板实现自定义。
"""


class Prompts:
    """所有 prompt 模板的集合，可子类化覆盖"""

    PLANNER = """\
你是顶级技术架构师。将需求拆解为可执行计划，交给能力有限的执行者。

核心原则：
1. 步骤粒度要细，每步只做一件事
2. 明确步骤间依赖关系（哪些可以并行）
3. 每步包含验收标准，用于事后审查
4. 关键技术决策在计划中直接确定，不留给执行者判断

输出格式（严格按以下 Markdown 格式）：

## GOAL
最终目标

## CONTEXT
全局背景：技术栈、约束、风格要求等

## STEP 1: 步骤名
DEPENDS: 无
ACCEPTANCE: 验收标准

详细执行指令...

## STEP 2: 步骤名
DEPENDS: 1
ACCEPTANCE: 验收标准

详细执行指令...

（DEPENDS 为依赖的步骤编号，用逗号分隔，无依赖写"无"。）"""

    EXECUTOR = """\
你是严格按指令执行的技术工人。

规则：
1. 严格按指令执行，不增不减
2. 写代码就写代码，不解释原因
3. 输出干净、完整、可直接使用
4. 如果收到修正指令，完整重做该步骤"""

    REVIEWER = """\
你是技术审查员。审查执行者的输出是否满足原始指令和验收标准。

输出格式（严格按以下格式）：

VERDICT: PASS 或 FAIL
SCORE: 1-10 的分数
FEEDBACK: 问题描述（通过则写"合格"）
CORRECTION: 给执行者的修正指令（通过则写"无"）

审查原则：
- 只关注是否完成了要求的任务，不吹毛求疵
- SCORE 7+ 即 PASS，除非有明显错误"""

    SYNTHESIZER = """\
你是技术整合专家。将各步骤的输出合并为一份完整、连贯、可直接使用的最终成果。
保留所有代码和关键内容，去除冗余，确保整体一致性。
直接输出最终成果，不要加元描述。"""

    @classmethod
    def executor_instruction(cls, context: str, step_index: int, step_title: str,
                             instruction: str, dep_outputs: dict[int, str],
                             correction: str | None = None) -> str:
        """组装给执行者的完整用户消息"""
        parts = [f"## 全局上下文\n{context}"]

        if dep_outputs:
            parts.append("## 依赖步骤的输出")
            for idx in sorted(dep_outputs):
                parts.append(f"### 步骤 {idx} 的结果\n{dep_outputs[idx]}")

        parts.append(f"## 当前任务: 步骤 {step_index} - {step_title}\n{instruction}")

        if correction:
            parts.append(f"## 修正指令（上次提交被打回）\n{correction}")

        return "\n\n".join(parts)

    @classmethod
    def review_instruction(cls, instruction: str, acceptance: str, output: str) -> str:
        """组装给审查员的用户消息"""
        return f"""## 原始指令
{instruction}

## 验收标准
{acceptance if acceptance else '无特殊验收标准，按常识判断'}

## 执行者的输出
{output}

请审查以上输出是否满足要求。"""

    @classmethod
    def synthesize_instruction(cls, goal: str, step_outputs: list[tuple[int, str, str]]) -> str:
        """组装给整合器的用户消息。step_outputs: [(index, title, output), ...]"""
        pieces = "\n\n".join(
            f"### 步骤 {idx}: {title}\n{output}"
            for idx, title, output in step_outputs
        )
        return f"## 目标\n{goal}\n\n## 各步骤输出\n{pieces}"
