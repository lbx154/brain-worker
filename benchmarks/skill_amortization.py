#!/usr/bin/env python3
"""
Skill-Amortization Benchmark
=============================
验证：大模型写一次通用技能指南，小模型拿着指南反复做一类任务。

对比：
  A) 小模型裸做 (无指南)
  B) 小模型 + 大模型写的指南
  C) 大模型自己做 (上限参考)

类别：动态规划（10 道题，难度递增）
"""

import json
import os
import re
import time
from dataclasses import dataclass

import httpx

BASE_URL = os.environ.get("BRAIN_WORKER_BASE_URL", "http://127.0.0.1:18080")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

# ─── API ──────────────────────────────────────────────────────────────────────

@dataclass
class Counter:
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    calls: int = 0
    @property
    def total(self): return self.input_tokens + self.output_tokens

def call_big(system, user, counter):
    with httpx.Client(base_url=BASE_URL, timeout=600) as c:
        r = c.post("/v1/messages", json={
            "model": "claude-opus-4.6", "max_tokens": 2048,
            "system": system, "messages": [{"role": "user", "content": user}],
        }, headers={"x-api-key": "unused", "anthropic-version": "2023-06-01"})
        r.raise_for_status()
        d = r.json()
        u = d.get("usage", {})
        counter.input_tokens += u.get("input_tokens", 0)
        counter.output_tokens += u.get("output_tokens", 0)
        counter.calls += 1
        return d["content"][0]["text"]

def call_small(system, user, counter):
    with httpx.Client(base_url=BASE_URL, timeout=180) as c:
        r = c.post("/v1/responses", json={
            "model": "gpt-5-mini", "instructions": system,
            "input": user, "stream": False,
        })
        r.raise_for_status()
        d = r.json()
        u = d.get("usage", {})
        counter.input_tokens += u.get("input_tokens", 0)
        counter.output_tokens += u.get("output_tokens", 0)
        counter.reasoning_tokens += u.get("output_tokens_details", {}).get("reasoning_tokens", 0)
        counter.calls += 1
        for item in d.get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        return part["text"]
        return d.get("output_text") or ""

# ─── 10 道 DP 题（难度递增）──────────────────────────────────────────────────

