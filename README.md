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

30 dynamic programming problems across 5 difficulty tiers (Medium → Expert). Big model: Claude Opus 4.6. Small model: GPT-5-mini.

30 道动态规划题，横跨 5 个难度等级（Medium → Expert）。大模型：Claude Opus 4.6，小模型：GPT-5-mini。

### Accuracy by Tier / 分层正确率

| Tier | Small alone | Small + skill | Big alone | Rescued |
|------|-------------|---------------|-----------|---------|
| Medium (5) | 4/5 | **5/5** | 5/5 | 1 |
| Medium-Hard (5) | 5/5 | 5/5 | 5/5 | 0 |
| Hard (5) | 5/5 | 5/5 | 5/5 | 0 |
| Hard+ (5) | 5/5 | 5/5 | 5/5 | 0 |
| Expert (10) | 10/10 | 10/10 | 10/10 | 0 |
| **Total** | **29/30** | **30/30** | **30/30** | **1** |

The skill **rescued 1 problem** (coin change) that the small model failed bare, and **degraded 0** — strictly non-negative impact.

技能指南**挽救了 1 道题**（零钱兑换），小模型裸做失败但加指南后通过。**0 道退化** —— 严格非负影响。

### Token Economics / Token 经济性

Output tokens only (input tokens can be cached via prompt caching):

只算 output token（input token 可通过 prompt caching 消除）：

| Metric (30 tasks) | Small alone | Small + skill | Big alone |
|--------------------|-------------|---------------|-----------|
| Output tokens | 21,304 | 20,284 | 6,844 |
| Reasoning tokens | 15,552 | 14,208 (-8.6%) | N/A |
| Skill generation (one-time) | — | 940 | — |

**Key findings / 关键发现:**

- Skill **reduced reasoning tokens by 8.6%** across 30 tasks (1,344 fewer thinking tokens)
- **1 problem rescued**, 0 degraded — the skill is strictly beneficial for accuracy
- Skill generation cost: **940 output tokens** (one-time, amortized to ~31 tokens/task over 30 tasks)
- At market pricing (big model ~15x more expensive): skill approach uses **940 big-model tokens once** vs **6,844 big-model tokens** for direct execution = **86% cheaper** on the big-model bill
- 技能指南让小模型 **reasoning 减少 8.6%**（30 题共少 1,344 个推理 token）
- **挽救 1 道题，退化 0 道** —— 正确率严格提升
- 指南生成成本：**940 output token**（一次性，摊到 30 题约 31 token/题）
- 按市场定价（大模型约 15 倍价格）：指南方案只花 **940 大模型 token**，直接调大模型要花 **6,844** = 大模型账单**省 86%**

### Novel Tasks: Invented Rules / 自创规则任务

Standard benchmarks (LeetCode, DP) are saturated in training data — all models ace them. To test skill distillation properly, we invented 5 rule systems that **don't exist in any training data**:

标准 benchmark（LeetCode、DP）在训练数据中已经饱和——所有模型都能做对。为了正确测试 skill distillation，我们发明了 5 套**不存在于任何训练数据中的规则系统**：

| Category | Description |
|----------|-------------|
| **StackLang** | Custom stack-based language with PUSH/POP/DUP/SWAP/ROT/IF |
| **ZoneTax** | Fictional tax system with zones, brackets, family deductions |
| **XorShift** | Invented XOR cipher with rolling key update |
| **GridHop** | Custom board game: jump by cell value, find shortest path |
| **MiniPack** | Invented binary serialization protocol |

Results (30 problems, 5 categories × 6 each):

| Category | Small alone | Small + skill | Big alone | Rescued | Degraded |
|----------|-------------|---------------|-----------|---------|----------|
| StackLang | 4/6 | 1/6 | 4/6 | 0 | 3 |
| ZoneTax | 4/6 | 3/6 | 3/6 | 0 | 1 |
| XorShift | 6/6 | 6/6 | 6/6 | 0 | 0 |
| GridHop | 3/6 | 3/6 | 3/6 | 0 | 0 |
| MiniPack | 6/6 | 6/6 | 6/6 | 0 | 0 |
| **Total** | **23/30** | **19/30** | **22/30** | **0** | **4** |

**Key findings / 关键发现:**

- **The skill degraded accuracy** from 23/30 → 19/30 (4 problems worsened, 0 rescued)
- The small model (GPT-5-mini, 23/30) **outperformed** the big model (Opus, 22/30) on these invented rules
- Reasoning tokens dropped 37% (29,120 → 18,368), but at the cost of correctness — the model "thought less" because the skill misled it
- **Root cause:** the big model itself misunderstood some rules (e.g., ROT semantics), and the skill propagated those errors to the small model
- Skill 导致正确率**下降** 23/30 → 19/30（4 题退化，0 题挽救）
- 小模型 (GPT-5-mini, 23/30) 在自创规则上**反超**大模型 (Opus, 22/30)
- reasoning 下降 37%，但代价是正确率——模型"少想了"是因为 skill 误导了它
- **根因：** 大模型自身对部分规则理解有误（如 ROT 语义），skill 把错误传播给了小模型

**Lesson / 教训:** Skill distillation has a hard ceiling — **the skill can only be as good as the model that wrote it**. It works when the big model truly knows the domain but the small model doesn't. When both models struggle with novel rules, the skill becomes a vector for error propagation.

Skill distillation 有硬上限——**skill 的质量不会超过写它的模型的能力**。只有在大模型真正掌握、小模型不掌握的领域才有效。当两个模型都对新规则理解不足时，skill 反而成了错误传播通道。

## Quick Start / 快速开始

### Install / 安装

```bash
git clone https://github.com/lbx154/brain-worker.git
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
