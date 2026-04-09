#!/usr/bin/env python3
"""
Large-Scale Skill Amortization Benchmark
==========================================
30 道 DP 题，难度从 Medium 到 Competition-Hard。
目标：找到小模型会失败的题，验证 skill 能否挽救。
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

# ─── 30 道 DP 题 ─────────────────────────────────────────────────────────────

PROBLEMS = [
    # ── Tier 1: Medium (baseline, should all pass) ────────────────────────────
    {"id": 1, "name": "爬楼梯", "tier": "Medium",
     "prompt": "写Python函数 climb_stairs(n: int) -> int，每次1或2阶，返回到第n阶的方法数。只输出函数。",
     "test": "assert climb_stairs(2)==2; assert climb_stairs(3)==3; assert climb_stairs(10)==89"},

    {"id": 2, "name": "打家劫舍", "tier": "Medium",
     "prompt": "写Python函数 rob(nums: list[int]) -> int，不偷相邻房屋，返回最大金额。只输出函数。",
     "test": "assert rob([1,2,3,1])==4; assert rob([2,7,9,3,1])==12"},

    {"id": 3, "name": "零钱兑换", "tier": "Medium",
     "prompt": "写Python函数 coin_change(coins: list[int], amount: int) -> int，最少硬币数，不可能返回-1。只输出函数。",
     "test": "assert coin_change([1,2,5],11)==3; assert coin_change([2],3)==-1; assert coin_change([1],0)==0"},

    {"id": 4, "name": "最长递增子序列", "tier": "Medium",
     "prompt": "写Python函数 length_of_lis(nums: list[int]) -> int，最长严格递增子序列长度，O(n log n)。只输出函数。",
     "test": "assert length_of_lis([10,9,2,5,3,7,101,18])==4; assert length_of_lis([0,1,0,3,2,3])==4; assert length_of_lis([7,7,7])==1"},

    {"id": 5, "name": "最长公共子序列", "tier": "Medium",
     "prompt": "写Python函数 longest_common_subsequence(text1: str, text2: str) -> int。只输出函数。",
     "test": 'assert longest_common_subsequence("abcde","ace")==3; assert longest_common_subsequence("abc","def")==0'},

    # ── Tier 2: Medium-Hard ───────────────────────────────────────────────────
    {"id": 6, "name": "编辑距离", "tier": "Medium-Hard",
     "prompt": "写Python函数 min_distance(word1: str, word2: str) -> int，最少编辑操作数（插入/删除/替换）。只输出函数。",
     "test": 'assert min_distance("horse","ros")==3; assert min_distance("intention","execution")==5'},

    {"id": 7, "name": "分割等和子集", "tier": "Medium-Hard",
     "prompt": "写Python函数 can_partition(nums: list[int]) -> bool，能否分成两个等和子集。只输出函数。",
     "test": "assert can_partition([1,5,11,5])==True; assert can_partition([1,2,3,5])==False"},

    {"id": 8, "name": "目标和", "tier": "Medium-Hard",
     "prompt": "写Python函数 find_target_sum_ways(nums: list[int], target: int) -> int，给每个数添加+或-，使总和等于target的方案数。只输出函数。",
     "test": "assert find_target_sum_ways([1,1,1,1,1],3)==5; assert find_target_sum_ways([1],1)==1; assert find_target_sum_ways([0,0,0,0,0],0)==32"},

    {"id": 9, "name": "最大正方形", "tier": "Medium-Hard",
     "prompt": "写Python函数 maximal_square(matrix: list[list[str]]) -> int，在01矩阵中找最大全1正方形，返回面积。只输出函数。",
     "test": """assert maximal_square([["1","0","1","0","0"],["1","0","1","1","1"],["1","1","1","1","1"],["1","0","0","1","0"]])==4; assert maximal_square([["0","1"],["1","0"]])==1; assert maximal_square([["0"]])==0"""},

    {"id": 10, "name": "不同路径II", "tier": "Medium-Hard",
     "prompt": "写Python函数 unique_paths_with_obstacles(grid: list[list[int]]) -> int，有障碍物(1)的网格中从左上到右下的路径数。只输出函数。",
     "test": "assert unique_paths_with_obstacles([[0,0,0],[0,1,0],[0,0,0]])==2; assert unique_paths_with_obstacles([[0,1],[0,0]])==1; assert unique_paths_with_obstacles([[1,0]])==0"},

    # ── Tier 3: Hard ──────────────────────────────────────────────────────────
    {"id": 11, "name": "戳气球", "tier": "Hard",
     "prompt": "写Python函数 max_coins(nums: list[int]) -> int，戳气球得分=左×自身×右，两端视为1，返回最大总分。只输出函数。",
     "test": "assert max_coins([3,1,5,8])==167; assert max_coins([1,5])==10"},

    {"id": 12, "name": "正则表达式匹配", "tier": "Hard",
     "prompt": "写Python函数 is_match(s: str, p: str) -> bool，'.'匹配任意单字符，'*'匹配零或多个前面的元素。只输出函数。",
     "test": 'assert is_match("aa","a")==False; assert is_match("aa","a*")==True; assert is_match("ab",".*")==True; assert is_match("aab","c*a*b")==True; assert is_match("mississippi","mis*is*p*.")==False'},

    {"id": 13, "name": "鸡蛋掉落", "tier": "Hard",
     "prompt": "写Python函数 super_egg_drop(k: int, n: int) -> int，k个鸡蛋n层楼，最坏情况下确定临界楼层的最少操作次数。只输出函数。",
     "test": "assert super_egg_drop(1,2)==2; assert super_egg_drop(2,6)==3; assert super_egg_drop(3,14)==4"},

    {"id": 14, "name": "通配符匹配", "tier": "Hard",
     "prompt": "写Python函数 is_wildcard_match(s: str, p: str) -> bool，'?'匹配任意单字符，'*'匹配任意字符串（含空串）。只输出函数。",
     "test": 'assert is_wildcard_match("aa","a")==False; assert is_wildcard_match("aa","*")==True; assert is_wildcard_match("cb","?a")==False; assert is_wildcard_match("adceb","*a*b")==True; assert is_wildcard_match("acdcb","a*c?b")==False'},

    {"id": 15, "name": "交错字符串", "tier": "Hard",
     "prompt": "写Python函数 is_interleave(s1: str, s2: str, s3: str) -> bool，判断s3是否由s1和s2交错组成。只输出函数。",
     "test": 'assert is_interleave("aabcc","dbbca","aadbbcbcac")==True; assert is_interleave("aabcc","dbbca","aadbbbaccc")==False; assert is_interleave("","","")==True'},

    # ── Tier 4: Hard+ (非标准 DP) ─────────────────────────────────────────────
    {"id": 16, "name": "最长有效括号", "tier": "Hard+",
     "prompt": "写Python函数 longest_valid_parentheses(s: str) -> int，返回最长有效括号子串的长度。只输出函数。",
     "test": 'assert longest_valid_parentheses("(()")==2; assert longest_valid_parentheses(")()())")==4; assert longest_valid_parentheses("")==0; assert longest_valid_parentheses("()(())")==6'},

    {"id": 17, "name": "不同的子序列", "tier": "Hard+",
     "prompt": "写Python函数 num_distinct(s: str, t: str) -> int，返回s的子序列中等于t的个数。只输出函数。",
     "test": 'assert num_distinct("rabbbit","rabbit")==3; assert num_distinct("babgbag","bag")==5; assert num_distinct("a","b")==0'},

    {"id": 18, "name": "最小覆盖子串DP", "tier": "Hard+",
     "prompt": "写Python函数 min_window(s: str, t: str) -> str，返回s中包含t所有字符的最短子串，不存在返回空字符串。只输出函数。",
     "test": 'assert min_window("ADOBECODEBANC","ABC")=="BANC"; assert min_window("a","a")=="a"; assert min_window("a","aa")==""'},

    {"id": 19, "name": "回文分割II", "tier": "Hard+",
     "prompt": "写Python函数 min_cut(s: str) -> int，返回将s分割成回文子串的最少切割次数。只输出函数。",
     "test": 'assert min_cut("aab")==1; assert min_cut("a")==0; assert min_cut("ab")==1; assert min_cut("aaabaa")==1'},

    {"id": 20, "name": "打家劫舍III(树形DP)", "tier": "Hard+",
     "prompt": """写Python代码：TreeNode类(val,left,right) + rob_tree(root: TreeNode) -> int。二叉树上不能同时偷直接相连的节点，返回最大金额。只输出代码。""",
     "test": """r=TreeNode(3);r.left=TreeNode(2);r.right=TreeNode(3);r.left.right=TreeNode(3);r.right.right=TreeNode(1);assert rob_tree(r)==7
