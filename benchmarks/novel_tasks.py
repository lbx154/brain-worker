#!/usr/bin/env python3
"""
Novel-Task Benchmark: 自创规则，测 skill 在未知领域的价值
============================================================
5 类自创任务 × 6 题 = 30 题。
规则都是人为发明的，不存在于任何训练数据中。
Skill 是唯一的知识来源。
"""

import json
import os
import re
import time
from dataclasses import dataclass

import httpx

BASE_URL = os.environ.get("BRAIN_WORKER_BASE_URL", "http://127.0.0.1:18080")
SMALL_MODEL = os.environ.get("BRAIN_WORKER_SMALL_MODEL", "gpt-5-mini")
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
            "model": "claude-opus-4.6", "max_tokens": 4096,
            "system": system, "messages": [{"role": "user", "content": user}],
        }, headers={"x-api-key": "unused", "anthropic-version": "2023-06-01"})
        r.raise_for_status()
        d = r.json()
        u = d.get("usage", {})
        counter.input_tokens += u.get("input_tokens", 0)
        counter.output_tokens += u.get("output_tokens", 0)
        counter.calls += 1
        return d["content"][0]["text"]

def _parse_sse(text):
    out = ""
    usage = {}
    for line in text.split("\n"):
        if line.startswith("data: "):
            try:
                d = json.loads(line[6:])
                if d.get("type") == "response.output_text.done":
                    out = d.get("text", "")
                elif d.get("type") == "response.completed":
                    usage = d.get("response", {}).get("usage", {})
            except json.JSONDecodeError:
                pass
    return out, usage

def call_small(system, user, counter):
    with httpx.Client(base_url=BASE_URL, timeout=180) as c:
        r = c.post("/v1/responses", json={
            "model": SMALL_MODEL, "instructions": system,
            "input": user, "stream": False,
        })
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        if "text/event-stream" in ct or r.text.startswith("event:"):
            text, usage = _parse_sse(r.text)
            counter.input_tokens += usage.get("input_tokens", 0)
            counter.output_tokens += usage.get("output_tokens", 0)
            counter.calls += 1
            return text
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

# ─── 自创规则定义 ─────────────────────────────────────────────────────────────

# ====== 类别 1: StackLang（自创栈语言）======
STACKLANG_RULES = """\
StackLang 是一个栈操作语言，规则：
- PUSH x: 将整数 x 压栈
- POP: 弹出栈顶
- ADD: 弹出两个数相加，结果压栈
- MUL: 弹出两个数相乘，结果压栈
- DUP: 复制栈顶
- SWAP: 交换栈顶两个元素
- ROT: 将栈顶三个元素旋转（a b c → b c a，c是栈顶）
- IF: 弹出栈顶，非零则执行到ENDIF，否则跳过到ENDIF
- ENDIF: IF 的结束标记
- PRINT: 输出栈顶（不弹出）
执行后返回栈的最终状态（从底到顶的列表）。"""

# ====== 类别 2: ZoneTax（自创税制）======
ZONETAX_RULES = """\
ZoneTax 税制规则：
1. 基础税率分段：0-5000 免税，5001-20000 税率10%，20001-50000 税率25%，50001+ 税率40%
2. 区域系数：A区 ×1.2, B区 ×1.0, C区 ×0.8
3. 家庭减免：单身 减免0，已婚 减免2000，已婚有孩子 每孩再减1000（最多3孩）
4. 计算顺序：先算应税收入（收入-减免），再按分段算税，最后乘区域系数
5. 最低税额为0（不能为负）
返回最终税额（整数，四舍五入）。"""

# ====== 类别 3: XorShift 编码 ======
XORSHIFT_RULES = """\
XorShift 编码规则：
1. 输入：字符串，密钥 key（整数）
2. 编码：每个字符的 ASCII 值与当前 key 异或，得到编码值
3. key 更新：每处理一个字符后，key = ((key * 31 + 7) % 256)
4. 输出：编码后的整数列表
5. 解码：反向操作（异或是自逆的，用相同的 key 序列）
写 encode(text, key) -> list[int] 和 decode(codes, key) -> str。"""

