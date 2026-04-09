"""
Quickstart: Generate a skill with a big model, use it with a small model.
"""

from brain_worker import AnthropicModel, ResponsesModel

BASE_URL = "http://127.0.0.1:18080"

big = AnthropicModel(base_url=BASE_URL, model="claude-opus-4.6")
small = ResponsesModel(base_url=BASE_URL, model="gpt-5-mini")

# Step 1: Big model writes a skill (one-time cost)
skill = big.call(
    "You are an expert. Write a concise, reusable problem-solving template.",
    "Write a dynamic programming solving skill in under 500 words. "
    "Include: 5-step method, 3 common patterns with state/transition templates.",
)
print(f"Skill generated ({len(skill)} chars)\n")

# Step 2: Small model uses the skill on multiple problems
problems = [
    "Write a Python function coin_change(coins, amount) -> int. Return min coins needed, -1 if impossible.",
    "Write a Python function longest_common_subsequence(text1, text2) -> int.",
    "Write a Python function min_distance(word1, word2) -> int for edit distance.",
]

for i, problem in enumerate(problems, 1):
    answer = small.call(skill, problem)
    print(f"--- Problem {i} ---")
    print(answer[:300])
    print()
