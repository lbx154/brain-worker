# Brain-Worker

**Prompt-level knowledge distillation: big models write skills once, small models reuse them forever.**

> 提示词级知识蒸馏：大模型写一次技能指南，小模型反复复用。

```
┌─────────────────────────────────────────────────────────────┐
│                      Brain-Worker                           │
│                                                             │
│   ┌───────────┐    skill     ┌───────────┐                  │
│   │ Big Model │───(once)───▶│  Skill.md │  ◀── reuse ──┐   │
│   │ (Planner) │             └─────┬─────┘               │   │
│   └───────────┘                   │                     │   │
│     opus, gpt-5                   ▼                     │   │
│                            ┌─────────────┐    task 1    │   │
│                            │ Small Model │──────────────┤   │
│                            │ (Executor)  │    task 2    │   │
│                            │             │──────────────┤   │
│                            │  mini, haiku│    task N    │   │
│                            └─────────────┘──────────────┘   │
│                                                             │
│   Big model cost: O(1)        Small model cost: O(N)        │
│   Amortized over N tasks → big model cost → 0               │
└─────────────────────────────────────────────────────────────┘
```

## Why / 为什么

The standard approach to complex tasks: call a big model every time. Expensive.

传统做法：每次都调大模型。贵。

The alternative: let the big model write a **reusable skill** (a structured prompt) for a *category* of tasks, then let a cheap small model execute with that skill. The big model's cost is paid once and amortized across all future tasks.

替代方案：让大模型为**一类任务**写一份可复用的技能指南（本质是个 prompt），然后让便宜的小模型带着指南反复执行。大模型的成本一次性支付，摊到所有后续任务上。

## Benchmark Results / 基准测试结果

Tested on 10 dynamic programming problems (Easy → Hard). Big model: Claude Opus 4.6. Small model: GPT-5-mini.

在 10 道动态规划题（Easy → Hard）上测试。大模型：Claude Opus 4.6，小模型：GPT-5-mini。

### Accuracy / 正确率

| Approach | Accuracy |
|----------|----------|
| Small model alone | 10/10 |
| Small model + skill | 10/10 |
| Big model alone | 10/10 |

### Token Economics / Token 经济性

Output tokens only (input tokens can be cached via prompt caching):

只算 output token（input token 可通过 prompt caching 消除）：

| Metric | Small alone | Small + skill | Big alone |
|--------|-------------|---------------|-----------|
| Output tokens (10 tasks) | 6,775 | 5,682 | 1,735 |
| Reasoning tokens | 5,056 | 3,968 (-21%) | N/A |
| Skill generation (one-time) | — | 776 | — |

**Key findings / 关键发现:**

- The skill **reduced small model reasoning by 21%** (1,088 fewer thinking tokens per 10 tasks)
- Skill generation cost: **776 tokens** (one-time). Break-even at **~7 tasks**
- At market pricing (big model output ~15x more expensive): **skill approach saves 33%** vs calling the big model every time
- 技能指南让小模型的**思考量减少了 21%**（每 10 题少 1,088 个推理 token）
- 指南生成成本：**776 token**（一次性）。**约 7 道题**回本
- 按市场定价（大模型输出价格约为小模型 15 倍）：技能方案比每次都调大模型**省 33%**

## Quick Start / 快速开始

### Install / 安装

```bash
git clone https://github.com/yourname/brain-worker.git
cd brain-worker
pip install -e .
```

### Generate a skill, then use it / 生成技能，然后复用

```python
from brain_worker import AnthropicModel, ResponsesModel

big = AnthropicModel(base_url="http://127.0.0.1:18080", model="claude-opus-4.6")
small = ResponsesModel(base_url="http://127.0.0.1:18080", model="gpt-5-mini")

# Step 1: Big model writes a skill once (一次性)
skill = big.call(
    "You are an expert. Write a concise problem-solving template for this category.",
    "Write a DP (dynamic programming) solving skill in under 500 words."
)

# Step 2: Small model uses the skill repeatedly (反复复用)
for problem in problems:
    answer = small.call(skill, problem)
```

### Full pipeline with planning + review / 完整流程（规划+审查）

```python
from brain_worker import Orchestrator, AnthropicModel, ResponsesModel

orch = Orchestrator(
    planner_model=AnthropicModel(model="claude-opus-4.6"),
    executor_model=ResponsesModel(model="gpt-5-mini"),
    review=True,       # big model reviews each step
    max_retries=2,     # retry on failure with correction
    max_parallel=3,    # parallel execution of independent steps
)

result = orch.run("Implement an LRU Cache with O(1) operations and tests")
print(result)
```