PROBLEMS = [
    # 1. 爬楼梯 (Easy)
    {"id": 1, "name": "爬楼梯", "difficulty": "Easy",
     "prompt": "写Python函数 climb_stairs(n: int) -> int，每次爬1或2阶，返回爬到第n阶的方法数。只输出函数。",
     "test": "assert climb_stairs(2)==2; assert climb_stairs(3)==3; assert climb_stairs(5)==8"},

    # 2. 打家劫舍 (Medium)
    {"id": 2, "name": "打家劫舍", "difficulty": "Medium",
     "prompt": "写Python函数 rob(nums: list[int]) -> int，不能偷相邻房屋，返回最大金额。只输出函数。",
     "test": "assert rob([1,2,3,1])==4; assert rob([2,7,9,3,1])==12; assert rob([2,1,1,2])==4"},

    # 3. 零钱兑换 (Medium)
    {"id": 3, "name": "零钱兑换", "difficulty": "Medium",
     "prompt": "写Python函数 coin_change(coins: list[int], amount: int) -> int，返回凑成amount所需最少硬币数，不可能返回-1。只输出函数。",
     "test": "assert coin_change([1,2,5],11)==3; assert coin_change([2],3)==-1; assert coin_change([1],0)==0"},

    # 4. 最长递增子序列 (Medium)
    {"id": 4, "name": "最长递增子序列", "difficulty": "Medium",
     "prompt": "写Python函数 length_of_lis(nums: list[int]) -> int，返回最长严格递增子序列的长度。要求O(n log n)。只输出函数。",
     "test": "assert length_of_lis([10,9,2,5,3,7,101,18])==4; assert length_of_lis([0,1,0,3,2,3])==4; assert length_of_lis([7,7,7,7])==1"},

    # 5. 编辑距离 (Medium-Hard)
    {"id": 5, "name": "编辑距离", "difficulty": "Medium-Hard",
     "prompt": "写Python函数 min_distance(word1: str, word2: str) -> int，返回将word1转换成word2所需的最少操作数（插入/删除/替换）。只输出函数。",
     "test": 'assert min_distance("horse","ros")==3; assert min_distance("intention","execution")==5; assert min_distance("","a")==1'},

    # 6. 最长公共子序列 (Medium)
    {"id": 6, "name": "最长公共子序列", "difficulty": "Medium",
     "prompt": "写Python函数 longest_common_subsequence(text1: str, text2: str) -> int，返回两个字符串的最长公共子序列的长度。只输出函数。",
     "test": 'assert longest_common_subsequence("abcde","ace")==3; assert longest_common_subsequence("abc","abc")==3; assert longest_common_subsequence("abc","def")==0'},

    # 7. 分割等和子集 (Medium)
    {"id": 7, "name": "分割等和子集", "difficulty": "Medium",
     "prompt": "写Python函数 can_partition(nums: list[int]) -> bool，判断能否将数组分成两个子集使得两子集元素和相等。只输出函数。",
     "test": "assert can_partition([1,5,11,5])==True; assert can_partition([1,2,3,5])==False; assert can_partition([1,1])==True"},

    # 8. 戳气球 (Hard)
    {"id": 8, "name": "戳气球", "difficulty": "Hard",
     "prompt": "写Python函数 max_coins(nums: list[int]) -> int，戳气球得分为左×自身×右，返回最大得分。nums两端视为1。只输出函数。",
     "test": "assert max_coins([3,1,5,8])==167; assert max_coins([1,5])==10"},

    # 9. 正则表达式匹配 (Hard)
    {"id": 9, "name": "正则表达式匹配", "difficulty": "Hard",
     "prompt": "写Python函数 is_match(s: str, p: str) -> bool，实现正则匹配，'.'匹配任意单字符，'*'匹配零或多个前面的元素。只输出函数。",
     "test": 'assert is_match("aa","a")==False; assert is_match("aa","a*")==True; assert is_match("ab",".*")==True; assert is_match("aab","c*a*b")==True; assert is_match("mississippi","mis*is*p*.")==False'},

    # 10. 鸡蛋掉落 (Hard)
    {"id": 10, "name": "鸡蛋掉落", "difficulty": "Hard",
     "prompt": "写Python函数 super_egg_drop(k: int, n: int) -> int，k个鸡蛋n层楼，返回最坏情况下确定临界楼层的最少操作次数。只输出函数。",
     "test": "assert super_egg_drop(1,2)==2; assert super_egg_drop(2,6)==3; assert super_egg_drop(3,14)==4"},
]

# ─── Step 0: 大模型写 DP 通用指南 ────────────────────────────────────────────

GUIDE_REQUEST = """\
你是算法教练。写一个精简的「DP 解题 Skill」给一个 AI 模型用。

要求：
- 总长度控制在 500 字以内
- 只写可直接套用的模板和规则，不要教学解释
- 包含：5 步解题流程 + 3 种常见模式的状态定义和转移方程模板
- 每种模式用 1 行伪代码表示
- 用中文"""

def generate_guide(counter):
    print("  生成 DP 解题指南中...", end=" ", flush=True)
    t0 = time.time()
    guide = call_big("你是算法竞赛教练，写出详尽的教学文档。", GUIDE_REQUEST, counter)
    elapsed = time.time() - t0
    print(f"完成 ({elapsed:.1f}s, {counter.total} tokens)")
    return guide

# ─── 辅助 ────────────────────────────────────────────────────────────────────

def extract_code(text):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()

def verify(code, test):
    try:
        exec(code + "\n" + test, {})
        return True
    except:
        return False

def c(t, color):
    codes = {"green":"32","red":"31","yellow":"33","bold":"1","gray":"90","cyan":"36","magenta":"35"}
    return f"\033[{codes.get(color,'0')}m{t}\033[0m"

# ─── 主流程 ───────────────────────────────────────────────────────────────────