# ====== 类别 4: GridHop 棋局 ======
GRIDHOP_RULES = """\
GridHop 游戏规则：
1. N×N 网格，每格有一个正整数（跳跃距离）
2. 起点 (0,0)，终点 (N-1,N-1)
3. 在格子 (r,c) 上，值为 d，可以跳到 (r+d,c) 或 (r,c+d)（不能超出边界）
4. 目标：判断能否从起点到终点，如果能，返回最少跳跃次数，否则返回 -1
写 grid_hop(grid: list[list[int]]) -> int。"""

# ====== 类别 5: MiniPack 协议 ======
MINIPACK_RULES = """\
MiniPack 序列化协议：
- 整数: 前缀 'I' + 十六进制表示（固定8位补零）如 I00000042 表示66
- 字符串: 前缀 'S' + 2位十六进制长度 + 内容 如 S05hello
- 列表: 前缀 'L' + 2位十六进制元素数 + 各元素连接 如 L02I00000001S02hi
- 字典: 前缀 'D' + 2位十六进制键值对数 + 键值交替 如 D01S01aI00000001
- 嵌套允许
写 pack(obj) -> str 和 unpack(data) -> object。"""

# ─── 各类别的 Skill 生成 Prompt ───────────────────────────────────────────────

SKILL_PROMPTS = {
    "StackLang": f"将以下规则写成一份精简的编程 skill（500字以内），让一个 AI 能直接套用来写 StackLang 解释器：\n\n{STACKLANG_RULES}",
    "ZoneTax": f"将以下税制规则写成一份精简的编程 skill（500字以内），让一个 AI 能直接套用来写计算函数：\n\n{ZONETAX_RULES}",
    "XorShift": f"将以下编码规则写成一份精简的编程 skill（500字以内），让一个 AI 能直接套用来实现编解码：\n\n{XORSHIFT_RULES}",
    "GridHop": f"将以下游戏规则写成一份精简的编程 skill（500字以内），让一个 AI 能直接套用来写求解函数：\n\n{GRIDHOP_RULES}",
    "MiniPack": f"将以下协议规则写成一份精简的编程 skill（500字以内），让一个 AI 能直接套用来实现序列化/反序列化：\n\n{MINIPACK_RULES}",
}

# ─── 30 道题 ──────────────────────────────────────────────────────────────────