r2=TreeNode(3);r2.left=TreeNode(4);r2.right=TreeNode(5);r2.left.left=TreeNode(1);r2.left.right=TreeNode(3);r2.right.right=TreeNode(1);assert rob_tree(r2)==9"""},

    # ── Tier 5: Expert (竞赛级) ───────────────────────────────────────────────
    {"id": 21, "name": "俄罗斯套娃信封", "tier": "Expert",
     "prompt": "写Python函数 max_envelopes(envelopes: list[list[int]]) -> int，信封[w,h]可以嵌套当且仅当宽和高都严格更大，返回最多嵌套层数。要求优于O(n^2)。只输出函数。",
     "test": "assert max_envelopes([[5,4],[6,4],[6,7],[2,3]])==3; assert max_envelopes([[1,1],[1,1],[1,1]])==1"},

    {"id": 22, "name": "最大矩形", "tier": "Expert",
     "prompt": "写Python函数 maximal_rectangle(matrix: list[list[str]]) -> int，在01矩阵中找最大全1矩形的面积。只输出函数。",
     "test": """assert maximal_rectangle([["1","0","1","0","0"],["1","0","1","1","1"],["1","1","1","1","1"],["1","0","0","1","0"]])==6; assert maximal_rectangle([["0"]])==0; assert maximal_rectangle([["1"]])==1"""},

    {"id": 23, "name": "K站中转最便宜航班", "tier": "Expert",
     "prompt": "写Python函数 find_cheapest_price(n: int, flights: list[list[int]], src: int, dst: int, k: int) -> int，n个城市，flights[i]=[from,to,price]，最多经过k站中转，返回最便宜价格，不可达返回-1。只输出函数。",
     "test": "assert find_cheapest_price(4,[[0,1,100],[1,2,100],[2,0,100],[1,3,600],[2,3,200]],0,3,1)==700; assert find_cheapest_price(3,[[0,1,100],[1,2,100],[0,2,500]],0,2,1)==200; assert find_cheapest_price(3,[[0,1,100],[1,2,100],[0,2,500]],0,2,0)==500"},

    {"id": 24, "name": "最大子数组乘积", "tier": "Expert",
     "prompt": "写Python函数 max_product(nums: list[int]) -> int，返回连续子数组的最大乘积。只输出函数。",
     "test": "assert max_product([2,3,-2,4])==6; assert max_product([-2,0,-1])==0; assert max_product([-2,3,-4])==24; assert max_product([-2])==-2"},

    {"id": 25, "name": "奇怪的打印机", "tier": "Expert",
     "prompt": "写Python函数 strange_printer(s: str) -> int，打印机每次可以打印一段相同字符覆盖已有内容，返回打印s所需的最少次数。只输出函数。",
     "test": 'assert strange_printer("aaabbb")==2; assert strange_printer("aba")==2; assert strange_printer("abcba")==3'},

    {"id": 26, "name": "自由之路(转盘DP)", "tier": "Expert",
     "prompt": "写Python函数 find_rotate_steps(ring: str, key: str) -> int，圆形转盘ring，拼写key中每个字符需要旋转到12点位置并按下，返回最少步数（旋转+按下）。每次旋转1格算1步，按下算1步。只输出函数。",
     "test": 'assert find_rotate_steps("godding","gd")==4; assert find_rotate_steps("godding","godding")==13'},

    {"id": 27, "name": "学生出勤记录II", "tier": "Expert",
     "prompt": "写Python函数 check_record(n: int) -> int，长度为n的出勤记录由A(缺勤)L(迟到)P(出勤)组成，要求A不超过1次且不连续3个L，返回满足条件的记录数对10**9+7取模。只输出函数。",
     "test": "assert check_record(2)==8; assert check_record(1)==3; assert check_record(10101)==183236316"},

    {"id": 28, "name": "猜数字大小II", "tier": "Expert",
     "prompt": "写Python函数 get_money_amount(n: int) -> int，从1到n猜数字，猜错付猜的数的金额，返回保证能赢的最少金额。只输出函数。",
     "test": "assert get_money_amount(10)==16; assert get_money_amount(1)==0; assert get_money_amount(2)==1"},

    {"id": 29, "name": "矩阵中的最长递增路径", "tier": "Expert",
     "prompt": "写Python函数 longest_increasing_path(matrix: list[list[int]]) -> int，在矩阵中找最长严格递增路径长度（上下左右移动）。只输出函数。",
     "test": "assert longest_increasing_path([[9,9,4],[6,6,8],[2,1,1]])==4; assert longest_increasing_path([[3,4,5],[3,2,6],[2,2,1]])==4; assert longest_increasing_path([[1]])==1"},

    {"id": 30, "name": "最大整除子集", "tier": "Expert",
     "prompt": "写Python函数 largest_divisible_subset(nums: list[int]) -> list[int]，返回最大子集使得每对元素满足整除关系，结果升序。只输出函数。",
     "test": "r=largest_divisible_subset([1,2,3]); assert (r==[1,2] or r==[1,3]); assert largest_divisible_subset([1,2,4,8])==[1,2,4,8]"},
]

# ─── Skill 生成 ──────────────────────────────────────────────────────────────

SKILL_PROMPT = """\
你是算法教练。写一个精简的「DP 解题 Skill」给一个 AI 模型用。

