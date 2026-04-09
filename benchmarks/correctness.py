#!/usr/bin/env python3
"""
Brain-Worker Benchmark
======================
对比三种方式的正确率和开销：
  A) 小模型单干 (gpt-5-mini)
  B) 大模型单干 (claude-opus-4.6)
  C) Brain-Worker (大模型规划 + 小模型执行)

10 道编程题，每道有自动化测试用例。
"""

import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from brain_worker.models import AnthropicModel, ResponsesModel
from brain_worker.pipeline import Orchestrator, Event

# ─── 配置 ────────────────────────────────────────────────────────────────────

BASE_URL = "http://127.0.0.1:18080"
BIG_MODEL = AnthropicModel(base_url=BASE_URL, model="claude-opus-4.6")
SMALL_MODEL = ResponsesModel(base_url=BASE_URL, model="gpt-5-mini")

# ─── 题库: 10 道中等难度编程题 ───────────────────────────────────────────────
# 来源: HumanEval / LeetCode 经典题改编
# 每道题包含: prompt(给模型的指令), test_code(自动验证代码)

PROBLEMS = [
    # 1. 最长回文子串
    {
        "id": 1,
        "name": "最长回文子串",
        "prompt": "写一个Python函数 longest_palindrome(s: str) -> str，返回字符串s中最长的回文子串。如果有多个同长度的，返回最先出现的那个。只输出函数代码。",
        "test_code": """
assert longest_palindrome("babad") in ("bab", "aba")
assert longest_palindrome("cbbd") == "bb"
assert longest_palindrome("a") == "a"
assert longest_palindrome("ac") in ("a", "c")
assert longest_palindrome("racecar") == "racecar"
""",
    },
    # 2. 括号生成
    {
        "id": 2,
        "name": "括号生成",
        "prompt": "写一个Python函数 generate_parentheses(n: int) -> list[str]，生成所有由n对括号组成的合法括号组合。返回列表，顺序不限。只输出函数代码。",
        "test_code": """
assert sorted(generate_parentheses(1)) == ["()"]
assert sorted(generate_parentheses(2)) == sorted(["(())", "()()"])
assert sorted(generate_parentheses(3)) == sorted(["((()))", "(()())", "(())()", "()(())", "()()()"])
assert len(generate_parentheses(4)) == 14
""",
    },
    # 3. 合并区间
    {
        "id": 3,
        "name": "合并区间",
        "prompt": "写一个Python函数 merge_intervals(intervals: list[list[int]]) -> list[list[int]]，合并所有重叠的区间并返回。结果按起始位置排序。只输出函数代码。",
        "test_code": """
assert merge_intervals([[1,3],[2,6],[8,10],[15,18]]) == [[1,6],[8,10],[15,18]]
assert merge_intervals([[1,4],[4,5]]) == [[1,5]]
assert merge_intervals([[1,4],[0,4]]) == [[0,4]]
assert merge_intervals([]) == []
assert merge_intervals([[1,4],[2,3]]) == [[1,4]]
""",
    },
    # 4. 字符串解码
    {
        "id": 4,
        "name": "字符串解码",
        "prompt": "写一个Python函数 decode_string(s: str) -> str，解码编码字符串。编码规则: k[encoded_string] 表示 encoded_string 重复 k 次。例如 '3[a2[c]]' -> 'accaccacc'。只输出函数代码。",
        "test_code": """
assert decode_string("3[a]2[bc]") == "aaabcbc"
assert decode_string("3[a2[c]]") == "accaccacc"
assert decode_string("2[abc]3[cd]ef") == "abcabccdcdcdef"
assert decode_string("abc3[cd]xyz") == "abccdcdcdxyz"
""",
    },
    # 5. LRU Cache
    {
        "id": 5,
        "name": "LRU Cache",
        "prompt": "写一个Python类 LRUCache，实现:\n- __init__(self, capacity: int)\n- get(self, key: int) -> int: 获取值，不存在返回-1\n- put(self, key: int, value: int) -> None: 写入/更新\nget和put必须O(1)时间复杂度。超出容量时淘汰最久未使用的。只输出类代码。",
        "test_code": """
c = LRUCache(2)
c.put(1, 1)
c.put(2, 2)
assert c.get(1) == 1
c.put(3, 3)
assert c.get(2) == -1
c.put(4, 4)
assert c.get(1) == -1
assert c.get(3) == 3
assert c.get(4) == 4
""",
    },
    # 6. 每日温度
    {
        "id": 6,
        "name": "每日温度（单调栈）",
        "prompt": "写一个Python函数 daily_temperatures(temperatures: list[int]) -> list[int]，返回一个数组，其中第i个元素表示要等多少天才能遇到比第i天更高的温度。如果之后没有更高的，填0。要求O(n)时间复杂度。只输出函数代码。",
        "test_code": """
assert daily_temperatures([73,74,75,71,69,72,76,73]) == [1,1,4,2,1,1,0,0]
assert daily_temperatures([30,40,50,60]) == [1,1,1,0]
assert daily_temperatures([30,60,90]) == [1,1,0]
assert daily_temperatures([90,80,70]) == [0,0,0]
""",
    },
    # 7. 二叉树序列化
    {
        "id": 7,
        "name": "二叉树序列化与反序列化",
        "prompt": """写Python代码实现二叉树的序列化和反序列化。

需要：
1. 定义 TreeNode 类 (val, left, right)
2. serialize(root: TreeNode) -> str 函数
3. deserialize(data: str) -> TreeNode 函数

要求 deserialize(serialize(tree)) 还原出完全相同的树。只输出代码。""",
        "test_code": """
# 构建测试树: [1, 2, 3, null, null, 4, 5]
root = TreeNode(1)
root.left = TreeNode(2)
root.right = TreeNode(3)
root.right.left = TreeNode(4)
root.right.right = TreeNode(5)

s = serialize(root)
new_root = deserialize(s)
assert new_root.val == 1
assert new_root.left.val == 2
assert new_root.right.val == 3
assert new_root.left.left is None
assert new_root.right.left.val == 4
assert new_root.right.right.val == 5

# 空树
assert deserialize(serialize(None)) is None
""",
    },
    # 8. 最小路径和 (DP)
    {
        "id": 8,
        "name": "最小路径和（动态规划）",
        "prompt": "写一个Python函数 min_path_sum(grid: list[list[int]]) -> int，给定一个m×n的非负整数网格，找到从左上角到右下角的一条路径，使得路径上的数字总和最小。每次只能向下或向右移动。只输出函数代码。",
        "test_code": """
assert min_path_sum([[1,3,1],[1,5,1],[4,2,1]]) == 7
assert min_path_sum([[1,2,3],[4,5,6]]) == 12
assert min_path_sum([[1]]) == 1
assert min_path_sum([[1,2],[1,1]]) == 3
""",
    },
    # 9. 单词搜索
    {
        "id": 9,
        "name": "单词搜索（回溯）",
        "prompt": "写一个Python函数 word_search(board: list[list[str]], word: str) -> bool，给定一个m×n字符网格和一个单词，判断单词是否可以在网格中找到。单词可以通过相邻单元格（上下左右）的字母构成，同一单元格不能重复使用。只输出函数代码。",
        "test_code": """
board1 = [["A","B","C","E"],["S","F","C","S"],["A","D","E","E"]]
assert word_search(board1, "ABCCED") == True
assert word_search(board1, "SEE") == True
assert word_search(board1, "ABCB") == False
board2 = [["a"]]
assert word_search(board2, "a") == True
assert word_search(board2, "b") == False
""",
    },
    # 10. 前K个高频元素
    {
        "id": 10,
        "name": "前K个高频元素",
        "prompt": "写一个Python函数 top_k_frequent(nums: list[int], k: int) -> list[int]，返回数组中出现频率前k高的元素。返回顺序不限。要求时间复杂度优于O(n log n)。只输出函数代码。",
        "test_code": """
assert sorted(top_k_frequent([1,1,1,2,2,3], 2)) == [1, 2]
assert top_k_frequent([1], 1) == [1]
assert sorted(top_k_frequent([1,2,2,3,3,3], 2)) == [2, 3]
assert sorted(top_k_frequent([4,4,4,1,1,2,2,2,3], 3)) == [1, 2, 4] or sorted(top_k_frequent([4,4,4,1,1,2,2,2,3], 3)) == [2, 3, 4]
""",
    },
]