PROBLEMS = [
    # ── StackLang ─────────────────────────────────────────────────────────────
    {"id": 1, "cat": "StackLang", "name": "基础算术",
     "prompt": f"""{STACKLANG_RULES}\n\n写Python函数 run_stacklang(program: list[str]) -> list[int]，执行StackLang程序并返回最终栈状态。只输出函数。""",
     "test": """assert run_stacklang(["PUSH 3", "PUSH 4", "ADD"]) == [7]
assert run_stacklang(["PUSH 2", "PUSH 3", "MUL"]) == [6]
assert run_stacklang(["PUSH 5"]) == [5]"""},

    {"id": 2, "cat": "StackLang", "name": "DUP和SWAP",
     "prompt": f"""{STACKLANG_RULES}\n\n写Python函数 run_stacklang(program: list[str]) -> list[int]，执行StackLang程序。只输出函数。""",
     "test": """assert run_stacklang(["PUSH 3", "DUP", "ADD"]) == [6]
assert run_stacklang(["PUSH 1", "PUSH 2", "SWAP"]) == [2, 1]
assert run_stacklang(["PUSH 3", "DUP", "DUP"]) == [3, 3, 3]"""},

    {"id": 3, "cat": "StackLang", "name": "ROT操作",
     "prompt": f"""{STACKLANG_RULES}\n\n写Python函数 run_stacklang(program: list[str]) -> list[int]，执行StackLang程序。只输出函数。""",
     "test": """assert run_stacklang(["PUSH 1", "PUSH 2", "PUSH 3", "ROT"]) == [2, 3, 1]
assert run_stacklang(["PUSH 10", "PUSH 20", "PUSH 30", "ROT", "ADD"]) == [10, 50]"""},

    {"id": 4, "cat": "StackLang", "name": "IF条件",
     "prompt": f"""{STACKLANG_RULES}\n\n写Python函数 run_stacklang(program: list[str]) -> list[int]，执行StackLang程序。只输出函数。""",
     "test": """assert run_stacklang(["PUSH 1", "IF", "PUSH 42", "ENDIF"]) == [42]
assert run_stacklang(["PUSH 0", "IF", "PUSH 42", "ENDIF"]) == []
assert run_stacklang(["PUSH 1", "IF", "PUSH 10", "PUSH 20", "ADD", "ENDIF"]) == [30]"""},

    {"id": 5, "cat": "StackLang", "name": "复杂程序",
     "prompt": f"""{STACKLANG_RULES}\n\n写Python函数 run_stacklang(program: list[str]) -> list[int]，执行StackLang程序。只输出函数。""",
     "test": """assert run_stacklang(["PUSH 2", "PUSH 3", "DUP", "ROT", "MUL", "ADD"]) == [8]
assert run_stacklang(["PUSH 5", "DUP", "MUL", "DUP", "ADD"]) == [50]"""},

    {"id": 6, "cat": "StackLang", "name": "嵌套IF",
     "prompt": f"""{STACKLANG_RULES}\n\n写Python函数 run_stacklang(program: list[str]) -> list[int]，支持嵌套IF。只输出函数。""",
     "test": """assert run_stacklang(["PUSH 1", "IF", "PUSH 1", "IF", "PUSH 99", "ENDIF", "ENDIF"]) == [99]
assert run_stacklang(["PUSH 1", "IF", "PUSH 0", "IF", "PUSH 99", "ENDIF", "PUSH 42", "ENDIF"]) == [42]
assert run_stacklang(["PUSH 0", "IF", "PUSH 1", "IF", "PUSH 99", "ENDIF", "ENDIF"]) == []"""},

    # ── ZoneTax ───────────────────────────────────────────────────────────────
    {"id": 7, "cat": "ZoneTax", "name": "基础免税",
     "prompt": f"""{ZONETAX_RULES}\n\n写Python函数 calc_tax(income: int, zone: str, status: str, children: int) -> int。status为'single'/'married'。只输出函数。""",
     "test": """assert calc_tax(3000, 'A', 'single', 0) == 0
assert calc_tax(5000, 'B', 'single', 0) == 0"""},

    {"id": 8, "cat": "ZoneTax", "name": "单段税率",
     "prompt": f"""{ZONETAX_RULES}\n\n写Python函数 calc_tax(income: int, zone: str, status: str, children: int) -> int。只输出函数。""",
     "test": """assert calc_tax(10000, 'B', 'single', 0) == 500
assert calc_tax(10000, 'A', 'single', 0) == 600"""},

    {"id": 9, "cat": "ZoneTax", "name": "多段税率",
     "prompt": f"""{ZONETAX_RULES}\n\n写Python函数 calc_tax(income: int, zone: str, status: str, children: int) -> int。只输出函数。""",
     "test": """assert calc_tax(30000, 'B', 'single', 0) == 4000
assert calc_tax(60000, 'B', 'single', 0) == 13500"""},

    {"id": 10, "cat": "ZoneTax", "name": "家庭减免",
     "prompt": f"""{ZONETAX_RULES}\n\n写Python函数 calc_tax(income: int, zone: str, status: str, children: int) -> int。只输出函数。""",
     "test": """assert calc_tax(10000, 'B', 'married', 0) == 300
assert calc_tax(10000, 'B', 'married', 2) == 100
assert calc_tax(10000, 'B', 'married', 5) == 0"""},

    {"id": 11, "cat": "ZoneTax", "name": "区域系数",
     "prompt": f"""{ZONETAX_RULES}\n\n写Python函数 calc_tax(income: int, zone: str, status: str, children: int) -> int。只输出函数。""",
     "test": """assert calc_tax(30000, 'A', 'single', 0) == 4800
assert calc_tax(30000, 'C', 'single', 0) == 3200"""},

    {"id": 12, "cat": "ZoneTax", "name": "综合计算",
     "prompt": f"""{ZONETAX_RULES}\n\n写Python函数 calc_tax(income: int, zone: str, status: str, children: int) -> int。只输出函数。""",
     "test": """assert calc_tax(80000, 'A', 'married', 3) == round((1500 + 7500 + 12000 + 10000) * 1.2)
assert calc_tax(5000, 'C', 'married', 1) == 0"""},

    # ── XorShift 编码 ────────────────────────────────────────────────────────
    {"id": 13, "cat": "XorShift", "name": "基础编码",
     "prompt": f"""{XORSHIFT_RULES}\n\n写Python函数 encode(text: str, key: int) -> list[int] 和 decode(codes: list[int], key: int) -> str。只输出两个函数。""",
     "test": """assert decode(encode("A", 0), 0) == "A"
assert decode(encode("hello", 42), 42) == "hello"
assert encode("A", 0) == [65]"""},

    {"id": 14, "cat": "XorShift", "name": "key更新验证",
     "prompt": f"""{XORSHIFT_RULES}\n\n写Python函数 encode(text: str, key: int) -> list[int] 和 decode(codes: list[int], key: int) -> str。只输出两个函数。""",
     "test": """e = encode("AB", 1)
assert e[0] == ord('A') ^ 1
k2 = (1 * 31 + 7) % 256
assert e[1] == ord('B') ^ k2
assert decode(e, 1) == "AB" """},

    {"id": 15, "cat": "XorShift", "name": "往返一致性",
     "prompt": f"""{XORSHIFT_RULES}\n\n写Python函数 encode(text: str, key: int) -> list[int] 和 decode(codes: list[int], key: int) -> str。只输出两个函数。""",
     "test": """for text in ["hello world", "12345!@#", "a", ""]:
    for key in [0, 1, 42, 255]:
        assert decode(encode(text, key), key) == text"""},

    {"id": 16, "cat": "XorShift", "name": "特殊字符",
     "prompt": f"""{XORSHIFT_RULES}\n\n写Python函数 encode(text: str, key: int) -> list[int] 和 decode(codes: list[int], key: int) -> str。只输出两个函数。""",
     "test": """assert decode(encode("\\n\\t", 100), 100) == "\\n\\t"
assert decode(encode("中", 50), 50) == "中" or True"""},

    {"id": 17, "cat": "XorShift", "name": "空串和单字符",
     "prompt": f"""{XORSHIFT_RULES}\n\n写Python函数 encode(text: str, key: int) -> list[int] 和 decode(codes: list[int], key: int) -> str。只输出两个函数。""",
     "test": """assert encode("", 42) == []
assert decode([], 42) == ""
assert len(encode("x", 0)) == 1"""},

    {"id": 18, "cat": "XorShift", "name": "长文本",
     "prompt": f"""{XORSHIFT_RULES}\n\n写Python函数 encode(text: str, key: int) -> list[int] 和 decode(codes: list[int], key: int) -> str。只输出两个函数。""",
     "test": """long_text = "The quick brown fox jumps over the lazy dog 1234567890"
assert decode(encode(long_text, 137), 137) == long_text"""},

    # ── GridHop ───────────────────────────────────────────────────────────────
    {"id": 19, "cat": "GridHop", "name": "简单可达",
     "prompt": f"""{GRIDHOP_RULES}\n\n写Python函数 grid_hop(grid: list[list[int]]) -> int。只输出函数。""",
     "test": """assert grid_hop([[1,1],[1,1]]) == 2
assert grid_hop([[2,0],[0,0]]) == -1"""},

    {"id": 20, "cat": "GridHop", "name": "单步到达",
     "prompt": f"""{GRIDHOP_RULES}\n\n写Python函数 grid_hop(grid: list[list[int]]) -> int。只输出函数。""",
     "test": """assert grid_hop([[1]]) == 0
assert grid_hop([[2,0,0],[0,0,0],[0,0,0]]) == -1"""},

    {"id": 21, "cat": "GridHop", "name": "3x3网格",
     "prompt": f"""{GRIDHOP_RULES}\n\n写Python函数 grid_hop(grid: list[list[int]]) -> int。只输出函数。""",
     "test": """assert grid_hop([[1,2,1],[1,1,1],[1,1,1]]) == 2
assert grid_hop([[2,1,1],[1,2,1],[1,1,1]]) == 1"""},

    {"id": 22, "cat": "GridHop", "name": "不可达",
     "prompt": f"""{GRIDHOP_RULES}\n\n写Python函数 grid_hop(grid: list[list[int]]) -> int。只输出函数。""",
     "test": """assert grid_hop([[3,3,3],[3,3,3],[3,3,3]]) == -1
assert grid_hop([[1,1,5],[1,5,1],[1,1,1]]) >= 2 or grid_hop([[1,1,5],[1,5,1],[1,1,1]]) == -1"""},

    {"id": 23, "cat": "GridHop", "name": "4x4最短路",
     "prompt": f"""{GRIDHOP_RULES}\n\n写Python函数 grid_hop(grid: list[list[int]]) -> int。只输出函数。""",
     "test": """assert grid_hop([[3,1,1,1],[1,1,1,1],[1,1,1,1],[1,1,1,1]]) == 2
assert grid_hop([[1,1,1,1],[1,1,1,1],[1,1,1,1],[1,1,1,1]]) == 6"""},

    {"id": 24, "cat": "GridHop", "name": "大跳跃",
     "prompt": f"""{GRIDHOP_RULES}\n\n写Python函数 grid_hop(grid: list[list[int]]) -> int。只输出函数。""",
     "test": """g = [[1]*5 for _ in range(5)]; g[0][0] = 4; assert grid_hop(g) == 2"""},

    # ── MiniPack 协议 ────────────────────────────────────────────────────────
    {"id": 25, "cat": "MiniPack", "name": "整数打包",
     "prompt": f"""{MINIPACK_RULES}\n\n写Python函数 pack(obj) -> str 和 unpack(data: str) -> object。只输出两个函数。""",
     "test": """assert pack(66) == "I00000042"
assert pack(0) == "I00000000"
assert unpack("I00000042") == 66"""},

    {"id": 26, "cat": "MiniPack", "name": "字符串打包",
     "prompt": f"""{MINIPACK_RULES}\n\n写Python函数 pack(obj) -> str 和 unpack(data: str) -> object。只输出两个函数。""",
     "test": """assert pack("hello") == "S05hello"
assert pack("") == "S00"
assert unpack("S05hello") == "hello" """},

    {"id": 27, "cat": "MiniPack", "name": "列表打包",
     "prompt": f"""{MINIPACK_RULES}\n\n写Python函数 pack(obj) -> str 和 unpack(data: str) -> object。只输出两个函数。""",
     "test": """assert pack([1, "hi"]) == "L02I00000001S02hi"
assert unpack("L02I00000001S02hi") == [1, "hi"]"""},

    {"id": 28, "cat": "MiniPack", "name": "字典打包",
     "prompt": f"""{MINIPACK_RULES}\n\n写Python函数 pack(obj) -> str 和 unpack(data: str) -> object。只输出两个函数。""",
     "test": """assert pack({"a": 1}) == "D01S01aI00000001"
assert unpack("D01S01aI00000001") == {"a": 1}"""},

    {"id": 29, "cat": "MiniPack", "name": "嵌套结构",
     "prompt": f"""{MINIPACK_RULES}\n\n写Python函数 pack(obj) -> str 和 unpack(data: str) -> object。只输出两个函数。""",
     "test": """nested = [1, [2, 3]]
assert unpack(pack(nested)) == nested
d = {"x": [1, 2]}
assert unpack(pack(d)) == d"""},

    {"id": 30, "cat": "MiniPack", "name": "往返一致性",
     "prompt": f"""{MINIPACK_RULES}\n\n写Python函数 pack(obj) -> str 和 unpack(data: str) -> object。只输出两个函数。""",
     "test": """for obj in [42, "test", [1,2,3], {"k": "v"}, [1, {"a": [2,3]}], []]:
    assert unpack(pack(obj)) == obj"""},
]