def main():
    print(c("\n  Skill-Amortization Benchmark: 动态规划 10 题", "bold"))
    print(c("  大模型写一次指南 → 小模型带着指南反复做\n", "gray"))

    # 生成指南 (一次性成本)
    guide_counter = Counter()
    guide = generate_guide(guide_counter)
    guide_tokens = guide_counter.total

    # 保存指南
    with open(os.path.join(RESULTS_DIR, "dp_skill.md"), "w") as f:
        f.write(guide)
    print(f"  指南已保存到 dp_guide.md ({len(guide)} 字符, {guide_tokens} tokens)\n")

    # 跑题
    results = []
    small_bare = Counter()     # A: 小模型裸做
    small_guided = Counter()   # B: 小模型+指南
    big_direct = Counter()     # C: 大模型直接做

    bare_system = "你是Python程序员。只输出函数代码，不要解释。"
    guided_system = f"你是Python程序员。只输出函数代码，不要解释。\n\n以下是动态规划解题指南，请参考：\n\n{guide}"

    print(f"  {'#':>2} {'题目':<14} {'难度':<12} {'裸做':>6} {'带指南':>6} {'大模型':>6}")
    print(f"  {'─' * 56}")

    for p in PROBLEMS:
        # A: 小模型裸做
        raw_a = call_small(bare_system, p["prompt"], small_bare)
        pass_a = verify(extract_code(raw_a), p["test"])

        # B: 小模型+指南
        raw_b = call_small(guided_system, p["prompt"], small_guided)
        pass_b = verify(extract_code(raw_b), p["test"])

        # C: 大模型
        raw_c = call_big(bare_system, p["prompt"], big_direct)
        pass_c = verify(extract_code(raw_c), p["test"])

        ma = c("✓","green") if pass_a else c("✗","red")
        mb = c("✓","green") if pass_b else c("✗","red")
        mc = c("✓","green") if pass_c else c("✗","red")
        print(f"  {p['id']:>2} {p['name']:<14} {p['difficulty']:<12} {ma:>15} {mb:>15} {mc:>15}")

        results.append({"id": p["id"], "name": p["name"], "difficulty": p["difficulty"],
                         "bare": pass_a, "guided": pass_b, "big": pass_c})

    # ─── 汇总 ────────────────────────────────────────────────────────────────

    n_bare = sum(1 for r in results if r["bare"])
    n_guided = sum(1 for r in results if r["guided"])
    n_big = sum(1 for r in results if r["big"])

    print(f"\n{'=' * 64}")
    print(c("  RESULTS", "bold"))
    print(f"{'=' * 64}\n")

    print(f"  正确率:")
    print(f"    A) 小模型裸做:     {n_bare}/10")
    print(f"    B) 小模型+指南:    {n_guided}/10")
    print(f"    C) 大模型直接做:   {n_big}/10")

    print(f"\n  Token 消耗:")
    print(f"    {'方式':<28} {'输入':>8} {'输出':>8} {'思考':>8} {'总计':>8}")
    print(f"    {'─' * 52}")
    print(f"    {'A) 小模型裸做':<28} {small_bare.input_tokens:>8,} {small_bare.output_tokens:>8,} {small_bare.reasoning_tokens:>8,} {small_bare.total:>8,}")
    print(f"    {'B) 小模型+指南 (小模型部分)':<28} {small_guided.input_tokens:>8,} {small_guided.output_tokens:>8,} {small_guided.reasoning_tokens:>8,} {small_guided.total:>8,}")
    print(f"    {'B) 指南生成 (大模型一次性)':<28} {guide_counter.input_tokens:>8,} {guide_counter.output_tokens:>8,} {'N/A':>8} {guide_tokens:>8,}")
    print(f"    {'B) 合计':<28} {'':>8} {'':>8} {'':>8} {small_guided.total + guide_tokens:>8,}")
    print(f"    {'C) 大模型直接做':<28} {big_direct.input_tokens:>8,} {big_direct.output_tokens:>8,} {'N/A':>8} {big_direct.total:>8,}")

    print(f"\n  经济性分析:")
    if big_direct.total > 0:
        ratio = guide_tokens / big_direct.total
        print(f"    指南成本 = 大模型做 {ratio:.1f} 道题的 token")
        if n_guided > n_bare:
            delta = n_guided - n_bare
            cost_per_improvement = guide_tokens / delta
            print(f"    指南提升了 {delta} 道题 → 每提升 1 道的大模型成本: {cost_per_improvement:.0f} tokens")
        breakeven = guide_tokens / (big_direct.total / 10) if big_direct.total > 0 else 0
        print(f"    盈亏平衡点: 做 >{breakeven:.0f} 道 DP 题后，方案 B 的大模型 token 总量 < 方案 C")

    # 保存
    with open(os.path.join(RESULTS_DIR, "skill_amortization.json"), "w") as f:
        json.dump({"guide_tokens": guide_tokens, "results": results,
                    "small_bare": small_bare.__dict__, "small_guided": small_guided.__dict__,
                    "big_direct": big_direct.__dict__, "guide_counter": guide_counter.__dict__}, f, ensure_ascii=False, indent=2)
    print(f"\n  详细数据已保存到 skill_benchmark.json")


if __name__ == "__main__":
    main()