### CLI

```bash
# Single task
python -m brain_worker "Implement a binary search tree"

# No review (faster, cheaper)
python -m brain_worker --no-review "Write a quicksort function"

# Custom models
python -m brain_worker --planner claude-sonnet-4.6 --executor gpt-4o-mini "task"

# Interactive mode
python -m brain_worker -i
```

## How It Works / 工作原理

### Mode 1: Skill Distillation (Recommended / 推荐)

```
User defines a task category
        │
        ▼
┌──────────────┐
│  Big Model   │──▶ Writes a concise skill/template (one-time, ~500-1000 tokens)
└──────────────┘
        │
        ▼
┌──────────────┐
│ Small Model  │──▶ Executes N tasks using the skill as system prompt
└──────────────┘
        │
    Cost: O(1) big + O(N) small
```

### Mode 2: Full Orchestration Pipeline

For complex, one-off tasks that need step-by-step execution:

对于复杂的一次性任务，需要分步执行：

```
Task ──▶ Phase 1: PLAN (big model decomposes into steps)
     ──▶ Phase 2: EXECUTE (small model executes each step)
     ──▶ Phase 3: REVIEW (big model checks quality, retries if needed)
     ──▶ Phase 4: SYNTHESIZE (big model merges results)
```

- Independent steps execute in parallel
- Failed steps get correction feedback and retry
- Dependency graph respected automatically

## Skill Protocol / 技能协议

Brain-Worker defines a framework-agnostic protocol for planner-executor collaboration. You can use it with any agent system:

Brain-Worker 定义了一个框架无关的规划-执行协议，可适配任何 agent 系统：

| System | Integration |
|--------|-------------|
| **Claude Code** | Drop `SKILL.md` into `.claude/skills/brain-worker/` |
| **OpenAI Agents SDK** | Use `protocol.md` as agent instructions |
| **LangChain** | Load as SystemMessage template |
| **AutoGen** | Set as `system_message` for planner agent |
| **Raw API** | Send as system prompt to your planner model |

See [`skills/protocol.md`](skills/protocol.md) for the full protocol spec.

## Architecture / 架构

```python
# Pluggable components — swap any part
Orchestrator(
    planner_model=...,       # Any BaseModel subclass
    executor_model=...,      # Any BaseModel subclass
    reviewer_model=...,      # Defaults to planner_model
    synthesizer_model=...,   # Defaults to planner_model
    prompts=MyPrompts,       # Subclass Prompts to customize
    on_event=my_callback,    # Custom logging/monitoring
)
```

### Model Adapters / 模型适配器

| Adapter | API | Models |
|---------|-----|--------|
| `AnthropicModel` | `/v1/messages` | Claude Opus, Sonnet, Haiku |
| `ResponsesModel` | `/v1/responses` | GPT-5, GPT-5-mini |
| `ChatCompletionsModel` | `/v1/chat/completions` | Any OpenAI-compatible (vLLM, Ollama, LiteLLM) |

## Related Work / 相关工作

| Paper | Core Idea | Relation to Brain-Worker |
|-------|-----------|--------------------------|
| [FrugalGPT](https://arxiv.org/abs/2305.05176) (Chen et al., 2023) | LLM cascade: try cheap model first, escalate if needed | Runtime routing. We do compile-time skill generation |
| [Meta-Prompting](https://arxiv.org/abs/2401.12954) (Suzgun & Kalai, 2024) | Single LLM as orchestrator + expert instances | Same model for all roles. We split big/small |
| [RouteLLM](https://arxiv.org/abs/2406.18665) (Ong et al., 2024) | Trained router chooses strong vs weak model per query | Per-query routing. We do per-category skill writing |
| [BetterTogether](https://arxiv.org/abs/2407.10930) (Soylu et al., 2024) | Co-optimize prompts and weights | Prompt optimization via search. We generate prompts via big model |

**Our position / 我们的定位:** Between prompt optimization and knowledge distillation. The big model's knowledge is distilled not into weights (expensive fine-tuning) nor routed at runtime (per-query overhead), but into **reusable prompts** — written once, cached, and amortized across unlimited tasks.

介于 prompt 优化和知识蒸馏之间。大模型的知识不蒸馏到权重里（微调太贵），也不在运行时路由（每次都有开销），而是蒸馏到**可复用的 prompt** 中——写一次，缓存，在无限任务上摊薄成本。

## License

MIT