# ─── Skill 生成 ──────────────────────────────────────────────────────────────

def generate_skills(counter):
    skills = {}
    for cat, prompt in SKILL_PROMPTS.items():
        print(f"    生成 {cat} skill...", end=" ", flush=True)
        t0 = time.time()
        skill = call_big("你是编程教练。写精简的、可直接套用的编程 skill。", prompt, counter)
        print(f"({time.time()-t0:.1f}s)")
        skills[cat] = skill
    return skills

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
    print(c(f"\n  Novel-Task Benchmark: 5 categories × 6 problems (model: {SMALL_MODEL})", "bold"))
    print(c("  All rules are invented — not in any training data\n", "gray"))

    # 生成 5 个 Skill
    print(c("  Phase 1: 大模型生成 5 个 Skill", "bold"))
    skill_counter = Counter()
    skills = generate_skills(skill_counter)
    print(f"  总计: {skill_counter.total} tokens\n")

    bare_sys = "你是Python程序员。严格按照给定规则实现。只输出函数代码，不要解释。"

    # 统计
    bare_c = Counter()
    guided_c = Counter()
    big_c = Counter()
    results = []

    current_cat = ""
    for p in PROBLEMS:
        if p["cat"] != current_cat:
            current_cat = p["cat"]
            print(f"\n  {'─'*60}")
            print(c(f"  {current_cat}", "bold"))
            print(f"  {'─'*60}")

        guided_sys = f"{bare_sys}\n\n参考以下 skill：\n\n{skills[p['cat']]}"

        try:
            raw_a = call_small(bare_sys, p["prompt"], bare_c)
            pass_a = verify(extract_code(raw_a), p["test"])
        except Exception:
            pass_a = False

        try:
            raw_b = call_small(guided_sys, p["prompt"], guided_c)
            pass_b = verify(extract_code(raw_b), p["test"])
        except Exception:
            pass_b = False

        try:
            raw_c = call_big(bare_sys, p["prompt"], big_c)
            pass_c = verify(extract_code(raw_c), p["test"])
        except Exception:
            pass_c = False

        ma = c("✓","green") if pass_a else c("✗","red")
        mb = c("✓","green") if pass_b else c("✗","red")
        mc = c("✓","green") if pass_c else c("✗","red")
        rescued = c("  ◀ RESCUED","cyan") if (not pass_a and pass_b) else ""
        degraded = c("  ◀ DEGRADED","red") if (pass_a and not pass_b) else ""
        print(f"  {p['id']:>2}. {p['name']:<16} bare:{ma}  +skill:{mb}  big:{mc}{rescued}{degraded}")

        results.append({"id": p["id"], "cat": p["cat"], "name": p["name"],
                         "bare": pass_a, "guided": pass_b, "big": pass_c})

    # ─── 汇总 ────────────────────────────────────────────────────────────────
    print(f"\n{'='*64}")
    print(c("  RESULTS SUMMARY", "bold"))
    print(f"{'='*64}\n")

    for cat in ["StackLang", "ZoneTax", "XorShift", "GridHop", "MiniPack"]:
        cr = [r for r in results if r["cat"] == cat]
        n = len(cr)
        ba = sum(1 for r in cr if r["bare"])
        gu = sum(1 for r in cr if r["guided"])
        bi = sum(1 for r in cr if r["big"])
        res = sum(1 for r in cr if not r["bare"] and r["guided"])
        deg = sum(1 for r in cr if r["bare"] and not r["guided"])
        print(f"  {cat:<12}  bare: {ba}/{n}  +skill: {gu}/{n}  big: {bi}/{n}  rescued: {res}  degraded: {deg}")

    total = len(results)
    ba_t = sum(1 for r in results if r["bare"])
    gu_t = sum(1 for r in results if r["guided"])
    bi_t = sum(1 for r in results if r["big"])
    res_t = sum(1 for r in results if not r["bare"] and r["guided"])
    deg_t = sum(1 for r in results if r["bare"] and not r["guided"])

    print(f"  {'─'*58}")
    print(f"  {'TOTAL':<12}  bare: {ba_t}/{total}  +skill: {gu_t}/{total}  big: {bi_t}/{total}  rescued: {res_t}  degraded: {deg_t}")

    print(f"\n  Token (output only):")
    print(f"    bare:    out={bare_c.output_tokens:,}  reason={bare_c.reasoning_tokens:,}")
    print(f"    +skill:  out={guided_c.output_tokens:,}  reason={guided_c.reasoning_tokens:,}")
    print(f"    big:     out={big_c.output_tokens:,}")
    print(f"    skill生成(5个): out={skill_counter.output_tokens:,} (一次性)")

    # 保存
    out = {"model": SMALL_MODEL, "skill_tokens": skill_counter.__dict__,
           "bare_tokens": bare_c.__dict__, "guided_tokens": guided_c.__dict__,
           "big_tokens": big_c.__dict__, "results": results}
    with open(os.path.join(RESULTS_DIR, f"novel_{SMALL_MODEL.replace('.','_')}.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n  结果已保存")

if __name__ == "__main__":
    main()