# ─── 统计 ────────────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    problem_id: int
    problem_name: str
    method: str         # "small" | "big" | "brain-worker"
    passed: bool
    error: str = ""
    time_sec: float = 0
    api_calls: int = 0  # API 调用次数

# ─── 执行 + 验证 ─────────────────────────────────────────────────────────────

def extract_code(text: str) -> str:
    """从模型输出中提取代码"""
    import re
    # 尝试提取 ```python ... ``` 块
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # 否则整段当代码
    return text.strip()


def verify(code: str, test_code: str) -> tuple[bool, str]:
    """执行代码 + 测试，返回 (passed, error)"""
    full_code = code + "\n\n" + test_code
    try:
        exec(full_code, {})
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# ─── 方式 A: 小模型单干 ──────────────────────────────────────────────────────

def run_small_only(problem: dict) -> RunResult:
    t0 = time.time()
    try:
        raw = SMALL_MODEL.call(
            "你是一个Python程序员。只输出代码，不要解释。",
            problem["prompt"],
        )
        code = extract_code(raw)
        passed, error = verify(code, problem["test_code"])
    except Exception as e:
        code = ""
        passed = False
        error = str(e)

    return RunResult(
        problem_id=problem["id"],
        problem_name=problem["name"],
        method="small-only",
        passed=passed,
        error=error,
        time_sec=time.time() - t0,
        api_calls=1,
    )


# ─── 方式 B: 大模型单干 ──────────────────────────────────────────────────────