要求：
- 总长度控制在 500 字以内
- 只写可直接套用的模板和规则，不要教学解释
- 包含：5 步解题流程 + 常见模式的状态定义和转移方程模板
- 覆盖：线性DP、区间DP、背包DP、树形DP、状态机DP
- 每种模式用 1-2 行伪代码表示
- 用中文"""

def generate_skill(counter):
    print("  生成 DP Skill...", end=" ", flush=True)
    t0 = time.time()
    skill = call_big("你是算法教练，写精简的解题模板。", SKILL_PROMPT, counter)
    print(f"完成 ({time.time()-t0:.1f}s, {counter.total} tokens, {len(skill)} chars)")
    return skill

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
    codes = {"green":"32","red":"31","yellow":"33","bold":"1","gray":"90","cyan":"36"}
    return f"\033[{codes.get(color,'0')}m{t}\033[0m"

# ─── 主流程 ───────────────────────────────────────────────────────────────────

def main():
    print(c("\n  Large-Scale DP Benchmark: 30 problems, 5 tiers", "bold"))
    print(c("  Comparing: small bare vs small+skill vs big model\n", "gray"))

    # 生成 Skill
    skill_counter = Counter()
    skill = generate_skill(skill_counter)
    with open(os.path.join(RESULTS_DIR, "dp_skill_v2.md"), "w") as f:
        f.write(skill)

    bare_sys = "你是Python程序员。只输出函数代码，不要解释。"
    guided_sys = f"你是Python程序员。只输出函数代码，不要解释。\n\n以下是DP解题技巧，请参考：\n\n{skill}"

    # 统计
    bare_c = Counter()
    guided_c = Counter()
    big_c = Counter()
    results = []

    current_tier = ""
    for p in PROBLEMS:
        if p["tier"] != current_tier:
            current_tier = p["tier"]
            print(f"\n  {'─'*55}")
            print(c(f"  Tier: {current_tier}", "bold"))
            print(f"  {'─'*55}")

        # A: 小模型裸做
        try:
            raw_a = call_small(bare_sys, p["prompt"], bare_c)
            pass_a = verify(extract_code(raw_a), p["test"])
        except Exception:
            pass_a = False

        # B: 小模型+Skill
        try:
            raw_b = call_small(guided_sys, p["prompt"], guided_c)
            pass_b = verify(extract_code(raw_b), p["test"])
        except Exception:
            pass_b = False

        # C: 大模型
        try:
            raw_c = call_big(bare_sys, p["prompt"], big_c)
            pass_c = verify(extract_code(raw_c), p["test"])
        except Exception:
            pass_c = False

        ma = c("✓","green") if pass_a else c("✗","red")
        mb = c("✓","green") if pass_b else c("✗","red")
        mc = c("✓","green") if pass_c else c("✗","red")

        # 标记 skill 挽救的题
        rescued = "  ◀ RESCUED" if (not pass_a and pass_b) else ""
        degraded = "  ◀ DEGRADED" if (pass_a and not pass_b) else ""
        print(f"  {p['id']:>2}. {p['name']:<18} bare:{ma}  +skill:{mb}  big:{mc}{c(rescued,'cyan')}{c(degraded,'red')}")

        results.append({
            "id": p["id"], "name": p["name"], "tier": p["tier"],
            "bare": pass_a, "guided": pass_b, "big": pass_c,
        })

    # ─── 汇总 ────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(c("  RESULTS SUMMARY", "bold"))
    print(f"{'='*60}\n")

    for tier in ["Medium", "Medium-Hard", "Hard", "Hard+", "Expert"]:
        tier_r = [r for r in results if r["tier"] == tier]
        n = len(tier_r)
        ba = sum(1 for r in tier_r if r["bare"])
        gu = sum(1 for r in tier_r if r["guided"])
        bi = sum(1 for r in tier_r if r["big"])
        rescued = sum(1 for r in tier_r if not r["bare"] and r["guided"])
        degraded = sum(1 for r in tier_r if r["bare"] and not r["guided"])
        print(f"  {tier:<14}  bare: {ba}/{n}  +skill: {gu}/{n}  big: {bi}/{n}  rescued: {rescued}  degraded: {degraded}")

    total = len(results)
    ba_t = sum(1 for r in results if r["bare"])
    gu_t = sum(1 for r in results if r["guided"])
    bi_t = sum(1 for r in results if r["big"])
    rescued_t = sum(1 for r in results if not r["bare"] and r["guided"])
    degraded_t = sum(1 for r in results if r["bare"] and not r["guided"])

    print(f"  {'─'*55}")
    print(f"  {'TOTAL':<14}  bare: {ba_t}/{total}  +skill: {gu_t}/{total}  big: {bi_t}/{total}  rescued: {rescued_t}  degraded: {degraded_t}")

    print(f"\n  Token (output only):")
    print(f"    bare:    out={bare_c.output_tokens:,}  reason={bare_c.reasoning_tokens:,}")
    print(f"    +skill:  out={guided_c.output_tokens:,}  reason={guided_c.reasoning_tokens:,}")
    print(f"    big:     out={big_c.output_tokens:,}")
    print(f"    skill生成: out={skill_counter.output_tokens:,} (一次性)")

    if bare_c.output_tokens > 0:
        save = bare_c.output_tokens - guided_c.output_tokens
        reason_save = bare_c.reasoning_tokens - guided_c.reasoning_tokens
        print(f"\n  output节省: {save:,} ({save/bare_c.output_tokens*100:.1f}%)")
        print(f"  reasoning节省: {reason_save:,} ({reason_save/bare_c.reasoning_tokens*100:.1f}%)" if bare_c.reasoning_tokens else "")

    # 保存
    out = {
        "skill_tokens": skill_counter.__dict__,
        "bare_tokens": bare_c.__dict__, "guided_tokens": guided_c.__dict__,
        "big_tokens": big_c.__dict__, "results": results,
    }
    with open(os.path.join(RESULTS_DIR, "large_scale.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n  结果已保存到 results/large_scale.json")

if __name__ == "__main__":
    main()