def run_big_only(problem: dict) -> RunResult:
    t0 = time.time()
    try:
        raw = BIG_MODEL.call(
            "你是一个Python程序员。只输出代码，不要解释。",
            problem["prompt"],
        )
        code = extract_code(raw)
        passed, error = verify(code, problem["test_code"])
    except Exception as e:
        code = ""
        passed = False
        error = str(e)

    return RunResult(
        problem_id=problem["id"],
        problem_name=problem["name"],
        method="big-only",
        passed=passed,
        error=error,
        time_sec=time.time() - t0,
        api_calls=1,
    )


# ─── 方式 C: Brain-Worker ────────────────────────────────────────────────────

def run_brain_worker(problem: dict) -> RunResult:
    api_calls = 0

    def count_calls(evt: Event):
        nonlocal api_calls
        if evt.event == "done" and evt.phase in ("plan", "execute", "review", "synthesize"):
            api_calls += 1

    orch = Orchestrator(
        planner_model=BIG_MODEL,
        executor_model=SMALL_MODEL,
        review=True,
        max_retries=1,       # 控制成本，只重试1次
        max_parallel=1,      # 串行，方便计数
        on_event=count_calls,
    )

    t0 = time.time()
    try:
        raw = orch.run(problem["prompt"])
        code = extract_code(raw)
        passed, error = verify(code, problem["test_code"])
    except Exception as e:
        passed = False
        error = str(e)

    return RunResult(
        problem_id=problem["id"],
        problem_name=problem["name"],
        method="brain-worker",
        passed=passed,
        error=error,
        time_sec=time.time() - t0,
        api_calls=api_calls,
    )


# ─── 颜色 ────────────────────────────────────────────────────────────────────

def c(text, color):
    codes = {"green": "32", "red": "31", "yellow": "33", "bold": "1", "gray": "90", "cyan": "36"}
    return f"\033[{codes.get(color, '0')}m{text}\033[0m"


# ─── 主流程 ───────────────────────────────────────────────────────────────────

def main():
    results: list[RunResult] = []
    methods = [
        ("small-only", "小模型单干 (gpt-5-mini)", run_small_only),
        ("big-only", "大模型单干 (claude-opus-4.6)", run_big_only),
        ("brain-worker", "Brain-Worker (大规划+小执行)", run_brain_worker),
    ]

    for prob in PROBLEMS:
        print(f"\n{'=' * 60}")
        print(c(f"题目 {prob['id']}: {prob['name']}", "bold"))
        print(f"{'=' * 60}")

        for method_key, method_name, run_fn in methods:
            print(f"\n  {c(method_name, 'cyan')}...", end=" ", flush=True)
            r = run_fn(prob)
            results.append(r)

            status = c("PASS", "green") if r.passed else c("FAIL", "red")
            print(f"{status} ({r.time_sec:.1f}s, {r.api_calls} calls)", end="")
            if r.error:
                print(f" — {c(r.error[:80], 'gray')}", end="")
            print()

    # ─── 汇总 ────────────────────────────────────────────────────────────────

    print(f"\n\n{'=' * 80}")
    print(c("  BENCHMARK RESULTS", "bold"))
    print(f"{'=' * 80}\n")

    # 按方法统计
    for method_key, method_name, _ in methods:
        method_results = [r for r in results if r.method == method_key]
        passed = sum(1 for r in method_results if r.passed)
        total = len(method_results)
        total_time = sum(r.time_sec for r in method_results)
        total_calls = sum(r.api_calls for r in method_results)
        pct = passed / total * 100

        bar = c(f"{'█' * passed}{'░' * (total - passed)}", "green" if passed > 7 else "yellow" if passed > 4 else "red")
        print(f"  {method_name:<40} {bar} {passed}/{total} ({pct:.0f}%)")
        print(c(f"    耗时: {total_time:.0f}s | API调用: {total_calls} 次 | 平均: {total_time/total:.1f}s/题", "gray"))
        print()

    # 逐题对比表
    print(f"\n{'─' * 80}")
    print(f"  {'#':<4} {'题目':<20} {'小模型':<10} {'大模型':<10} {'BW':<10}")
    print(f"{'─' * 80}")
    for prob in PROBLEMS:
        row = f"  {prob['id']:<4} {prob['name']:<20}"
        for method_key in ["small-only", "big-only", "brain-worker"]:
            r = next(r for r in results if r.problem_id == prob["id"] and r.method == method_key)
            mark = c("PASS", "green") if r.passed else c("FAIL", "red")
            row += f" {mark:<19}"
        print(row)

    # 保存 JSON
    out = [{"id": r.problem_id, "name": r.problem_name, "method": r.method,
            "passed": r.passed, "error": r.error, "time": round(r.time_sec, 1),
            "api_calls": r.api_calls} for r in results]
    with open(os.path.join(os.path.dirname(__file__), "results", "correctness.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n  结果已保存到 benchmark_results.json")


if __name__ == "__main__":
    main()
